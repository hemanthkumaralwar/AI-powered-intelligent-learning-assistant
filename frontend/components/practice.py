"""Practice inside a lesson: its coding exercises in the compiler panel, and the
activities that run on the learning platform."""

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


def show_platform_activities(activities: list[dict[str, Any]]) -> None:
    """The lesson's interactive activities, which run on the learning platform. Shown only
    in the lesson's Quiz & activities tab. The quiz is left out: it is taken in this app."""
    others = [a for a in activities if a["kind"] != "quiz"]
    if others:
        lines = "\n".join(f"- {activity_label(a)}" for a in others)
        st.info(f"**More practice on the learning platform:**\n{lines}")
