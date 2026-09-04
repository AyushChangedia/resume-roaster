"""
Parsing the model's reply.

This is the only place in the app where a wrong answer is silent. A bad parse
does not raise — it renders a blank card, or a score of 0 the model never
gave, and both look like the app working.
"""

import pytest

from parsing import RoastFormatError, parse_roast

WELL_FORMED = """SCORE: 34
MISSING: RAG, prompt engineering, SQL
ROAST: Your "AI Engineering Intern" bullet describes building a resume screener, which is this app.
Three internships in eighteen months and not one shipped thing anybody can open.
VERDICT: Next."""


def test_a_well_formed_reply_splits_into_its_sections():
    result = parse_roast(WELL_FORMED)
    assert result["score"] == 34
    assert result["missing"] == "RAG, prompt engineering, SQL"
    assert result["roast"].startswith('Your "AI Engineering Intern"')
    assert result["verdict"] == "Next."


def test_a_multi_line_roast_keeps_its_line_breaks():
    # The roast is five sentences and the page renders it pre-wrap.
    assert parse_roast(WELL_FORMED)["roast"].count("\n") == 1


def test_the_raw_reply_is_preserved():
    assert parse_roast(WELL_FORMED)["raw"] == WELL_FORMED.strip()


@pytest.mark.parametrize(
    "line, expected",
    [
        ("SCORE: 42", 42),
        ("SCORE: 42/100", 42),
        ("SCORE: 42 (and that is generous)", 42),
        ("SCORE: 0", 0),
        ("SCORE: 100", 100),
    ],
)
def test_the_score_survives_how_the_model_actually_writes_it(line, expected):
    assert parse_roast(f"{line}\nROAST: ouch")["score"] == expected


@pytest.mark.parametrize("value, expected", [("SCORE: 140", 100), ("SCORE: -5", 0)])
def test_an_out_of_range_score_is_clamped(value, expected):
    # A 140 would overflow the badge; a negative would render as "-5".
    assert parse_roast(f"{value}\nROAST: ouch")["score"] == expected


def test_a_score_line_with_no_number_is_none_not_zero():
    # Zero is a real, damning score. Showing one the model never gave is worse
    # than showing no badge at all.
    assert parse_roast("SCORE: unscoreable\nROAST: ouch")["score"] is None


def test_bold_labels_are_understood():
    # The model adds markdown emphasis unbidden, and reasonably often.
    result = parse_roast("**SCORE:** 12\n**ROAST:** ouch\n**VERDICT:** No.")
    assert result["score"] == 12
    assert result["verdict"] == "No."


def test_lowercase_labels_are_understood():
    assert parse_roast("score: 12\nroast: ouch")["score"] == 12


def test_a_repeated_label_takes_the_first_occurrence():
    # A second copy is the model echoing the template, not answering twice.
    assert parse_roast("SCORE: 10\nROAST: real\nROAST: <template>")["roast"] == "real"


def test_optional_sections_are_empty_rather_than_absent():
    # The page checks truthiness; a missing key would throw instead.
    result = parse_roast("SCORE: 10\nROAST: ouch")
    assert result["missing"] == ""
    assert result["verdict"] == ""


@pytest.mark.parametrize(
    "raw",
    ["", "   \n  ", "This resume is bad and you should feel bad.", "MISSING: SQL"],
)
def test_a_reply_without_the_required_sections_raises(raw):
    # Silently returning an empty roast renders as a blank box with nothing to
    # say anything went wrong.
    with pytest.raises(RoastFormatError):
        parse_roast(raw)


def test_the_error_names_what_was_missing():
    with pytest.raises(RoastFormatError, match="SCORE and ROAST"):
        parse_roast("VERDICT: No.")


def test_none_is_handled_like_an_empty_reply():
    # The Groq SDK types message.content as optional.
    with pytest.raises(RoastFormatError):
        parse_roast(None)


def test_a_section_body_is_stripped_of_surrounding_whitespace():
    result = parse_roast("SCORE:   34  \nROAST:    ouch   \n\n")
    assert result["roast"] == "ouch"


def test_the_word_score_inside_the_roast_does_not_start_a_new_section():
    # Labels are only recognised at the start of a line, so a roast that says
    # "your score" mid-sentence does not truncate itself.
    roast = "Your score on this is generous. It says SCORE somewhere else too."
    assert parse_roast(f"SCORE: 10\nROAST: {roast}")["roast"] == roast


def test_emphasis_closing_before_the_colon_is_also_understood():
    # "**ROAST**:" as well as "**ROAST:**" — the model uses both.
    result = parse_roast("**SCORE**: 12\n**ROAST**: ouch\n**VERDICT**: No.")
    assert result["score"] == 12
    assert result["roast"] == "ouch"
    assert result["verdict"] == "No."
