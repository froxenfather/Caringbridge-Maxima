import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend import ai  # noqa: E402


@pytest.fixture
def fake_ai(monkeypatch):
    """Stands in for the model.
    Records every prompt it is given."""
    class Fake:
        calls = []
        reply = json.dumps({"title": "A new chapter", "post": "We got news this week."})

    def call_ai(system, user):
        Fake.calls.append({"system": system, "user": user})
        return Fake.reply

    Fake.calls = []
    monkeypatch.setattr(ai, "call_ai", call_ai)
    return Fake


ANSWERS = {
    "what_happened": "Mom fell last week and broke her hip.",
    "what_next": "Surgery is on Thursday.",
    "help": ["meals", "prayers"],
    "help_other": "She loves tulips.",
    "update_frequency": "weekly",
    "reach_out": ["comments", "candle"],
    "profile": {"author_name": "Sam", "page_for": "Mom", "relationship": "son"},
}
