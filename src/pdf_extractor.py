import base64
import io
import logging

from pypdf import PdfReader, PdfWriter
from src.utils import claude_with_retry

# ---------------------------------------------------------------------------
# Extraction prompts — one per document type
# ---------------------------------------------------------------------------

_PROMPTS = {
    "SE": (
        "Please extract the headings, text, and images from this PDF publication. "
        "Place extracted content neatly formatted in a markdown file. "
        "Do not make any corrections on grammar, punctuation or spelling, simply extract as is.\n\n"
        "Extraction rules:\n\n"
        "Article text continuity — this is the highest priority rule:\n"
        "* Publications are formatted in multiple columns. Text from one article may continue in a "
        "different column or on the next page before a new article begins.\n"
        "* If a paragraph or sentence appears to end abruptly or mid-thought, do not move on — find "
        "the continuation of that text first, even if it means skipping over an image or crossing a "
        "page boundary. Keep article text flowing continuously before separating content by page or section.\n\n"
        "Images:\n"
        "- Extract as a text description in brackets, bold and italicized, e.g. [Image: description]\n"
        "- Note the presence of any video icons found near images. If no video icons are found, "
        'write "No video icons detected" at the end.\n\n'
        "Blank student response lines:\n"
        "- When blank lines appear for student writing — whether inside a table, under a question, "
        "or anywhere else — write ***blank lines for student response*** in bold italic in that "
        "location instead of leaving the space empty.\n\n"
        "Standalone content outside article text:\n"
        "- Any content that appears outside the main article body should be labeled according to "
        "what it is. Use these labels:\n"
        "  - **Fun Fact:** for callout boxes with interesting facts\n"
        "  - **Discussion Question:** for questions posed directly to the reader\n"
        "  - **Activity Instruction:** for directions telling students to highlight, underline, "
        "circle, or perform an action on the text\n"
        "  - **Activity Prompt:** for writing or creative response prompts\n"
        "  - **Caption:** for standalone captions or callout text associated with an image\n"
        "  - Use your best judgment for any other type of standalone content"
    ),
    "TE": (
        "Please extract the headings, text, and any images from this PDF document. "
        "Place extracted content neatly formatted in a markdown file. "
        "Images can be extracted as text descriptions of the image. "
        "If no images are found, disregard this instruction.\n\n"
        "Formatting rules:\n"
        "- Red text must be formatted in ***bold italic*** throughout to distinguish it from regular text\n"
        "- Use a single line break between: answer choices (a, b, c, d), bullet points, numbered "
        "list items, lettered sub-items, and any closely related list content\n"
        "- Use a blank line only between distinct paragraphs, major sections, or headings\n"
        "- Do not insert extra blank lines between answer options or list items\n\n"
        "Completeness — critical:\n"
        "- This is a long document. You must extract ALL content from ALL pages including the very last page.\n"
        "- Do not stop early. If you approach your output limit before finishing, complete the "
        "current question or section, then add: [EXTRACTION INCOMPLETE — document continues beyond this point]"
    ),
    "Walkthrough": (
        "You are extracting content from Studies Weekly walkthrough slides for a QA continuity check.\n\n"
        "For each slide, extract all visible text verbatim — including slide titles, headings, bullet points, "
        "discussion questions, activity instructions, vocabulary terms and definitions, and answer key responses.\n\n"
        "For slides containing long primary source excerpts or full article text blocks: summarize that specific "
        "block in 1-2 sentences instead of transcribing it (e.g. \"Contains excerpt from Pericles's Funeral "
        "Oration\"). All other text on that slide should still be extracted verbatim.\n\n"
        "Additional rules:\n"
        "- Blue slides with only a title and no other content are video slides — format as: Video: [title]\n"
        "- For image-only slides or slides where the main content is a map or illustration: describe the image "
        "briefly instead of transcribing\n"
        "- Answer key text should be formatted in **bold italic** to distinguish it from question text\n"
        "- Organize output into markdown file divided by slide number"
    ),
    "Printables": (
        "Please extract the headings, text, and any images from this PDF document. "
        "Place extracted content neatly formatted in a markdown file. "
        "Images can be extracted as text descriptions of the image."
    ),
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_base64(pdf_bytes: bytes) -> str:
    return base64.standard_b64encode(pdf_bytes).decode("utf-8")


def _call_claude(client, logger: logging.Logger, pdf_bytes: bytes, prompt: str) -> str:
    response = claude_with_retry(client, logger,
        model="claude-opus-4-6",
        max_tokens=16000,
        temperature=0,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": _to_base64(pdf_bytes),
                    },
                },
                {
                    "type": "text",
                    "text": prompt,
                },
            ],
        }],
    )
    return response.content[0].text


