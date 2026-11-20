"""Split a stored course into searchable chunks for RAG (pure: no database, no network).

What goes in: the answer-free teaching content stored in Step 8 (module and lesson
`content`), each lesson's flowchart, and the *prompt* parts of its exercises.
What never goes in: quiz questions and answers, bug-hunt fixes and explanations, and the
drag-and-drop / card-matching / code-reordering activities. Those are served and graded
through the API instead, so retrieval can never hand a student an answer.

Each chunk starts with a context header (course > module > lesson - section) so it reads
on its own; long sections are split by LangChain's recursive splitter with overlap.

Sections are deliberately coarse (examples packed together; analogy, story and use cases
combined; all exercise prompts in one chunk). The Gemini free tier counts every embedded
text against roughly 1,000 a day, so ~650 chunks per course instead of ~1,200 lets a
course be indexed in one day with room left for student questions.
"""

import hashlib
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.db.models import Course, Exercise, Lesson, Module
from app.db.repositories.chunks import NewChunk

MAX_BODY_CHARS = 1500
OVERLAP_CHARS = 150
# Header + body: ~450 tokens at most, far below the embedding model's 2,048-token limit.
MAX_CHUNK_CHARS = 1750
PARAGRAPH = "\n\n"


@dataclass(frozen=True)
class ChunkingConfig:
    """Size settings. Production uses DEFAULT_CHUNKING; the evaluation script compares
    other sizes offline (local embeddings) without touching the free quota."""

    max_body_chars: int = MAX_BODY_CHARS
    overlap_chars: int = OVERLAP_CHARS

    @property
    def max_chunk_chars(self) -> int:
        # Same header allowance as the defaults (1,750 - 1,500 = 250 characters).
        return self.max_body_chars + (MAX_CHUNK_CHARS - MAX_BODY_CHARS)

    def splitter(self) -> RecursiveCharacterTextSplitter:
        return RecursiveCharacterTextSplitter(
            chunk_size=self.max_body_chars,
            chunk_overlap=self.overlap_chars,
            # Paragraphs first, then lines, so code blocks stay together when they fit.
            separators=[PARAGRAPH, "\n", " ", ""],
        )


DEFAULT_CHUNKING = ChunkingConfig()

EXERCISE_TITLES = {
    "interactive": "Try it yourself",
    "mini_challenge": "Mini challenge",
    "bug_hunt": "Bug hunt",
}
_EXERCISE_ORDER = {kind: position for position, kind in enumerate(EXERCISE_TITLES)}


class ChunkTooLargeError(Exception):
    """A rendered chunk exceeds MAX_CHUNK_CHARS (a bug, never silently truncated)."""


@dataclass(frozen=True)
class Section:
    key: str  # stable within a document; part of the chunk id
    name: str  # human-readable, shown in the header and stored in `chunks.section`
    body: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Source:
    """Where a section comes from: its document, course, module and (if any) lesson."""

    document_id: uuid.UUID
    course: Course
    module: Module
    lesson: Lesson | None

    @property
    def trail(self) -> str:
        titles = (self.course.title, self.module.title, self.lesson and self.lesson.title)
        return " › ".join(t for t in titles if t)

    def metadata(self) -> dict[str, Any]:
        lesson = self.lesson
        return {
            "source": "course",
            "type": "content",
            "course_id": self.course.id,
            "course_title": self.course.title,
            "module_id": self.module.id,
            "module_title": self.module.title,
            "lesson_id": lesson.id if lesson else None,
            "lesson_title": lesson.title if lesson else None,
        }


def chunk_course(
    course: Course, document_id: uuid.UUID, config: ChunkingConfig = DEFAULT_CHUNKING
) -> list[NewChunk]:
    """All chunks for a course, positions 0..n in reading order."""
    splitter = config.splitter()
    chunks: list[NewChunk] = []

    def add(module: Module, lesson: Lesson | None, section: Section) -> None:
        source = Source(document_id, course, module, lesson)
        chunks.extend(_pieces(source, section, len(chunks), config, splitter))

    for module in course.modules:
        for section in module_sections(module):
            add(module, None, section)
        for lesson in module.lessons:
            for section in lesson_sections(lesson, course.language, config):
                add(module, lesson, section)
    return chunks


