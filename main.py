"""AI Pipeline Factory — main orchestrator.

Reads dynamic configuration from a Google Sheets control panel,
ingests data from RSS feeds and Google Drive, processes content
through a 5-stage AI chain, logs results to a dashboard, and
dispatches digest notifications via Slack and Gmail.
"""

from datetime import datetime

from core.google_services import AutomationServices
from modules.ai_chain import SequentialAIChain
from modules.data_extract import DataExtractor
from modules.doc_generator import DocumentGenerator
from modules.notify import Notifier


def main() -> None:
    """Orchestrate the entire AI Content Factory pipeline.

    Workflow:
        1. Load dynamic configuration from the ``Control_Panel`` sheet.
        2. Initialise extractor, AI chain, document generator, and
           notifier.
        3. Fetch new RSS items and Drive transcripts (deduplicated).
        4. Process up to 10 items through the AI chain.
        5. Append results to the Master Google Doc.
        6. Log to all dashboard tabs (Raw_Ingest, AI_Audit_Log,
           Deliverables, Deduplication_Hashes).
        7. Send a consolidated digest via Slack and Gmail.
    """
    try:
        # --- 1. Base Configuration ---
        SHEET_ID = "YOUR_GOOGLE_SHEET_ID_HERE"

        print("Initialising services...")
        services = AutomationServices()

        # --- 2. Dynamic Configuration (Reading the Control Panel) ---
        print(
            "Fetching settings from Google Sheets Control Panel..."
        )
        master_sheet = services.gspread_client.open_by_key(SHEET_ID)
        config_tab = master_sheet.worksheet("Control_Panel")

        config_records = config_tab.get_all_records()
        config = {
            row["Setting_Name"]: row["Value"] for row in config_records
        }

        # Assign the dynamic variables
        RSS_URL = config.get("RSS_FEED_URL")
        TARGET_EMAIL = config.get("TARGET_EMAIL")
        SLACK_CHANNEL_ID = config.get("SLACK_CHANNEL_ID")
        MASTER_DOC_ID = config.get("MASTER_DOC_ID")
        TRANSCRIPT_FOLDER_ID = config.get("TRANSCRIPT_FOLDER_ID")

        # --- 3. Initialise Modules ---
        extractor = DataExtractor(services, SHEET_ID)
        ai_brain = SequentialAIChain()
        doc_gen = DocumentGenerator(services, MASTER_DOC_ID)
        notify = Notifier(services)

        raw_tab = master_sheet.worksheet("Raw_Ingest")
        audit_tab = master_sheet.worksheet("AI_Audit_Log")
        deliverables_tab = master_sheet.worksheet("Deliverables")
        dedup_tab = master_sheet.worksheet("Deduplication_Hashes")
        print("Services and Dynamic Config initialised.")

        # --- Execution Flow ---
        print(f"Fetching new items from RSS feed: {RSS_URL}")
        rss_items = extractor.fetch_new_rss_items(RSS_URL) or []

        print(
            "Fetching new transcripts from Google Drive..."
        )
        transcript_items = (
            extractor.fetch_drive_transcripts(TRANSCRIPT_FOLDER_ID)
            or []
        )

        # Combine both lists into one master queue
        new_items = transcript_items + rss_items

        if not new_items:
            print("No new items found. Pipeline execution complete.")
            return

        print(f"Found {len(new_items)} new items to process.")

        # TEST MODE — only process 10 items to preserve API quota
        test_items = new_items[:10]
        print(
            f"Test Mode Active: Only processing {len(test_items)} "
            "items to preserve API quota."
        )

        successfully_processed = []

        for item in test_items:
            print(
                f"--- Processing item: {item['title']} ---"
            )

            # 1. AI Processing
            print("Executing AI chain...")
            ai_results = ai_brain.execute_full_chain(item["summary"])
            final_text = ai_results.get("Stage 5: Final Polish", "")
            if not final_text:
                print(
                    f"Warning: AI chain did not produce final text "
                    f"for '{item['title']}'. Skipping."
                )
                continue
            print("AI processing complete.")

            # 2. Document Generation
            print("Updating Master Google Doc...")
            today_date = datetime.now().strftime("%Y-%m-%d")
            doc_url = doc_gen.append_to_master(
                item["title"], final_text, today_date
            )
            print(f"Document updated: {doc_url}")

            # 3. State Tracking & Dashboard Logging
            print("Logging data to CEO Dashboard tabs...")

            # Determine if this came from RSS or a Drive PDF
            source_type = (
                "Drive PDF/TXT"
                if "TRANSCRIPT:" in item["title"]
                else "RSS Feed"
            )

            # 1. Log to Raw Ingest (limit text to 2000 chars)
            raw_tab.append_row(
                [
                    today_date,
                    source_type,
                    item["title"],
                    item["summary"][:2000],
                    item["hash"],
                ]
            )

            # 2. Log to AI Audit Log
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

            # 3. Log to Deliverables
            deliverables_tab.append_row(
                [today_date, item["title"], doc_url]
            )

            # 4. Log to Deduplication
            dedup_tab.append_row([item["hash"]])

            print("Dashboard updated.")

            successfully_processed.append(item["title"])
            print(
                f"--- Finished processing: {item['title']} ---\n"
            )

        # --- 4. Final Digest Notification (Outside the loop) ---
        if successfully_processed:
            print("Sending final digest notifications...")
            bullet_list = "\n".join(
                [f"- {title}" for title in successfully_processed]
            )
            success_message = (
                f"Pipeline execution complete. Added to Master Doc:\n"
                f"{bullet_list}\n\n"
                f"Access the document here: "
                f"https://docs.google.com/document/d/"
                f"{MASTER_DOC_ID}/edit"
            )

            notify.send_slack_message(
                SLACK_CHANNEL_ID, success_message
            )
            notify.send_gmail_summary(
                TARGET_EMAIL,
                "AI Content Factory: Daily Digest",
                success_message,
            )
            print("Digest notifications sent.")

    except Exception as e:
        print(
            f"A catastrophic pipeline failure occurred: {e}"
        )


if __name__ == "__main__":
    main()