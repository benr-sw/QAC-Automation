import json
import logging
from src.utils import claude_with_retry

_CONTINUITY_PROMPT = """You are performing a continuity analysis for a Studies Weekly educational publication. You have been provided with some or all of the following sources for the same week:

- **Scraped JSON** — contains toc_data (TOC structure), sv_articles (student view online), tr_articles (teacher resources online)
- **SE PDF** — student edition workbook (may or may not be provided)
- **TE PDF** — teacher edition (may or may not be provided)
- **Walkthrough Slides** — lesson walkthrough slide deck (may or may not be provided)
- **Printables** — printables PDF (may or may not be provided)

Before beginning, note which sources have been provided and which are absent. Only perform cross-reference checks between sources that are actually available. Do not flag something as missing simply because a source wasn't provided.

Your job is to identify and report ONLY problems, inconsistencies, missing content, mismatches, and errors. Do not summarize what looks correct. Every issue you report will be used directly by a QA reviewer, so precision and specificity matter.

---

## HOW TO REPORT ISSUES

Each issue must follow this format:

**[Primary Location]:** "exact quote or description" — [description of issue] → **[Secondary Location]:** "exact quote or description" `[CONFIDENCE: High/Medium/Low]`

Confidence levels:
- **High** — clear, verifiable mismatch or error with direct evidence from the text
- **Medium** — likely issue but requires human judgment to confirm (e.g. ambiguous phrasing, minor wording variation that may be intentional)
- **Low** — possible issue but uncertain; flagged for human review

Primary location format examples:
- `TOC - Article 3`
- `SV Online - Article 4 (The Persian Wars) - Vocabulary`
- `TR Online - Article 2 - Section Name`
- `SE PDF - Article Title - Question 2`
- `TE PDF - Assessment Question 3a`
- `Walkthrough Slides - Slide 4`
- `Printables - Activity 1`

If content exists in one source but is absent in another:
**[Location]:** "exact quote" — present here but absent in [other source] `[CONFIDENCE: High/Medium/Low]`

---

## PRIORITY ORDER FOR ANALYSIS

Your primary focus — in order of importance — is:

1. **Exact text consistency across sources** — the same title, question, name, or phrase
   appearing differently in different sources. This includes:
   - Singular vs. plural forms of any word used across sources
   - Preposition or word choice differences in titles and headings
   - Spelling variants of proper names — people, battles, places, events — across any two sources
   - Question text that differs even slightly between SE, SV, TE, TR, or Slides
   - Answer choice text that differs between TE and SV assessment
   - The same item referenced by different names or wordings across sources
   - Consistency in section text and numbering between TE PDF and TR Online Resources (Lesson Plan, vocabulary, Teacher Background Knowledge, etc.)

2. **Missing content** — something present in one source that is entirely absent from
   another where it should appear (missing video icons, missing questions, missing sections)

3. **Internal errors** — spelling, grammar, and punctuation errors within a single source

Do NOT spend analysis effort on:
- Factual accuracy or historical correctness of the content
- Whether content is age-appropriate or pedagogically sound
- Differences in level of detail between teacher and student materials (this is expected)
- Anything you are uncertain about — flag it as Low confidence rather than analyzing it extensively

---

## WHAT TO CHECK

For each available source, first check it internally, then cross-reference it against all other available sources.

---

### INTERNAL CHECKS (apply to every source)
For each source provided, flag:
- Spelling, grammar, and punctuation errors
- Inconsistent capitalization, hyphenation, or spelling of proper nouns within the document
- Inconsistent formatting of dates, names, or titles within the document
- Potentially sensitive or controversial content for an elementary school audience
- Repeated words, missing words, or clearly broken sentences

---

### CROSS-REFERENCE CHECKS

For every element listed below, verify it is consistent across all sources where it should appear. Flag any mismatch, absence, or unexpected difference — including cases where content exists in one source but not another, or where content appears under an incorrect or mismatched heading or section.

**Week-level elements** — check across all available sources:
- Week number and week title
- Essential question/Compelling Question
- Supporting questions
- Vocabulary terms and definitions

**Title and name consistency** — check across ALL sources:
- The week title must be worded identically across all sources. Flag any variation
  including preposition differences, capitalization, or word order
- Supporting questions must be worded identically across all sources. Check for
  singular vs. plural, added prefixes or qualifiers, and any word substitutions
- Proper names — people, events, locations — must be spelled consistently across
  all sources. Check for single vs. double letters, missing particles, and
  singular vs. plural
- Supplemental material titles (printables, activities) as they appear on the
  actual document must match exactly how they are referenced in the TE, TR, and
  Walkthrough Slides. Flag every variation
- The single exception to Title consistency is the word “Activity” may be substituted for Article in the online version (e.g. TE may read “Article 1:” while SV online reads “Activity 1:”). This is up to the department and does not need to be flagged.

**Question text exact matching** — check across all sources:
- Every discussion question, supporting question, and assessment question must be
  checked word-for-word between each source where it appears
- Flag singular/plural differences, added or removed words, and punctuation differences
- Assessment answer choices must be checked word-for-word between TE and SV Online

**Article-level elements** — for each article, check across all available sources:
- Article title (exact match)
- Article order and presence
- Article body text (meaningful wording differences, missing or added content)
- Questions, activities, and discussion prompts
- **Images and captions** — for each article, compare images between SV Online and SE PDF:
  - Every image in the SE PDF should have a corresponding image in SV Online. Flag any SE image with no apparent match online
  - Image descriptions between sources may differ in wording (alt text vs. written description) — this is acceptable as long as both are clearly describing the same subject. Flag cases where the subject or content of the image appears to differ
  - Captions in the SE PDF should match captions in SV Online exactly or near-exactly. Flag any caption that is meaningfully different, missing in one source, or present in one source but absent in the other

**Explore More content** — for each article in SV Online that contains explore_more items:
- All explore_more items (videos, images, audio, maps, etc.) should be listed or referenced in the TE PDF
- Flag any explore_more item that has no corresponding reference in the TE
- If an explore_more item is a video, a video icon should also be present in that article's section in the SE PDF. If the SE extraction notes "no video icons detected" or the section contains no video icon reference, flag this as a missing video icon in the SE

**Assessment** — check across all available sources:
- Assessment question text
- Answer choices
- Correct answers

**Teacher/student-facing content** — check across TR Online and TE PDF:
- All named sections (e.g. learning objectives, student outcomes, lesson plans, notes, background knowledge) should appear in both sources under consistent headings with consistent content
- Flag any section that appears in one but not the other, or where the content under a heading in one source does not match what is under the equivalent heading in the other source

**Supplemental materials** — if Walkthrough Slides and/or Printables are provided:
- Titles, activity names, and vocabulary on these materials should match the SE PDF and SV Online
- Discussion questions and primary source excerpts on slides should match the SE PDF exactly
- Printable activity names should match how those activities are referenced in the SE, TE, and SV Online

---

### IMPORTANT NOTES TO BE AWARE OF DURING ANALYSIS
- the "order": number in the json toc_data is for scraping purposes only and not relevant to the actual order of the articles
- TOC - "Misspilled" spelling is intentional and not a typo
- do not include has_video tag in the json in your analysis
- "Let's Write" prompts in the TE is the same as "Discussion Prompt, etc." in the SE and is not an issue to note
- If a particular thing matches and there is no issue, do not write it down
- Do not include the line number (e.g. line 546) where an issue appears, as these won't be known to the human reviewer
- Before writing any bullet point, ask yourself: "Is this actually an issue?" If the answer is no, or if your own note says "no issue," "matches," or "consistent," do not write it down at all. Every bullet in the output must describe a real problem.
- TR Online is structured so that week-level content (Vocabulary, Essential Question, Supporting Questions, Learning Objectives, Student Outcomes, Assessment Map, Printables, Teacher Background Knowledge, etc.) repeats identically across every article entry. This is expected and is not an issue to flag.
- Compelling Question or Essential Question Articles in the SV Online will typically not have a number by the Article/Activity. This is fine and does not need to be reported.

---

## OUTPUT FORMAT

Organize all findings under these section headers, using only the sections for which sources were provided:

- **TOC Structure**
- **SV Online**
- **TR Online**
- **SE PDF**
- **TE PDF**
- **Walkthrough Slides**
- **Printables**

Under each section, list only confirmed issues as bullets. If no issues are found in a section, write "No issues identified."

Before producing your final output, make a second pass through all sources specifically looking for issues you may have missed. Add any newly identified issues to the relevant sections.

After you've listed all issues, do NOT include any summary of issues.

Output the full analysis as a markdown file."""


