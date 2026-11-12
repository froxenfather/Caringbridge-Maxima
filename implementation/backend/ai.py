import logging
import re

import requests

from backend.config import setting

log = logging.getLogger("backend.ai")


class AIError(Exception):
    """Something went wrong talking to the AI.
    The message is safe to show a person.
    busy is True when the service is only asking us to slow down, so the person can be told to wait a moment."""

    def __init__(self, message, busy=False):
        super().__init__(message)
        self.busy = busy


def base_url():
    # Groq by default.
    # Anything that speaks the OpenAI chat format works, including a local Ollama (http://localhost:11434/v1).
    return setting("AI_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")


def api_key():
    return setting("AI_API_KEY") or setting("GROQ_API_KEY")


def auth_headers():
    key = api_key()
    if not key and "localhost" not in base_url():
        raise AIError("There's no AI key yet. Set AI_API_KEY in your .env file, or in your hosting settings when it's deployed.")
    return {"Authorization": "Bearer " + key} if key else {}


# Credit to the D2 team, since this is their OpenAICompatibleProvider from d2-team/backend/llm/ollama_provider.py boiled down to one function.
# The request to /chat/completions is the same.
# So is the idea of turning every failure into one friendly error, which they called LLMUnavailableError, so a hiccup never loses the author's work.
def call_ai(system, user):
    """Send one prompt, get the model's reply as text.
    This is the only place a model is called, so switching providers (Bedrock, for example) means replacing just this function."""
    body = {
        "model": setting("AI_MODEL", "openai/gpt-oss-20b"),
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    try:
        reply = requests.post(base_url() + "/chat/completions", json=body, headers=auth_headers(), timeout=60)
        reply.raise_for_status()
        choice = reply.json()["choices"][0]
        text = choice["message"]["content"]
        if not (text or "").strip():
            log.warning("The AI sent back no text (finish_reason=%s)", choice.get("finish_reason"))
    except requests.HTTPError as err:
        status = err.response.status_code
        log.warning("AI request failed with HTTP %s", status)
        if status == 429:
            raise AIError("The writing helper is busy right now. Please wait a minute and try again.", busy=True) from err
        raise AIError("The AI service turned the request down (HTTP %s). Check AI_API_KEY and AI_MODEL." % status) from err
    except (requests.RequestException, KeyError, IndexError, ValueError) as err:
        log.warning("AI request failed: %s", type(err).__name__)
        raise AIError("Couldn't reach the AI service. Check your internet connection and AI_BASE_URL.") from err
    # Some models think out loud first, and that isn't part of the answer.
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


# Credit to the D2 team for the same idea in their /api/diagnostics (d2-team/app.py), which asks the AI service whether the configured model is there.
def check():
    """Setup check: a list of plain sentences about what's ready and what isn't."""
    lines = []
    try:
        listing = requests.get(base_url() + "/models", headers=auth_headers(), timeout=10)
        listing.raise_for_status()
        names = [m.get("id") for m in listing.json().get("data", [])]
        model = setting("AI_MODEL", "openai/gpt-oss-20b")
        if model in names:
            lines.append("AI: connected, and the model %s is available." % model)
        else:
            lines.append("AI: connected, but the model %s isn't in the list. Change AI_MODEL." % model)
    except AIError as err:
        lines.append("AI: " + str(err))
    except (requests.RequestException, ValueError):
        lines.append("AI: couldn't connect to %s. Check your key, your internet and AI_BASE_URL." % base_url())
    return lines
