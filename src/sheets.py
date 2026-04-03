import re
import time
import logging
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

CATEGORY_EMOJIS = {
    "🗂️": "TOC",
    "📚": "SV",
    "🧑‍🏫": "TR",
    "📰": "SE",
    "📒": "TE",
    "⚠️": "Other",
}


def extract_sheet_id(url: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        raise ValueError(f"Could not extract sheet ID from URL: {url}")
    return match.group(1)


def get_gspread_client(service_account_path: str) -> gspread.Client:
    creds = Credentials.from_service_account_file(service_account_path, scopes=SCOPES)
    return gspread.authorize(creds)


def open_sheet(client: gspread.Client, sheet_id: str) -> gspread.Spreadsheet:
    try:
        return client.open_by_key(sheet_id)
    except gspread.exceptions.APIError as e:
        if "403" in str(e):
            raise PermissionError(
                f"Cannot access sheet. Please share it with: "
                f"the service account email in credentials/service_account.json"
            )
        raise


def get_checklist_worksheet(spreadsheet: gspread.Spreadsheet) -> gspread.Worksheet:
    # Try to find a worksheet with "checklist" in the name (case-insensitive)
    for ws in spreadsheet.worksheets():
        if "checklist" in ws.title.lower():
            return ws
    # Fall back to first sheet
    return spreadsheet.sheet1


def read_metadata(worksheet: gspread.Worksheet) -> dict:
    values = worksheet.batch_get(["A2", "A3", "A4"])
    raw_a2 = values[0][0][0] if values[0] else ""
    raw_a3 = values[1][0][0] if values[1] else ""
    raw_a4 = values[2][0][0] if values[2] else ""

    # Strip label prefixes (e.g. "State and Grade: TN-06" → "TN-06")
    def strip_prefix(val: str) -> str:
        return val.split(":")[-1].strip() if ":" in val else val.strip()

    state_grade = strip_prefix(raw_a2)  # e.g. "TN-06"
    week_raw = strip_prefix(raw_a3)     # e.g. "Week 23"
    week_title = strip_prefix(raw_a4)   # e.g. "Growth and Conflict..."

    # Accept formats: "NY-5", "NY5", "TN-06", "TN-K", "TN-00"
    sg_match = re.match(r'^([A-Za-z]+)-?([A-Za-z0-9]*)$', state_grade.strip())
    if sg_match:
        state = sg_match.group(1).upper()
        grade_raw = sg_match.group(2).upper()
    else:
        state = state_grade.strip()
        grade_raw = "0"
    if grade_raw == "K" or grade_raw == "":
        grade = 0
    else:
        grade_str = grade_raw.lstrip("0") or "0"
        grade = int(grade_str) if grade_str.isdigit() else 0

    week_num_match = re.search(r"\d+", week_raw)
    week_number = int(week_num_match.group()) if week_num_match else 0

    return {
        "state_grade": state_grade,
        "state": state,
        "grade": grade,
        "week_number": week_number,
        "week_title": week_title,
    }


def read_checklist_rows(worksheet: gspread.Worksheet) -> list[dict]:
    all_values = worksheet.get_all_values()
    rows = []
    current_category = "TOC"

    for i, row in enumerate(all_values):
        row_index = i + 1  # 1-based
        if row_index < 8:  # Skip header/metadata rows
            continue

        cell_a = row[0] if len(row) > 0 else ""
        cell_b = row[1] if len(row) > 1 else ""

        if not cell_a.strip():
            continue

        # Detect category header rows by emoji
        detected_category = None
        for emoji, cat in CATEGORY_EMOJIS.items():
            if emoji in cell_a:
                detected_category = cat
                break

        if detected_category:
            current_category = detected_category
            continue  # Category headers are not check rows

        # Check if this row has a checkbox (col B is TRUE, FALSE, or empty checkbox)
        has_checkbox = cell_b.strip().upper() in ("TRUE", "FALSE", "")

        # Only include rows that look like actual check items
        # (have meaningful text and are not obviously section headers)
        if len(cell_a.strip()) < 5:
            continue

        rows.append({
            "row_index": row_index,
            "text": cell_a.strip(),
            "category": current_category,
            "has_checkbox": has_checkbox,
            "note": None,  # Loaded lazily via get_cell_note if needed
        })

    return rows


def get_cell_note(worksheet: gspread.Worksheet, row: int) -> str | None:
    try:
        note = worksheet.get_note(f"A{row}")
        return note if note else None
    except Exception:
        return None


def write_issue_batch(worksheet: gspread.Worksheet, mappings: list[dict], logger: logging.Logger):
    """
    Write a batch of mapped issues to the sheet.
    Multiple issues targeting the same row are combined with a newline.
    """
    from collections import defaultdict

    # Group comments by row_index, skip row -1
    grouped = defaultdict(list)
    for m in mappings:
        row_idx = m.get("row_index", -1)
        comment = m.get("comment", "").strip()
        if row_idx != -1 and comment:
            grouped[row_idx].append(comment)

    logger.info(f"  Writing issues to {len(grouped)} sheet rows...")

    for row_idx, comments in sorted(grouped.items()):
        combined = "\n\n".join(comments)
        write_qa_result(worksheet, row_idx, True, combined)
        logger.info(f"    Row {row_idx}: {len(comments)} issue(s) written")

    logger.info(f"  Sheet update complete.")


def write_incremental_issue_batch(worksheet: gspread.Worksheet, mappings: list[dict], logger: logging.Logger):
    """
    Append new issues to existing sheet cells. New text is written in red.
    If a cell is empty, writes in red. If it has content, appends after two newlines in red.
    """
    from collections import defaultdict

    grouped = defaultdict(list)
    for m in mappings:
        row_idx = m.get("row_index", -1)
        comment = m.get("comment", "").strip()
        if row_idx != -1 and comment:
            grouped[row_idx].append(comment)

    logger.info(f"  Appending new issues to {len(grouped)} sheet rows (red text)...")

    for row_idx, comments in sorted(grouped.items()):
        new_text = "\n\n".join(comments)
        _append_red_text(worksheet, row_idx, new_text)
        logger.info(f"    Row {row_idx}: {len(comments)} new issue(s) appended")

    logger.info("  Incremental sheet update complete.")


def _append_red_text(worksheet: gspread.Worksheet, row_idx: int, new_text: str):
    """Append new_text in red to cell C{row_idx}, preserving any existing black text."""
    existing = worksheet.acell(f"C{row_idx}").value or ""
    time.sleep(0.3)

    if existing:
        full_text = existing + "\n\n" + new_text
        start_of_red = len(existing) + 2  # skip the two newlines
    else:
        full_text = new_text
        start_of_red = 0

    red = {"red": 0.8, "green": 0.0, "blue": 0.0}
    text_format_runs = []
    if start_of_red > 0:
        text_format_runs.append({"startIndex": 0, "format": {}})  # black
    text_format_runs.append({"startIndex": start_of_red, "format": {"foregroundColor": red}})

    sheet_id = worksheet.id
    row_0 = row_idx - 1  # 0-based

    worksheet.spreadsheet.batch_update({"requests": [{
        "updateCells": {
            "rows": [{"values": [{
                "userEnteredValue": {"stringValue": full_text},
                "textFormatRuns": text_format_runs,
            }]}],
            "fields": "userEnteredValue,textFormatRuns",
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row_0,
                "endRowIndex": row_0 + 1,
                "startColumnIndex": 2,  # column C
                "endColumnIndex": 3,
            },
        }
    }]})
    time.sleep(0.3)


def write_qa_result(worksheet: gspread.Worksheet, row: int, has_issue: bool, comment: str):
    if comment == "skipped":
        worksheet.update(f"C{row}", [["skipped"]])
        return

    if has_issue:
        worksheet.update(f"B{row}", [[True]])
        time.sleep(0.3)  # Avoid rate limiting
        worksheet.update(f"C{row}", [[comment]])
        time.sleep(0.3)
