// Sample sign-up details until the real sign-up steps are connected.
// The draft uses these to say who is writing and who the page is for.
const PROFILE = { author_name: "Sam", page_for: "Robert", relationship: "son" };

const MIC_LIMIT_SECONDS = 120;

let flow = null;        // the questions from GET /api/v1/flow
let state = load();     // everything the person has entered so far
let notice = "";        // a gentle message shown above the buttons
let busy = "";          // what we're waiting on: "draft", "rewrite" or "transcribe"
let recording = null;   // the microphone while someone is talking
let asking = "";        // the "tell us what to change" text on the draft screen

// Credit to the D2 team for keeping the session in the browser tab, which follows the sessionStorage recovery in d2-team/frontend/app.js.
// It survives a refresh, it is gone when the tab closes, and nothing is kept on the server.
// draft_before is the draft as it was just before the last AI rewrite, so the changes can be highlighted.
function blank() {
  return { step: "intro", path: "guide", draft: null, draft_before: null, self_draft: null,
    answers: { what_happened: "", what_next: "", help: [] } };
}

function load() {
  try { return JSON.parse(sessionStorage.getItem("first-post")) || blank(); } catch { return blank(); }
}

function save() {
  try { sessionStorage.setItem("first-post", JSON.stringify(state)); } catch { /* private windows can refuse, and that's fine */ }
}

// Builds an element without ever putting text through innerHTML, so nothing a person types can run as code.
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "class") el.className = value;
    else if (value === true) el.setAttribute(key, "");
    else if (value !== false && value != null) el.setAttribute(key, value);
  }
  for (const child of children.flat()) if (child != null && child !== false) el.append(child);
  return el;
}

