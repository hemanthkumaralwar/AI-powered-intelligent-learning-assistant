"""Mastery per lesson and module from graded exercise attempts and lesson quiz scores
(pure functions).

An exercise's score weights the student's attempts toward the most recent: the newest
counts 1, the one before it 1/2, then 1/4 and so on. Failing three times and then passing
scores 0.53, so recovering counts for more than old mistakes, and no clock is involved.

The lesson quiz (taken in this app) is scored the same way from each attempt's share of
correct answers, and counts as one more item next to the lesson's exercises. Activities on
the learning platform (drag and drop, card matching...) are not counted.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

# Each older attempt counts this much of the one after it.
RECENCY_FACTOR = 0.5


@dataclass(frozen=True)
class ExerciseInfo:
    id: str
    title: str
    kind: str


@dataclass(frozen=True)
class LessonInfo:
    id: str
    title: str
    exercises: tuple[ExerciseInfo, ...]
    # The lesson's activities on the learning platform (names and sizes only).
    practice: tuple[dict, ...] = ()


@dataclass(frozen=True)
class ModuleInfo:
    id: str
    title: str
    lessons: tuple[LessonInfo, ...]


@dataclass(frozen=True)
class LessonProgress:
    lesson: LessonInfo
    module_title: str
    # None: not started (no exercise attempted, quiz not taken), which is not 0%.
    mastery: float | None
    exercise_scores: dict[str, float] = field(default_factory=dict)
    # None: the lesson quiz has not been taken.
    quiz_score: float | None = None

    @property
    def started(self) -> bool:
        return self.mastery is not None


@dataclass(frozen=True)
class ModuleProgress:
    module: ModuleInfo
    mastery: float | None
    # Share of the module's lessons started (an exercise attempted or the quiz taken).
    coverage: float
    lessons: tuple[LessonProgress, ...]


def recent_score(results_newest_first: Sequence[float]) -> float:
    """Recency-weighted average of results from 0 to 1 (True and False count as 1 and 0);
    0.0 for no results (callers skip those items)."""
    weights = [RECENCY_FACTOR**age for age in range(len(results_newest_first))]
    if not weights:
        return 0.0
    total = sum(w * float(r) for w, r in zip(weights, results_newest_first, strict=True))
    return total / sum(weights)


def exercise_score(results_newest_first: Sequence[bool]) -> float:
    """Recency-weighted pass rate; 0.0 for no attempts (callers skip those exercises)."""
    return recent_score(results_newest_first)


def compute_progress(
    modules: Sequence[ModuleInfo],
    attempts: Mapping[str, Sequence[bool]],
    quizzes: Mapping[str, Sequence[float]] | None = None,
) -> list[ModuleProgress]:
    """`attempts`: exercise id -> that student's results, newest first. `quizzes`: lesson
    id -> that student's quiz scores (share correct), newest first."""
    return [_module_progress(module, attempts, quizzes or {}) for module in modules]


def _module_progress(
    module: ModuleInfo,
    attempts: Mapping[str, Sequence[bool]],
    quizzes: Mapping[str, Sequence[float]],
) -> ModuleProgress:
    lessons = tuple(
        _lesson_progress(lesson, module.title, attempts, quizzes) for lesson in module.lessons
    )
    started = [lesson.mastery for lesson in lessons if lesson.mastery is not None]
    return ModuleProgress(
        module=module,
        mastery=sum(started) / len(started) if started else None,
        coverage=len(started) / len(lessons) if lessons else 0.0,
        lessons=lessons,
    )


def _lesson_progress(
    lesson: LessonInfo,
    module_title: str,
    attempts: Mapping[str, Sequence[bool]],
    quizzes: Mapping[str, Sequence[float]],
) -> LessonProgress:
    scores = {
        exercise.id: exercise_score(attempts[exercise.id])
        for exercise in lesson.exercises
        if attempts.get(exercise.id)
    }
    quiz = recent_score(quizzes[lesson.id]) if quizzes.get(lesson.id) else None
    items = [*scores.values(), *([] if quiz is None else [quiz])]
    mastery = sum(items) / len(items) if items else None
    return LessonProgress(lesson, module_title, mastery, scores, quiz)
