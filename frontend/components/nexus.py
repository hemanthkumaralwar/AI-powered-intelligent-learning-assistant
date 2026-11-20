"""Nexus, the course assistant, in a lesson's "Ask Nexus" tab (Step 24; it was the Arc page).

Answers come only from the lesson's course, with citations; follow-ups stay in the same
chat; the student's past chats (from any course) are listed above the conversation.
"""

from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError
from components.lesson_nav import open_practice
from components.practice import show_practice_pointers

ACTIVE = "chat:active"  # the open chat's id; None for a new chat
POINTERS = "chat:practice"  # practice pointers of the last answer in the open chat


def show_nexus(client: ApiClient, token: str, course_id: str) -> None:
    choose_chat(client, token)
    active = st.session_state.get(ACTIVE)
    # Messages go in a container placed above the input, so a new question and its answer
    # appear under the conversation, not under the input box.
    messages = st.container()
    question = st.chat_input("Ask Nexus about this course…")
    with messages:
        if active:
            show_history(client, token, active)
        else:
            st.markdown("#### Ask Nexus about this course")
            st.caption(
                "Answers come only from your course materials, with sources. Ask a follow-up "
                "in the same chat; ask to be quizzed and you are pointed to the lesson's "
                "activities."
            )
        if question:
            ask(client, token, question, course_id, active)
        show_practice_pointers(st.session_state.get(POINTERS, []))


def choose_chat(client: ApiClient, token: str) -> None:
    try:
        chats = client.chat_sessions(token)
    except ApiError as exc:
        st.error(str(exc))
        return
    active = st.session_state.get(ACTIVE)
    new_column, chats_column = st.columns([1, 3], vertical_alignment="center")
    if new_column.button("New chat", icon=":material/add:", type="primary", width="stretch"):
        _open(None)
        st.rerun()
    with chats_column.expander(f"Your chats ({len(chats)})"):
        for chat in chats:
            kind = "secondary" if chat["id"] == active else "tertiary"
            if st.button(chat["title"], key=f"chat-{chat['id']}", type=kind, width="stretch"):
                _open(chat["id"])
                st.rerun()
        if active and st.button("Delete this chat", icon=":material/delete:"):
            _delete(client, token, active)


def _delete(client: ApiClient, token: str, chat_id: str) -> None:
    try:
        client.delete_chat(token, chat_id)
    except ApiError as exc:
        st.error(str(exc))
        return
    _open(None)
    st.rerun()


def show_history(client: ApiClient, token: str, chat_id: str) -> None:
    try:
        chat = client.chat_session(token, chat_id)
    except ApiError as exc:
        st.error(str(exc))
        _open(None)
        return
    enabled = practice_courses(client, token)
    for number, message in enumerate(chat["messages"]):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            citations = message.get("citations") or []
            show_sources(citations)
            show_practice_links(practice_lessons(citations, enabled), key=f"msg{number}")


def show_sources(citations: list[dict[str, Any]]) -> None:
    if citations:
        sources = "; ".join(
            f"[{c['number']}] {c['module_title']} › {c.get('lesson_title') or 'Overview'} "
            f"— {c['section']}"
            for c in citations
        )
        st.caption(f"Sources: {sources}")


def practice_courses(client: ApiClient, token: str) -> set[str]:
    """Courses whose admin turned on "Open in Practice". If the list cannot be loaded the
    buttons are simply not shown: the answer itself is unaffected."""
    try:
        return {c["id"] for c in client.courses(token) if c.get("arc_practice_enabled")}
    except ApiError:
        return set()


def practice_lessons(citations: list[dict[str, Any]], enabled: set[str]) -> list[dict[str, Any]]:
    """Distinct cited lessons in switched-on courses, in citation order. Module overviews
    (no lesson) and citations saved before course ids existed get no button."""
    lessons: dict[str, dict[str, Any]] = {}
    for citation in citations:
        lesson_id, course_id = citation.get("lesson_id"), citation.get("course_id")
        if lesson_id and course_id in enabled:
            lessons.setdefault(lesson_id, citation)
    return list(lessons.values())


def show_practice_links(lessons: list[dict[str, Any]], key: str) -> None:
    for citation in lessons:
        # Not an on_click callback: Streamlit ignores page switches made from callbacks.
        if st.button(
            f"Open in Practice: {citation.get('lesson_title') or citation['lesson_id']}",
            icon=":material/code:",
            key=f"practice:{key}:{citation['lesson_id']}",
        ):
            open_practice(citation["course_id"], citation["lesson_id"])


def ask(client: ApiClient, token: str, question: str, course_id: str, active: str | None) -> None:
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"), st.spinner("Looking in your course…"):
        try:
            reply = client.ask(token, question, course_id=course_id, session_id=active)
        except ApiError as exc:
            st.error(str(exc))
            return
    st.session_state[ACTIVE] = reply["session_id"]
    st.session_state[POINTERS] = reply.get("practice", [])
    st.rerun()


def _open(chat_id: str | None) -> None:
    st.session_state[ACTIVE] = chat_id
    st.session_state[POINTERS] = []
