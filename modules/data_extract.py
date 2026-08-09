"""RSS and Google Drive ingestion with in-memory MD5 deduplication."""

from __future__ import annotations

import hashlib
import io
import logging
import socket

import feedparser
import gspread
import PyPDF2
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from core.google_services import AutomationServices

logger = logging.getLogger(__name__)

_TRANSIENT_API_ERRORS = (
    socket.timeout,
    HttpError,
    gspread.exceptions.APIError,
)

_EXTRACTION_ERRORS = _TRANSIENT_API_ERRORS + (
    PyPDF2.errors.PyPdfError,
    UnicodeDecodeError,
)


class DataExtractor:
    """Fetch new items from an RSS feed or a Google Drive folder.

    Deduplication runs entirely in memory: the set of previously
    processed MD5 hashes is loaded from the ``Deduplication_Hashes``
    worksheet once per run, then checked with O(1) set lookups so the
    Google Sheets API is never queried inside the file loop.

    Attributes:
        services: An authenticated :class:`AutomationServices` instance.
        sheet: The ``Deduplication_Hashes`` worksheet.
    """

    def __init__(self, services: AutomationServices, sheet_id: str) -> None:
        """Initialise the extractor and resolve the dedup worksheet.

        Args:
            services: An authenticated :class:`AutomationServices`
                instance.
            sheet_id: ID of the Google Sheet that owns the
                ``Deduplication_Hashes`` worksheet.
        """
        self.services = services
        self.sheet = (
            self.services.gspread_client.open_by_key(sheet_id)
            .worksheet("Deduplication_Hashes")
        )

    def _get_processed_hashes(self) -> set[str] | None:
        """Load every processed MD5 hash into an in-memory set.

        Returns:
            The set of previously processed item hashes, or ``None`` if
            the worksheet cannot be read. ``None`` lets callers abort a
            run instead of reprocessing already-processed items, which
            protects API quota during a Sheets outage.
        """
        try:
            hashes = self.sheet.col_values(1)[1:]  # skip header row
            return set(hashes)
        except Exception:
            logger.exception(
                "Failed to read deduplication hashes from Google Sheets."
            )
            return None

    def _generate_hash(self, url: str, title: str) -> str:
        """Generate a deterministic MD5 hash for an item.

        Args:
            url: The item URL (or Google Drive file ID).
            title: The item title.

        Returns:
            The MD5 hex digest used for deduplication.
        """
        return hashlib.md5(f"{url}{title}".encode("utf-8")).hexdigest()

    def fetch_new_rss_items(self, rss_url: str) -> list[dict[str, str]]:
        """Return feed entries that have not been processed yet.

        Args:
            rss_url: The URL of the RSS feed to parse.

        Returns:
            A list of new items with keys ``title``, ``link``,
            ``summary``, and ``hash``.
        """
        processed_hashes = self._get_processed_hashes()
        if processed_hashes is None:
            logger.error(
                "Deduplication state unavailable; aborting RSS fetch."
            )
            return []

        try:
            feed = feedparser.parse(rss_url)
        except Exception:
            logger.exception("Failed to parse RSS feed at %s.", rss_url)
            return []
        if feed.bozo:
            logger.warning(
                "RSS feed at %s reported a parser issue: %s",
                rss_url,
                feed.bozo_exception,
            )
            return []

        new_items: list[dict[str, str]] = []
        for entry in feed.entries:
            item_hash = self._generate_hash(entry.link, entry.title)
            if item_hash in processed_hashes:
                continue
            summary = entry.get(
                "summary",
                entry.get("content", [{}])[0].get("value", ""),
            )
            new_items.append(
                {
                    "title": entry.title,
                    "link": entry.link,
                    "summary": summary,
                    "hash": item_hash,
                }
            )
        return new_items

    def fetch_drive_transcripts(
        self, folder_id: str
    ) -> list[dict[str, str]]:
        """Scan a Google Drive folder for new PDF/TXT transcripts.

        The deduplication set is loaded once before the file loop so
        per-file lookups never hit the Google Sheets API.

        Args:
            folder_id: The ID of the Google Drive folder to scan.

        Returns:
            A list of new transcripts with keys ``title``, ``link``,
            ``summary``, and ``hash``.
        """
        logger.info(
            "Scanning Drive folder %s for PDF/TXT transcripts.", folder_id
        )
        processed_hashes = self._get_processed_hashes()
        if processed_hashes is None:
            logger.error(
                "Deduplication state unavailable; aborting Drive scan."
            )
            return []

        try:
            query = (
                f"'{folder_id}' in parents "
                "and (mimeType='application/pdf' "
                "or mimeType='text/plain') "
                "and trashed=false"
            )
            results = (
                self.services.drive_service.files()
                .list(q=query, fields="files(id, name, mimeType)")
                .execute()
            )
        except _TRANSIENT_API_ERRORS:
            logger.exception(
                "Failed to list files in Drive folder %s.", folder_id
            )
            return []

        new_transcripts: list[dict[str, str]] = []
        for item in results.get("files", []):
            file_id = item["id"]
            file_name = item["name"]
            mime_type = item["mimeType"]
            file_hash = self._generate_hash(file_name, file_id)

            if file_hash in processed_hashes:
                logger.debug("Skipping duplicate transcript: %s", file_name)
                continue

            try:
                extracted_text = self._extract_file_text(
                    file_id, mime_type
                )
            except _EXTRACTION_ERRORS:
                logger.exception(
                    "Failed to download or parse transcript %s.",
                    file_name,
                )
                continue

            new_transcripts.append(
                {
                    "title": f"TRANSCRIPT: {file_name}",
                    "link": (
                        "https://drive.google.com/file/d/"
                        f"{file_id}/view"
                    ),
                    "summary": extracted_text[:15000],
                    "hash": file_hash,
                }
            )
        return new_transcripts

    def _extract_file_text(self, file_id: str, mime_type: str) -> str:
        """Download a Drive file into memory and extract its text.

        Args:
            file_id: The Google Drive file ID.
            mime_type: The file MIME type (``application/pdf`` or
                ``text/plain``).

        Returns:
            The extracted text content.
        """
        request = self.services.drive_service.files().get_media(
            fileId=file_id
        )
        file_stream = io.BytesIO()
        downloader = MediaIoBaseDownload(file_stream, request)
        while True:
            _, done = downloader.next_chunk()
            if done:
                break

        file_stream.seek(0)
        if mime_type == "application/pdf":
            reader = PyPDF2.PdfReader(file_stream)
            return "".join(
                f"{page.extract_text() or ''}\n"
                for page in reader.pages
            )
        return file_stream.read().decode("utf-8")