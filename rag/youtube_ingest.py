"""
Live YouTube ingestion: URL -> transcript -> chunks -> embeddings.

Given a YouTube link, fetch its transcript (auto-generated captions are fine),
split it into retrieval-sized chunks tagged as a "youtube" source, embed them
with Gemini, and cache the result on disk so the same video is instant next time.

Used by the web server when a student pastes a video link at source-selection.
"""

import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np

import rag_engine

CACHE_DIR = Path(__file__).resolve().parent / "yt_cache"
CACHE_DIR.mkdir(exist_ok=True)
TRANSCRIPT_DIR = CACHE_DIR / "transcripts"   # raw transcripts, cached separately
TRANSCRIPT_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
RETRIES = 3              # youtube-transcript-api attempts
BACKOFF_BASE = 2.0       # seconds; doubles each retry (2s, 4s)
FIGURE_RE = re.compile(r"\bFig\.?\s*\d+|\bfigure\b|\bdiagram\b", re.IGNORECASE)

# Failures where retrying is pointless (the video genuinely has no transcript).
_PERMANENT = {
    "TranscriptsDisabled", "NoTranscriptFound", "VideoUnavailable",
    "VideoUnplayable", "InvalidVideoId", "AgeRestricted",
}

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


def _build_api():
    """Build a YouTubeTranscriptApi, routing through a residential proxy if
    proxy credentials are set in the environment. This is what makes the feature
    work in the cloud (Render/etc.), where YouTube blocks datacenter IPs.

    - Locally (no env vars): direct connection, free.
    - In the cloud: set WEBSHARE_PROXY_USERNAME + WEBSHARE_PROXY_PASSWORD
      (Webshare residential), or a generic YT_HTTP_PROXY URL.
    """
    import os
    from youtube_transcript_api import YouTubeTranscriptApi

    ws_user = os.environ.get("WEBSHARE_PROXY_USERNAME")
    ws_pass = os.environ.get("WEBSHARE_PROXY_PASSWORD")
    if ws_user and ws_pass:
        from youtube_transcript_api.proxies import WebshareProxyConfig
        return YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(proxy_username=ws_user, proxy_password=ws_pass)
        )

    generic = os.environ.get("YT_HTTP_PROXY")  # e.g. http://user:pass@host:port
    if generic:
        from youtube_transcript_api.proxies import GenericProxyConfig
        return YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(http_url=generic, https_url=generic)
        )

    return YouTubeTranscriptApi()  # direct (local / has a residential IP)


def _proxy_url():
    """Proxy URL for yt-dlp / audio download, derived from the same env creds."""
    user = os.environ.get("WEBSHARE_PROXY_USERNAME")
    pw = os.environ.get("WEBSHARE_PROXY_PASSWORD")
    if user and pw:
        return f"http://{user}-rotate:{pw}@p.webshare.io:80"
    return os.environ.get("YT_HTTP_PROXY")


def _try_once(api, video_id: str):
    """One pass over language preferences; returns text or raises the last error."""
    last = None
    for langs in (["en"], ["hi"], ["en", "hi"], None):
        try:
            fetched = api.fetch(video_id) if langs is None else api.fetch(video_id, languages=langs)
            text = " ".join(seg.text.strip() for seg in fetched if seg.text.strip())
            if text:
                return text
        except Exception as e:
            last = e
    if last is not None:
        raise last
    raise YoutubeError("Transcript was empty.")


# ---- Primary (free): youtube-transcript-api with retries + exponential backoff ----
def _via_transcript_api(video_id):
    """Retries transient failures (blocked / network) with exponential backoff;
    gives up immediately if the video truly has no captions. Returns text or None."""
    delay = BACKOFF_BASE
    for attempt in range(1, RETRIES + 1):
        try:
            return _try_once(_build_api(), video_id)
        except Exception as e:
            if type(e).__name__ in _PERMANENT:
                return None  # no captions — retrying won't help
            if attempt < RETRIES:
                print(f"  transcript blocked/failed ({type(e).__name__}) — "
                      f"retry {attempt}/{RETRIES - 1} in {delay:.0f}s…", flush=True)
                time.sleep(delay)
                delay *= 2
    return None


# ---- Tier 3 (optional): yt-dlp audio -> Groq Whisper (whisper-large-v3) ----
def _whisper_enabled():
    return os.environ.get("ENABLE_WHISPER", "").lower() in ("1", "true", "yes")


def _via_whisper(video_id):
    if not _whisper_enabled():
        return None
    try:
        import yt_dlp
    except ImportError:
        return None
    tmp = Path(tempfile.mkdtemp(prefix="ytaud_"))
    try:
        opts = {
            "format": "bestaudio[ext=m4a]/bestaudio",
            "outtmpl": str(tmp / "%(id)s.%(ext)s"), "quiet": True, "no_warnings": True, "noprogress": True,
        }
        proxy = _proxy_url()
        if proxy:
            opts["proxy"] = proxy
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        files = [f for f in tmp.iterdir() if f.is_file()]
        if not files:
            return None
        audio = files[0]
        if audio.stat().st_size > 24 * 1024 * 1024:   # Groq Whisper ~25 MB upload limit
            return None
        from groq import Groq
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        with open(audio, "rb") as fh:
            resp = client.audio.transcriptions.create(
                file=(audio.name, fh.read()), model="whisper-large-v3",
            )
        return (resp.text or "").strip() or None
    except Exception:
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _fetch_transcript(video_id: str) -> str:
    """Cache-first, free-first transcript fetch:

        cache -> youtube-transcript-api (retries + backoff) -> (optional) Whisper

    Each video is fetched at most once (then cached forever). If the free path
    keeps failing on a datacenter IP, switch only this layer to a residential
    proxy or hosted transcript API later — the rest of the app is unaffected.
    """
    cache = TRANSCRIPT_DIR / f"{video_id}.txt"
    if cache.exists():
        return cache.read_text(encoding="utf-8")

    for source in (_via_transcript_api, _via_whisper):
        text = source(video_id)
        if text and len(text.strip()) >= 40:
            text = text.strip()
            cache.write_text(text, encoding="utf-8")   # fetch each video only once
            return text

    raise YoutubeError(
        "Couldn't fetch this video's transcript right now. It may have no captions, "
        "or YouTube is rate-limiting the server. Try again shortly, or a different video."
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
