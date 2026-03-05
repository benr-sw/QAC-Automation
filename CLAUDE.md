# QAC Automation (Quality Assurance Check Automation)

This is an app and agentic workflow that will aid our company, Studies Weekly, quality assurance team in reviewing our elementary school publications and making sure they are up to standards. The workflow uses AI to analyze several documents, agentically navigates pages in our online portal, and then makes QA suggestions/comments in our QA spreadsheets

---

## App User Experience
What the app experience should be for the end user:
1. The app opens up on a web browser
2. The user sees 3 columns
    a. in column 1 (left), 5 inputs and 1 button are available for the user: 
        i. QAC Checklist (this is where the user connects the unique google sheet they're using for their quality assurance checklist)
        ii. Student Edition PDF (the user has the option to upload the student workbook)
        iii. Teacher Edition PDF (the user has the option to upload the teacher version)
        iv. Printables PDF (the user has the option to upload the printables document)
        v. Walkthrough Slides PDF (the user has the option to upload a walkthrough slide deck)
        vi. At the bottom of the column is a button that says "Start Quality Assurance", that when clicked will initiate the workflow
    b. in column 2, the current stage of the workflow is displayed to the user. It should tell the user what is currently being worked on and dynamically update as it moves through the different steps of the workflow
    c. in column 3, when the workflow is finished, an "All done!" alert appears, and underneath it, a link to the finished quality assurance checklist (Google Sheet)

---

## Workflow steps
These docs contain the steps and instructions for the workflow:

See detailed specs in `docs/workflow/`:

**Reference docs:**
- `portal_reference.md` — SWO login, navigation, common selectors, quirks
- `google_sheet_schema.md` — what is read from and written to the sheet
- `ai_rules.md` — skip list and check behavior rules

**Phase 1 — first TOC check**
- `phase1_week_toc_check.md` — the first checks made in the workflow for the table of contents page

**Phase 2 — data gathering**
- `phase2_student_view_scraping.md` — the AI scrapes information from the student view articles
- `phase2_teacher_resources_scraping.md` — the AI scrapes information from the teacher resources articles

**Phase 3 — QA Check Loops:**
- `phase3_sv_online_check.md` — student view online checks (orange)
- `phase3_tr_online_check.md` — teacher resources online checks (yellow)
- `phase3_se_pdf_check.md` — student edition PDF checks (green)
- `phase3_te_pdf_check.md` — teacher edition PDF checks (blue)
- `phase3_other_misc_check.md` — other/misc checks (purple)


---

## Stack
- Language: Python 3.11
- Claude API model: claude-sonnet-4-6
- Google Sheets: gspread
- Web navigation: Playwright / requests+BeautifulSoup
- Document parsing: pypdf

---

## Project Structure
- `src/` — main workflow source code
- `docs/` — input documents to be analyzed
- `credentials/` — service account and API keys (gitignored)
- `.env` — environment variables (gitignored)
- `requirements.txt` — Python dependencies

---

## Inputs
- **Documents:** PDFs uploaded as inputs from user at start of workflow
- **Website:** details found in `docs/workflow/portal_reference.md`
- **Google Sheet:** details found in `docs/workflow/google_sheet_schema.md`

---

## Outputs
- **Google Sheet:** Update google sheet throughout workflow process
- **Logs:** `logs/` folder, one file per run named by timestamp (e.g. `qac_2026-03-04_14-32-01.log`), verbose during development

---

## Credentials & Environment Variables
All secrets are stored in `.env` (never hardcoded). 

---

## Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Run full workflow
python main.py

---