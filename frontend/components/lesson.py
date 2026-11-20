"""A lesson's Reading tab in LearnX stages: Mission, Brief, Concepts, Analogy, Syntax,
Examples, Flow, Real world, Recap. Stages without content are skipped and the rest are
numbered.

Course text is shown with `st.markdown`, which does not render raw HTML, and code with
`st.code`; flowcharts are shown as their Mermaid source, not executed. The course JSON's
embedded HTML snippets (hook images) are skipped.
"""

from collections.abc import Callable
from typing import Any

import streamlit as st

type Renderer = Callable[[dict[str, Any], str], None]
CONCEPT_COLUMNS = 4


def show_lesson_header(lesson: dict[str, Any]) -> None:
    content = lesson.get("content", {})
    st.markdown(f"## {lesson['title']}")
    facts = [  # the objective is the Reading tab's first stage, not repeated here
        content.get("duration"),
        _count(content.get("concepts"), "concept"),
        _count(content.get("example"), "example"),
        _count(lesson.get("exercises"), "exercise"),
    ]
    if shown := [fact for fact in facts if fact]:
        st.markdown(" · ".join(f"**{fact}**" for fact in shown))


def show_reading(lesson: dict[str, Any], language: str) -> None:
    content = {**lesson.get("content", {}), "objective": lesson.get("objective")}
    stages = [
        (title, render) for title, keys, render in STAGES if any(content.get(k) for k in keys)
    ]
    for number, (title, render) in enumerate(stages, 1):
        with st.container(border=True):
            st.caption(f"Stage {number} of {len(stages)}")
            st.markdown(f"#### {title}")
            render(content, language)


def _count(items: object, noun: str) -> str | None:
    if not isinstance(items, list) or not items:
        return None
    return f"{len(items)} {noun}{'' if len(items) == 1 else 's'}"


def _mission(content: dict[str, Any], language: str) -> None:
    if content.get("objective"):
        st.markdown(f"**Objective:** {content['objective']}")
    for hook in content.get("hooklines") or []:
        if isinstance(hook, dict) and hook.get("text"):
            st.markdown(f"- {hook['text']}")


def _brief(content: dict[str, Any], language: str) -> None:
    for block in content["lessonExplanation"]:
        if block.get("topic"):
            st.markdown(f"**{block['topic']}**")
        for point in block.get("points", []):
            st.markdown(f"- {point}")


def _concepts(content: dict[str, Any], language: str) -> None:
    concepts = content["concepts"]
    columns = st.columns(CONCEPT_COLUMNS)
    for number, concept in enumerate(concepts, 1):
        with columns[(number - 1) % CONCEPT_COLUMNS].container(border=True):
            st.caption(f"{number:02d}")
            st.markdown(f"**{concept}**")


def _analogy(content: dict[str, Any], language: str) -> None:
    analogy = content["analogy"]
    if analogy.get("subject"):
        st.markdown(f"**{analogy['subject']}**")
    if analogy.get("comparison"):
        st.markdown(analogy["comparison"])
    mapping = [m for m in analogy.get("mapping") or [] if isinstance(m, dict)]
    if mapping:
        rows = [f"| {_cell(m.get('from'))} | {_cell(m.get('to'))} |" for m in mapping]
        st.markdown("\n".join(["| In the analogy | In this lesson |", "|---|---|", *rows]))


def _cell(value: object) -> str:
    """Table-safe text: a `|` in course text would otherwise split the cell."""
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def _syntax(content: dict[str, Any], language: str) -> None:
    code = ((content.get("syntax") or {}).get("highlight") or {}).get("code")
    if code:
        st.code(code, language=language)
    for number, part in enumerate(content.get("parts") or [], 1):
        name = part.get("name") or part.get("label", "")
        st.markdown(f"{number}. **{name}:** {part.get('description', '')}")


def _examples(content: dict[str, Any], language: str) -> None:
    for example in content["example"]:
        st.markdown(f"**{example.get('title', 'Example')}**")
        if example.get("code"):
            st.code(example["code"], language=language)
        if example.get("explanation"):
            st.caption(example["explanation"])


def _flow(content: dict[str, Any], language: str) -> None:
    flowchart = content["flowchart"]
    st.markdown(f"**{flowchart.get('title', 'Flowchart')}**")
    st.code(flowchart.get("code", ""), language="mermaid")


def _real_world(content: dict[str, Any], language: str) -> None:
    story = content.get("realWorldStory") or {}
    if story.get("storyText"):
        company = f" ({story['storyCompany']})" if story.get("storyCompany") else ""
        st.markdown(f"**{story.get('storyTitle', 'A real-world story')}**{company}")
        st.markdown(story["storyText"])
    for card in content.get("useCaseCards") or []:
        role = " · ".join(part for part in (card.get("industry"), card.get("jobRole")) if part)
        st.markdown(f"- **{role}:** {card.get('useCase', '')}")


def _recap(content: dict[str, Any], language: str) -> None:
    for takeaway in content["keyTakeaways"]:
        st.markdown(f"- {takeaway}")


# (stage title, content keys that make it worth showing, renderer)
STAGES: list[tuple[str, tuple[str, ...], Renderer]] = [
    ("Your mission", ("objective", "hooklines"), _mission),
    ("Brief", ("lessonExplanation",), _brief),
    ("Core concepts", ("concepts",), _concepts),
    ("Mental model", ("analogy",), _analogy),
    ("Syntax anatomy", ("syntax", "parts"), _syntax),
    ("Examples", ("example",), _examples),
    ("Flow", ("flowchart",), _flow),
    ("In the real world", ("realWorldStory", "useCaseCards"), _real_world),
    ("Recap", ("keyTakeaways",), _recap),
]
