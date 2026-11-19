"""Practice pointers: "quiz me" detection, and pointers built from stored lessons."""

import pytest

from app.db.models import Course, Lesson, Module
from app.db.session import Database
from app.learning.practice import Activity, PracticeFinder, is_practice_request

pytestmark = pytest.mark.anyio

PRACTICE = [
    {"kind": "quiz", "title": "Quiz", "count": 10},
    {"kind": "drag_and_drop", "title": "Sort: const vs let", "count": 6},
]


@pytest.mark.parametrize(
    "question",
    [
        "Quiz me on closures",
        "can you test me about arrays?",
        "Give me a quiz on loops",
        "show me some practice questions about promises",
        "I want practice exercises for map",
        "Any MCQs on let and const?",
        "multiple-choice questions on objects please",
    ],
)
def test_practice_requests_are_recognised(question: str) -> None:
    assert is_practice_request(question)


@pytest.mark.parametrize(
    "question",
    [
        "What is a closure?",
        "How do I test whether an array is empty?",
        "Why is my quiz score variable undefined?",
        "Explain the practice exercise about map",
    ],
)
def test_ordinary_questions_are_not(question: str) -> None:
    assert not is_practice_request(question)


@pytest.fixture
async def lessons(database: Database) -> Database:
    async with database.session() as session:
        session.add(Course(id="js", title="JS", language="javascript"))
        session.add(Module(id="m1", course_id="js", position=1, title="Basics"))
        session.add(
            Lesson(
                id="l1",
                module_id="m1",
                position=1,
                title="Variables",
                content={"practice": PRACTICE},
            )
        )
        session.add(
            Lesson(
                id="l2",
                module_id="m1",
                position=2,
                title="Loops",
                content={"practice": PRACTICE[:1]},
            )
        )
        session.add(Lesson(id="l3", module_id="m1", position=3, title="No activities", content={}))
    return database


async def test_pointers_follow_the_given_order_skip_empty_and_cap(lessons: Database) -> None:
    finder = PracticeFinder()
    async with lessons.session() as session:
        pointers = await finder.for_lessons(session, ["l2", None, "l3", "l2", "missing", "l1"])

    assert [p.lesson_id for p in pointers] == ["l2", "l1"]
    assert pointers[0].activities == (Activity("quiz", "Quiz", 10),)
    assert pointers[1].lesson_title == "Variables"
    assert pointers[0].url is None


async def test_links_use_the_platform_template(lessons: Database) -> None:
    finder = PracticeFinder("https://learn.example/lessons/{lesson_id}#practice")
    async with lessons.session() as session:
        (pointer,) = await finder.for_lessons(session, ["l1"])

    assert pointer.url == "https://learn.example/lessons/l1#practice"


async def test_no_lessons_means_no_query(lessons: Database) -> None:
    async with lessons.session() as session:
        assert await PracticeFinder().for_lessons(session, []) == []
