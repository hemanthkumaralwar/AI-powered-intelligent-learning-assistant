"""Lesson quizzes: the order each student sees the options in, and marking (pure functions).

The course file puts the correct answer second in most questions, so options are shuffled.
The order is fixed per student and question (seeded from both ids), so it stays the same
across page reloads and retakes. Options keep their original index as their id: the
answers are shown after every attempt anyway, so hiding the index would protect nothing.
"""

import hashlib
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.db.models import QuizQuestion


class InvalidAnswersError(ValueError):
    """Answers name a question outside this quiz, or an option the question does not have."""


@dataclass(frozen=True)
class QuestionResult:
    question_id: str
    chosen: int | None
    correct_option: int
    explanation: str | None

    @property
    def correct(self) -> bool:
        return self.chosen == self.correct_option


@dataclass(frozen=True)
class QuizMark:
    results: tuple[QuestionResult, ...]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def correct(self) -> int:
        return sum(result.correct for result in self.results)

    def answers(self) -> dict[str, int | None]:
        return {result.question_id: result.chosen for result in self.results}


def option_order(student_id: str, question: QuizQuestion) -> list[int]:
    """The question's option indexes in the order this student sees them."""
    seed = hashlib.sha256(f"{student_id}:{question.id}".encode()).digest()
    order = list(range(len(question.options)))
    random.Random(seed).shuffle(order)  # noqa: S311 - display order, not security
    return order


def mark(questions: Sequence[QuizQuestion], answers: Mapping[str, int | None]) -> QuizMark:
    """Mark every question of the quiz; a question left out counts as unanswered (wrong)."""
    by_id = {str(question.id): question for question in questions}
    if set(answers) - set(by_id):
        raise InvalidAnswersError("Some answers are for questions that are not in this quiz.")
    for question_id, chosen in answers.items():
        if chosen is not None and not 0 <= chosen < len(by_id[question_id].options):
            raise InvalidAnswersError("An answer names an option the question does not have.")
    return QuizMark(
        tuple(
            QuestionResult(
                question_id=question_id,
                chosen=answers.get(question_id),
                correct_option=question.correct_index,
                explanation=question.explanation,
            )
            for question_id, question in by_id.items()
        )
    )