def module_sections(module: Module) -> Iterator[Section]:
    body = _topics(module.content.get("moduleExplanation"))
    if body:
        yield Section(f"{module.id}:overview", "Module overview", body)


def lesson_sections(
    lesson: Lesson, language: str, config: ChunkingConfig = DEFAULT_CHUNKING
) -> Iterator[Section]:
    content = lesson.content
    sections = [
        Section(f"{lesson.id}:explanation", "Explanation", _explanation(lesson)),
        Section(f"{lesson.id}:concepts", "Key concepts", _concepts(content, language)),
        *_example_sections(lesson, language, config.max_body_chars),
        Section(f"{lesson.id}:context", "Analogy, story and use cases", _context(content)),
        Section(f"{lesson.id}:summary", "Summary", _summary(content)),
        _practice_section(lesson, language),
    ]
    return (section for section in sections if section.body.strip())


def _example_sections(lesson: Lesson, language: str, max_body: int) -> Iterator[Section]:
    """Pack consecutive examples into as few chunks as fit `max_body` (code kept whole)."""
    group: list[tuple[int, str]] = []
    for number, example in enumerate(lesson.content.get("example") or [], 1):
        body = _example(example, language)
        candidate = PARAGRAPH.join(b for _, b in [*group, (number, body)])
        if group and len(candidate) > max_body:
            yield _examples(lesson, group)
            group = []
        group.append((number, body))
    if group:
        yield _examples(lesson, group)


def _examples(lesson: Lesson, group: list[tuple[int, str]]) -> Section:
    first, last = group[0][0], group[-1][0]
    name = f"Example {first}" if first == last else f"Examples {first}–{last}"
    body = PARAGRAPH.join(b for _, b in group)
    return Section(f"{lesson.id}:examples-{first}-{last}", name, body)


def _pieces(
    source: Source,
    section: Section,
    start: int,
    config: ChunkingConfig,
    splitter: RecursiveCharacterTextSplitter,
) -> Iterable[NewChunk]:
    header = f"{source.trail} — {section.name}"
    body = section.body
    bodies = [body] if len(body) <= config.max_body_chars else splitter.split_text(body)
    lesson_id = source.lesson.id if source.lesson else None
    for n, body in enumerate(bodies):
        text = f"{header}{PARAGRAPH}{body.strip()}"
        if len(text) > config.max_chunk_chars:
            raise ChunkTooLargeError(f"chunk for {section.key} is {len(text)} characters")
        yield NewChunk(
            id=chunk_id(source.document_id, section.key, n),
            position=start + n,
            section=section.name[:100],
            text=text,
            lesson_id=lesson_id,
            metadata={
                **source.metadata(),
                "section": section.name,
                "part": n + 1,
                "parts": len(bodies),
                **section.extra,
            },
        )


def chunk_id(document_id: uuid.UUID, section_key: str, piece: int) -> str:
    """Same document and section always give the same id; documents never collide."""
    return hashlib.sha256(f"{document_id}|{section_key}|{piece}".encode()).hexdigest()


# ---- exercises: prompt fields only (explicit allowlist) ---------------------------------


def _practice_section(lesson: Lesson, language: str) -> Section:
    """All of a lesson's exercises, asking side only. `solution` and `bug_explanation` are
    never read, and the `type: exercise` tag tells the tutor (Steps 12/14) to give hints,
    not answers."""
    # Fixed teaching order, whatever order the exercises were loaded in (file vs database),
    # so the same course always produces the same chunk text.
    exercises = sorted(lesson.exercises, key=lambda e: _EXERCISE_ORDER.get(e.kind, 99))
    return Section(
        f"{lesson.id}:practice",
        "Practice exercises",
        PARAGRAPH.join(_exercise_text(exercise, language) for exercise in exercises),
        extra={
            "type": "exercise",
            "exercise_kinds": [exercise.kind for exercise in exercises],
        },
    )


def _exercise_text(exercise: Exercise, language: str) -> str:
    parts = [
        f"{EXERCISE_TITLES.get(exercise.kind, 'Exercise')}: {exercise.title}",
        exercise.instructions,
    ]
    label = "Buggy code" if exercise.kind == "bug_hunt" else "Starter code"
    if exercise.starter_code.strip():
        parts.append(f"{label}:\n{_code(exercise.starter_code, language)}")
    if exercise.expected_output:
        parts.append(f"Expected result: {exercise.expected_output}")
    if exercise.hints:
        parts.append("Hints:\n" + _bullets(exercise.hints))
    return PARAGRAPH.join(p for p in parts if p)


