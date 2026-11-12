import pytest
import requests

from backend import ai, speech


class Reply:
    def __init__(self, data=None, status=200):
        self.data, self.status_code = data, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return self.data


def test_ai_call_sends_the_prompt_and_strips_thinking(monkeypatch):
    sent = {}

    def post(url, json=None, headers=None, timeout=None):
        sent.update(url=url, body=json, headers=headers)
        return Reply({"choices": [{"message": {"content": "<think>hmm</think>The answer."}}]})

    monkeypatch.setenv("AI_API_KEY", "secret")
    monkeypatch.setattr(requests, "post", post)
    assert ai.call_ai("rules", "question") == "The answer."
    assert sent["url"].endswith("/chat/completions")
    assert sent["headers"] == {"Authorization": "Bearer secret"}
    assert sent["body"]["messages"][0] == {"role": "system", "content": "rules"}


def test_ai_without_a_key_explains_what_to_do(monkeypatch):
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ai.AIError, match="AI_API_KEY"):
        ai.call_ai("rules", "question")


def test_ai_errors_are_plain_and_do_not_leak_the_key(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "secret")
    monkeypatch.setattr(requests, "post", lambda *a, **k: Reply(status=401))
    with pytest.raises(ai.AIError) as err:
        ai.call_ai("rules", "question")
    assert "401" in str(err.value) and "secret" not in str(err.value)

    def offline(*a, **k):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(requests, "post", offline)
    with pytest.raises(ai.AIError, match="Couldn't reach"):
        ai.call_ai("rules", "question")


def test_transcribe_uploads_the_audio(monkeypatch):
    sent = {}

    def post(url, headers=None, data=None, files=None, timeout=None):
        sent.update(url=url, data=data, files=files)
        return Reply({"text": " Mom fell last week. "})

    monkeypatch.setenv("AI_API_KEY", "secret")
    monkeypatch.setattr(requests, "post", post)
    assert speech.transcribe(b"audio bytes", "answer.wav") == "Mom fell last week."
    assert sent["url"].endswith("/audio/transcriptions")
    assert sent["files"]["file"][:2] == ("answer.wav", b"audio bytes")


def test_transcribe_refuses_empty_or_wordless_audio(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "secret")
    with pytest.raises(speech.SpeechError, match="empty"):
        speech.transcribe(b"")
    monkeypatch.setattr(requests, "post", lambda *a, **k: Reply({"text": " ... "}))
    with pytest.raises(speech.SpeechError, match="words"):
        speech.transcribe(b"audio")


def test_speech_can_use_a_different_service_than_the_writer(monkeypatch):
    seen = []
    monkeypatch.setenv("AI_API_KEY", "secret")
    monkeypatch.setenv("SPEECH_BASE_URL", "https://speech.example/v1/")
    monkeypatch.setattr(requests, "post", lambda url, **k: (seen.append(url), Reply({"text": "hello"}))[1])
    speech.transcribe(b"audio")
    assert seen == ["https://speech.example/v1/audio/transcriptions"]


def test_setup_check_reports_a_missing_model(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "secret")
    monkeypatch.setenv("AI_MODEL", "my-model")
    monkeypatch.setattr(requests, "get", lambda *a, **k: Reply({"data": [{"id": "other-model"}]}))
    assert "isn't in the list" in ai.check()[0]
    monkeypatch.setattr(requests, "get", lambda *a, **k: Reply({"data": [{"id": "my-model"}]}))
    assert "available" in ai.check()[0]


def test_a_rate_limit_says_the_helper_is_busy(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "secret")
    monkeypatch.setattr(requests, "post", lambda *a, **k: Reply(status=429))
    with pytest.raises(ai.AIError, match="busy") as err:
        ai.call_ai("rules", "question")
    assert err.value.busy is True


def sent_body(monkeypatch, model):
    seen = {}

    def post(url, json=None, headers=None, timeout=None):
        seen.update(json)
        return Reply({"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]})

    monkeypatch.setenv("AI_API_KEY", "secret")
    monkeypatch.setenv("AI_MODEL", model)
    monkeypatch.setattr(requests, "post", post)
    ai.call_ai("rules", "question")
    return seen


def test_thinking_models_get_a_big_budget_and_light_thinking(monkeypatch):
    body = sent_body(monkeypatch, "openai/gpt-oss-20b")
    assert body["max_tokens"] == 4000 and body["reasoning_effort"] == "low"


def test_other_models_are_not_sent_a_thinking_setting_they_might_reject(monkeypatch):
    body = sent_body(monkeypatch, "llama-3.3-70b-versatile")
    assert "reasoning_effort" not in body and body["max_tokens"] == 4000
