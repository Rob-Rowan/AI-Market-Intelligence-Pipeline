"""Google Docs integration for appending AI-generated content to a master document."""

from core.google_services import AutomationServices


class DocumentGenerator:
    """Append formatted AI content to the top of a Master Google Doc.

    Attributes:
        services: An authenticated :class:`AutomationServices` instance.
        master_doc_id: The ID of the target Google Document.
    """

    def __init__(
        self, services: AutomationServices, master_doc_id: str
    ) -> None:
        """Initialise the DocumentGenerator.

        Args:
            services: An authenticated :class:`AutomationServices`
                instance.
            master_doc_id: The Google Docs document ID of the master
                document to update.
        """
        self.services = services
        self.master_doc_id = master_doc_id

    def append_to_master(
        self, title: str, content: str, date_str: str
    ) -> str:
        """Inject formatted text at the very top of the master document.

        Prepends a market brief header followed by the AI-generated
        content to position 1 (the beginning) of the document.

        Args:
            title: The headline for the brief.
            content: The body text to insert (e.g. the final polished
                output from the AI chain).
            date_str: A date string (e.g. ``"2025-01-15"``) to record
                when the brief was processed.

        Returns:
            The full edit URL of the master document.

        Raises:
            Exception: Propagates any Google Docs API error.
        """
        # Format the block of text to be injected
        text_to_insert = (
            f"\n{'=' * 50}\n"
            f"MARKET BRIEF: {title}\n"
            f"PROCESSED DATE: {date_str}\n"
            f"{'=' * 50}\n\n"
            f"{content}\n\n"
        )

        requests = [
            {
                "insertText": {
                    "location": {"index": 1},
                    "text": text_to_insert,
                }
            }
        ]

        try:
            self.services.docs_service.documents().batchUpdate(
                documentId=self.master_doc_id,
                body={"requests": requests},
            ).execute()

            return (
                f"https://docs.google.com/document/d/"
                f"{self.master_doc_id}/edit"
            )
        except Exception as e:
            print(f"Error updating Master Doc: {e}")
            raise