"""Progress on the LearnX course page: what to do next, and mastery per module."""

from collections.abc import Callable
from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError

EXERCISE_NAMES = {
    "interactive": "Try it yourself",
    "mini_challenge": "Mini challenge",
    "bug_hunt": "Bug hunt",
}

type OpenLesson = Callable[[str], None]


def load_progress(
    client: ApiClient, token: str, course_id: str
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """(recommendations, progress) for the course, or None with the error shown."""
    try:
        picks = client.recommendations(token, course_id)
        progress = client.progress(token, course_id)
    except ApiError as exc:
        st.error(str(exc))
        return None
    return picks, progress


def show_next_steps(picks: dict[str, Any], open_lesson: OpenLesson) -> None:
    st.markdown("#### What to do next")
    st.caption("Based on your graded exercises and lesson quiz scores.")
    if not picks["recommendations"]:
        st.success("Nothing to review and nothing left to start. Well done!")
    for pick in picks["recommendations"]:
        show_recommendation(pick, open_lesson)


def show_recommendation(pick: dict[str, Any], open_lesson: OpenLesson) -> None:
    icon = "🔁" if pick["kind"] == "review" else "➡️"
    with st.container(border=True):
        st.markdown(f"{icon} **{pick['lesson_title']}** · {pick['module_title']}")
        st.caption(pick["reason"])
        if pick.get("quiz_score") is not None:
            st.markdown(f"- Lesson quiz ({pick['quiz_score']:.0%})")
        for item in pick["exercises"]:
            score = "not tried" if item["score"] is None else f"{item['score']:.0%}"
            name = EXERCISE_NAMES.get(item["kind"], item["kind"])
            st.markdown(f"- {name}: {item['title']} ({score})")
        if st.button("Open lesson", key=f"next:{pick['lesson_id']}", type="primary"):
            open_lesson(pick["lesson_id"])


def mastery_label(mastery: float | None) -> str:
    return "not started" if mastery is None else f"{mastery:.0%}"
