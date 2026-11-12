# CaringBridge first post

The "Help Me Find the Words" path of the first-post flow, as a web page backed by a small API.
Four short questions, then an AI writes a first draft in the author's own words.
The author edits it, nudges the length, tone and wording, and rewrites it with one more AI call.
Nothing is ever published, and nothing is stored on the server.

## Run it on your computer

You need Python 3.9 or newer and a free key from https://console.groq.com.

```
python -m pip install -r requirements-local.txt
copy .env.example .env
uvicorn app:app --reload
```

Put your key in `.env` as `AI_API_KEY=...`, then open http://127.0.0.1:8000.
http://127.0.0.1:8000/status.html shows whether the backend is running and has a button that tests the Groq connection.

There is also a terminal version of the same flow, `python voice_to_post.py` (add `--text` to type instead of talk, or `--check` to test your setup).

## The screens

Intro, then Questions 1 to 4, then the first draft with the Make It Feel Right sliders and the box to tell it what to change.
The words on every question come from `backend/flow.py`, so a copy change from Figma is an edit in that one file.
On the intro screen, choosing "I'd Like to Write It Myself" (or Previous, or Skip for now) shows a gentle "not built yet" message.
The stand-in sign-up details (Sam writing about Robert) are at the top of `public/app.js` until the real sign-up steps are connected.

Talking on Questions 1 and 2 records in the browser, sends the clip to the API, and puts the words in the box, where they stay editable.
The audio is not stored.

## The API

Nothing is kept on the server, so the page holds the answers and sends them with each request.

| Route | Does |
|---|---|
| `GET /api/v1/flow` | The questions, options and sliders to draw. |
| `POST /api/v1/transcribe` | Audio file in, `{text}` out. |
| `POST /api/v1/draft` | `answers` in, `{title, post, privacy_flags}` out. |
| `POST /api/v1/regenerate` | `answers`, `draft` (with the author's edits) and `adjustments` in, a new draft out. |
| `GET /api/v1/health` | Is it running, which deployment is answering, and whether a key is set (never the key). |
| `GET /api/v1/check` | Whether Groq is reachable and the model exists. |

The API docs are at http://127.0.0.1:8000/docs while it runs.
There is no login yet, so put authentication in front of it before it goes anywhere public.

## Where things are

| File | What it is |
|---|---|
| `public/index.html`, `styles.css`, `app.js` | The page, with no build step. |
| `public/status.html` | The status page. |
| `public/assets/` | The CaringBridge logos, from their media kit. |
| `backend/flow.py` | The questions, options and sliders. |
| `backend/writer.py` | The prompt and the two functions everything calls, `first_draft` and `regenerate`. |
| `backend/ai.py` | The one function that calls a model. |
| `backend/speech.py` | The one function that turns audio into text. |
| `app.py` | The API, and the page when you run it locally. |
| `voice_to_post.py` | The terminal version. |

To move to AWS Bedrock later, replace `call_ai` in `backend/ai.py`.
To use another speech service, replace `transcribe` in `backend/speech.py`.

## Put it online with Vercel and Groq

1. Push the repo to GitHub, making sure `.env` is not included.
2. On vercel.com, import the repo and set the Root Directory to `implementation`.
3. Add an environment variable named `AI_API_KEY` with your Groq key, then deploy.
4. Open the address Vercel gives you, and open `/status.html` on it to check the Groq connection.

Every push to `main` redeploys on its own.
Vercel serves the files in `public/` and runs `app.py` for the API, and `requirements.txt` is the list it installs.

## Tests

```
python -m pytest
```

They need no microphone, no internet and no key.
If the API tests are skipped, your Starlette needs an extra package for its test client, and the skip message says how to see which.

## Credits

This is built on the D2 team's CaringBridge First-Post Assistant (the `d2-team` folder), and we have their permission to fork and change it.
The pieces that come from them are marked with a comment next to the code.

- The writing rules in `backend/writer.py` come from their prompts in `d2-team/backend/post_generator.py`.
- The contact-detail patterns in `backend/writer.py` come from `d2-team/backend/privacy.py`.
- `call_ai` in `backend/ai.py` is their `OpenAICompatibleProvider` boiled down to one function, and `check` follows their `/api/diagnostics`.
- `transcribe` in `backend/speech.py` follows `d2-team/backend/stt/groq_engine.py`.
- The recording formats and microphone messages in `public/app.js` come from `d2-team/frontend/audio.js`, and keeping the session in the browser tab follows `d2-team/frontend/app.js`.
- Turning caching off for local development in `app.py`, and the way `voice_to_post.py` decides someone has finished talking, follow `d2-team/app.py`, `d2-team/frontend/audio.js` and `d2-team/backend/stt/vad.py`.
- Reading settings from a `.env` file follows `d2-team/backend/config.py`, and the error handling in `app.py` follows `d2-team/app.py`.

## If the writing helper says it's busy

Groq's free plan limits how many requests and how much text you can send in a minute, so pressing the buttons many times in a row can show "The writing helper is busy right now".
Waiting a minute fixes it, and the draft is never touched when that happens.
If a rewrite ever fails for another reason, the server logs a line like "The AI sent back no usable post", which you can find in the terminal or in Vercel's logs.

## Not done yet

- "I'd Like to Write It Myself", and Steps 1, 3 and 4 of the CaringBridge sign-up.
- The bold, italic, link and image toolbar on the post.
- The "What has been captured" line under the questions.
- Words appearing live while someone talks, and undo for a rewrite the author doesn't like.
- Real sign-up details in place of the stand-in profile.
- The recording has only been tried with a simulated microphone, and nothing has been tried with the real Groq service yet.
