"""Explanation levels shared by the chat and coding prompts.

A level only changes depth, vocabulary and length. It is appended after a prompt's rules
and says so explicitly, so no level can loosen grounding, citations, refusals or the
hints-only rule for course exercises.
"""

from typing import Literal, get_args

Level = Literal["beginner", "intermediate", "advanced"]
LEVELS: tuple[Level, ...] = get_args(Level)
# The courses are beginner courses, so a new account starts here.
DEFAULT_LEVEL: Level = "beginner"

_GUIDANCE: dict[Level, str] = {
    "beginner": (
        "The student is a beginner. Use plain words and define every technical term the "
        "first time you use it. Go step by step, use a small everyday analogy when it "
        "helps, and keep code examples short with a comment on each important line."
    ),
    "intermediate": (
        "The student knows the basics. Use normal technical terms without defining the "
        "common ones, explain the reasoning behind the answer, and mention one common "
        "pitfall or best practice where it fits."
    ),
    "advanced": (
        "The student is experienced. Be concise and precise: skip basic definitions, "
        "focus on edge cases, trade-offs and how things work under the hood, and use "
        "exact terminology."
    ),
}


def level_guidance(level: Level) -> str:
    """The block to append to a system prompt, after all of its rules."""
    return (
        f"Explanation level: {level}. {_GUIDANCE[level]}\n"
        "The level changes only depth and wording; every rule above still applies."
    )