# Labels used when assembling the message — maps pdf_files key → display name
_LABELS = {
    "SE":          "SE PDF (Student Edition)",
    "TE":          "TE PDF (Teacher Edition)",
    "Walkthrough": "Walkthrough Slides",
    "Printables":  "Printables",
}


def run_continuity_analysis(
    client,
    scraped_json_path: str,
    extracted_files: dict,
    output_path: str,
    logger: logging.Logger,
    temperature: float = 0,
) -> str:
    """
    Run the continuity analysis across all available sources.

    Args:
        client:            Anthropic client instance
        scraped_json_path: Path to the scraped JSON file
        extracted_files:   Dict of {doc_type: path_or_None} for each PDF
        output_path:       Where to write the resulting continuity_analysis.md
        logger:            Logger instance

    Returns:
        output_path
    """
    content_parts = []

    # --- Scraped JSON ---
    with open(scraped_json_path, encoding="utf-8") as f:
        scraped_data = json.load(f)

    # Strip the scraping-index `order` field from TOC articles so Claude doesn't
    # confuse the sequential scraping position with the article label number.
    toc_articles = scraped_data.get("toc_data", {}).get("articles", [])
    for article in toc_articles:
        article.pop("order", None)

    content_parts.append({
        "type": "text",
        "text": (
            "## SCRAPED JSON (TOC Structure, SV Online, TR Online)\n\n"
            f"```json\n{json.dumps(scraped_data, indent=2)}\n```"
        ),
    })

    # --- Extracted PDFs (only those that were provided) ---
    for doc_type, path in extracted_files.items():
        if path is None:
            continue
        label = _LABELS.get(doc_type, doc_type)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        content_parts.append({
            "type": "text",
            "text": f"## {label}\n\n{content}",
        })

    # --- Continuity analysis prompt ---
    content_parts.append({
        "type": "text",
        "text": _CONTINUITY_PROMPT,
    })

    logger.info("  Running continuity analysis via Claude (opus-4-6)...")
    logger.info("  (This may take several minutes for large publications)")

    response = claude_with_retry(
        client, logger,
        model="claude-opus-4-6",
        max_tokens=16000,
        temperature=temperature,
        messages=[{
            "role": "user",
            "content": content_parts,
        }],
    )

    result = response.content[0].text

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)

    logger.info(f"  Continuity analysis saved → {output_path}")
    return output_path


