import json
import time
import logging
import re
import anthropic

SKIP_KEYWORDS = [
    "audio", "podcast", "listen to", "watch video", "watch the video",
    "misspilled", "crossword", "collect coin", "collecting coin",
    "submit a question", "submit questions", "click on the answer",
    "click the answer", "qr code", "scan the",
]

SYSTEM_PROMPT = """You are a QA reviewer for Studies Weekly, an elementary school publication company.
Your job is to evaluate educational materials against specific QA checklist items.

Rules:
- Evaluate ONLY the specific check instruction provided
- Return a binary pass/fail — no severity scores
- If something is wrong, be succinct: describe the issue and where it's located
  (e.g. "Article 3 - title says 'Ancient Rome' but SE PDF page 4 says 'Ancient Greece'")
- If multiple issues exist for one check, separate them with semicolons
- Never fabricate issues that aren't evident in the provided content
- The guiding question for borderline cases:
  "Does this disrupt continuity or give the reader a poorer experience?"
  If yes, flag it. If no, pass it.
- Respond ONLY with valid JSON in this exact format:
  {"passed": true, "comment": ""}
  or
  {"passed": false, "comment": "brief description of the issue"}"""


def should_skip(check_text: str) -> bool:
    lower = check_text.lower()
    return any(kw in lower for kw in SKIP_KEYWORDS)


def run_qa_check(
    client: anthropic.Anthropic,
    check_instruction: str,
    check_note: str | None,
    relevant_content: dict,
    logger: logging.Logger,
) -> dict:
    user_message = _build_user_message(check_instruction, check_note, relevant_content)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        result = json.loads(raw)
        return {"passed": bool(result.get("passed", True)), "comment": result.get("comment", "")}

    except json.JSONDecodeError:
        logger.warning(f"Could not parse Claude response as JSON. Raw: {raw[:200]}")
        return {"passed": True, "comment": ""}
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return {"passed": True, "comment": ""}


def _build_user_message(check_instruction: str, check_note: str | None, relevant_content: dict) -> str:
    parts = [
        f"## Check Instruction\n{check_instruction}",
        f"## Additional Notes for this Check\n{check_note or 'None'}",
        "## Relevant Content",
    ]

    if relevant_content.get("toc_data"):
        toc = relevant_content["toc_data"]
        week = toc.get("week", {})
        icons = toc.get("week_icons", {})
        articles = toc.get("articles", [])
        parts.append(
            "### TOC Data\n"
            f"Week {week.get('number')}: {week.get('title')}\n"
            f"Week icons: student_edition={icons.get('student_edition')}, "
            f"printables={icons.get('printables')}, "
            f"teacher_edition={icons.get('teacher_edition')}, "
            f"assign={icons.get('assign')}\n"
            f"TOC articles ({len(articles)}): "
            + ", ".join(f"{a['order']}. [{a['type']}] {a['title']}" for a in articles)
        )

    if relevant_content.get("sv_articles"):
        sv = relevant_content["sv_articles"]
        sv_text = f"### Student View Articles ({len(sv)} total)\n"
        for article in sv:
            sv_text += f"\n**Article {article['order']}: {article['title']}**\n"
            sv_text += f"Text: {article['text'][:1500]}\n"
            if article.get("images"):
                img_parts = []
                for img in article["images"]:
                    if isinstance(img, dict):
                        part = img["alt"]
                        if img.get("caption"):
                            part += f' (caption: {img["caption"]})'
                        img_parts.append(part)
                    else:
                        img_parts.append(img)
                sv_text += f"Images: {'; '.join(img_parts)}\n"
            if article.get("has_audio"):
                sv_text += "Audio: yes\n"
            if article.get("has_video"):
                sv_text += "Video: yes\n"
            if article.get("questions"):
                sv_text += f"Questions ({len(article['questions'])}): "
                sv_text += "; ".join(article["questions"]) + "\n"
            if article.get("explore_more"):
                sv_text += f"Explore More: {', '.join(article['explore_more'])}\n"
        parts.append(sv_text)

    if relevant_content.get("tr_articles"):
        tr = relevant_content["tr_articles"]
        tr_text = f"### Teacher Resources Articles ({len(tr)} total)\n"
        for article in tr:
            tr_text += f"\n**Article {article['order']}: {article['title']}**\n"
            for sec in article.get("sections", []):
                sec_name = sec.get("name", "")
                if sec.get("type") == "attachments":
                    items = sec.get("items", [])
                    if items:
                        tr_text += f"{sec_name}: {', '.join(items)}\n"
                elif sec.get("type") == "text":
                    content = sec.get("content", "")[:800]
                    if content:
                        tr_text += f"{sec_name}:\n{content}\n"
        parts.append(tr_text)

    for key, label in [
        ("se_pdf", "Student Edition PDF"),
        ("te_pdf", "Teacher Edition PDF"),
        ("printables_pdf", "Printables PDF"),
        ("walkthrough_pdf", "Walkthrough Slides PDF"),
    ]:
        if relevant_content.get(key):
            text = relevant_content[key]
            parts.append(f"### {label}\n{text[:4000]}")

    parts.append(
        "## Your Task\n"
        "Evaluate whether the materials pass this check.\n"
        'Respond ONLY with JSON: {"passed": true/false, "comment": "..."}'
    )

    return "\n\n".join(parts)


