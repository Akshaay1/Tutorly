# Deploying to a permanent website

This guide hosts the **NCERT textbook tutor** as an always-on public site on
[Render](https://render.com)'s free tier, straight from GitHub.

> **Read first — two honest caveats:**
> 1. **Live YouTube transcription won't work in the cloud.** YouTube blocks
>    requests from datacenter IPs. The NCERT chat works perfectly; for the
>    YouTube feature, run locally via `./run.sh share` (a tunnel from your Mac),
>    or add a residential proxy (see "Making YouTube work in the cloud" below).
> 2. **Free API tiers rate-limit under load.** A few simultaneous users can hit
>    Gemini/Groq 429s. For real traffic, move to paid API tiers.

The vector index is **committed to the repo**, so the host serves instantly and
never re-embeds (which would hit rate limits on the server).

---

## Step 1 — Push to GitHub

```bash
cd /Users/akshaay/Desktop/projectA
git init
git add .
git commit -m "Build Your Own Tutor"
```

Create an empty repo on github.com (no README/gitignore), then:

```bash
git remote add origin https://github.com/<you>/<repo>.git
git branch -M main
git push -u origin main
```

What gets pushed: the app code + the prebuilt index (`rag/index.npz`,
`rag/index_meta.json`). What's excluded (see `.gitignore`): your `.env` keys,
the source PDFs, the virtualenv, and caches.

## Step 2 — Create the Render service

1. Go to https://render.com → **New + → Blueprint**.
2. Connect your GitHub repo. Render reads `render.yaml` automatically and
   configures the build/start commands for you.
3. Click **Apply**.

## Step 3 — Add your API keys

In the Render dashboard → your service → **Environment**, add:

- `GEMINI_API_KEY` = your key
- `GROQ_API_KEY` = your key

Save — Render redeploys. In a couple of minutes you get a fixed public URL like
`https://build-your-own-tutor.onrender.com`.

> Free Render services sleep after ~15 min idle and take ~30 s to wake on the
> next visit. That's normal for the free plan.

---

## Updating the site later

```bash
git add .
git commit -m "your change"
git push
```

Render auto-deploys on every push to `main`.

If you re-index (e.g. added a new class), commit the updated index too:

```bash
./run.sh build          # regenerates rag/index.npz + rag/index_meta.json
git add rag/index.npz rag/index_meta.json
git commit -m "reindex" && git push
```

---

## Making YouTube work in the cloud (optional)

Add a residential proxy so YouTube sees a non-datacenter IP. With a
[Webshare](https://www.webshare.io) residential plan, set its credentials as env
vars and pass them in `rag/youtube_ingest.py`:

```python
from youtube_transcript_api.proxies import WebshareProxyConfig
api = YouTubeTranscriptApi(proxy_config=WebshareProxyConfig(
    proxy_username=os.environ["WEBSHARE_USER"],
    proxy_password=os.environ["WEBSHARE_PASS"],
))
```

---

## Alternative: keep it on your Mac

If you don't need always-on hosting, skip all of the above and just run:

```bash
./run.sh share
```

That gives a public link via Cloudflare Tunnel, and **YouTube keeps working**
(your Mac's home IP). See [`app/SHARE.md`](app/SHARE.md).
