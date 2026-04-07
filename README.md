# QAC Automation

An AI-powered quality assurance tool for Studies Weekly editorial teams. The workflow automatically scrapes the Studies Weekly Online portal, analyzes uploaded PDFs, and writes QA findings directly into a QAC Google Sheet.

---

## How It Works

1. The QA reviewer opens the app in their browser
2. They paste their QAC Google Sheet URL, upload any available PDFs (SE, TE, Printables, Walkthrough Slides), and optionally add notes for the AI
3. They click **Start Quality Assurance**
4. The app scrapes the online portal, extracts content from the PDFs, and runs a full continuity and QA analysis via Claude AI
5. All findings are written directly into the QAC spreadsheet
6. The reviewer can click **Analyze Again** to run an additional pass — any new issues are added in blue

---

## Architecture

```
Browser (HTML frontend)
        |
        | HTTP
        v
Flask API  ─────────────────────────────────────────────────────┐
(app.py on EC2)                                                  │
        |                                                        │
        ├── Playwright (Chromium) → Studies Weekly Online portal │
        ├── Claude AI (Anthropic API) → continuity analysis      │
        ├── pypdf → PDF extraction                               │
        └── gspread → Google Sheets read/write                   │
                                                                 │
        └─────────────────────────────────────────────────────── ┘
```

The HTML frontend is served separately (locally during development, via SBP in production) and communicates with the Flask API over HTTP.

---

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| API / Backend | Flask |
| AI Model | Claude (Anthropic API) — Opus 4.6 for analysis, Sonnet 4.6 for mapping |
| Browser Automation | Playwright (Chromium, headless) |
| Google Sheets | gspread + Google Service Account |
| PDF Parsing | pypdf |
| Frontend | HTML / Vanilla JS |

---

## Project Structure

```
app.py                  # Flask API — entry point
static/
  index.html            # HTML/JS frontend
src/
  workflow.py           # Orchestrates the full pipeline
  portal.py             # Playwright scraping (SWO login, navigation, SV + TR)
  continuity.py         # AI continuity and QA analysis
  qa_engine.py          # Maps AI findings to sheet rows
  sheets.py             # Google Sheets read/write
  pdf_extractor.py      # PDF extraction via Claude
  logger.py             # Queue-based logger for live status
  utils.py              # Shared utilities
docs/
  workflow/             # Detailed workflow specs and reference docs
credentials/            # Service account JSON (gitignored)
logs/
  runs/                 # One folder per run, timestamped
.env                    # Environment variables (gitignored)
requirements.txt
```

---

## Credentials Required

All secrets are stored in `.env` and `credentials/` — never hardcoded.

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `SW_PORTAL_USERNAME` | Studies Weekly Online login |
| `SW_PORTAL_PASSWORD` | Studies Weekly Online password |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Path to Google service account JSON |

The Google service account must be granted **editor access** to any QAC Google Sheet before running.
Service account email: `qac-automation@tonal-history-489219-j7.iam.gserviceaccount.com`

---

## Setup & Deployment

### EC2 Server (one-time)

```bash
# Install system dependencies
sudo apt update && sudo apt install -y python3.11 python3.11-pip git

# Clone the repo
git clone https://github.com/COMPANY_ORG/qac-automation.git /home/ubuntu/qac
cd /home/ubuntu/qac

# Install Python dependencies
python3.11 -m pip install -r requirements.txt

# Install Playwright browser
python3.11 -m playwright install chromium
python3.11 -m playwright install-deps chromium

# Add .env and credentials/service_account.json to the server
```

### Run the Flask API

```bash
python3.11 app.py
# Runs on port 5000
```

For production, run as a systemd service so it starts on boot and restarts on crash.

### Deploy Updates

Push to `main` on GitHub — the EC2 server pulls and restarts automatically via GitHub Actions.

---

## Running Locally (Development)

```bash
# Install dependencies
python3.11 -m pip install -r requirements.txt
python3.11 -m playwright install chromium

# Start the Flask server
python3.11 app.py

# Open in browser
open http://localhost:5000
```

---

## Flask API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the HTML frontend |
| `POST` | `/start` | Starts a new QA workflow job. Returns `job_id` |
| `GET` | `/status/<job_id>` | Returns live log messages and job status |
| `POST` | `/analyze-again` | Runs an additional analysis pass on a completed job |

### POST /start — form fields

| Field | Type | Required |
|---|---|---|
| `sheet_url` | string | Yes |
| `classroom_override` | string | No |
| `reviewer_notes` | string | No |
| `SE` | file (.pdf) | No |
| `TE` | file (.pdf) | No |
| `Printables` | file (.pdf) | No |
| `Walkthrough` | file (.pdf) | No |

---

## Pointing the Frontend at EC2

In `static/index.html`, update the API constant at the top of the `<script>` block:

```js
const API = 'http://your-ec2-ip:5000';
```

For local development this should be an empty string (`''`) so requests go to the same machine.
