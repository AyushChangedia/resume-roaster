"""
The prompt is the product, and it is the thing most likely to soften.

Nobody breaks a prompt on purpose. It happens by editing: a section gets
tweaked, a rule gets rephrased more gently, "brutal" quietly becomes "honest",
and the app ends up encouraging again with every commit looking reasonable in
isolation. These tests are the ratchet.
"""

import re

import pytest

from prompt import SYSTEM_PROMPT, build_user_prompt

LOWER = SYSTEM_PROMPT.lower()


def section_names() -> list[str]:
    """
    The output fields the prompt asks for, in order.

    Only the four labels parsing.py knows how to read — the prompt also has
    all-caps headings like RULES: and SCORING CURVE: that instruct the model
    rather than naming an output section.
    """
    return re.findall(r"^(SCORE|MISSING|ROAST|VERDICT):", SYSTEM_PROMPT, re.MULTILINE)


# --------------------------------------------------------------- the format --


def test_the_output_format_is_exactly_the_four_sections():
    assert section_names() == ["SCORE", "MISSING", "ROAST", "VERDICT"]


def test_there_is_no_strengths_section():
    # The point of the whole change: no field whose job is to feel good.
    assert "STRENGTHS:" not in SYSTEM_PROMPT
    assert "STRENGTHS: <" not in SYSTEM_PROMPT


def test_the_verdict_comes_last():
    # It is the line the reader is left with; a section after it would blunt it.
    assert section_names()[-1] == "VERDICT"


# ------------------------------------------------------------------ the tone --


@pytest.mark.parametrize(
    "phrase",
    [
        "no praise",
        "no strengths section",
        "no compliments",
        "no encouraging closing line",
    ],
)
def test_praise_is_banned_explicitly(phrase):
    # Deleting the STRENGTHS field is not enough. A model trained to be helpful
    # reintroduces praise on its own — a "but your Python is solid" welded onto
    # the end of the roast — unless it is told not to.
    assert phrase in LOWER


def test_hedging_is_banned():
    assert "no hedging" in LOWER
    for weasel in ("arguably", "somewhat", "might be"):
        assert weasel in LOWER, f"{weasel} should be named as a banned hedge"


@pytest.mark.parametrize("word", ["savage", "cruel", "hurt", "rejected"])
def test_the_persona_is_still_the_harsh_one(word):
    # If these drift out, someone has softened the persona by degrees — which
    # is how it would happen, one reasonable-looking edit at a time.
    assert word in LOWER


@pytest.mark.parametrize("word", ["helpful", "constructive", "gentle", "supportive"])
def test_the_prompt_never_asks_for_kindness(word):
    # "gentle" appears in the old prompt only as "never gentle"; if it shows up
    # at all now it deserves a look, so the word is banned outright.
    assert word not in LOWER, f'the prompt should not contain "{word}"'


def test_advice_is_banned():
    # A roast that tells you how to fix it is a career counselor in a costume.
    assert "no advice" in LOWER
    assert '"you should"' in LOWER


# ------------------------------------------------------------ the guardrail --


def test_the_roast_is_aimed_at_the_document_not_the_person():
    # The one line that must survive every future sharpening: this attacks the
    # resume and the choices in it. An insult about who somebody is stops being
    # about the only thing here anyone can fix.
    assert "never the person's identity" in LOWER
    for protected in ("background", "nationality", "worth as a human being"):
        assert protected in LOWER, f"{protected} should be named as off limits"


# ---------------------------------------------------------------- specificity --


def test_specificity_is_required_rather_than_suggested():
    # Generic insults slide off. Naming the actual internship does not, and it
    # is also the only thing that makes the output worth reading.
    assert "must name something real" in LOWER
    assert "could apply to somebody else's resume" in LOWER


def test_the_roast_asks_for_five_sentences():
    assert "5 sentences" in LOWER


# -------------------------------------------------------------- the scoring --


def test_the_score_has_a_defined_curve_rather_than_a_bare_range():
    # "0-100" with no definition let the model anchor around a comfortable 70.
    assert "scoring curve" in LOWER
    for band in ("90-100", "70-89", "50-69", "30-49", "0-29"):
        assert band in SYSTEM_PROMPT, f"band {band} is missing from the curve"


def test_the_generosity_traps_are_named():
    assert "coursework is not experience" in LOWER
    assert "never round up to be kind" in LOWER
    assert "does not score above 55" in LOWER


# -------------------------------------------------------------- the user turn --


def test_the_user_prompt_labels_both_documents():
    built = build_user_prompt("MY RESUME", "THE JOB")
    assert "RESUME:\nMY RESUME" in built
    assert "JOB DESCRIPTION:\nTHE JOB" in built


def test_the_user_prompt_passes_the_documents_through_untouched():
    # No trimming, no truncation here — app.py has already validated length,
    # and quietly cutting a resume would change the roast without saying so.
    resume = "  Ayush\n\n\tTabbed bullet  "
    assert resume in build_user_prompt(resume, "jd")