# ---- Per-category check loops ----

def _run_checks_for_category(
    category: str,
    client: anthropic.Anthropic,
    relevant_content: dict,
    checklist_rows: list[dict],
    worksheet,
    logger: logging.Logger,
):
    rows = [r for r in checklist_rows if r["category"] == category and r["has_checkbox"]]
    total = len(rows)
    logger.info(f"--- {category}: {total} checks to run ---")

    for i, row in enumerate(rows, 1):
        check_text = row["text"]
        logger.info(f"[{category} {i}/{total}] {check_text[:70]}")

        if should_skip(check_text):
            logger.info(f"  → SKIP")
            from src.sheets import write_qa_result
            write_qa_result(worksheet, row["row_index"], False, "skipped")
            time.sleep(0.3)
            continue

        # Load cell note if not already fetched
        if row["note"] is None:
            from src.sheets import get_cell_note
            row["note"] = get_cell_note(worksheet, row["row_index"])

        result = run_qa_check(client, check_text, row["note"], relevant_content, logger)

        if not result["passed"]:
            logger.info(f"  → FAIL: {result['comment'][:100]}")
            from src.sheets import write_qa_result
            write_qa_result(worksheet, row["row_index"], True, result["comment"])
        else:
            logger.info(f"  → PASS")

        time.sleep(0.5)  # Rate limit guard

    logger.info(f"--- {category}: done ---")


def run_toc_checks(client, toc_data, pdf_texts, checklist_rows, worksheet, logger):
    content = {
        "toc_data": toc_data,
        "se_pdf": pdf_texts.get("SE", {}).get("full_text", ""),
        "te_pdf": pdf_texts.get("TE", {}).get("full_text", ""),
        "printables_pdf": pdf_texts.get("Printables", {}).get("full_text", ""),
    }
    _run_checks_for_category("TOC", client, content, checklist_rows, worksheet, logger)


def run_sv_checks(client, sv_articles, pdf_texts, checklist_rows, worksheet, logger):
    content = {
        "sv_articles": sv_articles,
        "se_pdf": pdf_texts.get("SE", {}).get("full_text", ""),
        "walkthrough_pdf": pdf_texts.get("Walkthrough", {}).get("full_text", ""),
    }
    _run_checks_for_category("SV", client, content, checklist_rows, worksheet, logger)


def run_tr_checks(client, tr_articles, pdf_texts, checklist_rows, worksheet, logger):
    content = {
        "tr_articles": tr_articles,
        "te_pdf": pdf_texts.get("TE", {}).get("full_text", ""),
        "printables_pdf": pdf_texts.get("Printables", {}).get("full_text", ""),
    }
    _run_checks_for_category("TR", client, content, checklist_rows, worksheet, logger)


def run_se_pdf_checks(client, pdf_texts, checklist_rows, worksheet, logger):
    content = {
        "se_pdf": pdf_texts.get("SE", {}).get("full_text", ""),
        "te_pdf": pdf_texts.get("TE", {}).get("full_text", ""),
    }
    _run_checks_for_category("SE", client, content, checklist_rows, worksheet, logger)


def run_te_pdf_checks(client, sv_articles, pdf_texts, checklist_rows, worksheet, logger):
    content = {
        "te_pdf": pdf_texts.get("TE", {}).get("full_text", ""),
        "sv_articles": sv_articles,
    }
    _run_checks_for_category("TE", client, content, checklist_rows, worksheet, logger)


_MAPPING_PROMPT = """You are mapping QA issues from a continuity analysis to rows in a QAC Google Sheet.

You will be given:
1. A list of checklist rows from the sheet, each with a row number, category, and check instruction
2. A continuity analysis containing identified issues

Your task: For EVERY issue bullet point in the continuity analysis, find the single best-matching checklist row and assign it there.

CRITICAL RULES:
- You MUST return one entry for every single issue bullet in the continuity analysis — do not skip any, do not merge any together
- Count the issues first, then make sure your output has the same number of entries
- Each issue gets its own separate JSON entry, even if two issues map to the same row_index
- Match each issue to the most specific checklist row that covers that type of problem
- Do NOT place issues in rows that involve: listening to audio, watching video, the Misspilled game, crosswords, collecting coins, submitting questions, or clicking answers
- Issues from the Walkthrough Slides section belong under SV Online rows in the sheet
- Issues from the Printables section belong under TR Online rows in the sheet
- If an issue has no reasonable match in any row, use row_index -1
- For the comment text: keep the issue description concise and clear, remove the confidence tag

Return ONLY a valid JSON array — no preamble, no counting text, no explanation. Each entry must be exactly:
{"row_index": <integer>, "comment": "<issue description>"}

Checklist rows:
{rows_text}

Continuity analysis:
{issues_text}"""


