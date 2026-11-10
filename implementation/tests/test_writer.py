import pytest

from backend import writer
from conftest import ANSWERS


def test_answers_are_tidied():
    tidy = writer.validate_answers({"what_happened": "  Mom fell.  ", "help": ["prayers", "meals", "meals"]})
    assert tidy["what_happened"] == "Mom fell."
    assert tidy["help"] == ["meals", "prayers"]  # menu order, no repeats
    assert tidy["reach_out"] == []
    assert tidy["profile"] == {"author_name": "", "page_for": "", "relationship": ""}


def test_reaching_out_can_pick_several_in_menu_order():
    tidy = writer.validate_answers({"what_happened": "x", "reach_out": ["candle", "comments", "candle"]})
    assert tidy["reach_out"] == ["comments", "candle"]


def test_bad_answers_are_refused():
    with pytest.raises(ValueError, match="know"):
        writer.validate_answers({"help": ["unicorns"]})
    with pytest.raises(ValueError, match="know"):
        writer.validate_answers({"what_happened": "x", "reach_out": ["carrier_pigeon"]})
    with pytest.raises(ValueError, match="know"):
        writer.validate_answers({"what_happened": "x", "update_frequency": "hourly"})
    with pytest.raises(ValueError, match="too long"):
        writer.validate_answers({"what_happened": "x", "profile": {"author_name": "S" * 101}})
    with pytest.raises(ValueError, match="too long"):
        writer.validate_answers({"what_happened": "x" * (writer.MAX_TEXT + 1)})
    with pytest.raises(ValueError, match="first"):
        writer.validate_answers({})


def test_sliders_default_to_the_middle_and_are_checked():
    assert writer.validate_adjustments(None) == {"length": 3, "tone": 3, "wording": 3, "extra": ""}
    with pytest.raises(ValueError):
        writer.validate_adjustments({"tone": 6})
    with pytest.raises(ValueError):
        writer.validate_adjustments({"length": True})


def test_the_middle_slider_position_says_nothing():
    assert writer.slider_text("tone", 3) == ""
    assert "shorter" in writer.slider_text("length", 1)
    assert "own" in writer.slider_text("wording", 5)


def test_first_prompt_has_every_answer_and_no_rewrite_sections():
    prompt = writer.build_prompt(writer.validate_answers(ANSWERS))
    for expected in ["Mom fell last week", "Surgery is on Thursday", "Meals, Prayers", "tulips", "Updates: About once a week",
                     "People can reach out by: Comments and Reactions on the page, Light a candle on the page"]:
        assert expected in prompt
    assert "CURRENT DRAFT" not in prompt


def test_the_stand_in_profile_reaches_the_prompt_and_missing_profile_says_so():
    prompt = writer.build_prompt(writer.validate_answers(ANSWERS))
    assert "ABOUT THE AUTHOR (from sign-up):\nAuthor: Sam; Writing about: Mom; Author's relationship to them: son" in prompt
    bare = writer.build_prompt(writer.validate_answers({"what_happened": "Mom fell."}))
    assert "ABOUT THE AUTHOR (from sign-up):\n(not provided)" in bare


def test_the_flow_matches_what_the_front_end_needs():
    from backend import flow
    assert [q["id"] for q in flow.QUESTIONS] == ["what_happened", "what_next", "help", "staying_in_touch"]
    assert [o["id"] for o in flow.HELP_OPTIONS][-2:] == ["pet_care", "fundraising"]
    fields = {f["id"]: f for f in flow.QUESTIONS[3]["fields"]}
    assert fields["update_frequency"]["multiple"] is False and fields["reach_out"]["multiple"] is True
    for slider in flow.SLIDERS:
        assert len(slider["labels"]) == 5 and slider["labels"][2] == "As it is"


def test_unanswered_sections_say_so_instead_of_being_left_for_the_ai_to_fill():
    prompt = writer.build_prompt(writer.validate_answers({"what_happened": "Mom fell."}))
    assert "WHAT HAPPENS NEXT (author's own words):\n(not provided)" in prompt
    assert "STAYING IN TOUCH:\n(not provided)" in prompt


def test_rewrite_prompt_adds_draft_sliders_and_instruction():
    answers = writer.validate_answers(ANSWERS)
    adjustments = writer.validate_adjustments({"length": 1, "wording": 5, "extra": "mention the tulips"})
    prompt = writer.build_prompt(answers, {"title": "My edit", "post": "Hand edited text."}, adjustments)
    assert "Title: My edit" in prompt and "Hand edited text." in prompt
    assert writer.slider_text("length", 1) in prompt
    assert writer.slider_text("wording", 5) in prompt
    assert "mention the tulips" in prompt
    assert writer.SLIDER_WORDS["tone"][5] not in prompt  # tone was left at 3


def test_reply_parsing():
    assert writer.parse_post('{"title": "Hello", "post": "Body."}') == ("Hello", "Body.")
    assert writer.parse_post('```json\n{"title": "Hi", "post": "Body."}\n```') == ("Hi", "Body.")
    assert writer.parse_post("Just a title\nAnd then the body.") == ("Just a title", "And then the body.")
    assert writer.parse_post("One lonely line") == ("", "One lonely line")


def test_contact_details_are_flagged():
    kinds = [f["kind"] for f in writer.privacy_flags("Call 555-123-4567 or mail mom@example.com, we're at 42 Maple Street.")]
    assert kinds == ["phone number", "email address", "street address"]
    assert writer.privacy_flags("She had surgery on Tuesday.") == []


def test_first_draft_makes_one_call(fake_ai):
    draft = writer.first_draft(ANSWERS)
    assert draft == {"title": "A new chapter", "post": "We got news this week.", "privacy_flags": []}
    assert len(fake_ai.calls) == 1
    assert "never invent" in fake_ai.calls[0]["system"].lower()


def test_regenerate_makes_exactly_one_call_and_carries_the_edits(fake_ai):
    writer.regenerate(ANSWERS, {"title": "T", "post": "My own edit."}, {"tone": 5, "extra": "keep it short"})
    assert len(fake_ai.calls) == 1
    assert "My own edit." in fake_ai.calls[0]["user"] and "keep it short" in fake_ai.calls[0]["user"]


def test_regenerate_needs_a_draft(fake_ai):
    with pytest.raises(ValueError, match="no draft"):
        writer.regenerate(ANSWERS, {"title": "", "post": " "}, {})
    assert fake_ai.calls == []
