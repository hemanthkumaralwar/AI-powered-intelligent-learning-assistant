"""Mastery per lesson and module from graded exercise attempts (pure functions).

Quiz and activity scores live on the learning platform, so mastery here comes from the
exercises solved in this app (bug hunts, mini challenges, interactive tasks).

An exercise's score weights the student's attempts toward the most recent: the newest
counts 1, the one before it 1/2, then 1/4 and so on. Failing three times and then passing
scores 0.53, so recovering counts for more than old mistakes, and no clock is involved.
"""

from collections.abc import Sequence
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
    # None: not started (no exercise of this lesson attempted yet), which is not 0%.
    mastery: float | None
    exercise_scores: dict[str, float] = field(default_factory=dict)

    @property
    def started(self) -> bool:
        return self.mastery is not None


@dataclass(frozen=True)
class ModuleProgress:
    module: ModuleInfo
    mastery: float | None
    # Share of the module's lessons with at least one attempted exercise.
    coverage: float
    lessons: tuple[LessonProgress, ...]


def exercise_score(results_newest_first: Sequence[bool]) -> float:
    """Recency-weighted pass rate; 0.0 for no attempts (callers skip those exercises)."""
    weights = [RECENCY_FACTOR**age for age in range(len(results_newest_first))]
    if not weights:
        return 0.0
    passed = sum(w for w, ok in zip(weights, results_newest_first, strict=True) if ok)
    return passed / sum(weights)


def compute_progress(
    modules: Sequence[ModuleInfo], attempts: dict[str, Sequence[bool]]
) -> list[ModuleProgress]:
    """`attempts`: exercise id -> that student's results, newest first."""
    return [_module_progress(module, attempts) for module in modules]


def _module_progress(module: ModuleInfo, attempts: dict[str, Sequence[bool]]) -> ModuleProgress:
    lessons = tuple(_lesson_progress(lesson, module.title, attempts) for lesson in module.lessons)
    started = [lesson.mastery for lesson in lessons if lesson.mastery is not None]
    return ModuleProgress(
        module=module,
        mastery=sum(started) / len(started) if started else None,
        coverage=len(started) / len(lessons) if lessons else 0.0,
        lessons=lessons,
    )


def _lesson_progress(
    lesson: LessonInfo, module_title: str, attempts: dict[str, Sequence[bool]]
) -> LessonProgress:
    scores = {
        exercise.id: exercise_score(attempts[exercise.id])
        for exercise in lesson.exercises
        if attempts.get(exercise.id)
    }
    mastery = sum(scores.values()) / len(scores) if scores else None
    return LessonProgress(lesson, module_title, mastery, scores)
