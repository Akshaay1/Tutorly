#!/usr/bin/env bash
# Build Your Own Tutor — one-command public share.
#
# Starts the local server (if it isn't already up) and opens a Cloudflare
# Tunnel, printing a public https://<random>.trycloudflare.com link that anyone
# can open while this stays running. Press Ctrl+C to stop sharing.
#
# Usage:  ./share.sh        (run from the app/ directory)

set -euo pipefail
cd "$(dirname "$0")"                       # -> app/
PY="../rag/.venv/bin/python"
PORT=8000

# 1. make sure cloudflared exists
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "❌ cloudflared not found. Install it first:  brew install cloudflared"
  exit 1
fi

# 2. start the server if it isn't already responding
if curl -s -o /dev/null "http://127.0.0.1:${PORT}/"; then
  echo "✓ Server already running on :${PORT}"
else
  echo "▶ Starting server on :${PORT} ..."
  "$PY" -m uvicorn server:app --host 127.0.0.1 --port "${PORT}" >/tmp/tutor_server.log 2>&1 &
  # wait for it to come up
  for _ in $(seq 1 20); do
    sleep 0.5
    curl -s -o /dev/null "http://127.0.0.1:${PORT}/" && break
  done
  echo "✓ Server is up"
fi

# 3. open the public tunnel (this blocks; Ctrl+C ends the share)
echo "🌐 Opening public link (keep this window open)…"
echo "   Your shareable URL will print below as  https://<something>.trycloudflare.com"
echo
exec cloudflared tunnel --url "http://localhost:${PORT}"
