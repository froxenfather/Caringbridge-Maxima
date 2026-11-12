// Sample sign-up details until the real sign-up steps are connected.
// The draft uses these to say who is writing and who the page is for.
const PROFILE = { author_name: "Sam", page_for: "Robert", relationship: "son" };

const MIC_LIMIT_SECONDS = 120;
const TWEAKS_START = () => ({ length: 3, tone: 3, wording: 3, extra: "" });

let flow = null;        // the questions and sliders from GET /api/v1/flow
let state = load();     // everything the person has entered so far
let notice = "";        // a gentle message shown above the buttons
let busy = "";          // what we're waiting on: "draft", "rewrite" or "transcribe"
let recording = null;   // the microphone while someone is talking
let tweaks = TWEAKS_START();  // the slider positions and the "tell us what to change" text
let photoURL = null;          // blob URL for the photo preview; lives in memory only, gone on refresh

// Credit to the D2 team for keeping the session in the browser tab, which follows the sessionStorage recovery in d2-team/frontend/app.js.
// It survives a refresh, it is gone when the tab closes, and nothing is kept on the server.
function blank() {
  return { step: "intro", path: "guide", draft: null, self_draft: { title: "", post: "" }, privacy: "",
    answers: { what_happened: "", what_next: "", help: [], help_other: "", update_frequency: "", reach_out: [] } };
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
  if (photoURL) { URL.revokeObjectURL(photoURL); photoURL = null; }
  state = blank();
  tweaks = TWEAKS_START();
  go("intro");
}

function render() {
  const screen = state.step === "intro" ? introScreen()
    : state.step === "draft" ? draftScreen()
    : state.step === "write" ? selfWriteScreen()
    : state.step === "photo" ? photoScreen()
    : state.step === "privacy" ? privacyScreen()
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

const SIDE_STEPS = [
  ["Create a new CaringBridge", "Who the CaringBridge is for"],
  ["Write your first post", "Share an update with family & friends"],
  ["Upload a photo", "Personalize by adding a photo"],
  ["Privacy settings", "Decide who can interact with your CaringBridge"],
];

function currentSideStep() {
  if (state.step === "photo") return 2;
  if (state.step === "privacy") return 3;
  return 1;
}

function wizard(...content) {
  const sideStep = currentSideStep();
  return h("div", { class: "wizard" },
    h("section", { class: "wizard-main" },
      h("img", { class: "mobile-logo", src: "assets/logo-horizontal.svg", alt: "CaringBridge" }),
      h("div", { class: "step-box" }, ...content),
      h("div", { class: "progress" }, [0, 1, 2, 3].map(i => h("span", { class: i === sideStep ? "on" : "" })))),
    h("aside", { class: "wizard-side" },
      h("img", { class: "side-logo", src: "assets/logo-stacked-white.svg", alt: "CaringBridge" }),
      h("ol", { class: "steps" }, SIDE_STEPS.map(([title, text], i) =>
        h("li", { class: i < sideStep ? "done" : i === sideStep ? "current" : "" },
          h("small", {}, "Step " + (i + 1)), h("b", {}, title), text)))));
}

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
    h("p", { class: "lead" }, "You don't need the perfect words. Just start with what's on your mind."),
    card("guide", "Help Me Find the Words (Recommended)", "Answer a few quick questions, one at a time. Type or talk, whatever feels right. We'll take it from there, together."),
    card("blank", "I'd Like to Write It Myself", "Start with a blank post. We'll offer ideas at your request if you change your mind."),
    h("div", { class: "info" }, h("div", {}, h("b", {}, "How the Writing Guide Works"),
      "The guide helps turn what you share into a draft. You approve the final post, and set privacy settings.")),
    noticeBox(),
    primary("Next Step", next),
    links(["Previous", () => say("The earlier steps aren't part of this prototype yet.")],
      ["Skip for now", () => say("Skipping the writing step isn't built yet. Could you try the first option?")]));
}

