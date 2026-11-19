"""Spot when submitted code is a course exercise, so its solution is never given away.

Best effort: whitespace-insensitive similarity against the course's exercise code. A
heavily rewritten copy will not match (documented in PLAN.md); the prompt's hints-only
rule for exercises is the second line of defence.
"""

from collections.abc import Iterable
from difflib import SequenceMatcher

# Measured on the JavaScript course's 64 bug hunts: renaming two identifiers keeps the
# ratio at 0.82-0.98 (median 0.93); different bug hunts score a median 0.34 and 0.61 at
# the 99th percentile (the few above 0.8 are near-duplicate exercises, rightly matched).
SIMILARITY_THRESHOLD = 0.8


def matches_exercise(code: str, exercise_code: Iterable[str]) -> bool:
    """True when `code` is at least `SIMILARITY_THRESHOLD` similar to any exercise."""
    submitted = _normalise(code)
    for candidate in exercise_code:
        known = _normalise(candidate)
        if not known:
            continue
        matcher = SequenceMatcher(None, submitted, known, autojunk=False)
        # The cheap upper bounds skip most candidates before the full comparison.
        if (
            matcher.real_quick_ratio() >= SIMILARITY_THRESHOLD
            and matcher.quick_ratio() >= SIMILARITY_THRESHOLD
            and matcher.ratio() >= SIMILARITY_THRESHOLD
        ):
            return True
    return False


def _normalise(code: str) -> str:
    return " ".join(code.split())
