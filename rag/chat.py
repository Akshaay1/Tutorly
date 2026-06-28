"""
Step 3: Ask questions about Chapter 1. Embeds your question (Gemini), retrieves
the closest chunks from the local index, and asks Groq's Llama model to answer
*only* using those chunks. Cites NCERT page numbers and teacher's class notes.
If nothing relevant is retrieved, it refuses to guess.

Needs: GEMINI_API_KEY and GROQ_API_KEY in .env

Run:
    python chat.py
"""

import json
import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google import genai
from groq import Groq

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

EMBED_MODEL = "gemini-embedding-001"
CHAT_MODEL = "llama-3.3-70b-versatile"
TOP_K = 5
MIN_SIMILARITY = 0.55  # raised from 0.45 — only answer when confident

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GEMINI_API_KEY or not GROQ_API_KEY:
    raise SystemExit("Set GEMINI_API_KEY and GROQ_API_KEY in rag/.env first (see .env.example).")

gemini = genai.Client(api_key=GEMINI_API_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """You are a personal study assistant for a Class 9 Science student \
studying Chapter 1: "Matter in Our Surroundings."

You have access to exactly two sources:
  1. The NCERT Class 9 Science textbook (Chapter 1)
  2. The student's own teacher's class video notes

STRICT RULES — follow every one without exception:

1. ONLY use the CONTEXT blocks provided below. Never add outside knowledge, \
even if you are certain it is correct. If the context doesn't cover something, say so.

2. ALWAYS cite your source in every sentence:
   - For textbook content → "As mentioned in your NCERT book (Page <N>), ..."
   - For teacher's notes  → "As your teacher explained in class, ..."
   - If one idea appears in both → mention both: \
"Your NCERT book (Page <N>) says ... and your teacher also explained ..."

3. DIAGRAMS: If the context mentions a figure, diagram, or "Fig.", ALWAYS add a line: \
"For a better understanding, refer to the diagram/figure in your NCERT book (Page <N>)."

4. NO GUESSING: If the retrieved context does not clearly and directly answer the \
question, respond with exactly: \
"This isn't covered in the material I have from your textbook and teacher's notes, \
so I can't give you a reliable answer."

5. ACCURACY FIRST: Never combine partial hints from the context into a speculative \
answer. It is better to say "I can't answer" than to give an answer that could be wrong.

6. Keep answers clear and simple — explain the way a teacher would to a 9th grader. \
Use bullet points for lists. Be concise but complete.
"""


def load_index():
    vectors = np.load(HERE / "index.npz")["vectors"]
    meta = json.loads((HERE / "index_meta.json").read_text(encoding="utf-8"))
    return vectors, meta


def embed_query(question: str):
    result = gemini.models.embed_content(
        model=EMBED_MODEL,
        contents=[question],
        config={"task_type": "RETRIEVAL_QUERY"},
    )
    return np.array(result.embeddings[0].values, dtype=np.float32)


def cosine_sim(a, b):
    a_norm = a / np.linalg.norm(a)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-8)
    return b_norm @ a_norm


def retrieve(question: str, vectors, meta):
    q_vec = embed_query(question)
    sims = cosine_sim(q_vec, vectors)
    top_idx = np.argsort(sims)[::-1][:TOP_K]
    return [(meta[i], float(sims[i])) for i in top_idx]


def _format_context(hits: list) -> str:
    parts = []
    for chunk, _ in hits:
        if chunk.get("source_type") == "book":
            page = chunk.get("page", "?")
            label = f"[NCERT Textbook, Page {page}]"
        else:
            label = "[Teacher's Class Video Notes]"
        parts.append(f"{label}\n{chunk['text']}")
    return "\n\n".join(parts)


def _source_summary(hits: list) -> list:
    summaries = []
    for chunk, sim in hits:
        if chunk.get("source_type") == "book":
            tag = f"NCERT Page {chunk.get('page', '?')}"
        else:
            tag = "Teacher's notes"
        summaries.append(f"{tag} (similarity={sim:.2f})")
    return summaries


def answer(question: str, vectors, meta):
    hits = retrieve(question, vectors, meta)
    good_hits = [h for h in hits if h[1] >= MIN_SIMILARITY]

    if not good_hits:
        return (
            "This isn't covered in the material I have from your textbook and "
            "teacher's notes, so I can't give you a reliable answer.",
            hits,
        )

    context = _format_context(good_hits)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}"},
    ]
    resp = groq_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=0.1,   # very low — factual, consistent
    )
    return resp.choices[0].message.content, good_hits


def main():
    vectors, meta = load_index()
    print("Chapter 1 chatbot ready. Type a question (or 'quit').\n")
    while True:
        q = input("You: ").strip()
        if q.lower() in {"quit", "exit"}:
            break
        if not q:
            continue
        reply, hits = answer(q, vectors, meta)
        print(f"\nBot: {reply}\n")
        print("  Sources used:", _source_summary(hits))
        print()


if __name__ == "__main__":
    main()
