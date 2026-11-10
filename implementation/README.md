# CaringBridge first post

A small backend for the first-post flow.
Four short questions, then an AI writes a first draft in the author's own words.
The author edits it, nudges the length, tone and wording, and rewrites it with one more AI call.
Nothing is ever published, the finished post is a text file to copy.

## Run it

You need Python 3.9 or newer.

```
python -m pip install -r requirements.txt
copy .env.example .env
python voice_to_post.py --check
python voice_to_post.py
```

Put a free key from https://console.groq.com in `.env` as `AI_API_KEY` first, it covers both the AI and the speech-to-text.
`--check` tells you what is and isn't ready.
Add `--text` to type every answer instead of talking.

If you only install `requests` you can still run the whole flow with `--text`.
Talking needs `sounddevice` as well.

## The flow

1. What happened? (talk or type)
2. What happens next? (talk or type)
3. How can others help right now? (tick the boxes, plus an optional note)
4. Staying in touch (how often you'll update, how people should reach out)
5. See what we've heard, then the first draft with an editable title and post.
6. Adjust: length, tone and wording from 1 to 5, plus an optional note to the AI, then one rewrite call.

The questions and every option live in `backend/flow.py`.
The question wording and the Q4 options are placeholders until we have the final copy from Figma.

## For the front end

`app.py` is the HTTP API.
It keeps nothing on the server, so the front end holds the answers and sends them with each request.

```
python -m pip install -r requirements-api.txt
uvicorn app:app --reload
```

| Route | Does |
|---|---|
| `GET /api/v1/flow` | The questions, options and sliders to draw. |
| `POST /api/v1/transcribe` | Audio file in, `{text}` out. |
| `POST /api/v1/draft` | `answers` in, `{title, post, privacy_flags}` out. |
| `POST /api/v1/regenerate` | `answers`, `draft` (with the author's edits) and `adjustments` in, a new draft out. |
| `GET /api/v1/check` | Whether the AI is reachable and the model exists. |

The API docs are at http://127.0.0.1:8000/docs while it runs.
There is no login yet, so put authentication in front of it before it goes anywhere public.

## Where things are

| File | What it is |
|---|---|
| `backend/flow.py` | The questions, options and sliders. |
| `backend/writer.py` | The prompt and the two functions everything calls, `first_draft` and `regenerate`. |
| `backend/ai.py` | The one function that calls a model. |
| `backend/speech.py` | The one function that turns audio into text. |
| `voice_to_post.py` | The terminal version, including the microphone. |
| `app.py` | The HTTP API. |

To move to AWS Bedrock later, replace `call_ai` in `backend/ai.py`.
To use another speech service, replace `transcribe` in `backend/speech.py`.

## Tests

```
python -m pytest
```

They need no microphone, no internet and no key.

## Credits

This is built on the D2 team's CaringBridge First-Post Assistant (the `d2-team` folder), and we have their permission to fork and change it.
The pieces that come from them are marked with a comment next to the code.

- The writing rules in `backend/writer.py` come from their prompts in `d2-team/backend/post_generator.py`.
- The contact-detail patterns in `backend/writer.py` come from `d2-team/backend/privacy.py`.
- `call_ai` in `backend/ai.py` is their `OpenAICompatibleProvider`, boiled down to one function, and `check` follows their `/api/diagnostics`.
- `transcribe` in `backend/speech.py` follows `d2-team/backend/stt/groq_engine.py`.
- The way `voice_to_post.py` decides someone has finished talking, and its microphone error messages, come from `d2-team/frontend/audio.js` and `d2-team/backend/stt/vad.py`.
- Reading settings from a `.env` file follows `d2-team/backend/config.py`, and the error handling in `app.py` follows `d2-team/app.py`.

## Not done yet

- The real sliders and regenerate button belong in the front end, which doesn't exist yet.
- The recording code has only been tested with a simulated microphone, and nothing has been tried with a real Groq key yet.
- Speech and writing both default to Groq, and Bedrock isn't wired in.
