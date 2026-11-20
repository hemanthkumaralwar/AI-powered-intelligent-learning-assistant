"""ArchintX Learning Assistant: Streamlit frontend in the LearnX style.

Run locally:  streamlit run frontend/streamlit_app.py
Config:       API_BASE_URL in .streamlit/secrets.toml (or the environment).

Signs the user in, then shows the left rail (Arc, LearnX, and Settings for admins), the
top bar and the chosen page. Students never see the admin page in the rail, and the API
refuses admin actions from them anyway (403), so hiding it is convenience, not the
protection.

The access token lives only in `st.session_state`, which stays on the Streamlit server;
it never reaches browser storage or cookies.
"""

from pathlib import Path

import streamlit as st
from streamlit.navigation.page import StreamlitPage

from components.account import load_user, show_login
from components.shell import apply_shell_style, show_topbar
from menu import pages_for
from session import TOKEN_KEY, api_base_url, api_client

LOGO = str(Path(__file__).parent / "static" / "logo.svg")


def navigation(user: dict) -> StreamlitPage:
    pages = [
        st.Page(path, title=title, icon=icon) for path, title, icon in pages_for(user.get("role"))
    ]
    return st.navigation(pages)


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
    if user is None:
        st.title("ArchintX Learning Assistant")
        if not token:
            show_login(client)
        return
    st.logo(LOGO, size="large")
    apply_shell_style()
    page = navigation(user)
    show_topbar(client, token, user, page.title)
    page.run()


main()
