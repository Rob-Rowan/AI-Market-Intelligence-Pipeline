"""Data extraction and deduplication for RSS feeds and Google Drive."""

import hashlib
import io

import feedparser
import gspread
import PyPDF2
from googleapiclient.http import MediaIoBaseDownload

from core.google_services import AutomationServices


class DataExtractor:
    """Fetch new items from an RSS feed or Google Drive folder while
    avoiding duplicates via an MD5 hash memory layer stored in a Google
    Sheet.

    Attributes:
        services: An authenticated :class:`AutomationServices` instance.
        sheet: The ``Deduplication_Hashes`` worksheet from the
            configured Google Sheet.
    """

    def __init__(
        self, services: AutomationServices, sheet_id: str
    ) -> None:
        """Initialise the DataExtractor.

        Args:
            services: An authenticated :class:`AutomationServices`
                instance.
            sheet_id: The ID of the Google Sheet whose
                ``Deduplication_Hashes`` worksheet stores processed
                item hashes.
        """
        self.services = services
        self.sheet = (
            self.services.gspread_client.open_by_key(sheet_id)
            .worksheet("Deduplication_Hashes")
        )

    def _get_processed_hashes(self) -> set[str]:
        """Retrieve all MD5 hashes from Column A of the dedup sheet.

        Returns:
            A set of hash strings representing previously processed
            items. Returns an empty set on error.
        """
        try:
            hashes = self.sheet.col_values(1)[1:]  # skip header row
            return set(hashes)
        except gspread.exceptions.APIError as e:
            print(f"Error reading from Google Sheet: {e}")
            return set()

    def _generate_hash(self, url: str, title: str) -> str:
        """Generate an MD5 hash from a URL and title.

        Args:
            url: The URL of the item.
            title: The title of the item.

        Returns:
            The MD5 hex digest string.
        """
        combined = f"{url}{title}"
        return hashlib.md5(combined.encode("utf-8")).hexdigest()

    def fetch_new_rss_items(self, rss_url: str) -> list[dict]:
        """Fetch items from an RSS feed that have not been processed yet.

        Args:
            rss_url: The URL of the RSS feed to parse.

        Returns:
            A list of dictionaries, each with keys ``title``, ``link``,
            ``summary``, and ``hash``, representing new items not found
            in the deduplication sheet.
        """
        processed_hashes = self._get_processed_hashes()
        new_items: list[dict] = []

        try:
            feed = feedparser.parse(rss_url)
            if feed.bozo:
                raise feed.bozo_exception
        except Exception as e:
            print(f"Error parsing RSS feed at {rss_url}: {e}")
            return []

        for entry in feed.entries:
            item_hash = self._generate_hash(entry.link, entry.title)

            if item_hash not in processed_hashes:
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

    def fetch_drive_transcripts(self, folder_id: str) -> list[dict]:
        """Scan a Google Drive folder for new PDF / TXT files.

        Downloads each file, extracts its text content, and returns a
        list of items formatted identically to RSS entries for the
        downstream AI pipeline.

        Args:
            folder_id: The ID of the Google Drive folder to scan.

        Returns:
            A list of dictionaries, each with keys ``title``,
            ``link``, ``summary``, and ``hash``, representing new
            transcripts not yet processed.
        """
        print(
            f"Scanning Google Drive folder {folder_id} for transcripts..."
        )
        new_transcripts: list[dict] = []

        try:
            # Query Drive for PDFs and TXTs in the specified folder
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
            items = results.get("files", [])

            if not items:
                print("No transcripts found in folder.")
                return new_transcripts

            for item in items:
                file_id = item["id"]
                file_name = item["name"]
                mime_type = item["mimeType"]

                # Generate a unique hash for the file
                file_hash = self._generate_hash(file_name, file_id)

                # Check deduplication memory layer
                existing_hashes = self.sheet.col_values(1)
                if file_hash in existing_hashes:
                    print(f"Skipping duplicate transcript: {file_name}")
                    continue

                print(
                    f"Downloading and reading transcript: {file_name}"
                )

                # Download the file from Google Drive into memory
                request = self.services.drive_service.files().get_media(
                    fileId=file_id
                )
                file_stream = io.BytesIO()
                downloader = MediaIoBaseDownload(file_stream, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()

                file_stream.seek(0)
                extracted_text = ""

                # Parse the text based on file type
                if mime_type == "application/pdf":
                    pdf_reader = PyPDF2.PdfReader(file_stream)
                    for page in pdf_reader.pages:
                        extracted_text += page.extract_text() + "\n"
                elif mime_type == "text/plain":
                    extracted_text = (
                        file_stream.read().decode("utf-8")
                    )

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

        except Exception as e:
            print(f"Error fetching transcripts from Drive: {e}")
            return []