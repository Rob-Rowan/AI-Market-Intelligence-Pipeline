"""Google Docs API integration for prepending briefs to a master document."""

from __future__ import annotations

import logging
import socket

from googleapiclient.errors import HttpError

from core.google_services import AutomationServices

logger = logging.getLogger(__name__)


class DocumentGenerator:
    """Prepend formatted briefs to the top of a Master Google Doc.

    Attributes:
        services: An authenticated :class:`AutomationServices` instance.
        master_doc_id: The Google Docs ID of the master document.
    """

    def __init__(
        self, services: AutomationServices, master_doc_id: str
    ) -> None:
        """Initialise the document generator.

        Args:
            services: An authenticated :class:`AutomationServices`
                instance.
            master_doc_id: The Google Docs document ID to update.
        """
        self.services = services
        self.master_doc_id = master_doc_id

    def append_to_master(
        self, title: str, content: str, date_str: str
    ) -> str:
        """Inject a formatted brief at the top of the master document.

        Args:
            title: The headline for the brief.
            content: The body text to insert (e.g. the final polished
                output from the AI chain).
            date_str: A date string (e.g. ``"2025-01-15"``) recording
                when the brief was processed.

        Returns:
            The full edit URL of the master document.

        Raises:
            Exception: Propagates any Google Docs API failure so the
                orchestrator can handle it.
        """
        text_to_insert = (
            f"\n{'=' * 50}\n"
            f"MARKET BRIEF: {title}\n"
            f"PROCESSED DATE: {date_str}\n"
            f"{'=' * 50}\n\n"
            f"{content}\n\n"
        )
        request = {
            "insertText": {
                "location": {"index": 1},
                "text": text_to_insert,
            }
        }
        try:
            self.services.docs_service.documents().batchUpdate(
                documentId=self.master_doc_id,
                body={"requests": [request]},
            ).execute()
        except (socket.timeout, HttpError):
            logger.exception(
                "Transient network failure while updating master "
                "document %s.",
                self.master_doc_id,
            )
            raise
        except Exception:
            logger.exception(
                "Google Docs API rejected update for master document %s.",
                self.master_doc_id,
            )
            raise

        logger.info("Prepended brief '%s' to master document.", title)
        return (
            "https://docs.google.com/document/d/"
            f"{self.master_doc_id}/edit"
        )