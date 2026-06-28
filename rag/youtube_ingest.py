"""
Live YouTube ingestion: URL -> transcript -> chunks -> embeddings.

Given a YouTube link, fetch its transcript (auto-generated captions are fine),
split it into retrieval-sized chunks tagged as a "youtube" source, embed them
with Gemini, and cache the result on disk so the same video is instant next time.

Used by the web server when a student pastes a video link at source-selection.
"""

import json
import re
from pathlib import Path

import numpy as np

import rag_engine

CACHE_DIR = Path(__file__).resolve().parent / "yt_cache"
CACHE_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
FIGURE_RE = re.compile(r"\bFig\.?\s*\d+|\bfigure\b|\bdiagram\b", re.IGNORECASE)

_ID_RE = re.compile(
    r"(?:v=|/shorts/|/embed/|youtu\.be/|/v/)([0-9A-Za-z_-]{11})"
)


class YoutubeError(RuntimeError):
    pass


def parse_video_id(url: str) -> str:
    url = url.strip()
    m = _ID_RE.search(url)
    if m:
        return m.group(1)
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url):  # raw id pasted
        return url
    raise YoutubeError("Couldn't find a valid YouTube video id in that link.")


def _fetch_transcript(video_id: str) -> str:
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    last_err = None
    # prefer English, then Hindi, then whatever exists
    for langs in (["en"], ["hi"], ["en", "hi"], None):
        try:
            fetched = api.fetch(video_id) if langs is None else api.fetch(video_id, languages=langs)
            return " ".join(seg.text.strip() for seg in fetched if seg.text.strip())
        except Exception as e:  # NoTranscriptFound / TranscriptsDisabled / etc.
            last_err = e
            continue
    raise YoutubeError(
        "No usable transcript for this video (captions may be disabled). "
        f"Details: {type(last_err).__name__}"
    )


def _chunk(text: str):
    out, i = [], 0
    while i < len(text):
        piece = text[i: i + CHUNK_SIZE].strip()
        if piece:
            out.append(piece)
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return out


def ingest(url: str):
    """
    Returns {video_id, n_chunks, vectors (np.float32 array), metas (list)}.
    Cached on disk by video id.
    """
    video_id = parse_video_id(url)
    cache = CACHE_DIR / f"{video_id}.json"

    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        return {
            "video_id": video_id,
            "n_chunks": len(data["metas"]),
            "vectors": np.array(data["vectors"], dtype=np.float32),
            "metas": data["metas"],
            "cached": True,
        }

    transcript = _fetch_transcript(video_id)
    if len(transcript) < 40:
        raise YoutubeError("Transcript was empty or too short to use.")

    pieces = _chunk(transcript)
    vectors = rag_engine.embed_documents(pieces)
    url_full = f"https://www.youtube.com/watch?v={video_id}"
    metas = [
        {
            "chunk_id": f"yt-{video_id}-{i}",
            "text": p,
            "source": f"YouTube video ({video_id})",
            "source_type": "youtube",
            "video_id": video_id,
            "video_url": url_full,
            **({"has_figure": True} if FIGURE_RE.search(p) else {}),
        }
        for i, p in enumerate(pieces)
    ]

    cache.write_text(
        json.dumps({"vectors": vectors.tolist(), "metas": metas}, ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "video_id": video_id,
        "n_chunks": len(metas),
        "vectors": vectors,
        "metas": metas,
        "cached": False,
    }
