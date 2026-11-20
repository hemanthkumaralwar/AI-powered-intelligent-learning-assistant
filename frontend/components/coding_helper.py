"""The lesson's Code tab: explain code, see an example, or get practice questions.
Debugging lives in the compiler panel on the Practice tab, next to the run output."""

from collections.abc import Callable
from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError
from components.compiler import LANGUAGES
from components.practice import show_practice_pointers

RESULT = "helper:result"


def show_coding_helper(client: ApiClient, token: str, language: str) -> None:
    languages = list(LANGUAGES)
    language = st.selectbox(
        "Language",
        languages,
        index=languages.index(language) if language in languages else 0,
        format_func=LANGUAGES.__getitem__,
        key="helper:language",
    )
    explain_tab, example_tab, practice_tab = st.tabs(
        ["Explain my code", "Show an example", "Practice questions"]
    )
    with explain_tab:
        code = st.text_area("Code", height=220, key="helper:code")
        if st.button("Explain", key="helper:explain", type="primary") and code.strip():
            _run(client, token, "explain", language, code=code)
    with example_tab:
        topic = st.text_input("Topic", key="helper:example-topic", placeholder="e.g. closures")
        if st.button("Show example", key="helper:example", type="primary") and topic.strip():
            _run(client, token, "example", language, topic=topic)
    with practice_tab:
        topic = st.text_input("Topic", key="helper:practice-topic", placeholder="e.g. loops")
        if st.button("Get questions", key="helper:practice", type="primary") and topic.strip():
            _run(client, token, "practice", language, topic=topic)
    show_result(st.session_state.get(RESULT))


def _run(client: ApiClient, token: str, task: str, language: str, **body: str) -> None:
    with st.spinner("Asking the assistant…"):
        try:
            result = client.coding(token, task, language, **body)
        except ApiError as exc:
            st.error(str(exc))
            return
    st.session_state[RESULT] = {"task": task, "language": language, **result}


def show_result(result: dict[str, Any] | None) -> None:
    if not result:
        return
    st.divider()
    RENDERERS[result["task"]](result)
    show_practice_pointers(result.get("practice", []))


def _explanation(result: dict[str, Any]) -> None:
    st.markdown(result["summary"])
    for note in result["lines"]:
        st.markdown(f"- **Line {note['line']}:** {note['explanation']}")


def _example(result: dict[str, Any]) -> None:
    st.subheader(result["title"])
    st.code(result["code"], language=result["language"])
    st.markdown(result["explanation"])


def _questions(result: dict[str, Any]) -> None:
    for number, question in enumerate(result["questions"], 1):
        st.markdown(f"**{number}. {question['question']}**")
        if question.get("expected_output"):
            st.caption(f"Expected output: {question['expected_output']}")
        with st.expander("Hints"):
            for hint in question["hints"]:
                st.markdown(f"- {hint}")


RENDERERS: dict[str, Callable[[dict[str, Any]], None]] = {
    "explain": _explanation,
    "example": _example,
    "practice": _questions,
}
