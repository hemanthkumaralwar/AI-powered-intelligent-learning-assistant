"""`CodingService`: explain, debug, example and practice as validated JSON.

Each request: quota → one structured LLM call (retried once if the reply is not valid
JSON for the schema) → server-side clean-up (line numbers checked against the code,
text trimmed) → related course lessons found from the model's `concepts`.
"""

import logging
from collections.abc import Hashable, Sequence
from dataclasses import dataclass, field

from app.coding import prompts
from app.coding.exercises import matches_exercise
from app.coding.schemas import (
    CodingOutput,
    DebugOutput,
    ExampleOutput,
    ExplainOutput,
    PracticeOutput,
)
from app.core.quota import Quota
from app.llm.base import ChatMessage, GenerationOptions
from app.llm.client import LLMClient
from app.llm.prompt_levels import DEFAULT_LEVEL, Level
from app.providers.errors import InvalidResponseError, ProviderCallError
from app.rag.retriever import Retriever, Source

logger = logging.getLogger(__name__)

CODING_OPTIONS = GenerationOptions(temperature=0.2, max_output_tokens=3000)
MAX_RELATED_LESSONS = 3
MAX_CONCEPTS = 3
# Long model text is cut so one runaway field cannot bloat a response.
MAX_TEXT_CHARS = 2000
MAX_CODE_CHARS = 12_000
MAX_PRACTICE_QUESTIONS = 5


@dataclass(frozen=True)
class RelatedLesson:
    lesson_id: str
    lesson_title: str | None
    module_title: str
    course_title: str

    @property
    def link(self) -> str:
        return f"/lessons/{self.lesson_id}"


@dataclass(frozen=True)
class CodingResult[OutputT: CodingOutput]:
    output: OutputT
    related_lessons: list[RelatedLesson] = field(default_factory=list)
    # Debug only: the code matched a course exercise, so only hints were given.
    exercise: bool = False


class CodingService:
    def __init__(self, llm: LLMClient, quota: Quota, retriever: Retriever) -> None:
        self._llm = llm
        self._quota = quota
        self._retriever = retriever

    async def explain(
        self, user_key: Hashable, language: str, code: str, level: Level = DEFAULT_LEVEL
    ) -> CodingResult[ExplainOutput]:
        self._quota.consume(user_key)
        messages = prompts.code_messages(prompts.EXPLAIN, language, code, level=level)
        output = await self._generate(messages, ExplainOutput)
        lines = len(code.splitlines())
        output.lines = sorted(
            (note for note in output.lines if 1 <= note.line <= lines), key=lambda n: n.line
        )
        for note in output.lines:
            note.explanation = _cut(note.explanation)
        output.summary = _cut(output.summary)
        return await self._finish(output, language)

    async def debug(
        self,
        user_key: Hashable,
        language: str,
        code: str,
        run_output: str | None,
        exercise_code: Sequence[str],
        level: Level = DEFAULT_LEVEL,
    ) -> CodingResult[DebugOutput]:
        """`exercise_code`: the course's exercise code in this language. A match switches
        to hints only, and `corrected_code` is forced to null whatever the model says."""
        self._quota.consume(user_key)
        exercise = matches_exercise(code, exercise_code)
        system = prompts.DEBUG_HINTS_ONLY if exercise else prompts.DEBUG
        messages = prompts.code_messages(system, language, code, run_output, level)
        output = await self._generate(messages, DebugOutput)
        lines = len(code.splitlines())
        output.issues = sorted(
            (issue for issue in output.issues if 1 <= issue.line <= lines),
            key=lambda i: i.line,
        )
        for issue in output.issues:
            issue.problem, issue.fix_hint = _cut(issue.problem), _cut(issue.fix_hint)
        output.summary = _cut(output.summary)
        if exercise or output.corrected_code is None:
            output.corrected_code = None
        else:
            output.corrected_code = output.corrected_code[:MAX_CODE_CHARS]
        return await self._finish(output, language, exercise=exercise)

    async def example(
        self, user_key: Hashable, language: str, topic: str, level: Level = DEFAULT_LEVEL
    ) -> CodingResult[ExampleOutput]:
        self._quota.consume(user_key)
        messages = prompts.topic_messages(prompts.EXAMPLE, language, topic, level)
        output = await self._generate(messages, ExampleOutput)
        output.title = _cut(output.title, 200)
        output.code = output.code[:MAX_CODE_CHARS]
        output.explanation = _cut(output.explanation)
        return await self._finish(output, language)

    async def practice(
        self, user_key: Hashable, language: str, topic: str, level: Level = DEFAULT_LEVEL
    ) -> CodingResult[PracticeOutput]:
        self._quota.consume(user_key)
        messages = prompts.topic_messages(prompts.PRACTICE, language, topic, level)
        output = await self._generate(messages, PracticeOutput)
        output.questions = output.questions[:MAX_PRACTICE_QUESTIONS]
        for question in output.questions:
            question.question = _cut(question.question)
            question.hints = [_cut(hint) for hint in question.hints[:3]]
        return await self._finish(output, language)

    async def _generate[OutputT: CodingOutput](
        self, messages: list[ChatMessage], schema: type[OutputT]
    ) -> OutputT:
        """One retry when the reply is not valid JSON for `schema`; then the error stands."""
        try:
            return await self._llm.generate_json(messages, schema, CODING_OPTIONS)
        except InvalidResponseError:
            logger.info("coding reply did not match %s; retrying once", schema.__name__)
            return await self._llm.generate_json(messages, schema, CODING_OPTIONS)

    async def _finish[OutputT: CodingOutput](
        self, output: OutputT, language: str, *, exercise: bool = False
    ) -> CodingResult[OutputT]:
        concepts = [c.strip() for c in output.concepts if c.strip()]
        related = await self._related(language, concepts[:MAX_CONCEPTS])
        # Metadata only: student code and model output are never logged.
        logger.info(
            "coding answer kind=%s language=%s related=%d",
            type(output).__name__,
            language,
            len(related),
        )
        return CodingResult(output, related, exercise=exercise)

    async def _related(self, language: str, concepts: list[str]) -> list[RelatedLesson]:
        """Course lessons about the concepts (one embedding), best match first, no repeats.

        An extra, not the answer: if the embedding provider fails (e.g. its daily quota
        is used up), the student still gets the explanation, just without lessons."""
        if not concepts:
            return []
        query = f"{prompts.LANGUAGE_NAMES[language]}: {', '.join(concepts)}"
        try:
            sources = await self._retriever.retrieve(query)
        except ProviderCallError as exc:
            logger.warning("related lessons skipped: %s", type(exc).__name__)
            return []
        lessons: dict[str, RelatedLesson] = {}
        for source in sources:
            if source.lesson_id and source.lesson_id not in lessons:
                lessons[source.lesson_id] = _lesson(source.lesson_id, source)
        return list(lessons.values())[:MAX_RELATED_LESSONS]


def _lesson(lesson_id: str, source: Source) -> RelatedLesson:
    return RelatedLesson(
        lesson_id=lesson_id,
        lesson_title=source.lesson_title,
        module_title=source.module_title,
        course_title=source.course_title,
    )


def _cut(text: str, limit: int = MAX_TEXT_CHARS) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"
