"""Fixtures shared by the rag tests."""

import pytest

from app.vectorstore.index import SearchHit

LESSON = "javascript-beginner-mod-1-lesson-1"


def make_hit(
    score: float = 0.8,
    *,
    lesson_id: str | None = LESSON,
    section: str = "Explanation",
    text: str = "let declares a block-scoped variable.",
    kind: str = "content",
) -> SearchHit:
    return SearchHit(
        chunk_id=f"{lesson_id}-{section}-{score}",
        score=score,
        course_id="javascript-beginner-v1",
        lesson_id=lesson_id,
        section=section,
        text=text,
        metadata={
            "type": kind,
            "course_title": "JavaScript for Beginners",
            "module_title": "Basics",
            "lesson_title": "Variables" if lesson_id else None,
        },
    )


class FakeSearch:
    """Returns canned hits and records each call."""

    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits
        self.calls: list[tuple[str, int, str | None]] = []

    async def __call__(self, query: str, k: int, course_id: str | None) -> list[SearchHit]:
        self.calls.append((query, k, course_id))
        return self.hits[:k]


@pytest.fixture
def hit():
    return make_hit


@pytest.fixture
def fake_search():
    return FakeSearch
