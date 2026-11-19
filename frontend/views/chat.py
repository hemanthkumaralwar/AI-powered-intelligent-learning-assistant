"""Chat with the course assistant: answers with citations, follow-ups, past chats."""

from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError
from components.practice import show_practice_pointers
from session import current

ACTIVE = "chat:active"  # the open chat's id; None for a new chat
POINTERS = "chat:practice"  # practice pointers of the last answer in the open chat


def main() -> None:
    session = current()
    st.title("Ask the assistant")
    st.caption(
        "Answers come only from your course materials, with sources. Ask a follow-up in the "
        "same chat; ask to be quizzed and you are pointed to the lesson's activities."
    )
    with st.sidebar:
        choose_chat(session.client, session.token)
    active = st.session_state.get(ACTIVE)
    if active:
        show_history(session.client, session.token, active)
    question = st.chat_input("Ask about your course…")
    if question:
        ask(session.client, session.token, question, active)
    show_practice_pointers(st.session_state.get(POINTERS, []))


def choose_chat(client: ApiClient, token: str) -> None:
    st.subheader("Your chats")
    if st.button("New chat", icon="➕"):
        _open(None)
    try:
        chats = client.chat_sessions(token)
    except ApiError as exc:
        st.error(str(exc))
        return
    for chat in chats:
        if st.button(chat["title"], key=f"chat-{chat['id']}", width="stretch"):
            _open(chat["id"])
    active = st.session_state.get(ACTIVE)
    if active and st.button("Delete this chat", icon="🗑️"):
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
    for message in chat["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            show_sources(message.get("citations") or [])


def show_sources(citations: list[dict[str, Any]]) -> None:
    if citations:
        sources = "; ".join(
            f"[{c['number']}] {c['module_title']} › {c.get('lesson_title') or 'Overview'} "
            f"— {c['section']}"
            for c in citations
        )
        st.caption(f"Sources: {sources}")


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
