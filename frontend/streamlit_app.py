"""ArchintX Learning Assistant: Streamlit frontend.

Run locally:  streamlit run frontend/streamlit_app.py
Config:       API_BASE_URL in .streamlit/secrets.toml (or the environment).

Signs the user in, then shows the pages their role allows. Students never see the admin
pages in the menu, and the API refuses admin actions from them anyway (403), so hiding
the menu entries is convenience, not the protection.

The access token lives only in `st.session_state`, which stays on the Streamlit server;
it never reaches browser storage or cookies.
"""

import streamlit as st
from streamlit.navigation.page import StreamlitPage

from components.account import load_user, show_account, show_login
from menu import pages_for
from session import TOKEN_KEY, api_base_url, api_client


def navigation(user: dict) -> StreamlitPage:
    return st.navigation(
        {
            section: [st.Page(path, title=title, icon=icon) for path, title, icon in pages]
            for section, pages in pages_for(user.get("role")).items()
        }
    )


def main() -> None:
    st.set_page_config(page_title="ArchintX Learning Assistant", page_icon="🎓", layout="wide")

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
    show_account(client, token, user)
    navigation(user).run()


main()
