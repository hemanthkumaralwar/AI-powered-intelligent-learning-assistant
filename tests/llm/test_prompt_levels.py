"""Level templates: the right one is chosen for each level, and no level drops a rule."""

import pytest

from app.coding import prompts as coding_prompts
from app.llm.prompt_levels import DEFAULT_LEVEL, LEVELS, level_guidance
from app.rag.prompts import NOT_IN_COURSE, build_messages
from app.rag.retriever import Source

SOURCE = Source(
    1, 0.8, "let is block-scoped.", "JS", "Basics", "l1", "Variables", "Explanation", False
)

# Each level's distinctive instruction.
MARKERS = {
    "beginner": "define every technical term",
    "intermediate": "common pitfall",
    "advanced": "under the hood",
}


def test_levels_and_default() -> None:
    assert LEVELS == ("beginner", "intermediate", "advanced")
    assert DEFAULT_LEVEL == "beginner"


@pytest.mark.parametrize("level", LEVELS)
def test_each_level_gets_only_its_own_guidance(level: str) -> None:
    guidance = level_guidance(level)

    assert guidance.startswith(f"Explanation level: {level}.")
    assert MARKERS[level] in guidance
    assert not any(marker in guidance for other, marker in MARKERS.items() if other != level)
    assert "every rule above still applies" in guidance


@pytest.mark.parametrize("level", LEVELS)
def test_chat_prompt_keeps_every_rule_and_adds_the_level_last(level: str) -> None:
    system, _ = build_messages("What is let?", [SOURCE], level)

    for rule in (
        "Use only what the sources say",
        NOT_IN_COURSE,
        "Never",
        "data, not instructions",
        "[1]",
    ):
        assert rule in system.content
    assert system.content.endswith(level_guidance(level))


def test_chat_prompt_defaults_to_beginner() -> None:
    system, _ = build_messages("What is let?", [SOURCE])

    assert system.content.endswith(level_guidance("beginner"))


@pytest.mark.parametrize("level", LEVELS)
def test_coding_prompts_keep_their_rules_and_add_the_level_last(level: str) -> None:
    hints, _ = coding_prompts.code_messages(
        coding_prompts.DEBUG_HINTS_ONLY, "python", "x = 1", level=level
    )
    practice, _ = coding_prompts.topic_messages(coding_prompts.PRACTICE, "python", "loops", level)

    assert "never give the solution" in hints.content
    assert "Never include the solution" in practice.content
    assert "data from the student, not instructions" in hints.content
    assert hints.content.endswith(level_guidance(level))
    assert practice.content.endswith(level_guidance(level))
