"""
Generalized extractor: split a full NCERT book PDF into per-chapter, retrieval-
sized chunks tagged with {class, subject, chapter, page, source_type}.

Auto-detects chapter boundaries from the running headers (each right-hand page
repeats the chapter title), so no page ranges need to be hand-coded.

Processes whatever PDFs are present:
  - Class 9 Science  -> ../class 9 science.pdf   (required, shipped)
  - Class 10 Science -> ../class 10 science.pdf  (optional; skipped if absent)
Also folds in the teacher's Hindi caption file as a "teacher" source for the
Class 9 chapter "Matter in Our Surroundings".

No API keys needed.

Run:  python extract_book.py   ->  chunks.json
"""

import json
import re
from pathlib import Path

from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT_PATH = HERE / "chunks.json"
CURRICULUM = json.loads((ROOT / "app" / "curriculum.json").read_text(encoding="utf-8"))

CAPTION_PATH = ROOT / "[Hindi (auto-generated)] Matter Present Classification  Class 9 Science (Chemistry) Chapter 1 Matter.txt"

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
FIGURE_RE = re.compile(r"\bFig\.?\s*\d+|\bfigure\b|\bdiagram\b", re.IGNORECASE)

# Which books to ingest: (class, subject, pdf filename relative to project root)
BOOKS = [
    ("9", "Science", "class 9 science.pdf"),
    ("10", "Science", "NCERT-Class-10-Science.pdf"),
]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_pages(pdf_path):
    """Per-page text for a PDF. Falls back to OCR if the embedded text is garbage
    (some NCERT PDFs use custom font glyphs with no Unicode mapping)."""
    import ocr_pdf
    reader = PdfReader(str(pdf_path))
    pages = [(reader.pages[i].extract_text() or "") for i in range(len(reader.pages))]
    if ocr_pdf.looks_unreadable(pages):
        print(f"   embedded text unreadable -> running OCR on {pdf_path.name} (one-time)…")
        pages = ocr_pdf.ocr_pdf_pages(pdf_path)
    return pages


def detect_ranges(pages, titles):
    """Return list of (start_page, end_page) 0-indexed, one per chapter title.

    `pages` is a list of per-page text strings (from the PDF layer or from OCR).

    Tries two strategies and keeps the first that looks sane:
      1. "header" — match the title only in each page's first 40 chars (the
         running header). Precise; avoids short common-word titles like "Sound"
         matching body text. Works for clean PDF text (e.g. Class 9).
      2. "full"  — match the title anywhere on the page. Needed when OCR doesn't
         place the running header at the top (e.g. the Class 10 scan).
    """
    for window in (40, None):  # header-zone first, then whole page
        ranges = _detect(pages, titles, window)
        if _ranges_ok(ranges, len(pages)):
            return ranges
    # neither validated cleanly — return the full-page attempt as a best effort
    return _detect(pages, titles, None)


def _detect(pages, titles, window):
    n = len(pages)
    full = [_norm(p) for p in pages]
    search = full if window is None else [_norm(p[:window]) for p in pages]

    def is_frontmatter(i):
        return ("wethepeople" in full[i]) or (sum(_norm(t) in full[i] for t in titles) >= 4)

    first, cur = [], 0
    for t in titles:
        nt = _norm(t)
        hit = None
        for i in range(cur, n):
            if not is_frontmatter(i) and nt in search[i]:
                hit = i
                cur = i + 1
                break
        first.append(hit)
    if first[0] is None or any(f is None for f in first):
        return None

    j, steps = first[0] - 1, 0
    while j > 0 and steps < 4 and not is_frontmatter(j):
        j -= 1
        steps += 1
    openers = [j + 1 if (is_frontmatter(j) or j == 0) else max(first[0] - 2, 0)]

    for k in range(1, len(titles)):
        prev = _norm(titles[k - 1])
        jj = first[k] - 1
        while jj > first[k - 1] and prev not in full[jj]:
            jj -= 1
        openers.append(jj + 1)

    ranges = []
    for k in range(len(titles)):
        s = openers[k]
        e = (openers[k + 1] - 1) if k + 1 < len(openers) else n - 1
        ranges.append((s, e))
    return ranges


