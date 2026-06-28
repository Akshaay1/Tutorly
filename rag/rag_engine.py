"""
Shared RAG engine. Imported by the web server (and the CLI).

Loads the local vector index once, embeds questions via Gemini, retrieves the
closest chunks *scoped to one chapter and the sources the student selected*, and
asks Groq's Llama model to answer ONLY from those chunks with cited answers.
Supports merging a live, in-memory pool (e.g. a freshly transcribed YouTube
video) into retrieval.

Needs: GEMINI_API_KEY and GROQ_API_KEY in rag/.env
"""

import json
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

EMBED_MODEL = "gemini-embedding-001"
CHAT_MODEL = "llama-3.3-70b-versatile"
TOP_K = 5
MIN_SIMILARITY = 0.55

SYSTEM_PROMPT = """You are a personal study assistant for a CBSE student. \
You answer ONLY using the CONTEXT blocks provided below, which come from the \
sources the student chose: their NCERT textbook, their teacher's class notes, \
and/or a video they added.

STRICT RULES — follow every one without exception:

1. ONLY use the CONTEXT blocks. Never add outside knowledge, even if you are \
certain it is correct. If the context doesn't cover it, say so.

2. ALWAYS cite your source:
   - Textbook content -> "As mentioned in your NCERT book (Page <N>), ..."
   - Teacher's notes   -> "As your teacher explained in class, ..."
   - Video content     -> "As explained in the video you added, ..."
   - If an idea is in more than one source, mention each.

3. DIAGRAMS: If the context mentions a figure, diagram, or "Fig.", add: \
"For better understanding, refer to the diagram/figure in your NCERT book (Page <N>)."

4. NO GUESSING: If the context does not clearly and directly answer the question, \
respond with exactly: "This isn't covered in the material you selected, so I can't \
give you a reliable answer."

5. ACCURACY FIRST: Never stitch partial hints into a speculative answer. It is \
better to say "I can't answer" than to risk being wrong.

6. Explain simply, the way a good teacher would. Use bullet points for lists. \
Be concise but complete.
"""


class RagError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _clients():
    gemini_key = os.environ.get("GEMINI_API_KEY")
    groq_key = os.environ.get("GROQ_API_KEY")
    if not gemini_key or not groq_key:
        raise RagError("Set GEMINI_API_KEY and GROQ_API_KEY in rag/.env to enable the chatbot.")
    from google import genai
    from groq import Groq
    return genai.Client(api_key=gemini_key), Groq(api_key=groq_key)


@lru_cache(maxsize=1)
def _index():
    npz, meta = HERE / "index.npz", HERE / "index_meta.json"
    if not npz.exists() or not meta.exists():
        raise RagError("No index found. Run build_index.py first.")
    return np.load(npz)["vectors"], json.loads(meta.read_text(encoding="utf-8"))


def index_is_ready():
    try:
        _clients(); _index(); return True
    except RagError:
        return False


def indexed_chapters(source_type=None):
    """Distinct {class, subject, chapter} present in the static index.

    If source_type is given (e.g. "book" or "teacher"), only chapters that have
    at least one chunk of that source type are returned.
    """
    try:
        _, meta = _index()
    except RagError:
        return []
    seen, out = set(), []
    for c in meta:
        if source_type and c.get("source_type") != source_type:
            continue
        key = (c.get("class"), c.get("subject"), c.get("chapter"))
        if key not in seen and all(key):
            seen.add(key)
            out.append({"class": key[0], "subject": key[1], "chapter": key[2]})
    return out


def embed_documents(texts):
    """Embed passages for indexing (used by the live YouTube ingester)."""
    gemini, _ = _clients()
    res = gemini.models.embed_content(
        model=EMBED_MODEL, contents=list(texts),
        config={"task_type": "RETRIEVAL_DOCUMENT"},
    )
    return np.array([e.values for e in res.embeddings], dtype=np.float32)


def _embed_query(question):
    gemini, _ = _clients()
    res = gemini.models.embed_content(
        model=EMBED_MODEL, contents=[question],
        config={"task_type": "RETRIEVAL_QUERY"},
    )
    return np.array(res.embeddings[0].values, dtype=np.float32)


def _cosine(q, mat):
    qn = q / (np.linalg.norm(q) + 1e-8)
    mn = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-8)
    return mn @ qn


def _retrieve(question, scope, allowed_types, dynamic):
    vectors, meta = _index()
    # gather candidate static chunks matching this chapter + allowed source types
    idx = [
        i for i, c in enumerate(meta)
        if c.get("class") == scope.get("class")
        and c.get("subject") == scope.get("subject")
        and c.get("chapter") == scope.get("chapter")
        and c.get("source_type") in allowed_types
    ]
    cand_vecs = [vectors[i] for i in idx]
    cand_meta = [meta[i] for i in idx]

    # merge the live pool (e.g. a transcribed YouTube video) if youtube is allowed
    if dynamic and "youtube" in allowed_types:
        dvecs, dmeta = dynamic
        cand_vecs.extend(list(dvecs))
        cand_meta.extend(dmeta)

    if not cand_vecs:
        return []
    sims = _cosine(_embed_query(question), np.array(cand_vecs, dtype=np.float32))
    order = np.argsort(sims)[::-1][:TOP_K]
    return [(cand_meta[i], float(sims[i])) for i in order]


def _label(chunk):
    st = chunk.get("source_type")
    if st == "book":
        return f"NCERT Page {chunk.get('page', '?')}"
    if st == "teacher":
        return "Teacher's notes"
    if st == "youtube":
        return "Your video"
    return "Source"


def _context_label(chunk):
    st = chunk.get("source_type")
    if st == "book":
        return f"[NCERT Textbook, Page {chunk.get('page', '?')}]"
    if st == "teacher":
        return "[Teacher's Class Notes]"
    if st == "youtube":
        return "[Your Added Video]"
    return "[Source]"


def source_summary(hits):
    return [{"label": _label(c), "similarity": round(s, 2)} for c, s in hits]


def answer(question, scope, allowed_types, dynamic=None):
    allowed = set(allowed_types) or {"book", "teacher", "youtube"}
    hits = _retrieve(question, scope, allowed, dynamic)
    good = [h for h in hits if h[1] >= MIN_SIMILARITY]

    if not good:
        return {
            "answer": "This isn't covered in the material you selected, so I can't "
                      "give you a reliable answer.",
            "sources": source_summary(hits), "grounded": False,
        }

    context = "\n\n".join(f"{_context_label(c)}\n{c['text']}" for c, _ in good)
    _, groq_client = _clients()
    resp = groq_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}"},
        ],
        temperature=0.1,
    )
    return {"answer": resp.choices[0].message.content,
            "sources": source_summary(good), "grounded": True}
