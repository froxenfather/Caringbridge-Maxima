import logging
import mimetypes

import requests

from backend import ai
from backend.config import setting

log = logging.getLogger("backend.speech")

MAX_AUDIO_BYTES = 25 * 1024 * 1024  # the most Groq accepts in one go (same limit as the D2 team's audio_utils.py)


class SpeechError(Exception):
    """Transcription failed.
    The message is safe to show a person."""


# Credit to the D2 team for the request below, which follows d2-team/backend/stt/groq_engine.py.
# The model, the language, temperature 0, the audio sent as a multipart file, and the check that there are actual words in the result are all from there.
def transcribe(audio, filename="voice.wav"):
    """Turn a recording (the bytes of a wav, webm, mp3 or m4a file) into text.
    Like call_ai, this is the one place to change if speech moves to another service."""
    if not audio:
        raise SpeechError("That recording was empty.")
    if len(audio) > MAX_AUDIO_BYTES:
        raise SpeechError("That recording is too long. Try a shorter one.")
    try:
        reply = requests.post(
            (setting("SPEECH_BASE_URL") or ai.base_url()).rstrip("/") + "/audio/transcriptions",
            headers=ai.auth_headers(),
            data={"model": setting("SPEECH_MODEL", "whisper-large-v3-turbo"), "language": "en", "temperature": "0"},
            files={"file": (filename, audio, mimetypes.guess_type(filename)[0] or "audio/webm")},
            timeout=60,
        )
        reply.raise_for_status()
        text = reply.json().get("text", "").strip()
    except ai.AIError as err:
        raise SpeechError(str(err)) from err
    except requests.HTTPError as err:
        log.warning("transcription failed with HTTP %s", err.response.status_code)
        raise SpeechError("The speech service turned the recording down (HTTP %s)." % err.response.status_code) from err
    except (requests.RequestException, ValueError) as err:
        log.warning("transcription failed: %s", type(err).__name__)
        raise SpeechError("Couldn't reach the speech service. Check your internet connection.") from err
    if not any(ch.isalnum() for ch in text):
        raise SpeechError("I couldn't make out any words in that recording.")
    return text
