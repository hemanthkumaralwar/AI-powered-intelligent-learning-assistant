"""Practice inside a lesson: its coding exercises in the compiler panel, and the quizzes
and activities that run on the learning platform."""

from typing import Any

import streamlit as st

from api_client import ApiClient
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


def show_exercises(client: ApiClient, token: str, lesson: dict[str, Any], language: str) -> None:
    """The lesson's coding exercises in the compiler panel, graded on submit."""
    exercises = lesson["exercises"]
    if not exercises:
        st.info("This lesson has no coding exercises; the editor below starts empty.")
        compiler_panel(client, token, key=f"lesson-{lesson['id']}", language=language)
        return
    exercise = st.selectbox(
        "Exercise",
        exercises,
        format_func=lambda e: f"{EXERCISE_LABELS.get(e['kind'], e['kind'])}: {e['title']}",
        key=f"exercises:{lesson['id']}",
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
        language=language,
        starter_code=exercise["starter_code"],
        exercise_id=str(exercise["id"]),
    )


def activity_label(activity: dict[str, Any]) -> str:
    unit = ACTIVITY_UNITS.get(activity["kind"], "")
    size = f" ({activity['count']} {unit})" if unit else ""
    return f"{ACTIVITY_NAMES.get(activity['kind'], activity['kind'])}: {activity['title']}{size}"


def show_platform_activities(activities: list[dict[str, Any]], url: str | None = None) -> None:
    """The lesson's quizzes and activities, which run on the learning platform."""
    if activities:
        lines = "\n".join(f"- {activity_label(a)}" for a in activities)
        link = f"\n\n[Open this lesson on the platform]({url})" if url else ""
        st.info(f"**Practise this lesson on the learning platform:**\n{lines}{link}")


def show_practice_pointers(pointers: list[dict[str, Any]]) -> None:
    """Practice pointers from chat or coding answers: each lesson's platform activities."""
    for pointer in pointers:
        lines = "\n".join(f"- {activity_label(a)}" for a in pointer["activities"])
        title = (
            f"[{pointer['lesson_title']}]({pointer['url']})"
            if pointer.get("url")
            else (pointer["lesson_title"])
        )
        st.info(f"**Practise {title} on the learning platform:**\n{lines}")
