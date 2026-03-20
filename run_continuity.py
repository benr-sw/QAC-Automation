"""
Standalone script to re-run the continuity analysis and/or sheet mapping
against an existing run folder. Skips scraping and PDF extraction.

Usage:
    # Re-run continuity analysis only
    /opt/homebrew/bin/python3.11 run_continuity.py logs/runs/run_20260319_145219

    # Re-run continuity analysis AND write issues to the sheet
    /opt/homebrew/bin/python3.11 run_continuity.py logs/runs/run_20260319_145219 --sheet <sheet_url>

    # Skip re-running analysis, just re-map existing continuity_analysis.md to the sheet
    /opt/homebrew/bin/python3.11 run_continuity.py logs/runs/run_20260319_145219 --sheet <sheet_url> --map-only
"""

import sys
import os
import logging
from anthropic import Anthropic
from dotenv import load_dotenv
from src.continuity import run_continuity_analysis
from src import sheets, qa_engine

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    run_folder = sys.argv[1]
    args = sys.argv[2:]
    sheet_url = None
    map_only = "--map-only" in args

    if "--sheet" in args:
        idx = args.index("--sheet")
        if idx + 1 < len(args):
            sheet_url = args[idx + 1]

    if not os.path.isdir(run_folder):
        print(f"Error: folder not found: {run_folder}")
        sys.exit(1)

    scraped_json = os.path.join(run_folder, "scraped.json")
    continuity_path = os.path.join(run_folder, "continuity_analysis.md")

    client = Anthropic()

    # --- Step 1: Continuity analysis (unless --map-only) ---
    if not map_only:
        if not os.path.exists(scraped_json):
            print(f"Error: scraped.json not found in {run_folder}")
            sys.exit(1)

        extracted_files = {}
        for doc_type, filename in [
            ("SE",          "extracted_se.md"),
            ("TE",          "extracted_te.md"),
            ("Walkthrough", "extracted_walkthrough.md"),
            ("Printables",  "extracted_printables.md"),
        ]:
            path = os.path.join(run_folder, filename)
            extracted_files[doc_type] = path if os.path.exists(path) else None

        found = [k for k, v in extracted_files.items() if v]
        missing = [k for k, v in extracted_files.items() if not v]
        logger.info(f"Run folder: {run_folder}")
        logger.info(f"Sources found: {', '.join(found)}")
        if missing:
            logger.info(f"Sources absent (will be skipped): {', '.join(missing)}")

        run_continuity_analysis(client, scraped_json, extracted_files, continuity_path, logger)
        logger.info(f"Continuity analysis saved → {continuity_path}")

    # --- Step 2: Map to sheet (if --sheet provided) ---
    if sheet_url:
        if not os.path.exists(continuity_path):
            print(f"Error: continuity_analysis.md not found in {run_folder}")
            sys.exit(1)

        service_account_path = os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_JSON", "credentials/service_account.json"
        )
        logger.info("Connecting to Google Sheet...")
        sheet_id = sheets.extract_sheet_id(sheet_url)
        gspread_client = sheets.get_gspread_client(service_account_path)
        spreadsheet = sheets.open_sheet(gspread_client, sheet_id)
        worksheet = sheets.get_checklist_worksheet(spreadsheet)

        checklist_rows = sheets.read_checklist_rows(worksheet)
        logger.info(f"Read {len(checklist_rows)} checklist rows")

        mappings = qa_engine.map_issues_to_sheet(
            client, continuity_path, checklist_rows, logger
        )
        sheets.write_issue_batch(worksheet, mappings, logger)
        logger.info("Sheet update complete.")

    logger.info("Done.")


if __name__ == "__main__":
    main()
