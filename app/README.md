# Build Your Own Tutor — web app

A minimalistic web frontend over the Chapter-1 RAG engine. Students log in (dummy),
pick **Class (6–12) → Subject (CBSE) → Chapter (NCERT) → Sources**, then chat with a
tutor that answers **only** from the chosen sources and cites every point back to the
NCERT page or the teacher's class notes.

## Run

```bash
# 1. (once) install deps into the rag venv
cd ../rag && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 2. make sure the index is built (needs GEMINI/GROQ keys in rag/.env)
.venv/bin/python extract_chapter1.py
.venv/bin/python build_index.py

# 3. start the web app
cd ../app
../rag/.venv/bin/python -m uvicorn server:app --reload --port 8000
```

Open <http://127.0.0.1:8000>.

## What's live vs. scaffolding

- The full navigation (every class, subject, chapter) is real.
- The **chatbot has indexed material for exactly one chapter**:
  **Class 9 → Science → "Matter in Our Surroundings"** (marked `● live` in the UI).
- Other chapters render and accept source selections, but their chat reports that
  material isn't indexed yet. To add a chapter: extract + chunk its text into
  `rag/chunks.json`, rebuild the index, and add it to `INDEXED` in `server.py`
  (or generalise that to a per-chapter index map).

## Files

- `server.py` — FastAPI: serves the SPA + `/api/curriculum` and `/api/chat`.
- `curriculum.json` — classes / subjects / NCERT chapters.
- `static/` — the single-page frontend (`index.html`, `styles.css`, `app.js`).
- `../rag/rag_engine.py` — shared retrieval + answer logic (used by the CLI too).