// Writing it yourself

function selfWriteScreen() {
  if (!state.self_draft) state.self_draft = { title: "", post: "" };
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
    h("p", { class: "eyebrow" }, "Step 2 of 4 · Write your post"),
    heading("Write Your Post"),
    h("p", { class: "lead" }, "It's your story — write it your way."),
    fields,
    noticeBox(),
    primary("Next Step", () => go("photo")),
    links(["Previous", () => go("intro")], ["Start over", startOver]));
}

// Photo upload

function photoScreen() {
  const fileInput = h("input", { type: "file", accept: "image/*", id: "photo-file",
    onchange: e => {
      const file = e.target.files[0];
      if (!file) return;
      if (photoURL) URL.revokeObjectURL(photoURL);
      photoURL = URL.createObjectURL(file);
      render();
    } });

  const uploadArea = photoURL
    ? h("div", { class: "photo-upload" },
        h("img", { class: "photo-preview", src: photoURL, alt: "Your photo preview" }),
        h("div", { class: "photo-actions" },
          h("button", { type: "button", class: "link", onclick: () => fileInput.click() }, "Change photo"),
          h("button", { type: "button", class: "link", onclick: () => { URL.revokeObjectURL(photoURL); photoURL = null; render(); } }, "Remove")),
        fileInput)
    : h("div", { class: "photo-upload" },
        h("label", { for: "photo-file", class: "photo-drop" },
          h("span", {}, "Choose a photo"),
          h("span", { class: "photo-hint" }, "JPG, PNG or GIF")),
        fileInput);

  const back = state.path === "blank" ? "write" : "draft";
  return wizard(
    h("p", { class: "eyebrow" }, "Step 3 of 4 · Upload a photo"),
    heading("Add a Photo"),
    h("p", { class: "lead" }, "A photo helps visitors connect with your CaringBridge. You can add or change it later."),
    uploadArea,
    noticeBox(),
    primary("Next Step", () => go("privacy")),
    links(["Previous", () => go(back)], ["Skip for now", () => go("privacy")]));
}

// Privacy settings

function privacyScreen() {
  const options = [
    { id: "public",   label: "Anyone with the link",    text: "Anyone who has the link to your page can read your posts." },
    { id: "approval", label: "With your approval",      text: "Visitors can request access, and you decide who can read your posts." },
    { id: "invite",   label: "By invite only",          text: "Only people you personally invite can read your posts." },
  ];
  const cards = options.map(opt =>
    h("label", { class: "card" + (state.privacy === opt.id ? " selected" : "") },
      h("input", { type: "radio", name: "privacy", checked: state.privacy === opt.id,
        onchange: () => { state.privacy = opt.id; notice = ""; save(); render(); } }),
      h("span", {}, h("strong", {}, opt.label), h("span", { class: "card-text" }, opt.text))));

  return wizard(
    h("p", { class: "eyebrow" }, "Step 4 of 4 · Privacy settings"),
    heading("Who Can See Your Page?"),
    h("p", { class: "lead" }, "You can change this any time from your page settings."),
    ...cards,
    noticeBox(),
    primary("Publish Post", () => {
      if (!state.privacy) return say("Please choose a privacy setting to continue.");
      say("Your post is ready! Publishing isn't wired up in this prototype yet.");
    }),
    links(["Previous", () => go("photo")], null));
}

// Questions 1 to 4

