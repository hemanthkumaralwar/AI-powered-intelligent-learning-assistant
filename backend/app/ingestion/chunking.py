"""Split a stored course into searchable chunks for RAG (pure: no database, no network).

What goes in: the answer-free teaching content stored in Step 8 (module and lesson
`content`), each lesson's flowchart, and the *prompt* parts of its exercises.
What never goes in: quiz questions and answers, bug-hunt fixes and explanations, and the
drag-and-drop / card-matching / code-reordering activities. Those are served and graded
through the API instead, so retrieval can never hand a student an answer.

Each chunk starts with a context header (course > module > lesson - section) so it reads
on its own; long sections are split by LangChain's recursive splitter with overlap.
"""

import hashlib
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.db.models import Course, Exercise, Lesson, Module
from app.db.repositories.chunks import NewChunk

MAX_BODY_CHARS = 1000
OVERLAP_CHARS = 150
# Header + body. Kept well under embedding model limits (~250 tokens of body).
MAX_CHUNK_CHARS = 1200

_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=MAX_BODY_CHARS,
    chunk_overlap=OVERLAP_CHARS,
    # Paragraphs first, then lines, so code blocks stay together when they fit.
    separators=["\n\n", "\n", " ", ""],
)

EXERCISE_TITLES = {
    "interactive": "Try it yourself",
    "mini_challenge": "Mini challenge",
    "bug_hunt": "Bug hunt",
}


class ChunkTooLargeError(Exception):
    """A rendered chunk exceeds MAX_CHUNK_CHARS (a bug, never silently truncated)."""


@dataclass(frozen=True)
class Section:
    key: str  # stable within a document; part of the chunk id
    name: str  # human-readable, shown in the header and stored in `chunks.section`
    body: str
    extra: dict[str, Any] = field(default_factory=dict)


def chunk_course(course: Course, document_id: uuid.UUID) -> list[NewChunk]:
    """All chunks for a course, positions 0..n in reading order."""
    chunks: list[NewChunk] = []
    for module in course.modules:
        for section in module_sections(module):
            chunks.extend(_pieces(course, module, None, section, document_id, len(chunks)))
        for lesson in module.lessons:
            for section in lesson_sections(lesson, course.language):
                chunks.extend(_pieces(course, module, lesson, section, document_id, len(chunks)))
    return chunks


def module_sections(module: Module) -> Iterator[Section]:
    body = _topics(module.content.get("moduleExplanation"))
    if body:
        yield Section(f"{module.id}:overview", "Module overview", body)


def lesson_sections(lesson: Lesson, language: str) -> Iterator[Section]:
    content = lesson.content
    sections = [
        Section(f"{lesson.id}:explanation", "Explanation", _explanation(lesson)),
        Section(f"{lesson.id}:concepts", "Key concepts", _concepts(content, language)),
        *(
            Section(f"{lesson.id}:example-{i}", f"Example {i}", _example(example, language))
            for i, example in enumerate(content.get("example") or [], 1)
        ),
        Section(f"{lesson.id}:analogy", "Analogy", _analogy(content.get("analogy"))),
        Section(f"{lesson.id}:flowchart", "Flowchart", _flowchart(content.get("flowchart"))),
        Section(f"{lesson.id}:use-cases", "Use cases", _use_cases(content.get("useCaseCards"))),
        Section(f"{lesson.id}:story", "Real-world story", _story(content.get("realWorldStory"))),
        Section(f"{lesson.id}:takeaways", "Key takeaways", _bullets(content.get("keyTakeaways"))),
        *(_exercise_section(lesson, exercise, language) for exercise in lesson.exercises),
    ]
    return (section for section in sections if section.body.strip())


def _pieces(
    course: Course,
    module: Module,
    lesson: Lesson | None,
    section: Section,
    document_id: uuid.UUID,
    start: int,
) -> Iterable[NewChunk]:
    trail = " › ".join(t for t in (course.title, module.title, lesson and lesson.title) if t)
    header = f"{trail} — {section.name}"
    bodies = (
        [section.body]
        if len(section.body) <= MAX_BODY_CHARS
        else _SPLITTER.split_text(section.body)
    )
    for n, body in enumerate(bodies):
        text = f"{header}\n\n{body.strip()}"
        if len(text) > MAX_CHUNK_CHARS:
            raise ChunkTooLargeError(f"chunk for {section.key} is {len(text)} characters")
        yield NewChunk(
            id=chunk_id(document_id, section.key, n),
            position=start + n,
            section=section.name[:100],
            text=text,
            lesson_id=lesson.id if lesson else None,
            metadata={
                "source": "course",
                "type": "content",
                "course_id": course.id,
                "course_title": course.title,
                "module_id": module.id,
                "module_title": module.title,
                "lesson_id": lesson.id if lesson else None,
                "lesson_title": lesson.title if lesson else None,
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


def _exercise_section(lesson: Lesson, exercise: Exercise, language: str) -> Section:
    """Only what a student is *asked*. `solution` and `bug_explanation` are never read,
    and the `type: exercise` tag tells the tutor (Steps 12/14) to give hints, not answers."""
    name = EXERCISE_TITLES.get(exercise.kind, "Exercise")
    parts = [exercise.title, exercise.instructions]
    label = "Buggy code" if exercise.kind == "bug_hunt" else "Starter code"
    if exercise.starter_code.strip():
        parts.append(f"{label}:\n{_code(exercise.starter_code, language)}")
    if exercise.expected_output:
        parts.append(f"Expected result: {exercise.expected_output}")
    if exercise.hints:
        parts.append("Hints:\n" + _bullets(exercise.hints))
    return Section(
        f"{lesson.id}:exercise-{exercise.kind}",
        name,
        "\n\n".join(p for p in parts if p),
        extra={"type": "exercise", "exercise_kind": exercise.kind},
    )


# ---- renderers: structured lesson content -> readable text ------------------------------


def _explanation(lesson: Lesson) -> str:
    content = lesson.content
    hooks = [h.get("text", "") for h in content.get("hooklines") or [] if isinstance(h, dict)]
    parts = [
        f"Objective: {lesson.objective}" if lesson.objective else "",
        _topics(content.get("lessonExplanation")),
        "\n".join(hook for hook in hooks if hook),
    ]
    return "\n\n".join(p for p in parts if p)


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
    return "\n\n".join(s for s in sections if s)


def _example(example: dict[str, Any], language: str) -> str:
    parts = [
        example.get("title", ""),
        _code(example.get("code", ""), language) if example.get("code") else "",
        example.get("explanation", ""),
    ]
    return "\n\n".join(p for p in parts if p)


def _analogy(analogy: dict[str, Any] | None) -> str:
    if not analogy:
        return ""
    mapping = [
        f"- {m.get('from', '')} → {m.get('to', '')}"
        for m in analogy.get("mapping") or []
        if isinstance(m, dict)
    ]
    parts = [analogy.get("subject", ""), analogy.get("comparison", ""), "\n".join(mapping)]
    return "\n\n".join(p for p in parts if p)


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
    return "\n\n".join(p for p in (heading, story.get("storyText", "")) if p)


def _topics(topics: list[dict[str, Any]] | None) -> str:
    blocks = []
    for topic in topics or []:
        if isinstance(topic, dict):
            points = _bullets(topic.get("points"))
            blocks.append("\n".join(p for p in (topic.get("topic", ""), points) if p))
    return "\n\n".join(blocks)


def _bullets(items: list[Any] | None) -> str:
    return "\n".join(f"- {item}" for item in items or [] if str(item).strip())


def _code(code: str, language: str) -> str:
    return f"```{language}\n{code.strip()}\n```"
