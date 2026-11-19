"""My progress: what to do next, and mastery per module and lesson."""

from typing import Any

import streamlit as st

from api_client import ApiError
from components.practice import show_platform_activities
from session import current

EXERCISE_NAMES = {
    "interactive": "Try it yourself",
    "mini_challenge": "Mini challenge",
    "bug_hunt": "Bug hunt",
}


def main() -> None:
    session = current()
    st.title("My progress")
    try:
        picks = session.client.recommendations(session.token)
        progress = session.client.progress(session.token, picks["course_id"])
    except ApiError as exc:
        st.error(str(exc))
        return
    st.caption(f"Course: {picks['course_title']} · based on your graded exercise attempts")
    st.subheader("What to do next")
    if not picks["recommendations"]:
        st.success("Nothing to review and nothing left to start. Well done!")
    for pick in picks["recommendations"]:
        show_recommendation(pick)
    st.subheader("Mastery")
    for module in progress["modules"]:
        show_module(module)


def show_recommendation(pick: dict[str, Any]) -> None:
    icon = "🔁" if pick["kind"] == "review" else "➡️"
    with st.container(border=True):
        st.markdown(f"{icon} **{pick['lesson_title']}** · {pick['module_title']}")
        st.caption(pick["reason"])
        for item in pick["exercises"]:
            score = "not tried" if item["score"] is None else f"{item['score']:.0%}"
            name = EXERCISE_NAMES.get(item["kind"], item["kind"])
            st.markdown(f"- {name}: {item['title']} ({score})")
        show_platform_activities(pick["practice"], pick.get("practice_url"))


def show_module(module: dict[str, Any]) -> None:
    mastery = module["mastery"]
    label = "not started" if mastery is None else f"{mastery:.0%}"
    st.markdown(f"**{module['title']}** · {label} · {module['coverage']:.0%} of lessons tried")
    st.progress(mastery or 0.0)
    weak = [lesson["title"] for lesson in module["lessons"] if lesson["weak"]]
    if weak:
        st.caption("Needs review: " + ", ".join(weak))


main()
