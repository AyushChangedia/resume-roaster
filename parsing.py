"""
Turning the model's reply into fields.

The prompt asks for four labelled sections, and until now the whole blob was
handed to the browser as one string for `white-space: pre-wrap` to deal with.
That works right up until you want the score in a big red number, or a copy
button on just the roast, or to notice that the model skipped a section.

Parsing here rather than in JavaScript keeps one implementation, and lets a
malformed reply be a server-side fact rather than a rendering accident.
"""

from __future__ import annotations

import re
from typing import Optional

SECTIONS = ("SCORE", "MISSING", "ROAST", "VERDICT")

# A label at the start of a line, allowing for the bold the model sometimes
# adds unbidden. The emphasis can close on either side of the colon —
# "**ROAST:**" and "**ROAST**:" are both the same section as "ROAST:" — and
# the trailing pair has to be eaten or it survives into the section body.
_LABEL = re.compile(
    r"^[ \t]*\**[ \t]*(SCORE|MISSING|ROAST|VERDICT)[ \t]*\**[ \t]*:[ \t]*\**[ \t]*",
    re.IGNORECASE | re.MULTILINE,
)


class RoastFormatError(ValueError):
    """The model did not answer in the format it was asked for."""


def parse_roast(raw: str) -> dict:
    """
    Split a reply into its sections.

    Returns score (int), missing (str), roast (str), verdict (str) and the
    raw text. Raises RoastFormatError when a required section is absent —
    silently returning an empty roast would render as a blank box with no
    indication that anything went wrong.
    """
    text = (raw or "").strip()
    if not text:
        raise RoastFormatError("The model returned nothing at all.")

    matches = list(_LABEL.finditer(text))
    if not matches:
        raise RoastFormatError("The reply had none of the expected sections.")

    found: dict[str, str] = {}
    for index, match in enumerate(matches):
        label = match.group(1).upper()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        # First occurrence wins; a model that repeats a label is echoing the
        # template rather than answering twice.
        found.setdefault(label, body)

    missing_sections = [name for name in ("SCORE", "ROAST") if name not in found]
    if missing_sections:
        raise RoastFormatError(
            f"The reply was missing its {' and '.join(missing_sections)} section."
        )

    return {
        "score": _parse_score(found["SCORE"]),
        "missing": found.get("MISSING", ""),
        "roast": found["ROAST"],
        "verdict": found.get("VERDICT", ""),
        "raw": text,
    }


def _parse_score(value: str) -> Optional[int]:
    """
    The first integer in the score line, clamped to 0-100.

    The model mostly writes "SCORE: 42" but sometimes "42/100" or "42 (and
    that is generous)". Returns None rather than guessing when there is no
    number at all, so the UI can omit the badge instead of showing a zero the
    model never gave.
    """
    match = re.search(r"-?\d+", value)
    if not match:
        return None
    return max(0, min(100, int(match.group())))