# ---- renderers: structured lesson content -> readable text ------------------------------


def _explanation(lesson: Lesson) -> str:
    content = lesson.content
    hooks = [h.get("text", "") for h in content.get("hooklines") or [] if isinstance(h, dict)]
    parts = [
        f"Objective: {lesson.objective}" if lesson.objective else "",
        _topics(content.get("lessonExplanation")),
        "\n".join(hook for hook in hooks if hook),
    ]
    return PARAGRAPH.join(p for p in parts if p)


def _concepts(content: dict[str, Any], language: str) -> str:
    concepts = content.get("concepts") or []
    syntax = (content.get("syntax") or {}).get("highlight", {}).get("code", "")
    parts_list = [
        f"{p.get('label', '')} — {p.get('name', '')}: {p.get('description', '')}".strip(" —:")
        for p in content.get("parts") or []
        if isinstance(p, dict)
    ]
    sections = [
        "Concepts: " + ", ".join(str(c) for c in concepts) if concepts else "",
        f"Syntax:\n{_code(syntax, language)}" if syntax else "",
        "\n".join(parts_list),
    ]
    return PARAGRAPH.join(s for s in sections if s)


def _example(example: dict[str, Any], language: str) -> str:
    parts = [
        example.get("title", ""),
        _code(example.get("code", ""), language) if example.get("code") else "",
        example.get("explanation", ""),
    ]
    return PARAGRAPH.join(p for p in parts if p)


def _context(content: dict[str, Any]) -> str:
    return _titled(
        ("Analogy", _analogy(content.get("analogy"))),
        ("Real-world story", _story(content.get("realWorldStory"))),
        ("Use cases", _use_cases(content.get("useCaseCards"))),
    )


def _summary(content: dict[str, Any]) -> str:
    return _titled(
        ("Key takeaways", _bullets(content.get("keyTakeaways"))),
        ("Flowchart", _flowchart(content.get("flowchart"))),
    )


def _titled(*parts: tuple[str, str]) -> str:
    return PARAGRAPH.join(f"{title}:\n{body}" for title, body in parts if body)


def _analogy(analogy: dict[str, Any] | None) -> str:
    if not analogy:
        return ""
    mapping = [
        f"- {m.get('from', '')} → {m.get('to', '')}"
        for m in analogy.get("mapping") or []
        if isinstance(m, dict)
    ]
    parts = [analogy.get("subject", ""), analogy.get("comparison", ""), "\n".join(mapping)]
    return PARAGRAPH.join(p for p in parts if p)


def _flowchart(flowchart: dict[str, Any] | None) -> str:
    if not flowchart or not flowchart.get("code"):
        return ""
    # The model reads Mermaid well; it is a teaching diagram, not an answer.
    return f"{flowchart.get('title', '')}\n\n```mermaid\n{flowchart['code'].strip()}\n```".strip()


def _use_cases(cards: list[dict[str, Any]] | None) -> str:
    return "\n".join(
        f"- {c.get('industry', '')} ({c.get('jobRole', '')}): {c.get('useCase', '')}"
        for c in cards or []
        if isinstance(c, dict)
    )


def _story(story: dict[str, Any] | None) -> str:
    if not story:
        return ""
    title = story.get("storyTitle", "")
    company = story.get("storyCompany", "")
    heading = f"{title} ({company})" if company else title
    return PARAGRAPH.join(p for p in (heading, story.get("storyText", "")) if p)


def _topics(topics: list[dict[str, Any]] | None) -> str:
    blocks = []
    for topic in topics or []:
        if isinstance(topic, dict):
            points = _bullets(topic.get("points"))
            blocks.append("\n".join(p for p in (topic.get("topic", ""), points) if p))
    return PARAGRAPH.join(blocks)


def _bullets(items: list[Any] | None) -> str:
    return "\n".join(f"- {item}" for item in items or [] if str(item).strip())


def _code(code: str, language: str) -> str:
    return f"```{language}\n{code.strip()}\n```"
