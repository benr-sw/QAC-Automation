import io
from pypdf import PdfReader


def extract_text_from_pdf(pdf_bytes: io.BytesIO, label: str) -> dict:
    if pdf_bytes is None:
        return {"label": label, "page_count": 0, "full_text": "", "pages": []}

    pdf_bytes.seek(0)
    reader = PdfReader(pdf_bytes)
    pages = []

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append({"page_num": i + 1, "text": text})

    full_text = "\n".join(
        f"\n--- Page {p['page_num']} ---\n{p['text']}" for p in pages
    )

    return {
        "label": label,
        "page_count": len(pages),
        "full_text": full_text,
        "pages": pages,
    }
