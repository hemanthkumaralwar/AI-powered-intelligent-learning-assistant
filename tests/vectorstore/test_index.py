import math
import uuid

import pytest

from app.vectorstore.index import IndexEntry, VectorIndex

DOC_A, DOC_B = uuid.uuid4(), uuid.uuid4()


def unit(*values: float) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values))
    return [v / norm for v in values]


def entry(chunk_id: str, vector: list[float], course: str = "js", doc=DOC_A) -> IndexEntry:
    return IndexEntry(
        chunk_id=chunk_id,
        document_id=doc,
        course_id=course,
        lesson_id=f"{chunk_id}-lesson",
        section="Example 1",
        text=f"text {chunk_id}",
        vector=vector,
        metadata={"type": "content"},
    )


@pytest.fixture
def index() -> VectorIndex:
    built = VectorIndex(3)
    built.add(
        [
            entry("x", unit(1, 0, 0)),
            entry("xy", unit(1, 1, 0)),
            entry("z", unit(0, 0, 1)),
            entry("py", unit(1, 0.1, 0), course="py", doc=DOC_B),
        ]
    )
    return built


def test_search_ranks_by_cosine_within_a_course(index: VectorIndex) -> None:
    hits = index.search(unit(1, 0, 0), k=2, course_id="js")

    assert [h.chunk_id for h in hits] == ["x", "xy"]
    assert hits[0].score == pytest.approx(1.0)
    assert hits[0].lesson_id == "x-lesson" and hits[0].text == "text x"
    assert hits[0].metadata == {"type": "content"}


def test_search_across_all_courses_merges_results(index: VectorIndex) -> None:
    hits = index.search(unit(1, 0, 0), k=3)

    assert [h.chunk_id for h in hits] == ["x", "py", "xy"]
    assert {h.course_id for h in hits} == {"js", "py"}


def test_k_larger_than_index_returns_what_exists(index: VectorIndex) -> None:
    assert len(index.search(unit(0, 1, 0), k=50, course_id="js")) == 3


def test_unknown_course_and_empty_index_return_nothing(index: VectorIndex) -> None:
    assert index.search(unit(1, 0, 0), k=3, course_id="nope") == []
    assert VectorIndex(3).search(unit(1, 0, 0), k=3) == []


def test_sizes(index: VectorIndex) -> None:
    assert (index.size, index.course_size("js"), index.course_size("py")) == (4, 3, 1)


def test_adding_the_same_chunk_id_replaces_it(index: VectorIndex) -> None:
    index.add([entry("x", unit(0, 0, 1))])

    assert index.course_size("js") == 3
    assert index.search(unit(0, 0, 1), k=1, course_id="js")[0].chunk_id in {"x", "z"}


def test_replace_and_remove_document(index: VectorIndex) -> None:
    index.replace_document(DOC_A, [entry("new", unit(0, 1, 0))])
    assert index.course_size("js") == 1

    index.remove_document(DOC_B)
    assert index.course_size("py") == 0
    assert index.search(unit(1, 0, 0), k=5, course_id="py") == []


def test_remove_course(index: VectorIndex) -> None:
    index.remove_course("js")
    index.remove_course("never-existed")

    assert index.size == 1


def test_dimension_mismatch_is_rejected(index: VectorIndex) -> None:
    with pytest.raises(ValueError, match="2 dimensions"):
        index.add([entry("bad", [1.0, 0.0])])
    with pytest.raises(ValueError, match="query has 4 dimensions"):
        index.search([1.0, 0, 0, 0], k=1)