function questionScreen() {
  const index = flow.questions.findIndex(q => q.id === state.step);
  const q = flow.questions[index];
  const last = index === flow.questions.length - 1;
  const before = index === 0 ? "intro" : flow.questions[index - 1].id;
  const onward = () => (last ? makeDraft() : go(flow.questions[index + 1].id));
  const skip = () => {
    for (const id of [q.id, q.other_id, ...(q.fields || []).map(f => f.id)]) {
      if (id in state.answers) state.answers[id] = Array.isArray(state.answers[id]) ? [] : "";
    }
    onward();
  };

  const body = q.type === "voice" ? voiceBox(q) : q.type === "checkboxes" ? checkboxes(q) : choiceFields(q);
  return wizard(
    h("p", { class: "eyebrow" }, `Question ${index + 1} of ${flow.questions.length}`),
    heading(q.title),
    q.prompt ? h("p", { class: "lead" }, q.prompt) : null,
    body,
    noticeBox(),
    primary(busy === "draft" ? "Writing your first draft..." : last ? "See What We Heard" : "Continue", onward, busy !== ""),
    links(["Previous", () => go(before)], ["Skip for now", skip]));
}

function voiceBox(q) {
  const box = h("textarea", { class: "text", "aria-label": q.title, oninput: e => { state.answers[q.id] = e.target.value; save(); } }, state.answers[q.id]);
  const talking = recording && recording.id === q.id;
  const label = busy === "transcribe" ? "Writing down what you said..." : talking ? "Listening... tap when you're done" : "Turn on speech to type instead";
  const pill = h("button", { type: "button", class: "pill" + (talking ? " listening" : ""), disabled: busy !== "",
    onclick: () => (talking ? recording.recorder.stop() : startRecording(q)) }, label);
  return h("div", {}, box, pill);
}

function checkboxes(q) {
  const other = h("input", { class: "text", type: "text", value: state.answers[q.other_id], oninput: e => { state.answers[q.other_id] = e.target.value; save(); } });
  return h("div", {},
    chips(q.options, state.answers[q.id], true, ids => { state.answers[q.id] = ids; save(); }),
    h("label", { class: "other" }, q.other_prompt, other));
}

function choiceFields(q) {
  return h("div", {}, q.fields.map(field => {
    const current = state.answers[field.id];
    return h("div", {}, h("p", { class: "field-title" }, field.prompt),
      chips(field.options, field.multiple ? current : current ? [current] : [], field.multiple, ids => {
        state.answers[field.id] = field.multiple ? ids : ids[0] || "";
        save();
      }));
  }), q.note ? h("p", { class: "fine" }, q.note) : null);
}

// The buttons change in place, so the keyboard focus stays where it was.
function chips(options, selected, multiple, onChange) {
  let current = [...selected];
  const buttons = options.map(option => h("button", { type: "button", class: "chip", "aria-pressed": String(current.includes(option.id)),
    onclick: () => {
      current = current.includes(option.id) ? current.filter(id => id !== option.id) : multiple ? [...current, option.id] : [option.id];
      onChange(current);
      buttons.forEach((button, i) => button.setAttribute("aria-pressed", String(current.includes(options[i].id))));
    } }, option.label));
  return h("div", { class: "chips" }, buttons);
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
    go("draft");
  } catch (err) {
    notice = err.message;
  }
  busy = "";
  render();
}

// One call carries the sliders and the text box together, along with the draft as the author has edited it.
async function rewrite() {
  if (!state.draft.post.trim()) return say("There's nothing in the post to rewrite yet. Type something, or go back to your answers.");
  busy = "rewrite";
  notice = "";
  render();
  try {
    const result = await post("/regenerate", { answers: answersForApi(), draft: { title: state.draft.title, post: state.draft.post }, adjustments: tweaks });
    const same = result.post.trim() === state.draft.post.trim();
    state.draft = { ...result, title: result.title || state.draft.title };  // a rewrite never swaps the title for nothing
    tweaks = TWEAKS_START();
    save();
    if (same) notice = "That came back the same as before. Try a bigger change, or tell us in your own words what to change.";
  } catch (err) {
    notice = err.message;
  }
  busy = "";
  render();
}

const slidersMoved = () => flow.sliders.some(s => tweaks[s.id] !== flow.slider_default);

function refreshButtons() {
  document.getElementById("suggest").disabled = busy !== "" || !slidersMoved();
  document.getElementById("ask").disabled = busy !== "" || !tweaks.extra.trim();
}