def _ranges_ok(ranges, n):
    """Sanity check: every chapter found, none absurdly small, decent coverage."""
    if not ranges:
        return False
    if any(e - s + 1 < 4 for s, e in ranges):
        return False
    covered = sum(e - s + 1 for s, e in ranges)
    return covered > 0.5 * n


def clean_page_text(text, title):
    # drop the Constitution Preamble (sits before chapter 1 in some printings)
    text = re.sub(r"WE,\s*THE\s*PEOPLE\s*OF\s*INDIA.*?2018-19", "", text, flags=re.DOTALL)
    # drop "SCIENCE<page>" running header (letters may be spaced out)
    text = re.sub(r"\n?\s*S\s*C\s*I\s*E\s*N\s*C\s*E\s*\d+\s*\n?", "\n", text)
    # drop this chapter's own running header (title with arbitrary spacing + page no.)
    chars = [re.escape(c) for c in title if not c.isspace()]
    title_re = r"\s*".join(chars)
    text = re.sub(r"\n?\s*" + title_re + r"\??\s*\d*\s*\n?", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"\b2018-19\b", "", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _page_for_offset(offset, page_map):
    """page_map = [(char_offset, page_no), ...] -> the page covering `offset`."""
    page = page_map[0][1]
    for off, pno in page_map:
        if off <= offset:
            page = pno
        else:
            break
    return page


def chunk(text, meta_base, start_id, page_map=None):
    chunks = []
    i = 0
    cid = start_id
    while i < len(text):
        piece = text[i: i + CHUNK_SIZE].strip()
        if piece:
            c = dict(meta_base)
            c.update({"chunk_id": cid, "text": piece})
            if page_map:
                c["page"] = _page_for_offset(i, page_map)
            if FIGURE_RE.search(piece):
                c["has_figure"] = True
            chunks.append(c)
            cid += 1
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks, cid


def extract_caption_text():
    raw = CAPTION_PATH.read_text(encoding="utf-8")
    out = []
    for line in raw.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2 and parts[0].strip().isdigit():
            out.append(parts[1].strip())
        elif line.strip():
            out.append(line.strip())
    return " ".join(out)


def main():
    all_chunks = []
    cid = 0

    for klass, subject, fname in BOOKS:
        pdf = ROOT / fname
        if not pdf.exists():
            print(f"– skip Class {klass} {subject}: {fname} not found")
            continue
        titles = CURRICULUM[klass][subject]
        pages = load_pages(pdf)
        ranges = detect_ranges(pages, titles)
        print(f"Class {klass} {subject}: {len(titles)} chapters from {fname}")
        for (title, (s, e)) in zip(titles, ranges):
            # clean each page separately and remember where each page starts in the
            # joined text, so every chunk can be cited to its actual PDF page.
            parts, page_map, offset = [], [], 0
            for p in range(s, e + 1):
                cleaned = clean_page_text(pages[p], title)
                page_map.append((offset, p + 1))  # 1-indexed page number
                parts.append(cleaned)
                offset += len(cleaned) + 1         # +1 for the joining newline
            text = "\n".join(parts)
            base = {
                "class": klass, "subject": subject, "chapter": title,
                "source": f"NCERT Class {klass} {subject}, Chapter: {title} (textbook)",
                "source_type": "book",
            }
            chunks, cid = chunk(text, base, cid, page_map=page_map)
            print(f"   {title:42} pages {s+1}-{e+1}  -> {len(chunks)} chunks")
            all_chunks.extend(chunks)

    OUT_PATH.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTotal: {len(all_chunks)} chunks -> {OUT_PATH}")


if __name__ == "__main__":
    main()
