"""ArchintX Learning Assistant: Streamlit frontend (login, then practice with the compiler
panel; full lesson pages arrive in Step 19).

Run locally:  streamlit run frontend/streamlit_app.py
Config:       API_BASE_URL in .streamlit/secrets.toml (or the environment).

The access token lives only in `st.session_state`, which stays on the Streamlit server;
it never reaches browser storage or cookies.
"""

import os

import streamlit as st

from api_client import ApiClient, ApiError, SessionExpiredError
from components.practice import show_practice

TOKEN_KEY = "access_token"  # noqa: S105 - session_state key name, not a secret


def api_base_url() -> str | None:
    try:
        configured = st.secrets.get("API_BASE_URL")
    except FileNotFoundError:
        # No secrets.toml at all: fall back to the environment.
        configured = None
    return configured or os.environ.get("API_BASE_URL")


@st.cache_resource
def api_client(base_url: str) -> ApiClient:
    """One HTTP client per server process; it is stateless, tokens are passed per call."""
    return ApiClient(base_url)


def show_login(client: ApiClient) -> None:
    st.subheader("Log in")
    # clear_on_submit: the password must not linger in widget state after submitting.
    with st.form("login", clear_on_submit=True):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")
    if not submitted:
        return
    try:
        st.session_state[TOKEN_KEY] = client.login(username, password)
    except ApiError as exc:
        st.error(str(exc))
        return
    st.rerun()


def show_account(client: ApiClient, token: str) -> bool:
    """The signed-in line and Log out button; False when the session cannot be used."""
    try:
        user = client.me(token)
    except SessionExpiredError as exc:
        del st.session_state[TOKEN_KEY]
        st.warning(str(exc))
        st.button("Back to login")
        return False
    except ApiError as exc:
        st.error(str(exc))
        return False
    st.success(f"Signed in as **{user['username']}** ({user['role']})")
    if st.button("Log out"):
        del st.session_state[TOKEN_KEY]
        st.rerun()
    return True


def main() -> None:
    st.set_page_config(page_title="ArchintX Learning Assistant", page_icon="🎓")
    st.title("ArchintX Learning Assistant")

    base_url = api_base_url()
    if not base_url:
        st.error("API_BASE_URL is not configured. Add it to the app's secrets.")
        st.stop()
    try:
        client = api_client(base_url)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

    token = st.session_state.get(TOKEN_KEY)
    if token:
        if show_account(client, token):
            show_practice(client, token)
    else:
        show_login(client)


main()
