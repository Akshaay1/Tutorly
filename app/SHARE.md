# Sharing your tutor with a public link

This uses a **Cloudflare Tunnel** to expose the app running on your Mac as a
public `https://…trycloudflare.com` link — no GitHub, no cloud account, no
deploy. Anyone with the link can use it while your Mac and the tunnel stay on.

> **Do I need to push code to Git?** No. Git/GitHub is only for permanent cloud
> hosting (e.g. Render). The tunnel shares the server already running locally.

---

## One-time setup

Install the tunnel tool (only needed once):

```bash
brew install cloudflared
```

---

## Share it (every time)

From the `app/` folder:

```bash
cd /Users/akshaay/Desktop/projectA/app
./share.sh
```

The script will:
1. Start the local server if it isn't already running.
2. Open a Cloudflare Tunnel.
3. Print your public link, e.g.:

```
https://brave-tiger-words.trycloudflare.com
```

**Copy that link and send it to anyone.** Keep the terminal window open — the
link works only while `share.sh` is running.

**To stop sharing:** press `Ctrl+C` in that terminal. The link dies immediately.

---

## What works over the shared link

| Feature | Works? | Why |
|---|---|---|
| Browse classes / subjects / chapters | ✅ | served from your Mac |
| Class 9 Science chat (NCERT, cited) | ✅ | uses the local index |
| **Live YouTube transcription** | ✅ | runs on your Mac's home IP, which YouTube allows |

> Hosting this on a cloud server instead would **break the YouTube feature**,
> because YouTube blocks transcript requests from datacenter IPs. Running it off
> your Mac via the tunnel is exactly what keeps YouTube working.

---

## Good to know / limitations

- **Your Mac must stay awake and online.** Close the lid or quit the terminal and
  the link stops working.
- **The URL changes** each time you run `share.sh` (these quick tunnels are
  temporary). For a fixed URL you'd need a Cloudflare account + named tunnel.
- **API rate limits still apply.** You're on the free Gemini (100 embeds/min) and
  Groq tiers — a few simultaneous users may see occasional "rate limit" messages.
- **Your API keys stay on your Mac** (in `rag/.env`) and are never exposed by the
  link — visitors only reach the web app, not your files.

---

## Manual version (without the script)

If you'd rather run the two pieces yourself:

```bash
# terminal 1 — the server
cd /Users/akshaay/Desktop/projectA/app
../rag/.venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8000

# terminal 2 — the public tunnel
cloudflared tunnel --url http://localhost:8000
```
