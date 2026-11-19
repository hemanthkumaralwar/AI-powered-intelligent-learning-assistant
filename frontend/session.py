"""What every page needs: the API client, the access token and the signed-in user.

The entry point (`streamlit_app.py`) signs the user in and stores them in
`st.session_state`, which lives on the Streamlit server; pages only read it.
"""

import os
from dataclasses import dataclass
from typing import Any

import streamlit as st

from api_client import ApiClient

TOKEN_KEY = "access_token"  # noqa: S105 - session_state key name, not a secret
USER_KEY = "user"


@dataclass(frozen=True)
class Session:
    client: ApiClient
    token: str
    user: dict[str, Any]

    @property
    def is_admin(self) -> bool:
        return self.user.get("role") == "admin"


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


def current() -> Session:
    """The signed-in session. Pages only run after the entry point has signed in."""
    base_url = api_base_url()
    if not base_url or TOKEN_KEY not in st.session_state or USER_KEY not in st.session_state:
        st.stop()
    return Session(api_client(base_url), st.session_state[TOKEN_KEY], st.session_state[USER_KEY])


def sign_out() -> None:
    for key in (TOKEN_KEY, USER_KEY):
        st.session_state.pop(key, None)
