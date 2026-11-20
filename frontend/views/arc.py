"""Arc: chat with the course assistant. Answers with citations, follow-ups in the same
chat, and your past chats on the left."""

from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError
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
