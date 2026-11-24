"""Quiz option order and marking (pure functions, no database)."""

import uuid

import pytest

from app.db.models import QuizQuestion
from app.learning.quiz import InvalidAnswersError, mark, option_order


def question(correct: int, options: int = 4, explanation: str | None = "Because.") -> QuizQuestion:
    return QuizQuestion(
        id=uuid.uuid4(),
        lesson_id="l1",
        position=1,
        question="Which?",
        options=[f"option {i}" for i in range(options)],
        correct_index=correct,
        explanation=explanation,
    )


def test_option_order_is_a_stable_shuffle_per_student() -> None:
    item = question(1, options=6)

    order = option_order("student-a", item)

    assert sorted(order) == list(range(6))
    assert option_order("student-a", item) == order  # same on every reload


def test_option_order_differs_between_students() -> None:
    item = question(1, options=6)

    orders = {tuple(option_order(f"student-{n}", item)) for n in range(20)}

    assert len(orders) > 1


def test_correct_answer_is_not_always_in_the_same_place() -> None:
    # The course file puts most correct answers second; shuffling spreads them out.
    places = {option_order("student-a", question(1)).index(1) for _ in range(30)}

    assert len(places) > 1


def test_mark_counts_correct_answers_and_keeps_explanations() -> None:
    first, second, third = question(0), question(2), question(1, explanation=None)

    marked = mark([first, second, third], {str(first.id): 0, str(second.id): 1, str(third.id): 1})

    assert (marked.correct, marked.total) == (2, 3)
    assert [r.correct for r in marked.results] == [True, False, True]
    assert marked.results[1].correct_option == 2
    assert marked.results[0].explanation == "Because."
    assert marked.answers() == {str(first.id): 0, str(second.id): 1, str(third.id): 1}


def test_unanswered_questions_count_as_wrong() -> None:
    first, second = question(0), question(1)

    marked = mark([first, second], {str(first.id): 0, str(second.id): None})

    assert (marked.correct, marked.total) == (1, 2)
    assert marked.answers() == {str(first.id): 0, str(second.id): None}


def test_left_out_questions_count_as_wrong() -> None:
    first, second = question(0), question(1)

    marked = mark([first, second], {str(first.id): 0})

    assert (marked.correct, marked.total) == (1, 2)
    assert marked.results[1].chosen is None


def test_answers_for_other_questions_are_refused() -> None:
    with pytest.raises(InvalidAnswersError, match="not in this quiz"):
        mark([question(0)], {str(uuid.uuid4()): 0})


@pytest.mark.parametrize("chosen", [-1, 4, 99])
def test_options_the_question_does_not_have_are_refused(chosen: int) -> None:
    item = question(0)

    with pytest.raises(InvalidAnswersError, match="option"):
        mark([item], {str(item.id): chosen})
