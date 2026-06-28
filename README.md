# Build Your Own Tutor 🎓

A study chatbot that answers **only** from sources you trust — your NCERT
textbook, your teacher's class videos, or a YouTube lecture you paste — and
**cites every answer** back to the exact page or source. If something isn't in
your selected material, it says so instead of guessing.

> Unlike general AI tools that answer from a randomized internet, this is
> grounded in credible sources you choose yourself.

**Flow:** pick a class (6–12) → subject → chapter → choose sources → chat.

---

## Quick start

You need **Python 3** and two free API keys.

### 1. Add your API keys

Create a file at `rag/.env` with:

```
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
```

- Gemini key (for embeddings): https://aistudio.google.com/apikey
- Groq key (for the chat model): https://console.groq.com/keys

### 2. Run it

```bash
./run.sh
```

That's it. The first run auto-creates a virtualenv and installs everything, then
starts the app. Open **http://127.0.0.1:8000** in your browser.

To stop: press `Ctrl+C`.

---

## The `run.sh` commands

| Command | What it does |
|---|---|
| `./run.sh` or `./run.sh start` | Run the app locally at http://127.0.0.1:8000 |
| `./run.sh setup` | Just install dependencies (no server) |
| `./run.sh build` | Rebuild the search index from the NCERT PDFs |
| `./run.sh share` | Run the app **and** open a public shareable link |

---

## Share it with a public link

```bash
./run.sh share
```

This opens a **Cloudflare Tunnel** and prints a public
`https://….trycloudflare.com` link anyone can open while your Mac stays on.
No GitHub or cloud account needed. Requires `cloudflared` once:

```bash
brew install cloudflared
```

Full details and limitations are in **[`app/SHARE.md`](app/SHARE.md)**.

---

## Host it permanently (GitHub → Render)

For an always-on public website (fixed URL, no need to keep your Mac on), push
to GitHub and deploy on Render's free tier. The repo ships a `render.yaml` and a
prebuilt index so it serves immediately. Step-by-step: **[`DEPLOY.md`](DEPLOY.md)**.

Note: live YouTube transcription only works when running locally (your home IP) —
cloud hosts are blocked by YouTube. The NCERT chat works everywhere.

---

## What's included (content)

- ✅ **Class 9 Science** — all 15 NCERT chapters, indexed and cited to the page.
- ✅ **Live YouTube** — paste a lecture link; it transcribes & learns it on the fly.
- ⏳ **Class 10 Science** — drop `class 10 science.pdf` in the project root, then
  run `./run.sh build` to index it.
- 🗺️ Classes 6–12 navigation for all CBSE subjects is present; chapters become
  chat-ready once their material is indexed.

### Adding more material

1. Put the NCERT book PDF in the project root, e.g. `class 10 science.pdf`.
2. Make sure it's listed in `rag/extract_book.py` (the `BOOKS` list).
3. Run `./run.sh build` — it auto-detects chapters and re-indexes.

---

## How it works (RAG pipeline)

```
PDF + captions ──▶ extract_book.py ──▶ chunks.json
                                            │
chunks.json ──▶ build_index.py (Gemini embeddings) ──▶ index.npz + index_meta.json

Your question ──▶ embed (Gemini) ──▶ find closest chunks for THIS chapter
              ──▶ Groq Llama answers using ONLY those chunks ──▶ cited answer
```

- **Embeddings:** Google Gemini (`gemini-embedding-001`)
- **Chat model:** Groq (`llama-3.3-70b-versatile`), temperature 0.1
- **Retrieval:** local NumPy + cosine similarity (no vector DB needed)
- **Guardrail:** answers below a similarity threshold are refused, not guessed.

---

## Project structure

```
projectA/
├── run.sh                 ← all-in-one launcher (start / setup / build / share)
├── README.md              ← you are here
├── class 9 science.pdf    ← source textbook
├── app/
│   ├── server.py          ← FastAPI: serves the UI + /api/chat, /api/youtube
│   ├── curriculum.json    ← classes / subjects / NCERT chapters
│   ├── share.sh           ← public-link helper
│   ├── SHARE.md           ← sharing guide
│   └── static/            ← the web UI (index.html, styles.css, app.js)
└── rag/
    ├── extract_book.py    ← PDF → per-chapter chunks (auto-detects boundaries)
    ├── build_index.py     ← chunks → embeddings (rate-limit aware)
    ├── youtube_ingest.py  ← YouTube link → transcript → embeddings
    ├── rag_engine.py      ← retrieval + grounded answering
    ├── index.npz          ← the vector index
    ├── index_meta.json    ← chunk text + source metadata
    └── .env               ← your API keys (not shared)
```

---

## Troubleshooting

- **"rate limit" / 429 in chat or YouTube** — the free Gemini tier allows ~100
  embeds/min. Wait a minute and retry. Heavy use needs a paid tier.
- **Chatbot says "engine isn't configured"** — your keys are missing in
  `rag/.env`. Add them and restart.
- **YouTube "could not fetch transcript"** — usually a momentary Gemini rate
  limit (the transcript itself is fine). Retry. Note: hosting on a cloud server
  (not your Mac) would break YouTube, since YouTube blocks datacenter IPs — which
  is exactly why we share via the tunnel instead.
- **A chapter shows no live answers** — its material isn't indexed yet. Add the
  PDF and run `./run.sh build`, or paste a YouTube link for that chapter.
```
