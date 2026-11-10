"""Walk through the CaringBridge first-post flow in the terminal.

    python voice_to_post.py            talk (or type) your way to a first draft
    python voice_to_post.py --text     type every answer instead of talking
    python voice_to_post.py --check    check the microphone and AI setup

The work happens in backend/, and this file only asks the questions and prints the results.
Nothing is ever published.
The finished post is saved as a text file.

Built on ideas and code from the D2 team's CaringBridge First-Post Assistant (the d2-team folder), used with their permission.
Notes next to the borrowed pieces say where they came from.
The full list is in README.md.
"""
import argparse
import importlib.util
import io
import os
import queue
import subprocess
import sys
import tempfile
import wave
from datetime import datetime

if importlib.util.find_spec("requests") is None:
    sys.exit("This needs the 'requests' package. Install it with:\n    python -m pip install requests")

from backend import ai, flow, speech, writer
from backend.config import ROOT, setting

# Credit to the D2 team for how we decide someone has finished talking.
# The idea comes from d2-team/frontend/audio.js and d2-team/backend/stt/vad.py, which use a loudness threshold, a minimum amount of speech, a pause that ends the answer, a wait for someone to start, and a cap on length.
# The numbers here are our own choices, except the 120 second cap, which is theirs.
RATE = 16000                                        # samples per second sent to speech-to-text
BLOCK = RATE // 10                                  # we listen in tenths of a second
QUIET_LEVEL = float(setting("MIC_LEVEL", "0.012"))  # how loud counts as talking (0 to 1)
PAUSE = 15                                          # tenths of a second of quiet that end an answer
GIVE_UP = 120                                       # how long we wait for someone to start
MAX_LENGTH = 1200                                   # longest single answer
MIN_SPEECH = 3                                      # a cough isn't an answer
MIC_WAIT = 3                                        # seconds to wait for the microphone to send anything


class MicError(Exception):
    pass


def loudness(block):
    # Root-mean-square loudness, the same measure as the D2 team's _energy_based_vad in vad.py.
    samples = memoryview(block).cast("h")
    if not len(samples):
        return 0.0
    return (sum(s * s for s in samples) / len(samples)) ** 0.5 / 32768


def record_until_pause(blocks):
    """Collect audio until the person has talked and then gone quiet.
    Returns the raw audio, or None if nobody said anything."""
    audio = bytearray()
    talking = quiet = count = 0
    for block in blocks:
        audio += block
        count += 1
        if loudness(block) >= QUIET_LEVEL:
            talking += 1
            quiet = 0
        elif talking >= MIN_SPEECH:
            quiet += 1
        if quiet >= PAUSE or count >= MAX_LENGTH or (talking < MIN_SPEECH and count >= GIVE_UP):
            break
    return bytes(audio) if talking >= MIN_SPEECH else None


def mic_blocks():
    # The plain-language microphone messages below follow the D2 team's VoiceRecorder.permissionMessage in d2-team/frontend/audio.js.
    try:
        import sounddevice
    except (ImportError, OSError):
        raise MicError("Recording needs the 'sounddevice' package: python -m pip install sounddevice")
    heard = queue.Queue()
    device = setting("MIC_DEVICE")
    try:
        with sounddevice.RawInputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=BLOCK,
                                        device=int(device) if device else None,
                                        callback=lambda data, *rest: heard.put(bytes(data))):
            while True:
                try:
                    yield heard.get(timeout=MIC_WAIT)
                except queue.Empty:
                    raise MicError("The microphone isn't sending any sound. Is it plugged in and not muted?")
    except sounddevice.PortAudioError as err:
        raise MicError("Couldn't open the microphone: %s" % err)


