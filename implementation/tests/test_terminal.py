import array
import builtins
import io
import sys
import threading
import time
import types
import wave

import pytest

import voice_to_post as cli
from backend import flow, speech


def blocks(*loudness_levels):
    """Fake microphone: each number is how loud one tenth of a second is (0 to 1)."""
    return [array.array("h", [int(level * 32767)] * cli.BLOCK).tobytes() for level in loudness_levels]


def test_recording_stops_after_a_pause():
    audio = cli.record_until_pause(iter(blocks(*([0] * 5 + [0.2] * 10 + [0] * 40))))
    assert audio is not None
    assert len(audio) // (cli.BLOCK * 2) == 5 + 10 + cli.PAUSE  # stopped right at the pause, not the end


def test_a_short_pause_mid_sentence_does_not_end_the_answer():
    levels = ([0.2] * 10 + [0] * 5) * 3 + [0.2] * 4
    assert len(cli.record_until_pause(iter(blocks(*levels)))) == len(levels) * cli.BLOCK * 2


def test_silence_gives_nothing():
    assert cli.record_until_pause(iter(blocks(*([0] * 200)))) is None


def test_a_cough_is_not_an_answer():
    assert cli.record_until_pause(iter(blocks(*([0.3] + [0] * 200)))) is None


def test_checkbox_picks():
    options = flow.HELP_OPTIONS
    assert cli.parse_picks("1, 3 5", options) == ["meals", "gift_cards", "visits"]
    assert cli.parse_picks("", options) == []
    assert cli.parse_picks("2 2", options) == ["rides"]
    assert cli.parse_picks("9", options) is None
    assert cli.parse_picks("meals", options) is None


def type_in(monkeypatch, lines):
    typed = iter(lines)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(typed))


def test_whole_typed_flow_with_one_rewrite(monkeypatch, tmp_path, fake_ai, capsys):
    type_in(monkeypatch, [
        "Mom fell and broke her hip.",   # question 1
        "Surgery is on Thursday.",       # question 2
        "1,4", "She loves tulips.",      # question 3: meals, prayers, and the extra note
        "2", "1,2",                      # question 4: about once a week, comments and candles
        "",                              # see your first draft
        "a", "1", "", "5", "mention the tulips",   # adjust: shorter, tone left alone, own words, extra instruction
        "s",                             # save
    ])
    assert cli.main(["--text", "--out", str(tmp_path)]) == 0

    assert len(fake_ai.calls) == 2  # one for the draft, one for the rewrite, nothing else
    first, rewrite = (c["user"] for c in fake_ai.calls)
    assert "Meals, Prayers" in first and "post updates about once a week" in first and "CURRENT DRAFT" not in first
    assert "reach out by: Comments and Reactions on the page, Light a candle on the page" in first
    assert "CURRENT DRAFT" in rewrite and "mention the tulips" in rewrite and "We got news this week." in rewrite

    saved = list(tmp_path.glob("caringbridge_post_*.txt"))
    assert len(saved) == 1
    assert saved[0].read_text(encoding="utf-8") == "A new chapter\n\nWe got news this week.\n"
    out = capsys.readouterr().out
    assert "Nothing has been posted" in out and flow.AI_NOTICE in out


def test_skipping_everything_asks_for_something_instead_of_calling_the_ai(monkeypatch, tmp_path, fake_ai, capsys):
    type_in(monkeypatch, ["", "", "", "", "", "", ""])
    cli.main(["--text", "--out", str(tmp_path)])
    assert fake_ai.calls == []
    assert "Tell us a little" in capsys.readouterr().out


def test_hand_edited_title_goes_into_the_rewrite(monkeypatch, tmp_path, fake_ai):
    type_in(monkeypatch, ["Mom fell.", "", "", "", "", "", "", "e", "My own title", "n", "a", "", "", "", "", "q"])
    cli.main(["--text", "--out", str(tmp_path)])
    assert "Title: My own title" in fake_ai.calls[1]["user"]
    assert list(tmp_path.iterdir()) == []  # quit without saving


