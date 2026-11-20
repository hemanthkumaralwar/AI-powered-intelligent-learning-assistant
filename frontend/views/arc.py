"""Arc: chat with the course assistant. Answers with citations, follow-ups in the same
chat, and your past chats on the left."""

from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError
from components.lesson_nav import open_practice
from components.practice import show_practice_pointers
from session import current

ACTIVE = "chat:active"  # the open chat's id; None for a new chat
POINTERS = "chat:practice"  # practice pointers of the last answer in the open chat


def main() -> None:
    session = current()
    chats_column, chat_column = st.columns([1, 3], gap="large")
    with chats_column:
        choose_chat(session.client, session.token)
    active = st.session_state.get(ACTIVE)
    with chat_column:
        # Messages go in a container placed above the input, so a new question and its
        # answer appear under the conversation, not under the input box.
        messages = st.container()
        question = st.chat_input("Ask about your course…")
    with messages:
        if active:
            show_history(session.client, session.token, active)
        else:
            st.markdown("#### Ask Arc about your course")
            st.caption(
                "Answers come only from your course materials, with sources. Ask a follow-up "
                "in the same chat; ask to be quizzed and you are pointed to the lesson's "
                "activities."
            )
        if question:
            ask(session.client, session.token, question, active)
        show_practice_pointers(st.session_state.get(POINTERS, []))


def choose_chat(client: ApiClient, token: str) -> None:
    if st.button("New chat", icon=":material/add:", type="primary", width="stretch"):
        _open(None)
    st.caption("Your chats")
    try:
        chats = client.chat_sessions(token)
    except ApiError as exc:
        st.error(str(exc))
        return
    active = st.session_state.get(ACTIVE)
    for chat in chats:
        kind = "secondary" if chat["id"] == active else "tertiary"
        if st.button(chat["title"], key=f"chat-{chat['id']}", type=kind, width="stretch"):
            _open(chat["id"])
            st.rerun()
    if active and st.button("Delete this chat", icon=":material/delete:", width="stretch"):
        try:
            client.delete_chat(token, active)
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


def ask(client: ApiClient, token: str, question: str, active: str | None) -> None:
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"), st.spinner("Looking in your course…"):
        try:
            reply = client.ask(token, question, session_id=active)
        except ApiError as exc:
            st.error(str(exc))
            return
    st.session_state[ACTIVE] = reply["session_id"]
    st.session_state[POINTERS] = reply.get("practice", [])
    st.rerun()


def _open(chat_id: str | None) -> None:
    st.session_state[ACTIVE] = chat_id
    st.session_state[POINTERS] = []


main()
