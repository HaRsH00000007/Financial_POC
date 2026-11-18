"""Page-level text extraction for long reports.

pypdfium2 (PDFium) is ~20x faster than pypdf on 150-page annual reports and keeps
table rows on single lines; pypdf is the fallback if PDFium cannot open a file.
"""
from __future__ import annotations

import io
import re

_WS = re.compile(r"[ \t   ]+")


def clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("￾", "")
    for dash in ("‐", "‑", "‒", "–", "—", "−"):
        text = text.replace(dash, "-")
    return "\n".join(_WS.sub(" ", line).strip() for line in text.split("\n"))


def page_texts(data: bytes) -> tuple[list[str], str]:
    """Return (one cleaned text per page, engine name)."""
    try:
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(data)
        try:
            texts = []
            for i in range(len(doc)):
                page = doc[i]
                tp = page.get_textpage()
                texts.append(clean(tp.get_text_range()))
                tp.close()
                page.close()
        finally:
            doc.close()
        return texts, "pdfium-text"
    except Exception:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return [clean(p.extract_text() or "") for p in reader.pages], "pypdf-text"
