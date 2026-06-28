"""
OCR fallback for PDFs whose embedded text layer is unusable (custom font glyphs
with no Unicode mapping — e.g. some NCERT PDFs extract as decorative symbols).

Renders each page to a 300-DPI image and runs Tesseract OCR, caching the result
to ocr_cache/<pdf-stem>.json so it only runs once per PDF.

Requires:  pip install pymupdf pytesseract pillow   and   brew install tesseract
"""

import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "ocr_cache"
CACHE.mkdir(exist_ok=True)


def looks_unreadable(pages, sample=6):
    """True if extracted text is mostly non-letters (garbage glyphs)."""
    joined = "".join(pages[8:8 + sample]) if len(pages) > 14 else "".join(pages)
    if not joined:
        return True
    letters = sum(c.isalpha() and ord(c) < 128 for c in joined)
    return (letters / max(len(joined), 1)) < 0.45


def ocr_pdf_pages(pdf_path, dpi=300, verbose=True):
    """Return a list of per-page text strings, OCR'ing once and caching."""
    import fitz  # PyMuPDF
    import pytesseract
    from PIL import Image

    pdf_path = Path(pdf_path)
    cache = CACHE / f"{pdf_path.stem}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    doc = fitz.open(str(pdf_path))
    pages = []
    for i in range(len(doc)):
        pix = doc[i].get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        pages.append(pytesseract.image_to_string(img))
        if verbose and (i + 1) % 20 == 0:
            print(f"  OCR {i + 1}/{len(doc)} pages", flush=True)

    cache.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    if verbose:
        print(f"  OCR complete: {len(pages)} pages -> {cache.name}", flush=True)
    return pages


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else "NCERT-Class-10-Science.pdf"
    pages = ocr_pdf_pages(HERE.parent / p)
    print(f"Done: {len(pages)} pages cached.")