def _page_range_to_bytes(pdf_bytes: bytes, start: int, end: int) -> bytes:
    """Return a new PDF containing pages [start, end) (0-indexed)."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for i in range(start, min(end, len(reader.pages))):
        writer.add_page(reader.pages[i])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _extract_pdf_chunk(
    client,
    pdf_bytes: bytes,
    start: int,
    end: int,
    base_prompt: str,
    logger: logging.Logger,
    doc_type: str = "",
) -> str:
    """Recursively extract PDF pages, halving the chunk on 413 or other failures."""
    chunk_bytes = _page_range_to_bytes(pdf_bytes, start, end)

    prompt = base_prompt
    if start > 0 or True:
        if doc_type == "Walkthrough":
            prompt = (
                base_prompt
                + f"\n\nNote: These slides are slides {start + 1} through {end} of the full deck. "
                "Number them accordingly in your output."
            )
        else:
            prompt = (
                base_prompt
                + f"\n\nNote: This is pages {start + 1} through {end} of the full document. "
                "Extract only the content on these pages — do not re-state or repeat content from previous pages."
            )

    try:
        return _call_claude(client, logger, chunk_bytes, prompt)
    except Exception as e:
        if end - start <= 1:
            label = f"Slide {start + 1}" if doc_type == "Walkthrough" else f"Page {start + 1}"
            logger.warning(f"  {label} could not be extracted: {e}")
            return f"\n*[Extraction failed for {label.lower()} — content too dense to process]*\n"
        mid = (start + end) // 2
        logger.info(
            f"  {doc_type} pages {start + 1}–{end} too large, "
            f"retrying as {start + 1}–{mid} and {mid + 1}–{end}"
        )
        left = _extract_pdf_chunk(client, pdf_bytes, start, mid, base_prompt, logger, doc_type)
        right = _extract_pdf_chunk(client, pdf_bytes, mid, end, base_prompt, logger, doc_type)
        return left + "\n" + right


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_pdf(
    client,
    pdf_file,
    doc_type: str,
    output_path: str,
    logger: logging.Logger,
) -> str | None:
    """
    Extract a single PDF to a markdown file using Claude.

    Args:
        client:      Anthropic client instance
        pdf_file:    File-like object (BytesIO / Streamlit UploadedFile), or None
        doc_type:    One of "SE", "TE", "Walkthrough", "Printables"
        output_path: Where to write the resulting .md file
        logger:      Logger instance

    Returns:
        output_path if extraction succeeded, None if pdf_file was None.
    """
    if pdf_file is None:
        logger.info(f"  {doc_type} PDF: not provided, skipping")
        return None

    pdf_file.seek(0)
    pdf_bytes = pdf_file.read()
    prompt = _PROMPTS[doc_type]

    logger.info(f"  Extracting {doc_type} PDF via Claude (opus-4-6)...")

    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)

    if doc_type == "Walkthrough":
        logger.info(f"  Walkthrough: {page_count} slides detected, using chunking")
        content = _extract_pdf_chunk(client, pdf_bytes, 0, page_count, prompt, logger, doc_type)
    else:
        try:
            content = _call_claude(client, logger, pdf_bytes, prompt)
        except Exception as e:
            if "413" in str(e) or "request_too_large" in str(e):
                logger.warning(f"  {doc_type} PDF too large ({page_count} pages), splitting into chunks...")
                content = _extract_pdf_chunk(client, pdf_bytes, 0, page_count, prompt, logger, doc_type)
            else:
                raise

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"  {doc_type} extraction saved → {output_path}")
    return output_path
