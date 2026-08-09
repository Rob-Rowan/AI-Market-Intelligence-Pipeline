"""AI pipeline orchestrator.

Reads dynamic configuration from a Google Sheets control panel, ingests
data from RSS feeds and Google Drive, processes content through a
5-stage AI chain, logs results to a dashboard, and dispatches digest
notifications via Slack and Gmail.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from core.google_services import AutomationServices
from modules.ai_chain import SequentialAIChain
from modules.data_extract import DataExtractor
from modules.doc_generator import DocumentGenerator
from modules.notify import Notifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

MAX_ITEMS_PER_RUN = 10
DEFAULT_SHEET_ID = "YOUR_GOOGLE_SHEET_ID_HERE"


def main() -> None:
    """Orchestrate the full AI market intelligence pipeline.

    Workflow:
        1. Load dynamic configuration from the ``Control_Panel`` sheet.
        2. Initialise the extractor, AI chain, document generator, and
           notifier.
        3. Fetch new RSS items and Drive transcripts (deduplicated).
        4. Process up to ``MAX_ITEMS_PER_RUN`` items through the AI
           chain.
        5. Prepend each brief to the Master Google Doc.
        6. Log to all dashboard tabs (Raw_Ingest, AI_Audit_Log,
           Deliverables, Deduplication_Hashes).
        7. Dispatch a consolidated digest via Slack and Gmail.
    """
    sheet_id = os.getenv("GOOGLE_SHEET_ID", DEFAULT_SHEET_ID)
    if sheet_id == DEFAULT_SHEET_ID:
        logger.error(
            "No Google Sheet configured. Set the GOOGLE_SHEET_ID "
            "environment variable (or edit DEFAULT_SHEET_ID in main.py) "
            "before running the pipeline."
        )
        return

    try:
        services = AutomationServices()

        master_sheet = services.gspread_client.open_by_key(sheet_id)
        config_tab = master_sheet.worksheet("Control_Panel")
        config: dict[str, str] = {
            row["Setting_Name"]: row["Value"]
            for row in config_tab.get_all_records()
        }

        rss_url = config.get("RSS_FEED_URL")
        target_email = config.get("TARGET_EMAIL")
        slack_channel_id = config.get("SLACK_CHANNEL_ID")
        master_doc_id = config.get("MASTER_DOC_ID")
        transcript_folder_id = config.get("TRANSCRIPT_FOLDER_ID")

        extractor = DataExtractor(services, sheet_id)
        ai_brain = SequentialAIChain()
        doc_gen = DocumentGenerator(services, master_doc_id)
        notify = Notifier(services)

        raw_tab = master_sheet.worksheet("Raw_Ingest")
        audit_tab = master_sheet.worksheet("AI_Audit_Log")
        deliverables_tab = master_sheet.worksheet("Deliverables")
        dedup_tab = master_sheet.worksheet("Deduplication_Hashes")

        rss_items = extractor.fetch_new_rss_items(rss_url) or []
        transcript_items = (
            extractor.fetch_drive_transcripts(transcript_folder_id) or []
        )
        new_items = transcript_items + rss_items

        if not new_items:
            logger.info("No new items found. Pipeline execution complete.")
            return

        batch = new_items[:MAX_ITEMS_PER_RUN]
        logger.info(
            "Found %d new item(s); processing up to %d each run.",
            len(new_items),
            MAX_ITEMS_PER_RUN,
        )

        successfully_processed: list[str] = []

        for item in batch:
            logger.info("--- Processing item: %s ---", item["title"])

            ai_results = ai_brain.execute_full_chain(item["summary"])
            final_text = ai_results.get("Stage 5: Final Polish", "")
            if not final_text:
                logger.warning(
                    "AI chain produced no final text for '%s'; skipping.",
                    item["title"],
                )
                continue

            today_date = datetime.now().strftime("%Y-%m-%d")
            doc_url = doc_gen.append_to_master(
                item["title"], final_text, today_date
            )

            source_type = (
                "Drive PDF/TXT"
                if "TRANSCRIPT:" in item["title"]
                else "RSS Feed"
            )
            raw_tab.append_row(
                [
                    today_date,
                    source_type,
                    item["title"],
                    item["summary"][:2000],
                    item["hash"],
                ]
            )
            audit_tab.append_row(
                [
                    today_date,
                    item["title"],
                    ai_results.get("summary", ""),
                    ai_results.get("action_items", ""),
                    ai_results.get("outline", ""),
                    ai_results.get("draft", ""),
                ]
            )
            deliverables_tab.append_row(
                [today_date, item["title"], doc_url]
            )
            dedup_tab.append_row([item["hash"]])

            successfully_processed.append(item["title"])
            logger.info("--- Finished processing: %s ---", item["title"])

        if successfully_processed:
            bullet_list = "\n".join(
                f"- {title}" for title in successfully_processed
            )
            success_message = (
                "Pipeline execution complete. Added to Master Doc:\n"
                f"{bullet_list}\n\n"
                "Access the document here: "
                f"https://docs.google.com/document/d/{master_doc_id}/edit"
            )
            notify.send_slack_message(slack_channel_id, success_message)
            notify.send_gmail_summary(
                target_email,
                "AI Content Factory: Daily Digest",
                success_message,
            )

        logger.info(
            "Pipeline complete. Processed %d item(s).",
            len(successfully_processed),
        )
    except Exception:
        logger.exception("Catastrophic pipeline failure; aborting run.")


if __name__ == "__main__":
    main()