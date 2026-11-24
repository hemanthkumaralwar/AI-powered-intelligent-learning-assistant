"""Where the student is in LearnX (course and lesson).

The state lives in `st.session_state`, so it survives reruns.
"""

import streamlit as st

COURSE = "learnx:course"  # the open course's id
LESSON = "learnx:lesson"  # the open lesson's id


def open_course(course_id: str | None) -> None:
    st.session_state[COURSE] = course_id
    st.session_state[LESSON] = None


def open_lesson(lesson_id: str | None) -> None:
    st.session_state[LESSON] = lesson_id
