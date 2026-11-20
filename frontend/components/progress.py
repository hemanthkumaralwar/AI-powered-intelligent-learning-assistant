"""Progress on the LearnX course page: lessons due for review, what to do next, and
mastery per module."""

from collections.abc import Callable
from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError
from components.lesson_nav import review_lesson
from components.practice import show_platform_activities

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


def load_due_reviews(client: ApiClient, token: str, course_id: str) -> list[dict[str, Any]]:
    """Lessons due for review now (spaced review). Empty if the course's switch is off; on
    an error the list is left out with a short note, the rest of the page still works."""
    try:
        body = client.reviews(token, course_id)
    except ApiError as exc:
        st.caption(f"Reviews could not be loaded: {exc}")
        return []
    return [review for review in body["reviews"] if review["due"]]


def show_due_reviews(due: list[dict[str, Any]]) -> None:
    st.markdown("#### Due for review")
    if not due:
        st.caption("Nothing is due for review right now.")
        return
    st.caption("Spaced review: redo one exercise in each to make it stick.")
    for review in due:
        with st.container(border=True):
            st.markdown(f"🕒 **{review['lesson_title']}** · {review['module_title']}")
            days = review["interval_days"]
            st.caption(f"Due now · current gap {days} day{'' if days == 1 else 's'}")
            st.button(
                "Review",
                key=f"review:{review['lesson_id']}",
                type="primary",
                on_click=review_lesson,
                args=(review["lesson_id"],),
            )


def show_next_steps(
    picks: dict[str, Any], open_lesson: OpenLesson, due_lessons: frozenset[str] = frozenset()
) -> None:
    """What to do next, leaving out reviews of lessons already listed as due."""
    st.markdown("#### What to do next")
    st.caption("Based on your graded exercise attempts.")
    shown = [
        pick
        for pick in picks["recommendations"]
        if not (pick["kind"] == "review" and pick["lesson_id"] in due_lessons)
    ]
    if not shown:
        if len(shown) < len(picks["recommendations"]):
            st.caption("Your reviews are listed under Due for review.")
        else:
            st.success("Nothing to review and nothing left to start. Well done!")
    for pick in shown:
        show_recommendation(pick, open_lesson)


def show_recommendation(pick: dict[str, Any], open_lesson: OpenLesson) -> None:
    icon = "🔁" if pick["kind"] == "review" else "➡️"
    with st.container(border=True):
        st.markdown(f"{icon} **{pick['lesson_title']}** · {pick['module_title']}")
        st.caption(pick["reason"])
        for item in pick["exercises"]:
            score = "not tried" if item["score"] is None else f"{item['score']:.0%}"
            name = EXERCISE_NAMES.get(item["kind"], item["kind"])
            st.markdown(f"- {name}: {item['title']} ({score})")
        show_platform_activities(pick["practice"], pick.get("practice_url"))
        if st.button("Open lesson", key=f"next:{pick['lesson_id']}", type="primary"):
            open_lesson(pick["lesson_id"])


def mastery_label(mastery: float | None) -> str:
    return "not started" if mastery is None else f"{mastery:.0%}"
