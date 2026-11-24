"""LearnX: the courses, a course's modules (with progress and what to do next once signed
in), and each lesson with Reading, Ask Nexus, Practice, Code and Quiz & activities tabs.

Open to everyone (Step 24): guests read courses and lessons; Nexus, practice, the coding
helper and progress need an account, and their tabs say so.

An open lesson shows its module's lessons in the sidebar (components/outline.py; the
sidebar's own button hides it) and previous/next arrows beside its title.

Where you are (course and lesson) lives in `st.session_state` (components/lesson_nav.py),
so it survives reruns.
"""

from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError
from components.coding_helper import show_coding_helper
from components.compiler import LANGUAGES
from components.lesson import show_reading
from components.lesson_nav import COURSE, LESSON, open_course, open_lesson
from components.nexus import show_nexus
from components.outline import lesson_status, show_outline
from components.practice import show_exercises, show_platform_activities
from components.progress import load_progress, mastery_label, show_next_steps
from components.quiz import show_quiz
from menu import SIGN_IN
from session import Visitor, current_visitor

CATALOG_COLUMNS = 3
LESSON_TABS = ["Reading", "Ask Nexus", "Practice", "Code", "Quiz & activities"]


def main() -> None:
    visitor = current_visitor()
    course_id, lesson_id = st.session_state.get(COURSE), st.session_state.get(LESSON)
    try:
        if course_id is None:
            show_catalog(visitor.client, visitor.token)
            return
        outline = visitor.client.course(visitor.token, course_id)
        if lesson_id is None:
            show_course(visitor, outline)
        else:
            show_lesson(visitor, outline, visitor.client.lesson(visitor.token, lesson_id))
    except ApiError as exc:
        st.error(str(exc))
        st.button("Back to all courses", on_click=open_course, args=(None,))


def show_catalog(client: ApiClient, token: str | None) -> None:
    st.markdown("#### Courses")
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


def show_course(visitor: Visitor, outline: dict[str, Any]) -> None:
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
    modules_column, next_column = st.columns([3, 2], gap="large")
    if visitor.token is None:
        with modules_column:
            show_modules(outline, None, scores=False)
        with next_column:
            sign_in_prompt("track your progress and see what to do next")
        return
    loaded = load_progress(visitor.client, visitor.token, outline["id"])
    picks, progress = loaded if loaded else (None, None)
    with modules_column:
        show_modules(outline, progress)
    if picks is not None:
        with next_column:
            show_next_steps(picks, _go_to_lesson)


def show_modules(
    outline: dict[str, Any], progress: dict[str, Any] | None, scores: bool = True
) -> None:
    """Modules and their lessons; `scores` off for guests (no progress to show)."""
    modules = {m["module_id"]: m for m in (progress or {}).get("modules", [])}
    for module in outline["modules"]:
        stats = modules.get(module["id"], {})
        lessons = {lesson["lesson_id"]: lesson for lesson in stats.get("lessons", [])}
        label = f"{module['position']}. {module['title']}"
        if scores:
            label += f" · {mastery_label(stats.get('mastery'))}"
        with st.expander(label, expanded=module is outline["modules"][0]):
            for lesson in module["lessons"]:
                lesson_row(lesson, lessons.get(lesson["id"], {}) if scores else None)


def lesson_row(lesson: dict[str, Any], done: dict[str, Any] | None) -> None:
    """One lesson in a module: title, its mastery (None: not shown, e.g. for guests), Open."""
    title_column, score_column, open_column = st.columns([6, 2, 2], vertical_alignment="center")
    title_column.markdown(lesson["title"])
    if done is not None:
        weak = " · review" if done.get("weak") else ""
        score_column.caption(mastery_label(done.get("mastery")) + weak)
    open_column.button(
        "Open", key=f"lesson:{lesson['id']}", on_click=open_lesson, args=(lesson["id"],)
    )


def show_lesson(visitor: Visitor, outline: dict[str, Any], lesson: dict[str, Any]) -> None:
    show_outline(outline, lesson["id"], lesson_status(visitor.client, visitor.token, outline["id"]))
    language = outline["language"]
    show_lesson_header(outline, lesson)
    reading, nexus, practice, code, activities = st.tabs(LESSON_TABS)
    with reading:
        show_reading(lesson, language)
    token = visitor.token
    with nexus:
        if token is None:
            sign_in_prompt("ask Nexus, the course assistant")
        else:
            show_nexus(visitor.client, token, outline["id"])
    with practice:
        if token is None:
            sign_in_prompt("run and submit this lesson's exercises")
        else:
            show_exercises(visitor.client, token, lesson, language)
    with code:
        if token is None:
            sign_in_prompt("use the coding helper")
        else:
            show_coding_helper(visitor.client, token, language)
    with activities:
        show_activities(visitor, lesson)


def show_activities(visitor: Visitor, lesson: dict[str, Any]) -> None:
    """The lesson quiz (taken here, counted in progress), then the platform's activities."""
    found = lesson.get("content", {}).get("practice", [])
    has_quiz = any(activity["kind"] == "quiz" for activity in found)
    if has_quiz and visitor.token is None:
        sign_in_prompt("take this lesson's quiz and count it in your progress")
    elif has_quiz:
        show_quiz(visitor.client, visitor.token, lesson["id"])
    if found:
        show_platform_activities(found)
    else:
        st.info("This lesson has no quiz or activities.")


def show_lesson_header(outline: dict[str, Any], lesson: dict[str, Any]) -> None:
    """The lesson title with previous/next arrows (course order) beside it."""
    order = [item for module in outline["modules"] for item in module["lessons"]]
    index = next((i for i, item in enumerate(order) if item["id"] == lesson["id"]), None)
    title_column, previous_column, next_column = st.columns([10, 1, 1], vertical_alignment="center")
    title_column.markdown(f"## {lesson['title']}")
    if index is None:
        return
    if index > 0:
        previous_column.button(
            "",
            key="lesson:previous",
            icon=":material/chevron_left:",
            help=f"Previous: {order[index - 1]['title']}",
            on_click=open_lesson,
            args=(order[index - 1]["id"],),
        )
    if index + 1 < len(order):
        next_column.button(
            "",
            key="lesson:next",
            icon=":material/chevron_right:",
            help=f"Next: {order[index + 1]['title']}",
            on_click=open_lesson,
            args=(order[index + 1]["id"],),
        )


def sign_in_prompt(to_do: str) -> None:
    st.info(f"Sign in to {to_do}.")
    st.page_link(SIGN_IN.path, label="Sign in", icon=SIGN_IN.icon)


def _go_to_lesson(lesson_id: str) -> None:
    open_lesson(lesson_id)
    st.rerun()


main()
