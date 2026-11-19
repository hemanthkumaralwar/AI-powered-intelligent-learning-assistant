"""Pointers to the learning platform's practice activities for a lesson.

Quizzes, drag and drop, card matching and code reordering run on the learning platform,
not here; answers never pass through the assistant (the Step 9 rule). The assistant only
names the activities a lesson has (from `lessons.content["practice"]`, written at
ingestion) and, when PLATFORM_LESSON_URL is set, links to the lesson there.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.courses import CourseRepository

# One or two lessons are useful; more turns a pointer into a reading list.
MAX_POINTERS = 2

# Requests to be quizzed or given practice questions. The chat sends these to the
# platform instead of writing questions (and answers) into the conversation.
# "Exercise" alone is not enough: "explain the practice exercise" is a question about a
# lesson, not a request to be quizzed, so it needs a request verb in front.
_PRACTICE_REQUEST = re.compile(
    r"\b(quiz|test)\s+me\b"
    r"|\b(give|show|send)\s+me\s+(a\s+|some\s+|more\s+)?(quiz|quizzes|mcqs?|practice|exercises?)\b"
    r"|\b(want|need|more)\s+(some\s+)?(practice|quiz|quizzes|exercises|mcqs?)\b"
    r"|\bpractice\s+(questions?|quiz|quizzes|tests?)\b"
    r"|\b(mcqs?|multiple[-\s]choice)\b",
    re.IGNORECASE,
)


def is_practice_request(question: str) -> bool:
    return bool(_PRACTICE_REQUEST.search(question))


@dataclass(frozen=True)
class Activity:
    kind: str
    title: str
    count: int


@dataclass(frozen=True)
class PracticePointer:
    lesson_id: str
    lesson_title: str
    activities: tuple[Activity, ...]
    url: str | None


class PracticeFinder:
    def __init__(self, lesson_url_template: str | None = None) -> None:
        self._template = lesson_url_template

    async def for_lessons(
        self, session: AsyncSession, lesson_ids: Sequence[str | None]
    ) -> list[PracticePointer]:
        """Pointers for the first `MAX_POINTERS` distinct lessons that have activities,
        in the order given (most relevant first)."""
        wanted = list(dict.fromkeys(lid for lid in lesson_ids if lid))
        lessons = {
            lesson.id: lesson for lesson in await CourseRepository(session).lessons_by_ids(wanted)
        }
        pointers = []
        for lesson_id in wanted:
            lesson = lessons.get(lesson_id)
            activities = _activities(lesson.content) if lesson else ()
            if activities:
                pointers.append(
                    PracticePointer(lesson_id, lesson.title, activities, self.url(lesson_id))
                )
        return pointers[:MAX_POINTERS]

    def url(self, lesson_id: str) -> str | None:
        """The lesson on the learning platform, when PLATFORM_LESSON_URL is set."""
        if self._template is None:
            return None
        # replace, not str.format: a template with other braces must not break or inject.
        return self._template.replace("{lesson_id}", quote(lesson_id, safe=""))


def _activities(content: dict) -> tuple[Activity, ...]:
    return tuple(
        Activity(str(item["kind"]), str(item["title"]), int(item["count"]))
        for item in content.get("practice", [])
    )
