// ---------- Build Your Own Tutor — single-page app ----------
const app = document.getElementById("app");
const topbar = document.getElementById("topbar");
const crumbsEl = document.getElementById("crumbs");
const whoEl = document.getElementById("who");

const state = {
  user: null,
  klass: null,
  subject: null,
  chapter: null,
  sources: { book: false, teacher: false, youtube: false },
  videoUrl: "",
  videoId: null,
  data: null,        // curriculum
  indexed: [],       // chapters with textbook chunks
  withTeacher: [],   // chapters with teacher-notes chunks
};

const SUBJECT_EMOJI = {
  Science: "🧪", Physics: "⚛️", Chemistry: "🧫", Biology: "🧬",
  Mathematics: "📐", "Social Science": "🌍", English: "📖",
  Hindi: "🪷", Sanskrit: "🕉️", "Computer Science": "💻",
};
const subjEmoji = (s) => SUBJECT_EMOJI[s] || "📚";
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// ---------- boot ----------
async function boot() {
  const res = await fetch("/api/curriculum");
  const json = await res.json();
  state.data = json.curriculum;
  state.indexed = Array.isArray(json.indexed) ? json.indexed : [];
  state.withTeacher = Array.isArray(json.withTeacher) ? json.withTeacher : [];
  renderLanding();
}

document.getElementById("homeBtn").onclick = () => (state.user ? renderClasses() : renderLanding());

function inList(list, k, s, ch) {
  return list.some((x) => x.class === k && x.subject === s && x.chapter === ch);
}
const isIndexed = (k, s, ch) => inList(state.indexed, k, s, ch);
const hasTeacher = (k, s, ch) => inList(state.withTeacher, k, s, ch);

// ---------- chrome (topbar + breadcrumbs) ----------
function chrome(show) {
  topbar.hidden = !show;
  if (!show) return;
  const parts = [];
  if (state.klass) parts.push({ label: `Class ${state.klass}`, go: renderSubjects });
  if (state.subject) parts.push({ label: state.subject, go: renderChapters });
  if (state.chapter) parts.push({ label: state.chapter, go: renderSources });
  crumbsEl.innerHTML = parts
    .map((p, i) => {
      const active = i === parts.length - 1 ? "active" : "";
      return `<span class="crumb ${active}" data-i="${i}">${esc(p.label)}</span>` +
        (i < parts.length - 1 ? '<span class="sep">/</span>' : "");
    })
    .join("");
  [...crumbsEl.querySelectorAll(".crumb")].forEach((el) => {
    el.style.cursor = "pointer";
    el.onclick = () => parts[+el.dataset.i].go();
  });
  if (state.user) {
    whoEl.innerHTML = `<span>${esc(state.user)}</span><span class="avatar">${(state.user[0] || "U").toUpperCase()}</span>`;
  }
}

const swap = (html) => (app.innerHTML = html);

// ---------- 1. landing ----------
function renderLanding() {
  chrome(false);
  swap(`
    <section class="view hero">
      <div>
        <span class="eyebrow"><span class="pulse"></span> Grounded in your real syllabus</span>
        <h1 class="display">Build Your<br/><span class="grad">Own Tutor.</span></h1>
        <p class="lede">Pick your class, subject and chapter. Choose the exact sources you trust —
          your NCERT book, your teacher's class videos — and get a tutor that answers only from them.</p>
        <div class="action-bar">
          <button class="btn btn-primary" id="startBtn">Get started <span class="arrow">→</span></button>
          <span class="muted-inline">No sign-up needed to try</span>
        </div>
        <div class="info-card">
          <span class="ic">🛡️</span>
          <div>
            <h4>Why this is different</h4>
            <p>Today's AI tools answer from a <span class="hl">randomized internet</span> — sometimes right,
              often confidently wrong. Here, every answer comes from <span class="hl">credible sources you
              chose yourself</span> and is cited back to the exact NCERT page, your teacher's class, or the
              video you added. No syllabus, no answer — never a guess.</p>
          </div>
        </div>
        <div class="feature-row">
          <span class="chip">📚 NCERT-aligned</span>
          <span class="chip">🎯 Cited to the page</span>
          <span class="chip">🎬 Add any YouTube lecture</span>
          <span class="chip">🚫 Refuses to hallucinate</span>
        </div>
      </div>
    </section>
  `);
  document.getElementById("startBtn").onclick = renderLogin;
}

