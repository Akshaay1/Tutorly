# Chapter 1 RAG chatbot (test build)

Answers questions strictly from NCERT Class 9 Science Chapter 1 (Matter in Our
Surroundings) + the teacher's video notes for that chapter. Refuses to answer
anything outside that material.

## Setup

```
pip install -r requirements.txt
cp .env.example .env        # then paste in your two free keys
```

Keys needed (both free, no card):
- `GEMINI_API_KEY` — https://aistudio.google.com/apikey (used for embeddings)
- `GROQ_API_KEY` — https://console.groq.com/keys (used for answering)

## Run, in order

```
python extract_chapter1.py   # parses PDF + caption file -> chunks.json (no key needed)
python build_index.py        # embeds chunks via Gemini -> index.npz / index_meta.json
python chat.py                # ask questions interactively
```

## Notes

- Vector storage is just numpy here (fine for one chapter). Swap in Qdrant
  Cloud once we scale to the full book / multiple subjects.
- `MIN_SIMILARITY` in `chat.py` controls how strict the "is this in syllabus"
  cutoff is — raise it if off-topic questions are still getting answered,
  lower it if legitimate questions are getting rejected.