function slider(def) {
  const word = h("span", { class: "slider-word" }, def.labels[tweaks[def.id] - 1]);
  const input = h("input", { type: "range", min: 1, max: 5, step: 1, value: tweaks[def.id], "aria-label": def.title,
    oninput: e => { tweaks[def.id] = Number(e.target.value); word.textContent = def.labels[tweaks[def.id] - 1]; refreshButtons(); } });
  return h("div", { class: "slider" }, h("div", { class: "slider-head" }, h("span", {}, def.title), word), input,
    h("div", { class: "slider-ends" }, h("span", {}, def.low), h("span", {}, def.high)));
}

function includes() {
  const a = state.answers;
  return [
    ["Who is writing", Boolean(PROFILE.author_name)],
    ["What happened", Boolean(a.what_happened.trim())],
    ["What's next", Boolean(a.what_next.trim())],
    ["How people can help", a.help.length > 0 || Boolean(a.help_other.trim())],
    ["When to expect updates", Boolean(a.update_frequency)],
    ["A thank you (optional)", state.draft.post.toLowerCase().includes("thank")],
  ];
}

function draftScreen() {
  const draft = state.draft;
  const title = h("input", { class: "text", id: "title", type: "text", value: draft.title, oninput: e => { draft.title = e.target.value; save(); } });
  const text = h("textarea", { class: "text post", id: "post", oninput: e => { draft.post = e.target.value; save(); } }, draft.post);
  const asking = h("textarea", { class: "text", placeholder: "e.g., add a thank you to the nurses", "aria-label": "Tell us what to change",
    oninput: e => { tweaks.extra = e.target.value; refreshButtons(); } }, tweaks.extra);

  const main = h("div", {},
    h("p", { class: "eyebrow" }, "Step 2 of 4 · Your draft"),
    heading("Here's a First Draft, in Your Words"),
    h("p", { class: "banner" }, "We kept your words and smoothed out the rough spots. Change anything you like."),
    h("label", { for: "title" }, "Title"), title,
    h("label", { for: "post" }, "Post"), text,
    draft.privacy_flags.length ? h("p", { class: "notice" }, "Heads up, this looks like contact details: " + draft.privacy_flags.map(f => f.text).join(", ") + ". You decide what stays in.") : null,
    h("p", { class: "fine" }, flow.ai_notice),
    noticeBox(),
    primary("Next Step", () => go("photo")),
    links(["Back to answers", () => go(flow.questions[0].id)], ["Start over", startOver]));

  const feel = h("div", { class: "panel" }, h("h2", {}, "Make It Feel Right"), h("p", { class: "fine" }, "Nothing changes until you say so."),
    flow.sliders.map(slider),
    primary(busy === "rewrite" ? "Working on it..." : "Suggest Changes", rewrite, true));
  feel.querySelector(".primary").id = "suggest";
  const ask = h("div", { class: "panel" }, h("h2", {}, "Or tell us what to change"), asking, primary("Ask", rewrite, true));
  ask.querySelector(".primary").id = "ask";
  const list = h("div", { class: "panel" }, h("h2", {}, "Your Post Includes"),
    h("ul", { class: "checks" }, includes().map(([label, yes]) => h("li", { class: yes ? "yes" : "no" }, label))));

  const screen = h("div", { class: "draft" }, main, h("aside", {}, feel, ask, list));
  queueMicrotask(refreshButtons);  // sets the two buttons once they are on the page
  return screen;
}

async function start() {
  try { flow = await api("/flow"); }
  catch (err) { document.getElementById("app").textContent = err.message; return; }
  const known = ["intro", "draft", "write", "photo", "privacy", ...flow.questions.map(q => q.id)];
  if (!known.includes(state.step) || (state.step === "draft" && !state.draft)) state.step = "intro";
  render();
}

start();