// ---------- 2. login (dummy) ----------
function renderLogin() {
  chrome(false);
  swap(`
    <section class="view">
      <div class="auth-wrap">
        <h1 class="display" style="font-size:clamp(30px,5vw,44px);text-align:center">Welcome 👋</h1>
        <p class="section-sub" style="text-align:center;margin:0 auto 28px">Sign in to build your tutor</p>
        <div class="auth-card">
          <div class="field"><label>Name</label><input id="name" placeholder="e.g. Akshay" autocomplete="off" /></div>
          <div class="field"><label>Password</label><input id="pass" type="password" placeholder="anything works for now" /></div>
          <button class="btn btn-primary" id="loginBtn">Continue <span class="arrow">→</span></button>
          <p class="dummy-note">🔒 Demo login — SSO &amp; real auth come later. Nothing is stored.</p>
        </div>
        <div style="text-align:center;margin-top:18px"><button class="back-link" id="back">← Back</button></div>
      </div>
    </section>
  `);
  const nameEl = document.getElementById("name");
  nameEl.focus();
  const go = () => { state.user = nameEl.value.trim() || "Student"; renderClasses(); };
  document.getElementById("loginBtn").onclick = go;
  document.getElementById("pass").addEventListener("keydown", (e) => e.key === "Enter" && go());
  document.getElementById("back").onclick = renderLanding;
}

// ---------- 3. classes ----------
function renderClasses() {
  state.klass = state.subject = state.chapter = null;
  chrome(true);
  const classes = Object.keys(state.data).sort((a, b) => +a - +b);
  swap(`
    <section class="view">
      <span class="eyebrow">Step 1 of 4</span>
      <h2 class="section-title">Choose your class</h2>
      <p class="section-sub">CBSE classes 6 through 12.</p>
      <div class="grid cols-classes">
        ${classes.map((c) => `
          <button class="card class-tile" data-c="${c}">
            <span class="cnum">${c}</span><span class="clabel">Class</span>
          </button>`).join("")}
      </div>
    </section>
  `);
  [...app.querySelectorAll(".card")].forEach((el) => (el.onclick = () => { state.klass = el.dataset.c; renderSubjects(); }));
}

// ---------- 4. subjects ----------
function renderSubjects() {
  state.subject = state.chapter = null;
  chrome(true);
  const subjects = Object.keys(state.data[state.klass]);
  swap(`
    <section class="view">
      <button class="back-link" id="back">← Class ${state.klass}</button>
      <span class="eyebrow">Step 2 of 4</span>
      <h2 class="section-title">Pick a subject</h2>
      <p class="section-sub">Class ${state.klass} · CBSE syllabus.</p>
      <div class="grid cols-cards">
        ${subjects.map((s) => {
          const liveCount = state.data[state.klass][s].filter((ch) => isIndexed(state.klass, s, ch)).length;
          const n = state.data[state.klass][s].length;
          return `
          <button class="card" data-s="${esc(s)}">
            <div class="k-index"><span class="k-emoji">${subjEmoji(s)}</span>${liveCount ? `<span style="color:#4ade80">● ${liveCount} live</span>` : ""}</div>
            <div class="k-title">${esc(s)}</div>
            <div class="k-meta">${n} chapters</div>
          </button>`;
        }).join("")}
      </div>
    </section>
  `);
  document.getElementById("back").onclick = renderClasses;
  [...app.querySelectorAll(".card")].forEach((el) => (el.onclick = () => { state.subject = el.dataset.s; renderChapters(); }));
}

// ---------- 5. chapters ----------
function renderChapters() {
  state.chapter = null;
  chrome(true);
  const chapters = state.data[state.klass][state.subject];
  swap(`
    <section class="view">
      <button class="back-link" id="back">← ${esc(state.subject)}</button>
      <span class="eyebrow">Step 3 of 4</span>
      <h2 class="section-title">Open a chapter</h2>
      <p class="section-sub">NCERT chapters for Class ${state.klass} ${esc(state.subject)}.</p>
      <div class="grid cols-cards">
        ${chapters.map((ch, i) => {
          const live = isIndexed(state.klass, state.subject, ch);
          return `
          <button class="card" data-ch="${esc(ch)}">
            <div class="k-index"><span>Chapter ${i + 1}</span>${live ? '<span style="color:#4ade80">● live</span>' : ""}</div>
            <div class="k-title">${esc(ch)}</div>
            <div class="k-meta">${live ? "Textbook indexed · ready" : "Add a video to study this"}</div>
          </button>`;
        }).join("")}
      </div>
    </section>
  `);
  document.getElementById("back").onclick = renderSubjects;
  [...app.querySelectorAll(".card")].forEach((el) => (el.onclick = () => { state.chapter = el.dataset.ch; renderSources(); }));
}

