# 📈 AI Market Intelligence Pipeline

An automated, multi-source data ingestion and AI summarization engine that produces highly scannable executive market briefs.

The pipeline acts as an autonomous financial analyst: it ingests live market news and raw PDF/TXT transcripts, processes the text through a strict 5-stage AI reasoning chain, logs a transparent audit trail to a Google Sheets dashboard, appends formatted briefs to a rolling Master Google Doc, and dispatches a consolidated digest via Slack and Gmail.

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
│  • MD5 hashing for deduplication              │
│  • feedparser for RSS parsing                 │
│  • PyPDF2 for PDF text extraction             │
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
| `main.py` | Orchestrator: reads config, runs pipeline, handles errors |
| `core/google_services.py` | OAuth & client initialisation (Google APIs + Slack SDK) |
| `modules/data_extract.py` | RSS parsing, Drive scanning, MD5 deduplication |
| `modules/ai_chain.py` | 5-stage Gemini prompt chain |
| `modules/doc_generator.py` | Google Docs API — append to master document |
| `modules/notify.py` | Slack & Gmail notification dispatch |

---

## 🔑 Key Features

- **Multi-Source Ingestion** — Simultaneously reads live RSS feeds and scans a Google Drive folder for newly uploaded Earnings Call PDFs and raw text files.
- **Intelligent Deduplication** — MD5 hashing memorises previously processed items, preventing duplicate LLM calls and protecting API quotas.
- **"CEO Dashboard" (No-Code Config)** — Fully controlled via a Google Sheet. Change RSS feeds, target emails, or folders without touching Python code.
- **Constrained AI Reasoning** — Forces the LLM to adhere to strict formatting rules (≤15 word TL;DR, 3 bullet points max) to prevent hallucinated fluff.
- **Transparent Audit Logging** — Every stage of the AI's "thought process" is logged to a structured Google Sheet for quality control.
- **Consolidated Notifications** — A single daily digest delivered via Slack and Gmail.

---

## 📊 Google Sheets Control Panel

The system requires a 5-tab Google Sheet:

| Tab | Purpose |
|---|---|
| `Control_Panel` | Stores dynamic variables (`RSS_FEED_URL`, `TARGET_EMAIL`, `SLACK_CHANNEL_ID`, `MASTER_DOC_ID`, `TRANSCRIPT_FOLDER_ID`) |
| `Raw_Ingest` | Logs raw text extracted from RSS / Drive sources |
| `AI_Audit_Log` | Logs intermediate outputs of each AI stage |
| `Deliverables` | Logs URLs of finalised Google Doc updates |
| `Deduplication_Hashes` | Memory bank of MD5 hashes for processed items |

---

## 🛠 Tech Stack

| Component | Technology |
|---|---|
| Language | **Python 3.10+** |
| AI Model | **Google Gemini 2.5 Flash** (`google-genai`) |
| Google APIs | Sheets, Drive, Docs, Gmail (`google-api-python-client`, `gspread`) |
| RSS Parsing | `feedparser` |
| PDF Parsing | `PyPDF2` |
| Notifications | `slack_sdk` (Slack), `smtplib` (Gmail) |
| Auth | `google-auth` (service account), `python-dotenv` |

---

## 💻 Setup & Execution

### 1. Prerequisites

- Python 3.10+
- A Google Cloud project with **Sheets, Drive, Docs, and Gmail APIs** enabled
- A **service account** JSON key file downloaded to `credentials.json`
- A Google Sheet with the 5 tabs listed above (share it with the service account email)
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
```

Place your Google service account key as `credentials.json` in the project root.

Update the `SHEET_ID` variable in `main.py` to point to your Google Sheet.

### 4. Run

```bash
python main.py
```

The pipeline will:
1. Read the Control_Panel sheet for dynamic configuration.
2. Fetch new RSS items and Drive transcripts (deduplicated).
3. Process up to **10 items** per run (test mode).
4. Append each brief to the Master Google Doc.
5. Log everything to the dashboard tabs.
6. Send a Slack message and Gmail digest with a summary of processed items.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `SLACK_BOT_TOKEN` | Yes | Slack bot OAuth token (`xoxb-...`) |
| `GMAIL_SENDER` | Yes | Gmail address used as SMTP sender |
| `GMAIL_APP_PASSWORD` | Yes | 16-digit Gmail app password |

---

## Quality & Linting

The codebase follows **PEP 8** conventions and includes detailed **Google-style** docstrings for every function and class. Run the linter locally:

```bash
pip install flake8
flake8 . --max-line-length=79