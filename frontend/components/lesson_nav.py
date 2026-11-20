"""Where the student is in LearnX (course, lesson, tab), shared by LearnX and Nexus.

The state lives in `st.session_state`, so it survives reruns and page switches. The tab
stays fixed for the whole visit to a lesson: changing `st.tabs(default=...)` mid-visit
would make Streamlit redraw the tabs and jump back to the first one.
"""

import streamlit as st

COURSE = "learnx:course"  # the open course's id
LESSON = "learnx:lesson"  # the open lesson's id
TAB = "learnx:tab"  # the tab a lesson opens on; None = Reading
LEARNX_PAGE = "views/learnx.py"
PRACTICE_TAB = "Practice"


def open_course(course_id: str | None) -> None:
    st.session_state[COURSE] = course_id
    st.session_state[LESSON] = None
    st.session_state[TAB] = None


def open_lesson(lesson_id: str | None) -> None:
    st.session_state[LESSON] = lesson_id
    st.session_state[TAB] = None


def review_lesson(lesson_id: str) -> None:
    """Open a lesson due for review on its Practice tab (reviewing = re-submitting an
    exercise). Same page, so a button callback can call it."""
    st.session_state[LESSON] = lesson_id
    st.session_state[TAB] = PRACTICE_TAB


def open_practice(course_id: str, lesson_id: str) -> None:
    """Go to LearnX with the lesson open on its Practice tab (used from Nexus)."""
    st.session_state[COURSE] = course_id
    st.session_state[LESSON] = lesson_id
    st.session_state[TAB] = PRACTICE_TAB
    st.switch_page(LEARNX_PAGE)
