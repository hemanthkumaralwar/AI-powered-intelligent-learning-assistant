import pytest

from app.rag.citations import resolve_markers


@pytest.mark.parametrize(
    ("text", "count", "expected_text", "expected_cited"),
    [
        ("let is block-scoped [1].", 2, "let is block-scoped [1].", [1]),
        ("A [2]. B [1][2].", 2, "A [2]. B [1][2].", [2, 1]),
        ("Made up [7]. Real [1].", 2, "Made up . Real [1].", [1]),
        ("Zero [0] is never a source.", 2, "Zero  is never a source.", []),
        ("No markers at all.", 2, "No markers at all.", []),
    ],
    ids=["one", "order-and-dedupe", "invalid-dropped", "zero", "none"],
)
def test_markers(text: str, count: int, expected_text: str, expected_cited: list[int]) -> None:
    assert resolve_markers(text, count) == (expected_text, expected_cited)


def test_code_is_never_treated_as_a_citation() -> None:
    text = "Use `arr[1]` [1].\n```js\nconst x = list[2];\nlist[9] = 0;\n```\nDone [2]."

    out, cited = resolve_markers(text, 2)

    assert out == text
    assert cited == [1, 2]


def test_unclosed_fence_protects_the_rest() -> None:
    text = "See [1].\n```js\nitems[2] = 1;"

    assert resolve_markers(text, 1) == (text, [1])