# Maps continuity analysis section headers → checklist category codes
_SECTION_TO_CATEGORY = {
    "TOC Structure":    "TOC",
    "SV Online":        "SV",
    "TR Online":        "TR",
    "SE PDF":           "SE",
    "TE PDF":           "TE",
    "Walkthrough Slides": "SV",  # Walkthrough lives under SV in the sheet
    "Printables":       "TR",    # Printables checks are under TR in the sheet
}


def _extract_issue_bullets(text: str) -> list[tuple[str, str]]:
    """
    Extract individual issue bullet points from continuity analysis markdown.
    Returns list of (category_code, bullet_text) tuples.
    """
    bullets = []
    current_section = ""
    current_category = "Other"
    for line in text.splitlines():
        stripped = line.strip()
        # Detect section headers like "## SE PDF"
        if stripped.startswith("## "):
            section_name = stripped[3:].strip()
            current_section = section_name
            current_category = _SECTION_TO_CATEGORY.get(section_name, "Other")
        elif stripped.startswith("- ") and len(stripped) > 15:
            bullets.append((current_category, stripped[2:].strip()))
    return bullets


def map_issues_to_sheet(
    client: anthropic.Anthropic,
    continuity_analysis_path: str,
    checklist_rows: list[dict],
    logger: logging.Logger,
) -> list[dict]:
    """
    Use Claude to map each issue in the continuity analysis to the best-matching
    checklist row. Returns a list of {row_index, comment} dicts.
    """
    with open(continuity_analysis_path, encoding="utf-8") as f:
        issues_text = f.read()

    # Pre-parse bullets so we know the exact count and category for each
    bullets = _extract_issue_bullets(issues_text)
    logger.info(f"  Parsed {len(bullets)} issue bullets from continuity analysis")

    # Number the issues and tag each with its required category
    numbered_issues = "\n".join(
        f"{i+1}. [MUST MAP TO: {cat}] {text}"
        for i, (cat, text) in enumerate(bullets)
    )

    # Format checklist rows for the prompt
    rows_lines = []
    for row in checklist_rows:
        if row.get("has_checkbox"):
            rows_lines.append(
                f"Row {row['row_index']} [{row['category']}]: {row['text']}"
            )
    rows_text = "\n".join(rows_lines)

    prompt = (
        _MAPPING_PROMPT
        .replace("{rows_text}", rows_text)
        .replace(
            "{issues_text}",
            f"There are exactly {len(bullets)} issues. You MUST return exactly {len(bullets)} JSON entries — one per numbered issue below.\n\n"
            f"Each issue is tagged [MUST MAP TO: <category>]. You MUST only choose a row whose category matches that tag. "
            f"If no specific row in that category fits, use the 'Other issues' or 'Other' row within that same category.\n\n"
            f"{numbered_issues}"
        )
    )

    logger.info("  Mapping continuity issues to sheet rows via Claude...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Extract JSON array from response — Claude may prepend counting/reasoning text
    json_match = re.search(r"\[.*\]", raw, re.DOTALL)
    if json_match:
        raw = json_match.group(0).strip()
    elif raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()

    try:
        mappings = json.loads(raw)
        valid = [
            m for m in mappings
            if isinstance(m, dict) and "row_index" in m and "comment" in m
        ]
        invalid_count = len(mappings) - len(valid)
        mapped = [m for m in valid if m["row_index"] != -1]
        unmatched = [m for m in valid if m["row_index"] == -1]
        logger.info(
            f"  Claude returned {len(mappings)} mappings: "
            f"{len(mapped)} to rows, {len(unmatched)} unmatched (row -1), "
            f"{invalid_count} invalid entries dropped"
        )
        if unmatched:
            logger.info("  Unmatched issues (no row found):")
            for m in unmatched:
                logger.info(f"    - {m['comment'][:120]}")
        return valid
    except json.JSONDecodeError as e:
        logger.error(f"  Failed to parse mapping response as JSON: {e}")
        logger.error(f"  Raw response (first 500 chars): {raw[:500]}")
        return []


def run_other_checks(client, all_data, pdf_texts, checklist_rows, worksheet, logger):
    content = {
        "toc_data": all_data.get("toc_data"),
        "sv_articles": all_data.get("sv_articles"),
        "tr_articles": all_data.get("tr_articles"),
        "se_pdf": pdf_texts.get("SE", {}).get("full_text", ""),
        "te_pdf": pdf_texts.get("TE", {}).get("full_text", ""),
        "printables_pdf": pdf_texts.get("Printables", {}).get("full_text", ""),
        "walkthrough_pdf": pdf_texts.get("Walkthrough", {}).get("full_text", ""),
    }
    _run_checks_for_category("Other", client, content, checklist_rows, worksheet, logger)