// ---------- 6. sources ----------
function renderSources() {
  chrome(true);
  state.sources = { book: false, teacher: false, youtube: false };
  state.videoUrl = "";
  state.videoId = null;
  const live = isIndexed(state.klass, state.subject, state.chapter);
  const teacher = hasTeacher(state.klass, state.subject, state.chapter);

  swap(`
    <section class="view">
      <button class="back-link" id="back">← ${esc(state.subject)}</button>
      <span class="eyebrow">Step 4 of 4</span>
      <h2 class="section-title">Choose your sources</h2>
      <p class="section-sub">Your tutor answers <b>only</b> from what you switch on — ${esc(state.chapter)}.</p>

      <div class="source-grid">
        <div class="source ${live ? "" : "locked"}" data-src="book">
          <span class="s-ic">📕</span>
          <div><h4>NCERT Textbook</h4><p>${live ? "Official chapter text, cited to the exact page." : "Not indexed for this chapter yet."}</p></div>
          ${live ? '<span class="tick">✓</span>' : '<span class="soon">SOON</span>'}
        </div>

        ${teacher ? `
        <div class="source" data-src="teacher">
          <span class="s-ic">📝</span>
          <div><h4>Class Notes</h4><p>Your teacher's pre-loaded class video notes.</p></div>
          <span class="tick">✓</span>
        </div>` : ""}

        <div class="source" data-src="youtube">
          <span class="s-ic">🎬</span>
          <div>
            <h4>YouTube Video</h4>
            <p>Paste a lecture link — I'll transcribe &amp; learn it live.</p>
            <div class="extra"><input id="videoUrl" placeholder="https://youtube.com/watch?v=…" /></div>
          </div>
          <span class="tick">✓</span>
        </div>

        <div class="source locked" data-src="audio">
          <span class="s-ic">🎙️</span>
          <div><h4>Your Audio File</h4><p>Upload a recording to transcribe &amp; index.</p></div>
          <span class="soon">SOON</span>
        </div>
      </div>

      <div class="action-bar">
        <button class="btn btn-primary" id="enter" disabled>Meet your tutor <span class="arrow">→</span></button>
        <span class="muted-inline" id="srcCount">Select at least one source</span>
      </div>
    </section>
  `);
  document.getElementById("back").onclick = renderChapters;

  const enterBtn = document.getElementById("enter");
  const count = document.getElementById("srcCount");
  const refresh = () => {
    const n = Object.values(state.sources).filter(Boolean).length;
    enterBtn.disabled = n === 0;
    if (n === 0) count.textContent = "Select at least one source";
    else count.textContent = `${n} source${n > 1 ? "s" : ""} selected`;
  };

  [...app.querySelectorAll(".source[data-src]")].forEach((el) => {
    if (el.classList.contains("locked")) { el.onclick = () => bump(el); return; }
    el.onclick = (e) => {
      if (e.target.tagName === "INPUT") return;
      const key = el.dataset.src;
      state.sources[key] = !state.sources[key];
      el.classList.toggle("on", state.sources[key]);
      refresh();
    };
  });
  const v = document.getElementById("videoUrl");
  if (v) v.oninput = () => (state.videoUrl = v.value.trim());

  enterBtn.onclick = async () => {
    // If YouTube is selected with a link, transcribe + embed it live before chat.
    if (state.sources.youtube && state.videoUrl) {
      enterBtn.disabled = true;
      count.innerHTML = '<span class="typing"><span></span><span></span><span></span></span> Transcribing &amp; embedding your video…';
      try {
        const res = await fetch("/api/youtube", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: state.videoUrl }),
        });
        const data = await res.json();
        if (!data.ok) { count.textContent = "⚠️ " + data.error; enterBtn.disabled = false; return; }
        state.videoId = data.video_id;
        count.textContent = `✓ Video learned (${data.n_chunks} segments)`;
      } catch (err) {
        count.textContent = "⚠️ Couldn't reach the server.";
        enterBtn.disabled = false;
        return;
      }
    } else if (state.sources.youtube && !state.videoUrl) {
      count.textContent = "Paste a YouTube link, or unselect that source.";
      return;
    }
    renderChat();
  };
}

