"""The lesson quiz in the Quiz & activities tab: answer every question, submit, then see the
score, the right answers and their explanations. Marking happens on the server, and the
score counts toward the student's progress.
"""

from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError


def _key(lesson_id: str, part: str) -> str:
    return f"quiz:{lesson_id}:{part}"


def show_quiz(client: ApiClient, token: str, lesson_id: str) -> None:
    st.markdown("#### Lesson quiz")
    try:
        quiz = client.quiz(token, lesson_id)
        attempts = client.quiz_attempts(token, lesson_id)
    except ApiError as exc:
        st.error(str(exc))
        return
    show_past_scores(attempts)
    result = st.session_state.get(_key(lesson_id, "result"))
    if result is not None:
        show_marked(quiz, result)
        st.button(
            "Retake the quiz",
            key=_key(lesson_id, "retake"),
            icon=":material/replay:",
            on_click=_retake,
            args=(lesson_id,),
        )
        return
    answers = quiz_form(quiz, lesson_id)
    if answers is None:
        return
    left = sum(choice is None for choice in answers.values())
    if left:
        st.warning(f"Answer every question first ({left} left).")
        return
    try:
        st.session_state[_key(lesson_id, "result")] = client.submit_quiz(token, lesson_id, answers)
    except ApiError as exc:
        st.error(str(exc))
        return
    st.rerun()


def show_past_scores(attempts: list[dict[str, Any]]) -> None:
    if not attempts:
        st.caption("Your score counts toward your progress on this lesson.")
        return
    last = attempts[0]
    best = max(attempts, key=lambda a: a["correct"] / a["total"])
    st.caption(
        f"Last score {last['correct']}/{last['total']} · best {best['correct']}/{best['total']}"
        f" · {len(attempts)} attempt{'' if len(attempts) == 1 else 's'}"
    )


def quiz_form(quiz: dict[str, Any], lesson_id: str) -> dict[str, int | None] | None:
    """The questions as one form. Returns question id -> chosen option id once submitted,
    else None. A new round (after a retake) starts with every answer cleared."""
    round_ = st.session_state.get(_key(lesson_id, "round"), 0)
    with st.form(_key(lesson_id, f"form{round_}")):
        answers: dict[str, int | None] = {}
        for number, question in enumerate(quiz["questions"], 1):
            texts = {option["id"]: option["text"] for option in question["options"]}
            answers[question["id"]] = st.radio(
                f"**{number}. {question['question']}**",
                list(texts),
                index=None,
                format_func=texts.__getitem__,
                key=_key(lesson_id, f"q{round_}:{question['id']}"),
            )
        submitted = st.form_submit_button("Submit answers", type="primary")
    return answers if submitted else None


def show_marked(quiz: dict[str, Any], result: dict[str, Any]) -> None:
    correct, total = result["correct"], result["total"]
    st.markdown(f"**Score: {correct}/{total} ({correct / total:.0%})**")
    marked = {item["question_id"]: item for item in result["results"]}
    for number, question in enumerate(quiz["questions"], 1):
        item = marked.get(question["id"])
        if item is None:
            continue
        texts = {option["id"]: option["text"] for option in question["options"]}
        with st.container(border=True):
            icon = "✅" if item["correct"] else "❌"
            st.markdown(f"{icon} **{number}. {question['question']}**")
            chosen = texts.get(item["chosen"], "no answer")
            if item["correct"]:
                st.markdown(f"Your answer: {chosen}")
            else:
                st.markdown(
                    f"Your answer: {chosen}  \nCorrect answer: {texts[item['correct_option']]}"
                )
            if item.get("explanation"):
                st.caption(item["explanation"])


def _retake(lesson_id: str) -> None:
    st.session_state.pop(_key(lesson_id, "result"), None)
    st.session_state[_key(lesson_id, "round")] = (
        st.session_state.get(_key(lesson_id, "round"), 0) + 1
    )