def test_ai_trouble_keeps_the_answers_and_lets_you_retry(monkeypatch, tmp_path, fake_ai):
    from backend import ai
    results = iter([ai.AIError("Couldn't reach the AI service."), None])
    real = ai.call_ai

    def flaky(system, user):
        problem = next(results)
        if problem:
            raise problem
        return real(system, user)

    monkeypatch.setattr(ai, "call_ai", flaky)
    type_in(monkeypatch, ["Mom fell.", "", "", "", "", "", "", "", "s"])  # ... draft fails, Enter retries, then save
    cli.main(["--text", "--out", str(tmp_path)])
    assert len(list(tmp_path.glob("caringbridge_post_*.txt"))) == 1


def test_missing_microphone_package_falls_back_to_typing(monkeypatch, tmp_path, fake_ai, capsys):
    import sys
    monkeypatch.setitem(sys.modules, "sounddevice", None)  # makes "import sounddevice" fail
    # Question 1 presses Enter to talk, the mic is missing, so it falls back to typing the answer.
    # After that every question is typed, and we skip the rest.
    type_in(monkeypatch, ["", "Mom fell.", "", "", "", "", "", "", "q"])
    cli.main(["--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert "python -m pip install sounddevice" in out
    assert "We'll type this one instead." in out


def fake_microphone(monkeypatch, levels, fail_to_open=False):
    """Puts a pretend sounddevice in place that plays the given loudness levels."""
    class PortAudioError(Exception):
        pass

    class Stream:
        def __init__(self, callback):
            self.callback, self.stopped = callback, threading.Event()
            self.closed = False

        def __enter__(self):
            def play():
                for block in blocks(*levels):
                    if self.stopped.is_set():
                        return
                    self.callback(block, cli.BLOCK, None, None)
                    time.sleep(0.001)
            threading.Thread(target=play, daemon=True).start()
            return self

        def __exit__(self, *rest):
            self.stopped.set()
            self.closed = True

    opened = []

    def raw_input_stream(**settings):
        if fail_to_open:
            raise PortAudioError("Invalid device")
        opened.append(Stream(settings["callback"]))
        return opened[-1]

    monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(
        RawInputStream=raw_input_stream, PortAudioError=PortAudioError))
    return opened


def test_listening_records_until_the_pause_and_sends_a_proper_wav(monkeypatch):
    opened = fake_microphone(monkeypatch, [0] * 3 + [0.2] * 10 + [0] * 40)
    sent = []
    monkeypatch.setattr(speech, "transcribe", lambda audio, name: sent.append(audio) or "Mom fell.")
    assert cli.listen() == "Mom fell."
    with wave.open(io.BytesIO(sent[0])) as recording:
        assert (recording.getnchannels(), recording.getframerate()) == (1, 16000)
        assert recording.getnframes() == (3 + 10 + cli.PAUSE) * cli.BLOCK
    assert opened[0].closed  # the microphone was let go


def test_listening_to_silence_sends_nothing(monkeypatch):
    fake_microphone(monkeypatch, [0] * 200)
    monkeypatch.setattr(speech, "transcribe", lambda audio, name: pytest.fail("nothing should be sent"))
    assert cli.listen() is None


def test_a_microphone_that_sends_nothing_is_explained(monkeypatch):
    fake_microphone(monkeypatch, [])
    monkeypatch.setattr(cli, "MIC_WAIT", 0.05)
    with pytest.raises(cli.MicError, match="isn't sending any sound"):
        cli.listen()


def test_a_microphone_that_will_not_open_is_explained(monkeypatch):
    fake_microphone(monkeypatch, [], fail_to_open=True)
    with pytest.raises(cli.MicError, match="Couldn't open the microphone"):
        cli.listen()
