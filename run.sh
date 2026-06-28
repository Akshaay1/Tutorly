#!/usr/bin/env bash
# ============================================================================
# Build Your Own Tutor — all-in-one launcher
#
#   ./run.sh            start the app locally  -> http://127.0.0.1:8000
#   ./run.sh start      (same as above)
#   ./run.sh setup      create the virtualenv + install dependencies only
#   ./run.sh build      (re)build the search index from the NCERT PDFs
#   ./run.sh share      start the app AND open a public shareable link
#
# First run auto-installs everything. You only need: Python 3, and your API
# keys in rag/.env  (GEMINI_API_KEY and GROQ_API_KEY).
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RAG="$ROOT/rag"
APP="$ROOT/app"
VENV="$RAG/.venv"
PY="$VENV/bin/python"
PORT=8000
CMD="${1:-start}"

ensure_setup() {
  if [ ! -x "$PY" ]; then
    echo "▶ First-time setup: creating virtualenv + installing dependencies…"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --upgrade pip >/dev/null
    "$VENV/bin/pip" install -r "$RAG/requirements.txt"
    echo "✓ Setup complete"
  fi
}

check_keys() {
  if [ ! -f "$RAG/.env" ] || ! grep -qE 'GEMINI_API_KEY=.+' "$RAG/.env" 2>/dev/null \
     || ! grep -qE 'GROQ_API_KEY=.+' "$RAG/.env" 2>/dev/null; then
    echo "⚠  Missing API keys. Create  rag/.env  with:"
    echo "       GEMINI_API_KEY=your_gemini_key   (https://aistudio.google.com/apikey)"
    echo "       GROQ_API_KEY=your_groq_key       (https://console.groq.com/keys)"
    echo "   The app will load, but the chatbot can't answer until these are set."
  fi
}

case "$CMD" in
  setup)
    ensure_setup
    ;;

  build)
    ensure_setup; check_keys
    echo "▶ Extracting chapters from the NCERT PDFs…"
    ( cd "$RAG" && "$PY" extract_book.py )
    echo "▶ Building the embedding index (this is rate-limited; be patient)…"
    ( cd "$RAG" && "$PY" build_index.py )
    echo "✓ Index built."
    ;;

  start)
    ensure_setup; check_keys
    echo "▶ Build Your Own Tutor is starting…"
    echo "   Open  http://127.0.0.1:$PORT  in your browser.  (Ctrl+C to stop)"
    cd "$APP"
    exec "$PY" -m uvicorn server:app --host 127.0.0.1 --port "$PORT" --reload
    ;;

  share)
    ensure_setup; check_keys
    cd "$APP"
    exec ./share.sh
    ;;

  *)
    echo "Usage: ./run.sh [start|setup|build|share]"
    echo "  start  (default)  run the app locally at http://127.0.0.1:$PORT"
    echo "  setup             install dependencies only"
    echo "  build             rebuild the search index from the PDFs"
    echo "  share             run the app and open a public link"
    exit 1
    ;;
esac