async function api(path, options = {}) {
  let reply;
  try { reply = await fetch("/api/v1" + path, options); }
  catch { throw new Error("Couldn't reach the server. Check your connection and try again."); }
  const data = await reply.json().catch(() => ({}));
  if (reply.status >= 500) {
    // The server's own wording can mention setup details, which belong in the console and not in front of a person.
    console.warn("The server said:", data.detail);
    throw new Error(path === "/transcribe"
      ? "We couldn't turn that recording into words. You can try again, or type your answer instead."
      : "We couldn't reach the writing helper just now. Your words are safe here, so please try again in a moment.");
  }
  if (!reply.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.");
  return data;
}

const post = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const answersForApi = () => ({ ...state.answers, profile: PROFILE });

// Moving around

function go(step) {
  cancelRecording();
  notice = "";
  state.step = step;
  save();
  render();
  window.scrollTo(0, 0);
  document.querySelector("h1").focus();
}

function say(message) {
  notice = message;
  render();
}

function startOver() {
  if (!confirm("Start over? Your answers and draft will be cleared.")) return;
  state = blank();
  asking = "";
  go("intro");
}

function render() {
  const screen = state.step === "intro" ? introScreen()
    : state.step === "draft" ? draftScreen()
    : state.step === "write" ? selfWriteScreen()
    : questionScreen();
  document.getElementById("app").replaceChildren(screen);
}

// Pieces the screens share

const heading = text => h("h1", { tabindex: "-1" }, text);
const noticeBox = () => (notice ? h("p", { class: "notice", role: "status" }, notice) : null);
const primary = (label, onclick, disabled) => h("button", { type: "button", class: "primary", onclick, disabled }, label);
const links = (left, right) => h("div", { class: "links" },
  h("button", { type: "button", class: "link", onclick: left[1] }, left[0]),
  right ? h("button", { type: "button", class: "link", onclick: right[1] }, right[0]) : null);

// The steps in the berry panel on the right: the questions, then the draft.
// Someone writing it themselves has just the one step.
function sideSteps() {
  if (state.path === "blank") return [["write", "Write your post"]];
  return [...flow.questions.map(q => [q.id, q.step_label]), ["draft", "Review your draft"]];
}

// The "Step 2 of 4" line, counted the same way as the berry panel.
function stepOf(id) {
  const steps = sideSteps();
  return `Step ${steps.findIndex(([s]) => s === id) + 1} of ${steps.length}`;
}

// A finished step can be clicked to go back to it, and so can the draft once there is one.
function sideStep([id, label], i, here) {
  const current = i === here;
  const canGo = !current && busy === "" && !recording && (i < here || (id === "draft" && state.draft));
  const inner = [h("small", {}, "Step " + (i + 1)), h("b", {}, label)];
  return h("li", { class: i < here ? "done" : current ? "current" : "", "aria-current": current ? "step" : null },
    canGo ? h("button", { type: "button", class: "step-item", onclick: () => go(id) }, ...inner)
      : h("span", { class: "step-item" }, ...inner));
}

function wizard(...content) {
  const steps = sideSteps();
  const here = steps.findIndex(([id]) => id === state.step);
  const aiStep = state.path === "guide" && here >= 0;  // the questions and the draft
  return h("div", { class: "wizard" + (state.step === "draft" ? " wide" : "") },
    h("section", { class: "wizard-main" },
      h("img", { class: "mobile-logo", src: "assets/logo-horizontal.svg", alt: "CaringBridge" }),
      h("div", { class: "step-box" }, ...content),
      aiStep ? h("p", { class: "ai-disclaimer" }, h("span", { "aria-hidden": "true" }, "✦"), flow.ai_disclaimer) : null),
    h("aside", { class: "wizard-side" },
      h("img", { class: "side-logo", src: "assets/logo-stacked-white.svg", alt: "CaringBridge" }),
      h("nav", { class: "side-steps", "aria-label": "Your steps" },
        h("ol", { class: "steps" }, steps.map((step, i) => sideStep(step, i, here))))));
}

// Nothing is published from this prototype, so the last button on either path ends here.
const finish = () => say("Your post is ready. Publishing isn't connected in this prototype yet.");

// The first screen

function introScreen() {
  const card = (value, title, text) => h("label", { class: "card" + (state.path === value ? " selected" : "") },
    h("input", { type: "radio", name: "path", checked: state.path === value, onchange: () => { state.path = value; notice = ""; save(); render(); } }),
    h("span", {}, h("strong", {}, title), h("span", { class: "card-text" }, text)));

  const next = () => {
    if (state.path === "blank") return go("write");
    go(flow.questions[0].id);
  };
  return wizard(
    heading("Write Your First Post"),
    h("p", { class: "lead intro-lead" }, "You don't need the perfect words to begin. Just start with what's on your mind. "
      + "Our writing guide asks a few gentle questions and shapes your answers into a first draft that still sounds like you. "
      + "You can change anything along the way, and nothing is shared until you're ready."),
    card("guide", "Help Me Find the Words (Recommended)", "Answer a few quick questions, one at a time. Type or talk, whatever feels right. We'll take it from there, together."),
    card("blank", "I'd Like to Write It Myself", "Start with a blank post. We'll offer ideas at your request if you change your mind."),
    noticeBox(),
    primary("Next Step", next),
    links(["Previous", () => say("The earlier steps aren't part of this prototype yet.")],
      ["Skip for now", () => say("Skipping the writing step isn't built yet. Could you try the first option?")]));
}

// Writing it yourself

function selfWriteScreen() {
  if (!state.self_draft) state.self_draft = { title: flow.default_title, post: "" };
  const self = state.self_draft;
  const titleInput = h("input", { class: "text", id: "self-title", type: "text",
    placeholder: "Give your post a title",
    value: self.title,
    oninput: e => { self.title = e.target.value; save(); } });
  const postArea = h("textarea", { class: "text post", id: "self-post",
    placeholder: "Start with whatever comes to mind.",
    oninput: e => { self.post = e.target.value; save(); } }, self.post);
  const fields = h("div", { class: "write-screen" },
    h("label", { for: "self-title" }, "Title"), titleInput,
    h("label", { for: "self-post" }, "Post"), postArea);
  return wizard(
    h("p", { class: "eyebrow" }, "Your post"),
    heading("Write Your Post"),
    h("p", { class: "lead" }, "It's your story — write it your way."),
    fields,
    noticeBox(),
    primary("I'm Happy With This", finish),
    links(["Previous", () => go("intro")], ["Start over", startOver]));
}

// The questions

function questionScreen() {
  const index = flow.questions.findIndex(q => q.id === state.step);
  const q = flow.questions[index];
  const last = index === flow.questions.length - 1;
  const before = index === 0 ? "intro" : flow.questions[index - 1].id;
  const onward = () => (last ? makeDraft() : go(flow.questions[index + 1].id));
  const skip = () => {
    state.answers[q.id] = Array.isArray(state.answers[q.id]) ? [] : "";
    onward();
  };

  const body = q.type === "voice" ? voiceBox(q) : checkboxes(q);
  return wizard(
    h("p", { class: "eyebrow" }, stepOf(q.id),
      q.type === "voice" ? h("span", { class: "voice-tag" }, micIcon(), "Type or talk") : null),
    heading(q.title),
    q.prompt ? h("p", { class: "lead" }, q.prompt) : null,
    body,
    noticeBox(),
    primary(busy === "draft" ? "Writing your first draft..." : last ? "See What We Heard" : "Continue", onward, busy !== ""),
    links(["Previous", () => go(before)], ["Skip for now", skip]));
}

// A small microphone drawing. SVG needs its own namespace, so it can't go through h().
function micIcon() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  for (const [k, v] of Object.entries({ viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "2",
    "stroke-linecap": "round", "stroke-linejoin": "round", class: "mic-icon", "aria-hidden": "true" })) svg.setAttribute(k, v);
  const shapes = [["rect", { x: 9, y: 2, width: 6, height: 12, rx: 3 }], ["path", { d: "M5 10v1a7 7 0 0 0 14 0v-1" }], ["path", { d: "M12 18v4M8 22h8" }]];
  for (const [tag, attrs] of shapes) {
    const shape = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) shape.setAttribute(k, v);
    svg.append(shape);
  }
  return svg;
}

