"""The compiler panel: edit code, run it, share it, try DOM code in a sandbox, and ask
the AI about the output. Reusable: every widget key is prefixed with the caller's `key`,
so several panels can live on one page.
"""

from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from api_client import ApiClient, ApiError
from components.sandbox import needs_dom, sandbox_page

LANGUAGES = {
    "javascript": "JavaScript",
    "python": "Python",
    "c": "C",
    "cpp": "C++",
    "java": "Java",
    "sql": "SQL",
}
# Compiler Explorer can run these; it has no JavaScript or SQL execution.
SHAREABLE = {"c", "cpp", "java", "python"}
OUTCOME_LABELS = {
    "ok": "Ran successfully",
    "compile_error": "Compile error",
    "runtime_error": "Runtime error",
    "timeout": "Stopped: took too long",
    "output_limit": "Stopped: too much output",
}
SANDBOX_HEIGHT = 440


def compiler_panel(
    client: ApiClient,
    token: str,
    *,
    key: str,
    language: str,
    starter_code: str = "",
    exercise_id: str | None = None,
) -> None:
    """`exercise_id`: the course exercise being solved, which adds "Submit for grading"."""
    languages = list(LANGUAGES)
    language = st.selectbox(
        "Language",
        languages,
        index=languages.index(language) if language in languages else 0,
        format_func=LANGUAGES.__getitem__,
        key=f"{key}:language",
    )
    code = st.text_area("Code", value=starter_code, height=260, key=f"{key}:code")
    with st.expander("Program input (stdin)"):
        stdin = st.text_area("Input", key=f"{key}:stdin", label_visibility="collapsed")

    run_column, share_column = st.columns(2)
    if run_column.button("Run", key=f"{key}:run", type="primary"):
        _run(client, token, key, language, code, stdin)
    if language in SHAREABLE and share_column.button(
        "Open in Compiler Explorer", key=f"{key}:share"
    ):
        _share(client, token, language, code)

    last_run = _current_run(key, code)
    if last_run:
        show_run(last_run)
    if language == "javascript" and needs_dom(code):
        _sandbox(key, code)
    _ask_ai(client, token, key, language, code, last_run)
    if exercise_id:
        _submit(client, token, key, exercise_id, code)


def show_run(result: dict[str, Any]) -> None:
    label = OUTCOME_LABELS.get(result.get("outcome", ""), "Finished")
    st.markdown(f"**{label}**")
    st.code(result.get("stdout") or "(no output)", language="text")
    errors = "\n".join(
        part for part in (result.get("compile_output"), result.get("stderr")) if part
    )
    if errors:
        st.code(errors, language="text")


def show_debug(answer: dict[str, Any]) -> None:
    if answer.get("exercise"):
        st.info("This is a course exercise, so the assistant gives hints, not the answer.")
    st.markdown(answer.get("summary", ""))
    for issue in answer.get("issues", []):
        st.markdown(f"**Line {issue['line']}:** {issue['problem']}")
        st.caption(f"Hint: {issue['fix_hint']}")
    if answer.get("corrected_code"):
        st.markdown("**Corrected code**")
        st.code(answer["corrected_code"])
    lessons = answer.get("related_lessons", [])
    if lessons:
        titles = ", ".join(lesson.get("lesson_title") or lesson["lesson_id"] for lesson in lessons)
        st.caption(f"Related lessons: {titles}")


def debug_evidence(last_run: dict[str, Any] | None, pasted: str) -> dict[str, Any] | None:
    """What the AI gets as evidence: this code's latest run, else output pasted from a
    run elsewhere (no outcome), else nothing."""
    if last_run:
        return {
            "outcome": last_run.get("outcome"),
            "stdout": last_run.get("stdout", ""),
            "stderr": last_run.get("stderr", ""),
            "compile_output": last_run.get("compile_output", ""),
        }
    if pasted.strip():
        return {"stdout": pasted}
    return None


def _submit(client: ApiClient, token: str, key: str, exercise_id: str, code: str) -> None:
    if st.button("Submit for grading", key=f"{key}:submit"):
        with st.spinner("Checking your solution…"):
            try:
                attempt = client.submit_attempt(token, exercise_id, code)
            except ApiError as exc:
                st.error(str(exc))
                return
        st.session_state[f"{key}:attempt"] = {"code": code, "attempt": attempt}
    saved = st.session_state.get(f"{key}:attempt")
    if saved and saved["code"] == code:
        attempt = saved["attempt"]
        show = st.success if attempt["passed"] else st.warning
        show(("Passed! " if attempt["passed"] else "Not yet. ") + attempt["feedback"])


def _run(client: ApiClient, token: str, key: str, language: str, code: str, stdin: str) -> None:
    with st.spinner("Running…"):
        try:
            result = client.run_code(token, language, code, stdin)
        except ApiError as exc:
            st.error(str(exc))
            return
    # Remember which code produced this output: once the code changes, it no longer applies.
    st.session_state[f"{key}:last_run"] = {"code": code, "result": result}


def _current_run(key: str, code: str) -> dict[str, Any] | None:
    saved = st.session_state.get(f"{key}:last_run")
    return saved["result"] if saved and saved["code"] == code else None


def _share(client: ApiClient, token: str, language: str, code: str) -> None:
    try:
        url = client.share_code(token, language, code)
    except ApiError as exc:
        st.error(str(exc))
        return
    st.success(f"Public link (anyone with it can see this code): {url}")


def _sandbox(key: str, code: str) -> None:
    with st.expander("Page sandbox: run DOM code in your browser", expanded=True):
        st.caption(
            "Runs here in your browser, isolated from this site and with no internet "
            "access. Elements the code looks up (like `.output`) are created for you."
        )
        html = st.text_area("Page HTML (optional)", key=f"{key}:html", height=100)
        if st.button("Run in page sandbox", key=f"{key}:sandbox"):
            st.session_state[f"{key}:sandboxed"] = (code, html)
        shown = st.session_state.get(f"{key}:sandboxed")
        if shown:
            components.html(sandbox_page(*shown), height=SANDBOX_HEIGHT)


def _ask_ai(
    client: ApiClient,
    token: str,
    key: str,
    language: str,
    code: str,
    last_run: dict[str, Any] | None,
) -> None:
    pasted = ""
    if not last_run:
        with st.expander("Ran it somewhere else? Paste the output"):
            pasted = st.text_area("Output", key=f"{key}:pasted", label_visibility="collapsed")
    if st.button("Ask AI about this output", key=f"{key}:ask"):
        with st.spinner("Asking the assistant…"):
            try:
                answer = client.debug_code(token, language, code, debug_evidence(last_run, pasted))
            except ApiError as exc:
                st.error(str(exc))
                return
        st.session_state[f"{key}:answer"] = {"code": code, "answer": answer}
    saved = st.session_state.get(f"{key}:answer")
    if saved and saved["code"] == code:
        show_debug(saved["answer"])