_INCREMENTAL_PROMPT = """You are reviewing a new QA continuity analysis for a Studies Weekly educational publication.

A previous QA analysis was already performed and its issues are listed below. Your job is to go through the NEW analysis issue by issue and identify only issues that are NOT already covered by the previously reported issues.

PREVIOUSLY REPORTED ISSUES:
{existing_issues}

NEW CONTINUITY ANALYSIS:
{new_analysis}

ALGORITHM (follow exactly):
1. Go through the new analysis issue by issue.
2. For each issue, ask: "Is this issue already described in the previously reported issues?"
3. Two issues are the same if they describe the same problem in the same location — even if worded differently.
4. If it is new, include it in your output under the correct section header.
5. If it is already covered, skip it.

RULES:
- Do NOT add issues you think of yourself — only include issues from the new analysis that aren't already reported.
- Do NOT include any bullet that says there is no issue, or that something "matches" or is "consistent."
- Before including any issue, ask: is this issue SOLELY about the word "Article" being used instead of "Activity" (or vice versa)? If yes, drop it.
- Preserve section headers (## TOC Structure, ## SV Online, ## TR Online, ## SE PDF, ## TE PDF, ## Walkthrough Slides, ## Printables).
- Only include section headers that have at least one new issue under them.
- If no new issues are found, output exactly: No new issues identified.
- Output ONLY the markdown — no preamble, no explanation."""


def find_incremental_issues(
    client,
    new_analysis_path: str,
    final_qa_check_path: str,
    output_path: str,
    logger: logging.Logger,
) -> str:
    """
    Compare a new continuity analysis against the existing final_QA_check.md.
    Write only the new (not-yet-reported) issues to output_path.
    Returns output_path.
    """
    with open(new_analysis_path, encoding="utf-8") as f:
        new_analysis = f.read()
    with open(final_qa_check_path, encoding="utf-8") as f:
        existing_issues = f.read()

    prompt = (
        _INCREMENTAL_PROMPT
        .replace("{existing_issues}", existing_issues)
        .replace("{new_analysis}", new_analysis)
    )

    logger.info("  Comparing new analysis against previously reported issues (sonnet-4-6)...")

    response = claude_with_retry(
        client, logger,
        model="claude-sonnet-4-6",
        max_tokens=8192,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    result = response.content[0].text.strip()

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)

    logger.info(f"  Incremental issues saved → {output_path}")
    return output_path
