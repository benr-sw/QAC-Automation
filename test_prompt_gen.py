"""
Test script: reads the QAC checklist, loads notes, and generates the
tailored analysis prompt via Sonnet. Prints input and output.

Usage:
    /opt/homebrew/bin/python3.11 test_prompt_gen.py <sheet_url>
"""

import os
import sys
import logging
from dotenv import load_dotenv
import anthropic

load_dotenv(".env")

from src import sheets, continuity

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3.11 test_prompt_gen.py <sheet_url>")
        sys.exit(1)

    sheet_url = sys.argv[1]
    service_account_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials/service_account.json")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    client = anthropic.Anthropic(api_key=anthropic_key)

    # Connect to sheet
    logger.info("Connecting to sheet...")
    sheet_id = sheets.extract_sheet_id(sheet_url)
    gspread_client = sheets.get_gspread_client(service_account_path)
    spreadsheet = sheets.open_sheet(gspread_client, sheet_id)
    worksheet = sheets.get_checklist_worksheet(spreadsheet)

    # Read checklist rows
    logger.info("Reading checklist rows...")
    rows = sheets.read_checklist_rows(worksheet)
    logger.info(f"  {len(rows)} checklist rows found")

    # Load notes
    logger.info("Loading notes...")
    rows = sheets.load_notes_for_rows(worksheet, rows, logger)
    notes_count = sum(1 for r in rows if r.get("note"))
    logger.info(f"  {notes_count} rows have notes")

    # Print what gets fed in
    print("\n" + "="*60)
    print("INPUT TO SONNET (checklist + notes)")
    print("="*60)
    current_category = None
    for row in rows:
        if row["category"] != current_category:
            current_category = row["category"]
            print(f"\n### {current_category}")
        note_text = f"\n   Note: {row['note']}" if row.get("note") else ""
        print(f"- {row['text']}{note_text}")

    # Generate prompt
    print("\n" + "="*60)
    print("GENERATED CROSS-REFERENCE CHECKS (Sonnet output)")
    print("="*60)
    cross_ref = continuity.generate_analysis_prompt(client, rows, logger)
    print(cross_ref)

    # Also show the full assembled prompt
    print("\n" + "="*60)
    print("FULL ASSEMBLED CONTINUITY PROMPT (what Opus receives)")
    print("="*60)
    full_prompt = continuity._CONTINUITY_PROMPT_TOP.replace("{cross_reference_checks}", cross_ref)
    print(full_prompt)

if __name__ == "__main__":
    main()
