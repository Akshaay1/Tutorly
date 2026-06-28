"""
Build Your Own Tutor — web server.

Serves the single-page frontend and exposes a small JSON API:
  GET  /api/curriculum   -> classes / subjects / chapters + which are indexed
  POST /api/youtube      -> transcribe + embed a pasted YouTube link (live)
  POST /api/chat         -> grounded, cited RAG answer for the selected chapter

Real indexed textbook material currently covers every chapter of Class 9 Science
(and Class 10 Science too, once class-10 chunks are built). YouTube videos are
ingested live, per link.

Run:
    uvicorn server:app --reload --port 8000     (from the app/ directory)
or:
    python server.py
"""

import json
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "rag"))

import rag_engine        # noqa: E402
import youtube_ingest    # noqa: E402

app = FastAPI(title="Build Your Own Tutor")

CURRICULUM = json.loads((HERE / "curriculum.json").read_text(encoding="utf-8"))

# In-memory pool of live-ingested YouTube videos: video_id -> (vectors, metas)
YT_POOL: dict[str, tuple] = {}


class YoutubeRequest(BaseModel):
    url: str


class ChatRequest(BaseModel):
    klass: str
    subject: str
    chapter: str
    sources: list[str] = ["book"]
    question: str
    video_id: str | None = None


@app.get("/api/curriculum")
def curriculum():
    return {
        "curriculum": CURRICULUM,
        "indexed": rag_engine.indexed_chapters("book"),
        "withTeacher": rag_engine.indexed_chapters("teacher"),
    }


@app.post("/api/youtube")
def youtube(req: YoutubeRequest):
    if not rag_engine.index_is_ready():
        return {"ok": False, "error": "Engine not configured (set API keys in rag/.env)."}
    try:
        res = youtube_ingest.ingest(req.url)
    except youtube_ingest.YoutubeError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:  # network / library issues
        return {"ok": False, "error": f"Could not fetch transcript: {type(e).__name__}"}
    YT_POOL[res["video_id"]] = (res["vectors"], res["metas"])
    return {"ok": True, "video_id": res["video_id"], "n_chunks": res["n_chunks"],
            "cached": res["cached"]}


@app.post("/api/chat")
def chat(req: ChatRequest):
    if not rag_engine.index_is_ready():
        return {
            "answer": "The chatbot engine isn't configured yet. Add GEMINI_API_KEY and "
                      "GROQ_API_KEY to rag/.env and build the index, then try again.",
            "sources": [], "grounded": False,
        }

    scope = {"class": req.klass, "subject": req.subject, "chapter": req.chapter}
    dynamic = YT_POOL.get(req.video_id) if req.video_id else None

    # If they only picked YouTube but the video isn't ingested, say so plainly.
    if set(req.sources) == {"youtube"} and not dynamic:
        return {
            "answer": "Add a YouTube link on the previous screen so I can transcribe it "
                      "first — then I can answer from the video.",
            "sources": [], "grounded": False,
        }

    try:
        return rag_engine.answer(req.question, scope, req.sources, dynamic=dynamic)
    except rag_engine.RagError as e:
        return {"answer": str(e), "sources": [], "grounded": False}


# Static frontend (mounted last so /api routes win).
app.mount("/", StaticFiles(directory=HERE / "static", html=True), name="static")


@app.get("/")
def root():
    return FileResponse(HERE / "static" / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