function voiceBox(q) {
  const box = h("textarea", { class: "text", "aria-label": q.title, placeholder: "Type here, or tap the microphone and talk.",
    oninput: e => { state.answers[q.id] = e.target.value; save(); } }, state.answers[q.id]);
  const talking = recording && recording.id === q.id;
  const label = busy === "transcribe" ? "Writing down what you said..." : talking ? "Listening... tap when you're done" : "Tap to talk instead of typing";
  const mic = h("button", { type: "button", class: "mic" + (talking ? " listening" : ""), disabled: busy !== "",
    onclick: () => (talking ? recording.recorder.stop() : startRecording(q)) }, h("span", { class: "mic-badge" }, micIcon()), label);
  return h("div", {}, box, mic);
}

// The help options are a plain checklist, one per line, kept in menu order.
// Real checkboxes keep their own state, so nothing redraws and the keyboard focus stays put.
function checkboxes(q) {
  const ids = q.options.map(o => o.id);
  let current = [...state.answers[q.id]];
  return h("fieldset", { class: "checklist" },
    h("legend", { class: "sr-only" }, q.title),
    q.options.map(option => h("label", { class: "check-row" },
      h("input", { type: "checkbox", checked: current.includes(option.id), onchange: e => {
        current = e.target.checked ? [...current, option.id] : current.filter(id => id !== option.id);
        state.answers[q.id] = ids.filter(id => current.includes(id));
        save();
      } }),
      h("span", {}, option.label))));
}

// Talking

// Credit to the D2 team for the list of recording formats to try and the plain-language microphone messages, which come from d2-team/frontend/audio.js.
const FORMATS = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
const MIC_PROBLEMS = {
  NotAllowedError: "The microphone is blocked. Allow it for this site in your browser, then try again.",
  NotFoundError: "No microphone was found. Plug one in, or type your answer instead.",
  NotReadableError: "The microphone couldn't be opened. Another app might be using it.",
};

async function startRecording(q) {
  if (!navigator.mediaDevices || !window.MediaRecorder) return say("Talking isn't available in this browser, but you can type your answer.");
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const type = FORMATS.find(format => MediaRecorder.isTypeSupported(format));
    const recorder = new MediaRecorder(stream, type ? { mimeType: type } : {});
    const chunks = [];
    recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
    recorder.onstop = () => finishRecording(q, new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
    recorder.start();
    recording = { id: q.id, recorder, stream, timer: setTimeout(() => recorder.stop(), MIC_LIMIT_SECONDS * 1000) };
    notice = "";
    render();
  } catch (err) {
    say(MIC_PROBLEMS[err.name] || "Couldn't start the microphone. You can type your answer instead.");
  }
}

function releaseMicrophone() {
  clearTimeout(recording.timer);
  recording.stream.getTracks().forEach(track => track.stop());
  recording = null;
}

function cancelRecording() {
  if (!recording) return;
  recording.recorder.onstop = null;
  if (recording.recorder.state !== "inactive") recording.recorder.stop();
  releaseMicrophone();
}