function bump(el) {
  el.animate(
    [{ transform: "translateX(0)" }, { transform: "translateX(-6px)" }, { transform: "translateX(6px)" }, { transform: "translateX(0)" }],
    { duration: 250 }
  );
}

// ---------- 7. chat ----------
function renderChat() {
  chrome(true);
  const picked = Object.entries(state.sources).filter(([, v]) => v).map(([k]) => k);
  const pillNames = { book: "📕 NCERT", teacher: "📝 Class notes", youtube: "🎬 Your video" };
  const canAnswer = isIndexed(state.klass, state.subject, state.chapter) || state.videoId;

  swap(`
    <section class="view" style="padding-top:18px">
      <div class="chat-shell">
        <div class="chat-head">
          <button class="back-link" id="back" style="margin-bottom:14px">← Change sources</button>
          <div class="ch-title">${esc(state.chapter)}</div>
          <div class="ch-sub">
            <span>Class ${state.klass} · ${esc(state.subject)}</span>
            ${picked.map((p) => `<span class="src-pill">${pillNames[p] || p}</span>`).join("")}
          </div>
        </div>
        <div class="stream" id="stream"></div>
        <div class="composer">
          <div class="composer-inner">
            <textarea id="q" rows="1" placeholder="Ask anything from this chapter…"></textarea>
            <button class="send-btn" id="send">↑</button>
          </div>
          <p class="hint">Answers are grounded in your selected sources &amp; cited back to them.</p>
        </div>
      </div>
    </section>
  `);
  document.getElementById("back").onclick = renderSources;

  const stream = document.getElementById("stream");
  const q = document.getElementById("q");
  const send = document.getElementById("send");

  const greet = canAnswer
    ? `Hey ${esc(state.user)} 👋 I'm your tutor for <b>${esc(state.chapter)}</b>. I'll only answer from your selected sources and cite every point. Ask me anything from this chapter.`
    : `Hey ${esc(state.user)} 👋 You haven't given me any indexed material for <b>${esc(state.chapter)}</b> yet. Go back and either pick a chapter with the textbook indexed, or paste a YouTube lecture link so I can learn it.`;
  addBot(stream, greet, [], false, true);

  q.addEventListener("input", () => { q.style.height = "auto"; q.style.height = Math.min(q.scrollHeight, 140) + "px"; });
  q.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } });
  send.onclick = submit;

  async function submit() {
    const text = q.value.trim();
    if (!text) return;
    addUser(stream, text);
    q.value = ""; q.style.height = "auto";
    send.disabled = true;
    const typing = addTyping(stream);
    try {
      const res = await fetch("/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          klass: state.klass, subject: state.subject, chapter: state.chapter,
          sources: picked, question: text, video_id: state.videoId,
        }),
      });
      const data = await res.json();
      typing.remove();
      addBot(stream, data.answer, data.sources || [], !data.grounded);
    } catch (err) {
      typing.remove();
      addBot(stream, "Couldn't reach the tutor engine. Is the server running?", [], true);
    } finally {
      send.disabled = false; q.focus();
    }
  }
}

// ---------- chat bubble helpers ----------
const scrollDown = (s) => (s.scrollTop = s.scrollHeight);

function addUser(stream, text) {
  const el = document.createElement("div");
  el.className = "msg user";
  el.innerHTML = `<div class="av">🧑</div><div class="bubble">${esc(text)}</div>`;
  stream.appendChild(el); scrollDown(stream);
}

function addBot(stream, html, sources, warn, isHtml) {
  const el = document.createElement("div");
  el.className = "msg bot";
  const body = isHtml ? html : esc(html);
  const cites = (sources && sources.length)
    ? `<div class="cite-row">${sources.map((s) => `<span class="cite"><b>${esc(s.label)}</b> · match ${s.similarity}</span>`).join("")}</div>`
    : "";
  el.innerHTML = `<div class="av">✦</div><div class="bubble ${warn ? "warn" : ""}">${body}${cites}</div>`;
  stream.appendChild(el); scrollDown(stream);
}

function addTyping(stream) {
  const el = document.createElement("div");
  el.className = "msg bot";
  el.innerHTML = `<div class="av">✦</div><div class="bubble"><span class="typing"><span></span><span></span><span></span></span></div>`;
  stream.appendChild(el); scrollDown(stream);
  return el;
}

boot();
