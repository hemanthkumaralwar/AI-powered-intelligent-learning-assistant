"""Course browser: pick a course and lesson, read it, then practise."""

import streamlit as st

from api_client import ApiError
from components.lesson import show_lesson
from components.practice import pick_course, pick_lesson, show_platform_activities
from session import current


def main() -> None:
    session = current()
    st.title("Courses")
    try:
        course = pick_course(session.client, session.token)
        lesson = pick_lesson(session.client, session.token, course) if course else None
    except ApiError as exc:
        st.error(str(exc))
        return
    if course is None or lesson is None:
        return
    show_lesson(lesson, course["language"])
    show_platform_activities(lesson.get("content", {}).get("practice", []))
    if lesson["exercises"]:
        st.page_link("views/practice.py", label="Try this lesson's coding exercises", icon="🧪")


main()
