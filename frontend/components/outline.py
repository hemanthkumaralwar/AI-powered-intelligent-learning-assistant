"""The course outline beside an open lesson: the course name (back to the course page),
then the open lesson's module with its lessons, each marked done, started or not started.

It lives in Streamlit's sidebar, so the sidebar's own collapse button shows and hides it.
"""

from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError
from components.lesson_nav import open_lesson

DONE = ":material/check_circle:"
STARTED = ":material/timelapse:"
NOT_STARTED = ":material/radio_button_unchecked:"
CURRENT = ":material/radio_button_checked:"

# Left-align the lesson buttons (Streamlit centres button labels). Static CSS only.
OUTLINE_CSS = """
<style>
section[data-testid="stSidebar"] [data-testid^="stBaseButton"],
section[data-testid="stSidebar"] [data-testid^="stBaseButton"] > div,
section[data-testid="stSidebar"] [data-testid^="stBaseButton"] > div > span {
  justify-content: flex-start;
  width: 100%;
}
section[data-testid="stSidebar"] [data-testid^="stBaseButton"] p { text-align: left; }
</style>
"""


def lesson_status(client: ApiClient, token: str | None, course_id: str) -> dict[str, Any]:
    """Per-lesson progress for the outline's marks, keyed by lesson id. Empty for guests,
    or if progress cannot be loaded: the outline then just shows no marks."""
    if token is None:
        return {}
    try:
        progress = client.progress(token, course_id)
    except ApiError:
        return {}
    return {
        lesson["lesson_id"]: lesson
        for module in progress.get("modules", [])
        for lesson in module.get("lessons", [])
    }


def lesson_icon(stats: dict[str, Any] | None, current: bool) -> str:
    """Done: tried and not weak. Started: tried but still weak. Otherwise not started."""
    if current:
        return CURRENT
    if not stats or stats.get("mastery") is None:
        return NOT_STARTED
    return STARTED if stats.get("weak") else DONE


def show_outline(outline: dict[str, Any], lesson_id: str, status: dict[str, Any]) -> None:
    module = next(
        (m for m in outline["modules"] if any(x["id"] == lesson_id for x in m["lessons"])),
        None,
    )
    with st.sidebar:
        st.html(OUTLINE_CSS)
        st.button(
            outline["title"],
            key="outline:course",
            icon=":material/arrow_back:",
            type="tertiary",
            help="All lessons in this course",
            on_click=open_lesson,
            args=(None,),
        )
        if module is None:
            return
        st.caption(f"{module['position']}. {module['title']}")
        for lesson in module["lessons"]:
            current = lesson["id"] == lesson_id
            st.button(
                lesson["title"],
                key=f"outline:{lesson['id']}",
                icon=lesson_icon(status.get(lesson["id"]), current),
                type="secondary" if current else "tertiary",
                width="stretch",
                on_click=open_lesson,
                args=(lesson["id"],),
            )
