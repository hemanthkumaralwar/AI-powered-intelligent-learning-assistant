"""The LearnX-style frame around every page: the page links sit in Streamlit's header
(`st.navigation(position="top")`), and a top bar shows the page title and the profile menu
(or, for guests, a Sign in link). The sidebar is left free: an open lesson puts its course
outline there (components/outline.py), and the sidebar's own button hides it.
"""

import streamlit as st

from api_client import ApiClient
from components.account import show_profile
from menu import SIGN_IN

# Static CSS only (no user data is ever placed in it).
SHELL_CSS = """
<style>
/* Room for Streamlit's own header (page links, and the ⋮ menu with light/dark). */
.block-container { padding-top: 4rem; max-width: 1280px; }
</style>
"""


def apply_shell_style() -> None:
    st.html(SHELL_CSS)


def show_topbar(client: ApiClient, token: str | None, user: dict | None, title: str) -> None:
    title_column, account_column = st.columns([5, 1], vertical_alignment="center")
    title_column.markdown(f"### {title}")
    with account_column:
        if user is None or token is None:
            st.page_link(SIGN_IN.path, label="Sign in", icon=SIGN_IN.icon)
        else:
            show_profile(client, token, user)
    st.divider()
