import pytest

from app.rag.retriever import Retriever, Source

pytestmark = pytest.mark.anyio


async def test_keeps_hits_at_or_above_the_threshold_numbered_from_one(hit, fake_search) -> None:
    search = fake_search([hit(0.8), hit(0.63, section="Summary"), hit(0.62)])

    sources = await Retriever(search, k=5, min_score=0.63).retrieve("let?", "c1")

    assert [(s.number, s.section) for s in sources] == [(1, "Explanation"), (2, "Summary")]
    assert search.calls == [("let?", 5, "c1")]


async def test_nothing_relevant_gives_no_sources(hit, fake_search) -> None:
    sources = await Retriever(fake_search([hit(0.4)]), k=5, min_score=0.63).retrieve("docker?")

    assert sources == []


async def test_empty_index_gives_no_sources(fake_search) -> None:
    assert await Retriever(fake_search([]), k=5, min_score=0.0).retrieve("q") == []


def test_source_reads_titles_and_exercise_flag_from_metadata(hit) -> None:
    source = Source.from_hit(3, hit(kind="exercise", section="Practice exercises"))

    assert source.number == 3
    assert source.is_exercise
    assert (source.course_title, source.module_title, source.lesson_title) == (
        "JavaScript for Beginners",
        "Basics",
        "Variables",
    )


def test_source_falls_back_when_metadata_is_missing(hit) -> None:
    bare = hit(lesson_id=None)
    bare.metadata.clear()

    source = Source.from_hit(1, bare)

    assert (source.course_title, source.module_title, source.lesson_title) == (
        "javascript-beginner-v1",
        "",
        None,
    )
    assert not source.is_exercise