async function finishRecording(q, blob) {
  releaseMicrophone();
  busy = "transcribe";
  render();
  try {
    const form = new FormData();
    form.append("audio", blob, "answer." + (blob.type.includes("mp4") ? "mp4" : blob.type.includes("ogg") ? "ogg" : "webm"));
    const result = await api("/transcribe", { method: "POST", body: form });
    const before = state.answers[q.id].trim();
    state.answers[q.id] = (before ? before + " " : "") + result.text;
    save();
  } catch (err) {
    notice = err.message;
  }
  busy = "";
  render();
}

// The draft

async function makeDraft() {
  busy = "draft";
  notice = "";
  render();
  try {
    state.draft = await post("/draft", answersForApi());
    state.draft_before = null;  // a fresh draft has nothing to compare against
    go("draft");
  } catch (err) {
    notice = err.message;
  }
  busy = "";
  render();
}

// One call carries what the author asked for, along with the draft as they have edited it.
// The draft as it was just before is kept, so the screen can highlight what the AI changed.
async function rewrite() {
  if (!asking.trim()) return;
  if (!state.draft.post.trim()) return say("There's nothing in the post to rewrite yet. Type something, or go back to your answers.");
  busy = "rewrite";
  notice = "";
  render();
  try {
    const before = { title: state.draft.title, post: state.draft.post };
    const result = await post("/regenerate", { answers: answersForApi(), draft: before, adjustments: { extra: asking } });
    const same = result.post.trim() === before.post.trim();
    state.draft = { ...result, title: result.title || before.title };  // a rewrite never swaps the title for nothing
    state.draft_before = before;
    asking = "";
    save();
    if (same) notice = "That came back the same as before. Try a bigger change, or tell us in your own words what to change.";
  } catch (err) {
    notice = err.message;
  }
  busy = "";
  render();
}

// Which words in `after` are new compared with `before`, and which words of `before` are gone.
// `pieces` is `after` in order, each piece marked changed or not; `removed` is each run of words taken out.
// It's a word-level longest-common-subsequence, which is plenty fast for a post.
function wordChanges(before, after) {
  const pieces = after.match(/\S+|\s+/g) || [];
  const words = pieces.filter(p => /\S/.test(p));
  const old = (before.match(/\S+/g) || []);
  const n = words.length, m = old.length;
  if (n * m > 4000000) return { pieces: pieces.map(text => ({ text, changed: false })), removed: [] };  // too long to compare

  // lcs[i][j] is the longest run shared by words[i..] and old[j..], kept in one flat array.
  const lcs = new Uint32Array((n + 1) * (m + 1));
  const at = (i, j) => i * (m + 1) + j;
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[at(i, j)] = words[i] === old[j] ? lcs[at(i + 1, j + 1)] + 1 : Math.max(lcs[at(i + 1, j)], lcs[at(i, j + 1)]);
    }
  }
  const kept = new Array(n).fill(false);
  const oldKept = new Array(m).fill(false);
  for (let i = 0, j = 0; i < n && j < m;) {
    if (words[i] === old[j]) { kept[i] = true; oldKept[j] = true; i++; j++; }
    else if (lcs[at(i + 1, j)] >= lcs[at(i, j + 1)]) i++;
    else j++;
  }

  // Spaces between two changed words are part of the change, so the highlight reads as one stretch.
  let w = 0;
  const marked = pieces.map(text => /\S/.test(text) ? { text, changed: !kept[w++] } : { text, changed: false, space: true });
  marked.forEach((piece, i) => {
    if (piece.space && !piece.text.includes("\n") && marked[i - 1] && marked[i - 1].changed && marked[i + 1] && marked[i + 1].changed) piece.changed = true;
  });

  const removed = [];
  let run = [];
  old.forEach((word, j) => {
    if (!oldKept[j]) run.push(word);
    else if (run.length) { removed.push(run.join(" ")); run = []; }
  });
  if (run.length) removed.push(run.join(" "));
  return { pieces: marked, removed };
}

// A removed stretch is shown in full unless it is long, so a dropped paragraph doesn't fill the screen.
const REMOVED_WORDS_SHOWN = 30;
const REMOVED_MIN_WORDS = 3;
function shortened(text) {
  const words = text.split(" ");
  if (words.length <= REMOVED_WORDS_SHOWN) return text;
  return words.slice(0, REMOVED_WORDS_SHOWN).join(" ") + ` … (${words.length - REMOVED_WORDS_SHOWN} more words)`;
}

