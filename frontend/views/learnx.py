"""LearnX: your courses, a course's modules with progress and what to do next, and each
lesson with Reading, Practice, Code and Quiz & activities tabs.

Where you are (course, lesson, tab) lives in `st.session_state` (components/lesson_nav.py),
so it survives reruns, and Arc can open a lesson's Practice tab directly.
"""

from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError
from components.coding_helper import show_coding_helper
from components.compiler import LANGUAGES
from components.lesson import show_lesson_header, show_reading
from components.lesson_nav import COURSE, LESSON, TAB, open_course, open_lesson
from components.practice import show_exercises, show_platform_activities
from components.progress import load_progress, mastery_label, show_next_steps
from session import Session, current

CATALOG_COLUMNS = 3
LESSON_TABS = ["Reading", "Practice", "Code", "Quiz & activities"]


def main() -> None:
    session = current()
    course_id, lesson_id = st.session_state.get(COURSE), st.session_state.get(LESSON)
    try:
        if course_id is None:
            show_catalog(session.client, session.token)
            return
        outline = session.client.course(session.token, course_id)
        if lesson_id is None:
            show_course(session, outline)
        else:
            show_lesson(session, outline, session.client.lesson(session.token, lesson_id))
    except ApiError as exc:
        st.error(str(exc))
        st.button("Back to all courses", on_click=open_course, args=(None,))


def show_catalog(client: ApiClient, token: str) -> None:
    st.markdown("#### Your courses")
    courses = client.courses(token)
    if not courses:
        st.info("No courses yet. An admin needs to upload one first.")
        return
    columns = st.columns(CATALOG_COLUMNS)
    for index, course in enumerate(courses):
        with columns[index % CATALOG_COLUMNS].container(border=True):
            st.markdown(f"**{course['title']}**")
            language = LANGUAGES.get(course["language"], course["language"])
            level = (course.get("level") or "").capitalize()
            st.caption(" · ".join(part for part in (language, level) if part))
            if course.get("description"):
                st.markdown(course["description"])
            st.button(
                "Open course",
                key=f"course:{course['id']}",
                type="primary",
                on_click=open_course,
                args=(course["id"],),
            )


def show_course(session: Session, outline: dict[str, Any]) -> None:
    st.button(
        "All courses",
        icon=":material/arrow_back:",
        type="tertiary",
        on_click=open_course,
        args=(None,),
    )
    st.markdown(f"## {outline['title']}")
    if outline.get("description"):
        st.caption(outline["description"])
    loaded = load_progress(session.client, session.token, outline["id"])
    picks, progress = loaded if loaded else (None, None)
    modules_column, next_column = st.columns([3, 2], gap="large")
    with modules_column:
        show_modules(outline, progress)
    if picks is not None:
        with next_column:
            show_next_steps(picks, _go_to_lesson)


def show_modules(outline: dict[str, Any], progress: dict[str, Any] | None) -> None:
    modules = {m["module_id"]: m for m in (progress or {}).get("modules", [])}
    for module in outline["modules"]:
        stats = modules.get(module["id"], {})
        lessons = {lesson["lesson_id"]: lesson for lesson in stats.get("lessons", [])}
        label = f"{module['position']}. {module['title']} · {mastery_label(stats.get('mastery'))}"
        with st.expander(label, expanded=module is outline["modules"][0]):
            for lesson in module["lessons"]:
                done = lessons.get(lesson["id"], {})
                title_column, score_column, open_column = st.columns(
                    [6, 2, 2], vertical_alignment="center"
                )
                title_column.markdown(lesson["title"])
                weak = " · review" if done.get("weak") else ""
                score_column.caption(mastery_label(done.get("mastery")) + weak)
                open_column.button(
                    "Open", key=f"lesson:{lesson['id']}", on_click=open_lesson, args=(lesson["id"],)
                )


def show_lesson(session: Session, outline: dict[str, Any], lesson: dict[str, Any]) -> None:
    st.button(
        outline["title"],
        icon=":material/arrow_back:",
        type="tertiary",
        on_click=open_lesson,
        args=(None,),
    )
    language = outline["language"]
    show_lesson_header(lesson)
    reading, practice, code, activities = st.tabs(LESSON_TABS, default=st.session_state.get(TAB))
    with reading:
        show_reading(lesson, language)
    with practice:
        show_exercises(session.client, session.token, lesson, language)
    with code:
        show_coding_helper(session.client, session.token, language)
    with activities:
        found = lesson.get("content", {}).get("practice", [])
        if found:
            show_platform_activities(found)
        else:
            st.info("This lesson has no quizzes or activities on the platform.")
    show_neighbours(outline, lesson["id"])


def show_neighbours(outline: dict[str, Any], lesson_id: str) -> None:
    """Previous and next lesson in course order."""
    order = [lesson for module in outline["modules"] for lesson in module["lessons"]]
    index = next((i for i, lesson in enumerate(order) if lesson["id"] == lesson_id), None)
    if index is None:
        return
    st.divider()
    previous_column, next_column = st.columns(2)
    if index > 0:
        previous_column.button(
            f"Previous: {order[index - 1]['title']}",
            icon=":material/arrow_back:",
            on_click=open_lesson,
            args=(order[index - 1]["id"],),
        )
    if index + 1 < len(order):
        next_column.button(
            f"Next: {order[index + 1]['title']}",
            icon=":material/arrow_forward:",
            on_click=open_lesson,
            args=(order[index + 1]["id"],),
        )


def _go_to_lesson(lesson_id: str) -> None:
    open_lesson(lesson_id)
    st.rerun()


main()
