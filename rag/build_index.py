"""
Step 2: Embed every chunk with Google's Gemini embedding API and save a local
vector index (plain numpy + cosine similarity — no hosted vector DB needed).

Rate-limit aware: the free tier caps embedding requests per minute, so this
paces requests, retries on 429 with the server-suggested delay, and checkpoints
progress to disk so an interrupted run resumes instead of starting over.

Needs: GEMINI_API_KEY in .env (free key: https://aistudio.google.com/apikey)

Run:
    python build_index.py
Output:
    index.npz  -> embedding vectors
    index_meta.json -> matching chunk text + source for each vector
"""

import json
import os
import re
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

EMBED_MODEL = "gemini-embedding-001"
BATCH_SIZE = 8          # items per request
PACE_SECONDS = 1.2      # gap between requests to stay under the per-minute cap
CKPT = HERE / "index_build_ckpt.npz"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise SystemExit("Set GEMINI_API_KEY in rag/.env first (see .env.example).")

client = genai.Client(api_key=GEMINI_API_KEY)


def _retry_delay(err) -> float:
    m = re.search(r"retry.{0,15}?(\d+(?:\.\d+)?)s", str(err), re.IGNORECASE)
    return min(float(m.group(1)) + 1, 60) if m else 20.0


def embed_batch(texts):
    net_fails = 0
    while True:
        try:
            res = client.models.embed_content(
                model=EMBED_MODEL, contents=texts,
                config={"task_type": "RETRIEVAL_DOCUMENT"},
            )
            return [e.values for e in res.embeddings]
        except genai_errors.ClientError as e:
            if getattr(e, "code", None) == 429 or "RESOURCE_EXHAUSTED" in str(e):
                wait = _retry_delay(e)
                print(f"  rate limited — sleeping {wait:.0f}s…", flush=True)
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            # transient network/SSL/server hiccups — back off and retry a few times
            net_fails += 1
            if net_fails > 8:
                raise
            wait = min(5 * net_fails, 40)
            print(f"  network error ({type(e).__name__}) — retry {net_fails}/8 in {wait}s…", flush=True)
            time.sleep(wait)


def main():
    chunks = json.loads((HERE / "chunks.json").read_text(encoding="utf-8"))
    texts = [c["text"] for c in chunks]
    total = len(texts)

    # resume from checkpoint if it matches this chunk set
    done = []
    if CKPT.exists():
        saved = np.load(CKPT)["vectors"]
        if saved.shape[0] <= total:
            done = [v for v in saved]
            print(f"Resuming from checkpoint: {len(done)}/{total} already embedded")

    for i in range(len(done), total, BATCH_SIZE):
        batch = texts[i: i + BATCH_SIZE]
        done.extend(embed_batch(batch))
        np.savez(CKPT, vectors=np.array(done, dtype=np.float32))  # checkpoint
        print(f"Embedded {min(i + BATCH_SIZE, total)}/{total}")
        if i + BATCH_SIZE < total:
            time.sleep(PACE_SECONDS)

    vectors = np.array(done, dtype=np.float32)
    np.savez(HERE / "index.npz", vectors=vectors)
    (HERE / "index_meta.json").write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    CKPT.unlink(missing_ok=True)
    print(f"Saved index with {len(chunks)} chunks -> index.npz / index_meta.json")


if __name__ == "__main__":
    main()
