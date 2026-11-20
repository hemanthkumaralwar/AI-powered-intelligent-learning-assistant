"""Turns a question into numbered course sources that clear the similarity threshold."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.vectorstore.index import SearchHit

type Search = Callable[[str, int, str | None], Awaitable[list[SearchHit]]]


@dataclass(frozen=True)
class Source:
    """One retrieved chunk, numbered from 1 in the order the model sees it."""

    number: int
    score: float
    text: str
    course_title: str
    module_title: str
    lesson_id: str | None
    lesson_title: str | None
    section: str
    is_exercise: bool
    course_id: str | None = None

    @classmethod
    def from_hit(cls, number: int, hit: SearchHit) -> "Source":
        metadata = hit.metadata
        return cls(
            number=number,
            score=hit.score,
            text=hit.text,
            course_title=metadata.get("course_title") or hit.course_id,
            module_title=metadata.get("module_title") or "",
            lesson_id=hit.lesson_id,
            lesson_title=metadata.get("lesson_title"),
            section=hit.section,
            is_exercise=metadata.get("type") == "exercise",
            course_id=hit.course_id,
        )


class Retriever:
    def __init__(self, search: Search, k: int, min_score: float) -> None:
        self._search = search
        self._k = k
        self._min_score = min_score

    async def retrieve(self, question: str, course_id: str | None = None) -> list[Source]:
        """The top-k chunks scoring at least `min_score`; empty means "not in the course"."""
        hits = await self._search(question, self._k, course_id)
        relevant = [hit for hit in hits if hit.score >= self._min_score]
        return [Source.from_hit(n, hit) for n, hit in enumerate(relevant, start=1)]
