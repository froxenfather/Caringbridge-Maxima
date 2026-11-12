import importlib.util
import logging

import pytest
import requests

pytest.importorskip("fastapi")
try:
    from fastapi.testclient import TestClient
except (ImportError, RuntimeError):
    # Newer versions of Starlette ask for an extra HTTP package before their test client will import.
    pytest.skip("FastAPI's test client needs an HTTP package, see the error from: python -c 'from fastapi.testclient import TestClient'",
                allow_module_level=True)

import app as server  # noqa: E402
from backend import ai, speech  # noqa: E402
from conftest import ANSWERS  # noqa: E402

client = TestClient(server.app)
API = "/api/v1"


def test_flow_describes_what_the_front_end_should_draw():
    data = client.get(API + "/flow").json()
    assert [q["id"] for q in data["questions"]] == ["what_happened", "what_next", "help", "staying_in_touch"]
    assert [s["id"] for s in data["sliders"]] == ["length", "tone", "wording"]
    assert data["slider_default"] == 3 and data["ai_notice"]


def test_draft(fake_ai):
    response = client.post(API + "/draft", json=ANSWERS)
    assert response.status_code == 200
    assert response.json() == {"title": "A new chapter", "post": "We got news this week.", "privacy_flags": []}
    assert len(fake_ai.calls) == 1
    assert "Author: Sam" in fake_ai.calls[0]["user"] and "Light a candle on the page" in fake_ai.calls[0]["user"]


def test_bad_answers_are_a_400_and_never_reach_the_ai(fake_ai):
    assert client.post(API + "/draft", json={"help": ["unicorns"]}).status_code == 400
    assert client.post(API + "/draft", json={}).status_code == 400
    assert client.post(API + "/draft", json={"what_happened": "x" * 6000}).status_code == 422
    assert fake_ai.calls == []


def test_regenerate_sends_the_edited_draft_in_one_call(fake_ai):
    response = client.post(API + "/regenerate", json={
        "answers": ANSWERS,
        "draft": {"title": "My title", "post": "My edited post."},
        "adjustments": {"length": 1, "tone": 5, "wording": 3, "extra": "mention the tulips"},
    })
    assert response.status_code == 200
    assert len(fake_ai.calls) == 1
    prompt = fake_ai.calls[0]["user"]
    assert "My edited post." in prompt and "mention the tulips" in prompt


def test_regenerate_checks_the_sliders(fake_ai):
    body = {"answers": ANSWERS, "draft": {"post": "x"}, "adjustments": {"tone": 9}}
    assert client.post(API + "/regenerate", json=body).status_code == 422
    assert fake_ai.calls == []


def test_ai_trouble_is_a_502_with_a_readable_message(monkeypatch):
    def broken(system, user):
        raise ai.AIError("Couldn't reach the AI service.")

    monkeypatch.setattr(ai, "call_ai", broken)
    response = client.post(API + "/draft", json=ANSWERS)
    assert response.status_code == 502 and "Couldn't reach" in response.json()["detail"]


@pytest.mark.skipif(importlib.util.find_spec("python_multipart") is None, reason="python-multipart isn't installed")
def test_transcribe_takes_an_upload(monkeypatch):
    monkeypatch.setattr(speech, "transcribe", lambda data, name: "Mom fell last week (%d bytes, %s)" % (len(data), name))
    response = client.post(API + "/transcribe", files={"audio": ("answer.wav", b"12345", "audio/wav")})
    assert response.json() == {"text": "Mom fell last week (5 bytes, answer.wav)"}


def test_health_says_whether_a_key_is_set_but_never_shows_it(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "super-secret-key")
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "abcdef1234567890")
    response = client.get(API + "/health")
    assert response.json()["status"] == "ok"
    assert response.json()["ai_key_set"] is True
    assert response.json()["commit"] == "abcdef1"
    assert "super-secret-key" not in response.text
    monkeypatch.delenv("AI_API_KEY")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert client.get(API + "/health").json()["ai_key_set"] is False


def test_the_pages_are_served_when_running_locally():
    home = client.get("/")
    assert home.status_code == 200 and "app.js" in home.text and "styles.css" in home.text
    assert client.get("/app.js").status_code == 200
    assert client.get("/styles.css").status_code == 200
    status = client.get("/status.html")
    assert status.status_code == 200 and 'get("/health")' in status.text and 'get("/check")' in status.text
    assert client.get(API + "/health").status_code == 200  # the API still wins over the static files


def test_what_people_write_never_reaches_the_logs(monkeypatch, fake_ai, caplog):
    caplog.set_level(logging.DEBUG)
    secret = {**ANSWERS, "what_happened": "ZEBRA-PRIVATE-STORY"}
    client.post(API + "/draft", json=secret)

    monkeypatch.undo()  # drop the fake AI so the real code runs, then break the network under it
    monkeypatch.setenv("AI_API_KEY", "key")

    def offline(*args, **kwargs):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(requests, "post", offline)
    assert client.post(API + "/draft", json=secret).status_code == 502
    assert "ZEBRA-PRIVATE-STORY" not in caplog.text


def test_a_busy_ai_is_a_429_the_page_can_show_as_it_is(monkeypatch):
    def busy(system, user):
        raise ai.AIError("The writing helper is busy right now. Please wait a minute and try again.", busy=True)

    monkeypatch.setattr(ai, "call_ai", busy)
    response = client.post(API + "/draft", json=ANSWERS)
    assert response.status_code == 429 and "busy" in response.json()["detail"]


def test_an_empty_ai_reply_is_an_error_and_the_draft_is_left_alone(fake_ai):
    fake_ai.reply = ""
    response = client.post(API + "/regenerate", json={
        "answers": ANSWERS, "draft": {"title": "Mine", "post": "My words."}, "adjustments": {"tone": 5}})
    assert response.status_code == 502 and "usable draft" in response.json()["detail"]
    assert len(fake_ai.calls) == 2  # it tried once more before giving up
