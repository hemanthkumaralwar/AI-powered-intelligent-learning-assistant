"""Practice view: pick a course, lesson and exercise, then work on it in the compiler
panel with the exercise's starter code. A minimal host for the panel; the full lesson
pages arrive in Step 19.
"""

from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError
from components.compiler import compiler_panel

ACTIVITY_NAMES = {
    "quiz": "Quiz",
    "drag_and_drop": "Drag and drop",
    "card_matching": "Card matching",
    "code_reordering": "Code reordering",
}
ACTIVITY_UNITS = {
    "quiz": "questions",
    "drag_and_drop": "items",
    "card_matching": "pairs",
    "code_reordering": "lines",
}
EXERCISE_LABELS = {
    "interactive": "Try it yourself",
    "mini_challenge": "Mini challenge",
    "bug_hunt": "Bug hunt",
}


def show_practice(client: ApiClient, token: str) -> None:
    st.header("Practice")
    try:
        course = _pick_course(client, token)
        lesson = _pick_lesson(client, token, course) if course else None
    except ApiError as exc:
        st.error(str(exc))
        return
    if course is None or lesson is None:
        return
    show_platform_activities(lesson.get("content", {}).get("practice", []))
    exercises = lesson["exercises"]
    if not exercises:
        st.info("This lesson has no coding exercises; the editor below starts empty.")
        compiler_panel(client, token, key=f"lesson-{lesson['id']}", language=course["language"])
        return
    exercise = st.selectbox(
        "Exercise",
        exercises,
        format_func=lambda e: f"{EXERCISE_LABELS.get(e['kind'], e['kind'])}: {e['title']}",
    )
    st.markdown(exercise["instructions"])
    if exercise["hints"]:
        with st.expander("Hints"):
            for hint in exercise["hints"]:
                st.markdown(f"- {hint}")
    compiler_panel(
        client,
        token,
        key=f"exercise-{exercise['id']}",
        language=course["language"],
        starter_code=exercise["starter_code"],
        exercise_id=str(exercise["id"]),
    )


def activity_label(activity: dict[str, Any]) -> str:
    unit = ACTIVITY_UNITS.get(activity["kind"], "")
    size = f" ({activity['count']} {unit})" if unit else ""
    return f"{ACTIVITY_NAMES.get(activity['kind'], activity['kind'])}: {activity['title']}{size}"


def show_platform_activities(activities: list[dict[str, Any]]) -> None:
    """The lesson's quizzes and activities, which run on the learning platform."""
    if activities:
        lines = "\n".join(f"- {activity_label(a)}" for a in activities)
        st.info(f"**Practise this lesson on the learning platform:**\n{lines}")


def _pick_course(client: ApiClient, token: str) -> dict[str, Any] | None:
    courses = client.courses(token)
    if not courses:
        st.info("No courses yet. An admin needs to upload one first.")
        return None
    return st.selectbox("Course", courses, format_func=lambda c: c["title"])


def _pick_lesson(client: ApiClient, token: str, course: dict[str, Any]) -> dict[str, Any] | None:
    outline = client.course(token, course["id"])
    lessons = [
        (module["title"], lesson) for module in outline["modules"] for lesson in module["lessons"]
    ]
    if not lessons:
        st.info("This course has no lessons yet.")
        return None
    _, lesson = st.selectbox(
        "Lesson", lessons, format_func=lambda pair: f"{pair[0]} › {pair[1]['title']}"
    )
    return client.lesson(token, lesson["id"])
