# AI Market Intelligence Pipeline

An automated, multi-source data ingestion and AI summarisation engine that produces scannable executive market briefs.

The pipeline acts as an autonomous financial analyst: it ingests live market news and raw PDF/TXT transcripts, processes them through a strict 5-stage AI reasoning chain, logs an audit trail to a Google Sheets dashboard, **prepends** formatted briefs to a rolling Master Google Doc, and dispatches a consolidated digest via Slack and Gmail.

---

## Architecture Overview

```
┌─────────────────────┐     ┌─────────────────────┐
│    RSS Feeds        │     │   Google Drive      │
│  (WSJ, CNBC, ...)   │     │  (PDF / TXT files)  │
└────────┬────────────┘     └────────┬────────────┘
         │                          │
         ▼                          ▼
┌──────────────────────────────────────────────┐
│         data_extract.py (DataExtractor)       │
│  • feedparser RSS parsing                     │
│  • PyPDF2 PDF text extraction                 │
│  • In-memory MD5 deduplication set            │
│    (one Sheets read per run, zero per-file    │
│    API round trips)                           │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│         ai_chain.py (SequentialAIChain)       │
│  Stage 1: Fact Extraction                     │
│  Stage 2: Sentiment Analysis                  │
│  Stage 3: TL;DR (≤15 words)                   │
│  Stage 4: Impact Bullets (×3, ≤10 words ea.)  │
│  Stage 5: Final Polish (Markdown template)    │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│       doc_generator.py (DocumentGenerator)    │
│  Prepends formatted briefs to Master Google   │
│  Doc via the Google Docs API.                 │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│            notify.py (Notifier)               │
│  • Slack message via slack_sdk                │
│  • Gmail summary via SMTP_SSL                 │
└──────────────────────────────────────────────┘
```

### Package Structure

| Path | Responsibility |
|---|---|
| `main.py` | Orchestrator: root logging config, reads config, runs the pipeline, handles errors |
| `core/google_services.py` | OAuth & client initialisation (Google APIs + Slack SDK) |
| `modules/data_extract.py` | RSS parsing, Drive scanning, in-memory MD5 deduplication |
| `modules/ai_chain.py` | 5-stage Gemini prompt chain |
| `modules/doc_generator.py` | Google Docs API — prepend to master document |
| `modules/notify.py` | Slack & Gmail notification dispatch |

---

## Key Features

- **Multi-Source Ingestion** — Reads live RSS feeds and scans a Google Drive folder for new Earnings Call PDFs and raw text files in the same run.
- **In-Memory MD5 Deduplication** — Processed hashes are loaded from the `Deduplication_Hashes` sheet exactly once per run; every item is then checked with O(1) `set` lookups. This removes per-file Sheets API round trips (N+1 eliminated) and prevents duplicate LLM calls.
- **Structured Logging** — The entire execution path uses the Python stdlib `logging` module (`logger.info/error/debug`) with a consistent `timestamp [LEVEL] logger: message` format. No `print()` statements; failures are logged with `exc_info=True` instead of stringified exceptions.
- **Scale-Safe Google API Quota Management** — Capped batches (`MAX_ITEMS_PER_RUN`), graceful `socket.timeout` / `HttpError` handling, per-file failure isolation, and a fail-safe abort when the dedup store is unreachable — a transient Sheets outage never triggers a mass reprocess.
- **"CEO Dashboard" (No-Code Config)** — RSS feeds, target emails, and Drive folders are controlled from a Google Sheet, not Python code.
- **Constrained AI Reasoning** — The 5-stage chain enforces strict formatting (≤15-word TL;DR, 3 impact bullets) to keep briefs scannable and honest.
- **Transparent Audit Logging** — Every AI stage is recorded to a structured Google Sheet for quality control.
- **Consolidated Notifications** — A single daily digest dispatched via Slack and Gmail.

---

## Google Sheets Control Panel

The system requires a 5-tab Google Sheet:

| Tab | Purpose |
|---|---|
| `Control_Panel` | Dynamic variables (`RSS_FEED_URL`, `TARGET_EMAIL`, `SLACK_CHANNEL_ID`, `MASTER_DOC_ID`, `TRANSCRIPT_FOLDER_ID`) |
| `Raw_Ingest` | Raw text extracted from RSS / Drive sources |
| `AI_Audit_Log` | Intermediate outputs of each AI stage |
| `Deliverables` | URLs of finalised Google Doc updates |
| `Deduplication_Hashes` | Memory bank of MD5 hashes for processed items |

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | **Python 3.10+** |
| AI Model | **Google Gemini 2.5 Flash** (`google-genai`) |
| Google APIs | Sheets, Drive, Docs, Gmail (`google-api-python-client`, `gspread`) |
| RSS Parsing | `feedparser` |
| PDF Parsing | `PyPDF2` |
| Notifications | `slack_sdk` (Slack), `smtplib` (Gmail) |
| Auth | `google-auth` (service account), `python-dotenv` |
| Logging | Python stdlib `logging` (single root config in `main.py`) |

---

## Setup & Execution

### 1. Prerequisites

- Python 3.10+
- A Google Cloud project with **Sheets, Drive, Docs, and Gmail APIs** enabled
- A **service account** JSON key file saved as `credentials.json`
- A Google Sheet with the 5 tabs listed above (shared with the service account email)
- A Slack Bot Token (`SLACK_BOT_TOKEN`) with `chat:write` scope
- A Gmail App Password for the sender account

### 2. Clone & Environment

```bash
git clone https://github.com/yourusername/ai-intelligence-pipeline.git
cd ai-intelligence-pipeline
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configuration

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
SLACK_BOT_TOKEN=your_slack_bot_token_here
GMAIL_SENDER=your_email@email.com
GMAIL_APP_PASSWORD=your_16_digit_app_password
GOOGLE_SHEET_ID=your_google_sheet_id_here
```

Place your Google service account key as `credentials.json` in the project root.

`GOOGLE_SHEET_ID` points to the 5-tab control-panel sheet. Alternatively, set `DEFAULT_SHEET_ID` at the top of `main.py`.

### 4. Run

```bash
python main.py
```

The pipeline will:
1. Read the `Control_Panel` sheet for dynamic configuration.
2. Fetch new RSS items and Drive transcripts (deduplicated in memory).
3. Process up to **10 items** per run (quota-protection cap).
4. Prepend each brief to the Master Google Doc.
5. Log everything to the dashboard tabs.
6. Send a Slack message and Gmail digest summarising processed items.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_SHEET_ID` | Yes* | ID of the 5-tab control-panel Google Sheet (*or set `DEFAULT_SHEET_ID` in `main.py`) |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `SLACK_BOT_TOKEN` | Yes | Slack bot OAuth token (`xoxb-...`) |
| `GMAIL_SENDER` | Yes | Gmail address used as SMTP sender |
| `GMAIL_APP_PASSWORD` | Yes | 16-digit Gmail app password |

---

## Quality & Linting

The codebase follows **PEP 8** conventions with **Google-style** docstrings, `from __future__ import annotations`, and no `print()` statements on the execution path. Run the linter locally:

```bash
pip install flake8
flake8 . --max-line-length=79
```