// The highlight sits behind a see-through textarea, lined up word for word, so the post stays editable.
// Words that were taken out can't sit in the post itself, so they are listed under it, struck through.
function paintChanges(backdrop, removedBox, text) {
  const before = state.draft_before;
  const { pieces, removed } = before ? wordChanges(before.post, text) : { pieces: [{ text, changed: false }], removed: [] };
  backdrop.replaceChildren(...pieces.map(p => (p.changed ? h("mark", {}, p.text) : p.text)), "\n");
  // A word or two swapped out already shows as a highlight, so only longer stretches are listed.
  const shown = removed.filter(r => r.split(" ").length >= REMOVED_MIN_WORDS);
  removedBox.hidden = shown.length === 0;
  removedBox.replaceChildren(h("p", { class: "removed-title" }, "Taken out"),
    h("ul", {}, shown.map(r => h("li", {}, h("del", {}, shortened(r))))));
}

// The post box grows to fit its text, so it never scrolls and the highlight never drifts.
function growPost() {
  const box = document.getElementById("post");
  if (!box) return;
  box.style.height = "auto";
  box.style.height = box.scrollHeight + "px";
}
window.addEventListener("resize", growPost);

function clearHighlights() {
  state.draft_before = null;
  save();
  render();
}

function draftScreen() {
  const draft = state.draft;
  const before = state.draft_before;
  const titleChanged = () => Boolean(before) && before.title !== draft.title;

  const title = h("input", { class: "text" + (titleChanged() ? " changed" : ""), id: "title", type: "text", value: draft.title,
    oninput: e => { draft.title = e.target.value; e.target.classList.toggle("changed", titleChanged()); save(); } });
  const backdrop = h("div", { class: "post-backdrop", "aria-hidden": "true" });
  const removedBox = h("div", { class: "removed" });
  const text = h("textarea", { class: "text post", id: "post",
    oninput: e => { draft.post = e.target.value; paintChanges(backdrop, removedBox, draft.post); growPost(); save(); } }, draft.post);
  paintChanges(backdrop, removedBox, draft.post);

  const askBox = h("textarea", { class: "text", id: "ask-text", placeholder: "e.g., make it shorter, or add a thank you to the nurses",
    oninput: e => { asking = e.target.value; askButton.disabled = busy !== "" || !asking.trim(); } }, asking);
  const askButton = h("button", { type: "button", class: "secondary", onclick: rewrite, disabled: busy !== "" || !asking.trim() },
    busy === "rewrite" ? "Working on it..." : "Make these changes");

  const screen = wizard(h("div", { class: "draft" },
    h("p", { class: "eyebrow" }, stepOf("draft") + " \u00b7 Your draft"),
    heading("Here's a First Draft, in Your Words"),
    h("p", { class: "banner" }, "We kept your words and smoothed out the rough spots. Change anything you like."),
    h("label", { for: "title" }, "Title"), title,
    h("label", { for: "post" }, "Post"),
    h("div", { class: "post-wrap" }, backdrop, text),
    removedBox,
    before ? h("p", { class: "changes-note" }, h("mark", {}, "Highlighted"), " words are new, and anything longer we took out is listed above. ",
      h("button", { type: "button", class: "link", onclick: clearHighlights }, "Hide highlights")) : null,
    draft.privacy_flags.length ? h("p", { class: "notice" }, "Heads up, this looks like contact details: " + draft.privacy_flags.map(f => f.text).join(", ") + ". You decide what stays in.") : null,
    h("div", { class: "ask" },
      h("label", { for: "ask-text" }, "Want us to change anything?"),
      h("p", { class: "fine" }, "Tell us in your own words. Nothing changes until you ask, and you can still edit by hand."),
      askBox, askButton),
    noticeBox(),
    primary("I'm Happy With This", finish),
    links(["Back to answers", () => go(flow.questions[0].id)], ["Start over", startOver])));
  queueMicrotask(growPost);  // sizes the post box once it is on the page
  return screen;
}

async function start() {
  try { flow = await api("/flow"); }
  catch (err) { document.getElementById("app").textContent = err.message; return; }
  const known = ["intro", "draft", "write", ...flow.questions.map(q => q.id)];
  if (!known.includes(state.step) || (state.step === "draft" && !state.draft)) state.step = "intro";
  // A tab opened before the questions changed may still hold answers or options that no longer exist.
  const helpIds = (flow.questions.find(q => q.id === "help") || { options: [] }).options.map(o => o.id);
  state.answers = { what_happened: state.answers.what_happened || "", what_next: state.answers.what_next || "",
    help: (state.answers.help || []).filter(id => helpIds.includes(id)) };
  render();
}

start();
