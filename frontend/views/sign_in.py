"""Sign in (guests only). After signing in, the rail switches to the student's (or
admin's) pages and LearnX opens."""

import streamlit as st

from components.account import show_login
from session import current_visitor


def main() -> None:
    visitor = current_visitor()
    st.caption(
        "Courses are open to everyone. Sign in to ask Nexus, practise with the code "
        "editor and track your progress."
    )
    show_login(visitor.client)


main()
