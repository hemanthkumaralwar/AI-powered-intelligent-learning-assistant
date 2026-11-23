"""ArchintX Learning Assistant: Streamlit frontend in the LearnX style.

Run locally:  streamlit run frontend/streamlit_app.py
Config:       API_BASE_URL in .streamlit/secrets.toml (or the environment).

Anyone can browse courses and read lessons (Step 24). Signing in adds Nexus (the course
assistant, in each lesson), practice and progress; admins also get Settings at /admin.
Students never have the admin page in their navigation, and the API refuses admin
actions from them anyway (403), so hiding it is convenience, not the protection.

The access token lives only in `st.session_state`, which stays on the Streamlit server;
it never reaches browser storage or cookies.
"""

from pathlib import Path

import streamlit as st
from streamlit.navigation.page import StreamlitPage

from components.account import load_user
from components.shell import apply_shell_style, show_topbar
from menu import pages_for
from session import TOKEN_KEY, api_base_url, api_client

LOGO = str(Path(__file__).parent / "static" / "logo.svg")


def navigation(user: dict | None) -> StreamlitPage:
    pages = [
        st.Page(page.path, title=page.title, icon=page.icon, url_path=page.url_path)
        for page in pages_for(user)
    ]
    # In the top bar, so the sidebar is free for the open lesson's course outline.
    return st.navigation(pages, position="top")


def main() -> None:
    st.set_page_config(page_title="ArchintX Learning Assistant", page_icon=LOGO, layout="wide")

    base_url = api_base_url()
    if not base_url:
        st.title("ArchintX Learning Assistant")
        st.error("API_BASE_URL is not configured. Add it to the app's secrets.")
        st.stop()
    try:
        client = api_client(base_url)
    except ValueError as exc:
        st.title("ArchintX Learning Assistant")
        st.error(str(exc))
        st.stop()

    token = st.session_state.get(TOKEN_KEY)
    user = load_user(client, token) if token else None
    if token and user is None:
        return  # load_user explained it (expired session, or the server failed)
    st.logo(LOGO, size="large")
    apply_shell_style()
    page = navigation(user)
    show_topbar(client, token, user, page.title)
    page.run()


main()
