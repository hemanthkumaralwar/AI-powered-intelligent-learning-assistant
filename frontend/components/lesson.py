"""Render a lesson's stored content (explanation, concepts, examples, takeaways...).

Course text is shown with `st.markdown`, which does not render raw HTML, and code with
`st.code`; flowcharts are shown as their Mermaid source, not executed. The course JSON's
embedded HTML snippets (hook images) are skipped.
"""

from collections.abc import Callable
from typing import Any

import streamlit as st

type Renderer = Callable[[Any, str], None]


def show_lesson(lesson: dict[str, Any], language: str) -> None:
    st.header(lesson["title"])
    if lesson.get("objective"):
        st.caption(lesson["objective"])
    content = lesson.get("content", {})
    for key, render in RENDERERS:
        value = content.get(key)
        if value:
            render(value, language)


def _explanation(value: list[dict], language: str) -> None:
    for block in value:
        if block.get("topic"):
            st.subheader(block["topic"])
        for point in block.get("points", []):
            st.markdown(f"- {point}")


def _concepts(value: list[str], language: str) -> None:
    st.markdown("**Key concepts:** " + ", ".join(f"`{concept}`" for concept in value))


def _syntax(value: dict, language: str) -> None:
    code = (value.get("highlight") or {}).get("code")
    if code:
        st.markdown(f"**{value.get('title', 'Syntax')}**")
        st.code(code, language=language)


def _parts(value: list[dict], language: str) -> None:
    for part in value:
        st.markdown(
            f"- **{part.get('name', part.get('label', ''))}:** {part.get('description', '')}"
        )


def _examples(value: list[dict], language: str) -> None:
    for example in value:
        st.markdown(f"**{example.get('title', 'Example')}**")
        if example.get("code"):
            st.code(example["code"], language=language)
        if example.get("explanation"):
            st.markdown(example["explanation"])


def _analogy(value: dict, language: str) -> None:
    text = " ".join(str(v) for k, v in value.items() if isinstance(v, str) and k != "subject")
    st.info(f"**{value.get('subject', 'Analogy')}**\n\n{text}")


def _flowchart(value: dict, language: str) -> None:
    with st.expander(value.get("title", "Flowchart")):
        st.code(value.get("code", ""), language="mermaid")


def _story(value: dict, language: str) -> None:
    with st.expander(value.get("storyTitle", "A real-world story")):
        st.markdown(value.get("storyText", ""))


def _use_cases(value: list[dict], language: str) -> None:
    with st.expander("Where this is used"):
        for card in value:
            role = " · ".join(part for part in (card.get("industry"), card.get("jobRole")) if part)
            st.markdown(f"- **{role}:** {card.get('useCase', '')}")


def _takeaways(value: list[str], language: str) -> None:
    st.subheader("Key takeaways")
    for takeaway in value:
        st.markdown(f"- {takeaway}")


RENDERERS: list[tuple[str, Renderer]] = [
    ("lessonExplanation", _explanation),
    ("concepts", _concepts),
    ("syntax", _syntax),
    ("parts", _parts),
    ("example", _examples),
    ("analogy", _analogy),
    ("flowchart", _flowchart),
    ("realWorldStory", _story),
    ("useCaseCards", _use_cases),
    ("keyTakeaways", _takeaways),
]