def listen():
    """Record one answer from the microphone and return it as text (or None)."""
    print("  Listening... pause when you're done.")
    blocks = mic_blocks()
    try:
        audio = record_until_pause(blocks)
    finally:
        blocks.close()  # lets go of the microphone
    if audio is None:
        print("  I didn't hear anything.")
        return None
    wav = io.BytesIO()  # kept in memory, so the recording never touches the disk
    with wave.open(wav, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(audio)
    print("  Writing down what you said...")
    return speech.transcribe(wav.getvalue(), "answer.wav")


def parse_picks(text, options):
    """'1, 3' -> ['meals', 'gift_cards'].
    Returns None if it isn't a valid list."""
    picked = []
    for word in text.replace(",", " ").split():
        if not word.isdigit() or not 1 <= int(word) <= len(options):
            return None
        if options[int(word) - 1]["id"] not in picked:
            picked.append(options[int(word) - 1]["id"])
    return picked


def pick(options, many=True):
    """Show a numbered list and return the ids picked (an empty list if skipped)."""
    for number, option in enumerate(options, 1):
        print("  %d) %s" % (number, option["label"]))
    while True:
        what = "the numbers you want, like 1,3" if many else "a number"
        picked = parse_picks(input("  Type %s (Enter to skip): " % what), options)
        if picked is not None and (many or len(picked) <= 1):
            return picked
        print("  Just %s from the list, please." % ("numbers" if many else "one number"))


def ask_voice(question, can_talk):
    """Returns (answer, can_talk).
    can_talk turns False if the microphone fails.
    Falling back to typing instead of stopping is the D2 team's rule, voice is never the only way through."""
    print("\n%s\n  %s" % (question["title"], question["prompt"]))
    while True:
        choice = input("  Press Enter to talk, t to type, s to skip: ").strip().lower() if can_talk else "t"
        if choice == "s":
            return "", can_talk
        if choice == "t":
            return input("  Type your answer (Enter to skip): ").strip(), can_talk
        try:
            heard = listen()
        except (MicError, speech.SpeechError) as err:
            print("  " + str(err))
            if isinstance(err, MicError):
                print("  We'll type this one instead.")
                can_talk = False
            continue
        if heard is None:
            continue
        print('  I heard: "%s"' % heard)
        keep = input("  Keep it? Enter = yes, r = record again, t = type instead: ").strip().lower()
        if keep == "":
            return heard, can_talk
        if keep == "t":
            return input("  Type your answer (Enter to skip): ").strip(), can_talk
        # Anything else means record again.


def ask_questions(can_talk):
    answers = {}
    for number, question in enumerate(flow.QUESTIONS, 1):
        print("\nQuestion %d of %d" % (number, len(flow.QUESTIONS)), end="")
        if question["type"] == "voice":
            answers[question["id"]], can_talk = ask_voice(question, can_talk)
        elif question["type"] == "checkboxes":
            print("\n" + question["title"])
            answers[question["id"]] = pick(question["options"])
            answers[question["other_id"]] = input("  " + question["other_prompt"] + " ").strip()
        else:
            print("\n" + question["title"])
            for field in question["fields"]:
                print("\n  " + field["prompt"])
                answers[field["id"]] = (pick(field["options"], many=False) or [""])[0]
    return answers


def show_heard(answers):
    print("\nHere's what we heard:")
    for key, name in [("what_happened", "What happened"), ("what_next", "What happens next"),
                      ("help_other", "Anything else")]:
        print("  %s: %s" % (name, answers[key] or "(skipped)"))
    ticked = [writer.label_for(flow.HELP_OPTIONS, h) for h in answers["help"]]
    print("  Help wanted: " + (", ".join(ticked) or "(none)"))
    print("  Updates: %s. Reach out by: %s." % (
        writer.label_for(flow.UPDATE_OPTIONS, answers["update_frequency"]) or "(skipped)",
        writer.label_for(flow.REACH_OPTIONS, answers["reach_out"]) or "(skipped)"))


def show_draft(draft):
    print("\n" + "-" * 60)
    print("%s\n\n%s" % (draft["title"] or "(no title)", draft["post"]))
    print("-" * 60)
    print(flow.AI_NOTICE)
    for flag in draft["privacy_flags"]:
        print("Heads up, this looks like a %s: %s" % (flag["kind"], flag["text"]))


def edit_in_editor(text):
    """Open the post in Notepad (or $EDITOR) and return what was saved."""
    editor = setting("EDITOR", "notepad" if os.name == "nt" else "nano")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(text)
    try:
        subprocess.call([editor, f.name])
        # The new Windows 11 Notepad can hand control back before you're done.
        input("  Save the file and close the editor, then press Enter here... ")
        with open(f.name, encoding="utf-8") as saved:
            return saved.read().strip()
    except OSError:
        print("  Couldn't open an editor. Type the whole post on one line instead:")
        return input("  > ").strip()
    finally:
        os.remove(f.name)


def edit_draft(draft):
    title = input("  New title (Enter keeps it): ").strip()
    if title:
        draft["title"] = title
    if input("  Open the post in your editor? (y/N) ").strip().lower().startswith("y"):
        draft["post"] = edit_in_editor(draft["post"]) or draft["post"]


def ask_adjustments():
    print("\n  Rate each from 1 to 5. Press Enter to leave it as it is.")
    adjustments = {}
    for slider in flow.SLIDERS:
        while True:
            raw = input("  %s: 1 = %s, 5 = %s: " % (slider["title"], slider["low"], slider["high"])).strip()
            if raw in ("", "1", "2", "3", "4", "5"):
                break
            print("  A number from 1 to 5, please.")
        adjustments[slider["id"]] = int(raw) if raw else flow.SLIDER_DEFAULT
    adjustments["extra"] = input("  Anything else you'd like changed? (optional): ").strip()
    return adjustments


def save_post(draft, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "caringbridge_post_%s.txt" % datetime.now().strftime("%Y%m%d_%H%M%S"))
    with open(path, "w", encoding="utf-8") as f:
        f.write("%s\n\n%s\n" % (draft["title"], draft["post"]))
    return path


def run_flow(can_talk, out_dir):
    answers = ask_questions(can_talk)
    show_heard(answers)
    input("\nPress Enter to see your first draft...")
    while True:
        try:
            draft = writer.first_draft(answers)
            break
        except ValueError as err:  # nothing to write from; retrying won't help
            print("\n" + str(err))
            return
        except ai.AIError as err:
            print("\n" + str(err))
            if input("Press Enter to try again, or q to quit: ").strip().lower() == "q":
                return
    show_draft(draft)

    while True:
        choice = input("\n[e] edit  [a] adjust and rewrite  [s] save and finish  [q] quit: ").strip().lower()
        if choice == "e":
            edit_draft(draft)
            show_draft(draft)
        elif choice == "a":
            try:
                draft = writer.regenerate(answers, draft, ask_adjustments())
                show_draft(draft)
            except (ValueError, ai.AIError) as err:
                print("\n%s Your draft is still here." % err)
        elif choice == "s":
            print("\nSaved to " + save_post(draft, out_dir))
            print("Nothing has been posted. Copy it into CaringBridge when you're happy with it.")
            return
        elif choice == "q":
            return


def check_setup():
    # Same idea as the D2 team's /api/diagnostics, a read-only look at what's ready.
    print("Python " + sys.version.split()[0])
    for line in ai.check():
        print(line)
    try:
        import sounddevice
        mics = [d["name"] for d in sounddevice.query_devices() if d["max_input_channels"] > 0]
        print("Microphones: " + ("; ".join(mics) if mics else "none found"))
    except (ImportError, OSError):
        print("Microphones: can't check yet. To talk instead of type, run: python -m pip install sounddevice")


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")  # curly quotes shouldn't crash a Windows console
    parser = argparse.ArgumentParser(description="Write a CaringBridge first post by talking or typing.")
    parser.add_argument("--text", action="store_true", help="type every answer instead of talking")
    parser.add_argument("--check", action="store_true", help="check the microphone and AI setup, then stop")
    parser.add_argument("--out", default=str(ROOT / "exports"), help="folder to save the finished post in")
    args = parser.parse_args(argv)

    if args.check:
        check_setup()
        return 0
    print("CaringBridge first post. Answer in your own words; you can skip anything.")
    try:
        run_flow(can_talk=not args.text, out_dir=args.out)
    except (KeyboardInterrupt, EOFError):
        print("\nStopped. Nothing was saved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
