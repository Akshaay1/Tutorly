"""
Step 1: Pull Chapter 1 text out of the NCERT PDF + the teacher's video-caption
txt, clean both, and split into retrieval-sized chunks with source metadata.

No API keys needed for this step.

Run:
    python extract_chapter1.py
Output:
    chunks.json  -> list of {"text": ..., "source": ..., "source_type": ...,
                              "chunk_id": ..., "page": ..., "has_figure": ...}
"""

import json
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent  # projectA/
PDF_PATH = ROOT / "class 9 science.pdf"
CAPTION_PATH = ROOT / "[Hindi (auto-generated)] Matter Present Classification  Class 9 Science (Chemistry) Chapter 1 Matter.txt"
OUT_PATH = Path(__file__).resolve().parent / "chunks.json"

# 0-indexed pypdf page range covering Chapter 1 "Matter in Our Surroundings"
# (verified by inspecting page text: chapter starts ~page 9, chapter 2 starts at page 23)
CHAPTER1_PAGE_START = 9
CHAPTER1_PAGE_END = 22  # inclusive

CHUNK_SIZE = 900   # characters
CHUNK_OVERLAP = 150

FIGURE_RE = re.compile(r'\bFig\.?\s*\d+|\bfigure\b|\bdiagram\b', re.IGNORECASE)


def _clean_page(text: str) -> str:
    text = re.sub(r"WE,\s*THE\s*PEOPLE\s*OF\s*INDIA.*?2018-19", "", text, flags=re.DOTALL)
    text = re.sub(r"\n?(SCIENCE\d+|MA\s*TTER\s+IN\s+O\s*UR\s+S\s*URROUNDING\s*S\s*\d+)\n?", "\n", text)
    text = re.sub(r"\b2018-19\b", "", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def extract_book_text() -> tuple:
    """Returns (full_text, page_map) where page_map is [(char_offset, pdf_page_1indexed), ...]."""
    reader = PdfReader(str(PDF_PATH))
    parts = []
    page_map = []
    current_offset = 0

    for i in range(CHAPTER1_PAGE_START, CHAPTER1_PAGE_END + 1):
        raw = reader.pages[i].extract_text() or ""
        cleaned = _clean_page(raw)
        page_map.append((current_offset, i + 1))  # store 1-indexed PDF page
        parts.append(cleaned)
        current_offset += len(cleaned) + 1  # +1 for the joining newline

    return "\n".join(parts), page_map


def extract_caption_text() -> str:
    raw = CAPTION_PATH.read_text(encoding="utf-8")
    lines = []
    for line in raw.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2 and parts[0].strip().isdigit():
            lines.append(parts[1].strip())
        elif line.strip():
            lines.append(line.strip())
    return " ".join(lines)


def _page_for_offset(offset: int, page_map: list) -> int:
    """Return the 1-indexed PDF page number that contains char at `offset`."""
    page = page_map[0][1]
    for map_offset, map_page in page_map:
        if map_offset <= offset:
            page = map_page
        else:
            break
    return page


def chunk_text(text: str, source_type: str, source: str, start_id: int, page_map: list = None):
    chunks = []
    i = 0
    cid = start_id
    while i < len(text):
        piece = text[i: i + CHUNK_SIZE].strip()
        if piece:
            chunk = {
                "chunk_id": cid,
                "text": piece,
                "source": source,
                "source_type": source_type,   # "book" | "teacher"
            }
            if page_map:
                chunk["page"] = _page_for_offset(i, page_map)
            if FIGURE_RE.search(piece):
                chunk["has_figure"] = True
            chunks.append(chunk)
            cid += 1
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks, cid


def main():
    book_text, page_map = extract_book_text()
    caption_text = extract_caption_text()

    chunks, next_id = chunk_text(
        book_text,
        source_type="book",
        source="NCERT Class 9 Science, Chapter 1: Matter in Our Surroundings (textbook)",
        start_id=0,
        page_map=page_map,
    )
    notes_chunks, _ = chunk_text(
        caption_text,
        source_type="teacher",
        source="Teacher's class video notes, Chapter 1: Matter — classification",
        start_id=next_id,
    )
    chunks.extend(notes_chunks)

    OUT_PATH.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Book chars: {len(book_text)} | Caption chars: {len(caption_text)}")
    print(f"Total chunks: {len(chunks)} -> wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
