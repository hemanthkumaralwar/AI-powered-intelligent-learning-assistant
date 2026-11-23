"""Nexus, the course assistant, in a lesson's "Ask Nexus" tab (Step 24; it was the Arc page).

Answers come only from the lesson's course, with citations; follow-ups stay in the same
chat. The conversation is on the left; the student's past chats (from any course) are in a
"Past chats" panel on the right, with New chat, and the panel can be hidden. An answer the
course materials do not cover is shown as a notice, not as a normal answer.
"""

from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError
from components.lesson_nav import open_practice

ACTIVE = "chat:active"  # the open chat's id; None for a new chat
PANEL_HIDDEN = "chat:panel-hidden"  # True once the student hides the Past chats panel


def show_nexus(client: ApiClient, token: str, course_id: str) -> None:
    hidden = st.session_state.get(PANEL_HIDDEN, False)
    if hidden:
        chat_column = st.container()
        _, show_column = chat_column.columns([5, 1])
        show_column.button(
            "Past chats",
            key="chat:show-panel",
            icon=":material/right_panel_open:",
            width="stretch",
            on_click=_set_panel_hidden,
            args=(False,),
        )
    else:
        chat_column, panel_column = st.columns([3, 1], gap="medium")
        with panel_column.container(border=True):
            show_past_chats(client, token)
    with chat_column:
        show_conversation(client, token, course_id)


def show_conversation(client: ApiClient, token: str, course_id: str) -> None:
    active = st.session_state.get(ACTIVE)
    # Messages go in a container placed above the input, so a new question and its answer
    # appear under the conversation, not under the input box.
    messages = st.container()
    question = st.chat_input("Ask Nexus about this lesson…")
    with messages:
        if active:
            show_history(client, token, active)
        else:
            st.markdown("#### Ask Nexus about this course")
            st.caption(
                "Answers come only from your course materials, with sources. Ask a follow-up "
                "in the same chat."
            )
        if question:
            ask(client, token, question, course_id, active)


def show_past_chats(client: ApiClient, token: str) -> None:
    heading, new_column, hide_column = st.columns([4, 2, 1], vertical_alignment="center")
    heading.markdown("**Past chats**")
    if new_column.button("New chat", icon=":material/add:", key="chat:new", type="primary"):
        _open(None)
        st.rerun()
    hide_column.button(
        "",
        key="chat:hide-panel",
        icon=":material/right_panel_close:",
        help="Hide past chats",
        type="tertiary",
        on_click=_set_panel_hidden,
        args=(True,),
    )
    try:
        chats = client.chat_sessions(token)
    except ApiError as exc:
        st.error(str(exc))
        return
    if not chats:
        st.caption("Your chats will appear here.")
        return
    active = st.session_state.get(ACTIVE)
    for chat in chats:
        kind = "secondary" if chat["id"] == active else "tertiary"
        if st.button(chat["title"], key=f"chat-{chat['id']}", type=kind, width="stretch"):
            _open(chat["id"])
            st.rerun()
    if active and st.button(
        "Delete this chat", icon=":material/delete:", key="chat:delete", type="tertiary"
    ):
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
            if message["role"] == "assistant" and message.get("grounded") is False:
                st.warning(message["content"], icon=":material/info:")
            else:
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
    st.rerun()


def _open(chat_id: str | None) -> None:
    st.session_state[ACTIVE] = chat_id


def _set_panel_hidden(hidden: bool) -> None:
    st.session_state[PANEL_HIDDEN] = hidden
