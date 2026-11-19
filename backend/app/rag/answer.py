"""`AnswerService`: quota → rewrite follow-up → retrieve → grounded prompt → citations
checked by the server."""

import logging
from collections.abc import Hashable, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from app.core.quota import Quota
from app.learning.practice import is_practice_request
from app.llm.base import ChatMessage, GenerationOptions
from app.llm.client import LLMClient
from app.llm.prompt_levels import DEFAULT_LEVEL, Level
from app.rag.citations import resolve_markers
from app.rag.condense import Condenser
from app.rag.prompts import NOT_IN_COURSE, build_messages
from app.rag.retriever import Retriever, Source

logger = logging.getLogger(__name__)

REFUSAL = (
    "I couldn't find this in your course materials, so I can't answer it reliably. "
    "Try rephrasing your question, or ask about a topic covered in the course."
)

PRACTICE_REPLY = (
    "Practice activities for this topic are on the learning platform: try the ones listed "
    "below, then come back here if anything is unclear."
)

# answered: grounded and cited.
# practice: a request to be quizzed; the reply points to the lessons' activities on the
#   platform instead of writing questions (and their answers) into the chat.
# The rest are refusals:
# - no_relevant_material: nothing cleared the similarity threshold (no LLM call made)
# - not_in_sources: the model said the sources do not answer it
# - uncited: the model answered but cited no real source, so the answer is not shown
Outcome = Literal["answered", "practice", "no_relevant_material", "not_in_sources", "uncited"]

ANSWER_OPTIONS = GenerationOptions(temperature=0.2, max_output_tokens=1024)


@dataclass(frozen=True)
class Citation:
    number: int
    course_title: str
    module_title: str
    lesson_id: str | None
    lesson_title: str | None
    section: str
    score: float

    @property
    def link(self) -> str | None:
        """API path of the cited lesson; module overviews have no lesson page."""
        return f"/lessons/{self.lesson_id}" if self.lesson_id else None


@dataclass(frozen=True)
class Answer:
    text: str
    outcome: Outcome
    citations: tuple[Citation, ...] = ()
    # The question actually searched and answered, when a follow-up was rewritten.
    standalone: str | None = None

    @property
    def grounded(self) -> bool:
        """Course-based (an answer, or a pointer to the course's activities)."""
        return self.outcome in ("answered", "practice")


class AnswerService:
    def __init__(
        self,
        retriever: Retriever,
        llm: LLMClient,
        quota: Quota,
        condenser: Condenser,
        options: GenerationOptions = ANSWER_OPTIONS,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._quota = quota
        self._condenser = condenser
        self._options = options

    async def ask(
        self,
        user_key: Hashable,
        question: str,
        course_id: str | None = None,
        history: Sequence[ChatMessage] = (),
        level: Level = DEFAULT_LEVEL,
    ) -> Answer:
        """Answer from the course or refuse; a follow-up is first rewritten from `history`
        (oldest first). Raises `QuotaExceededError` (counted before any provider call)
        and `ProviderCallError` from the embedding or answering LLM call."""
        self._quota.consume(user_key)
        standalone = await self._condenser.condense(question, history)
        sources = await self._retriever.retrieve(standalone, course_id)
        if not sources:
            answer = Answer(REFUSAL, "no_relevant_material")
        elif is_practice_request(standalone):
            # The search still runs, to find which lessons the topic belongs to.
            answer = practice_pointer(sources)
        else:
            response = await self._llm.chat(
                build_messages(standalone, sources, level), self._options
            )
            answer = ground(response.text, sources)
        if standalone != question:
            answer = replace(answer, standalone=standalone)
        # Metadata only: questions and answers can contain personal data.
        logger.info(
            "chat answer outcome=%s sources=%d cited=%d rewritten=%s",
            answer.outcome,
            len(sources),
            len(answer.citations),
            answer.standalone is not None,
        )
        return answer


def practice_pointer(sources: Sequence[Source]) -> Answer:
    """The practice reply, citing the best-matching lessons (one citation per lesson)."""
    by_lesson: dict[str, Source] = {}
    for source in sources:
        if source.lesson_id and source.lesson_id not in by_lesson:
            by_lesson[source.lesson_id] = source
    if not by_lesson:
        return Answer(REFUSAL, "no_relevant_material")
    citations = tuple(_citation(source) for source in by_lesson.values())
    return Answer(PRACTICE_REPLY, "practice", citations)


def ground(reply: str, sources: Sequence[Source]) -> Answer:
    """Keep the reply only if it cites at least one real source; otherwise refuse."""
    if reply.strip().startswith(NOT_IN_COURSE):
        return Answer(REFUSAL, "not_in_sources")
    text, cited = resolve_markers(reply, len(sources))
    if not cited:
        return Answer(REFUSAL, "uncited")
    by_number = {source.number: source for source in sources}
    return Answer(text.strip(), "answered", tuple(_citation(by_number[n]) for n in cited))


def _citation(source: Source) -> Citation:
    return Citation(
        number=source.number,
        course_title=source.course_title,
        module_title=source.module_title,
        lesson_id=source.lesson_id,
        lesson_title=source.lesson_title,
        section=source.section,
        score=source.score,
    )
