"""The LearnX-style frame around every signed-in page: a narrow icon rail on the left
(Streamlit's sidebar, restyled) and a top bar with the page title and the profile menu.

The rail is CSS over Streamlit's own sidebar markup (`data-testid` hooks). Streamlit does
not promise those hooks across versions, which is one reason `streamlit` is pinned; if an
upgrade breaks the rail, the navigation still works as a normal sidebar.
"""

import streamlit as st

from api_client import ApiClient
from components.account import show_profile

RAIL_WIDTH = "84px"

# Static CSS only (no user data is ever placed in it).
SHELL_CSS = f"""
<style>
section[data-testid="stSidebar"] {{
  width: {RAIL_WIDTH} !important;
  min-width: {RAIL_WIDTH} !important;
  max-width: {RAIL_WIDTH} !important;
}}
section[data-testid="stSidebar"] > div {{ padding: 0.5rem 0.25rem; }}
[data-testid="stSidebarHeader"] {{ padding: 0.5rem 0; justify-content: center; }}
[data-testid="stSidebarCollapseButton"] {{ display: none; }}
[data-testid="stSidebarNavItems"] {{ padding-top: 0.5rem; gap: 0.5rem; }}
[data-testid="stSidebarNavLink"] {{
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  height: auto;
  padding: 0.6rem 0.25rem;
  border-radius: 0.75rem;
}}
[data-testid="stSidebarNavLink"] span {{
  font-size: 0.72rem;
  font-weight: 600;
  text-align: center;
  margin: 0;
}}
[data-testid="stSidebarNavLink"] [data-testid="stIconMaterial"] {{ font-size: 1.4rem; }}
[data-testid="stSidebarNavSeparator"],
[data-testid="stSidebarResizeHandle"] {{ display: none; }}
/* Room for Streamlit's own header (its ⋮ menu holds the light/dark setting). */
.block-container {{ padding-top: 3.75rem; max-width: 1200px; }}
</style>
"""


def apply_shell_style() -> None:
    st.html(SHELL_CSS)


def show_topbar(client: ApiClient, token: str, user: dict, title: str) -> None:
    title_column, profile_column = st.columns([5, 1], vertical_alignment="center")
    title_column.markdown(f"### {title}")
    with profile_column:
        show_profile(client, token, user)
    st.divider()
