"""Admin: upload course JSON, watch indexing, per-course feature switches, delete courses,
re-index.

Only admins get this page in the menu; the check below and the API's own 403 back that up.
"""

from dataclasses import dataclass
from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError
from components.compiler import LANGUAGES
from session import current

STATUS_ICONS = {"pending": "⏳", "processing": "⚙️", "ready": "✅", "failed": "❌"}
FLASH = "admin:flash"
FEATURE_ERROR = "admin:feature-error"  # set by the switch callback, shown on the next run


def main() -> None:
    session = current()
    if not session.is_admin:
        st.error("This page is for admins.")
        st.stop()
    st.title("Manage courses")
    if flash := st.session_state.pop(FLASH, None):
        st.success(flash)
    upload(session.client, session.token)
    documents = show_documents(session.client, session.token)
    course_features(session.client, session.token)
    if documents:
        delete_course(session.client, session.token, documents)
    reindex(session.client, session.token)


def upload(client: ApiClient, token: str) -> None:
    st.subheader("Upload a course")
    with st.form("upload", clear_on_submit=True):
        file = st.file_uploader("Course JSON", type=["json"])
        language = st.selectbox(
            "Programming language", list(LANGUAGES), format_func=LANGUAGES.__getitem__
        )
        submitted = st.form_submit_button("Upload")
    if not submitted:
        return
    if file is None:
        st.warning("Choose a course JSON file first.")
        return
    try:
        document = client.upload_course(token, file.name, file.getvalue(), language)
    except ApiError as exc:
        st.error(str(exc))
        return
    st.success(
        f"Uploaded **{document['filename']}** for course `{document['course_id']}`. "
        "Indexing runs in the background; refresh the list below to follow it."
    )


def show_documents(client: ApiClient, token: str) -> list[dict[str, Any]]:
    st.subheader("Uploaded courses")
    st.button("Refresh", icon="🔄")
    try:
        documents = client.documents(token)
    except ApiError as exc:
        st.error(str(exc))
        return []
    if not documents:
        st.info("No courses uploaded yet.")
        return []
    st.dataframe(
        [
            {
                "Status": f"{STATUS_ICONS.get(d['status'], '')} {d['status']}",
                "Course": d["course_id"],
                "File": d["filename"],
                "Size (KB)": round(d["size_bytes"] / 1024),
                "Uploaded": d["created_at"][:16].replace("T", " "),
                "Problem": d.get("error_message") or "",
            }
            for d in documents
        ],
        hide_index=True,
        width="stretch",
    )
    return documents


@dataclass(frozen=True)
class Feature:
    """A per-course admin switch (a course setting on the API)."""

    short: str  # widget key part
    setting: str  # field name in PATCH /admin/courses/{id}
    label: str
    help: str


FEATURES = (
    Feature(
        "arc",
        "arc_practice_enabled",
        "Open in Practice from Nexus",
        "Nexus answers citing this course get a button that opens the lesson's Practice tab.",
    ),
    Feature(
        "review",
        "spaced_review_enabled",
        "Spaced review",
        "Students see which lessons they attempted are due for review (1, 3, 7, 14, 30 days).",
    ),
)


def course_features(client: ApiClient, token: str) -> None:
    """Per-course switches. Every course is a coding course, so every course has them."""
    st.subheader("Course features")
    try:
        courses = client.courses(token)
    except ApiError as exc:
        st.error(str(exc))
        return
    for course in courses:
        st.markdown(f"**{course['title']}**")
        for feature in FEATURES:
            key = f"feature:{feature.short}:{course['id']}"
            # on_change, not "compare with the server every run": that would call the
            # API again on every rerun whenever the two disagree (e.g. another admin
            # changed it).
            st.toggle(
                feature.label,
                value=course[feature.setting],
                key=key,
                on_change=_set_feature,
                args=(client, token, course["id"], feature, key),
                help=feature.help,
            )
    if error := st.session_state.pop(FEATURE_ERROR, None):
        st.error(error)


def _set_feature(client: ApiClient, token: str, course_id: str, feature: Feature, key: str) -> None:
    enabled = st.session_state[key]
    try:
        client.update_course_settings(token, course_id, **{feature.setting: enabled})
    except ApiError as exc:
        # Forget the flipped widget, so it is redrawn with the server's value.
        del st.session_state[key]
        st.session_state[FEATURE_ERROR] = str(exc)
        return
    state = "on" if enabled else "off"
    st.session_state[FLASH] = f"{feature.label} is {state} for `{course_id}`."


def delete_course(client: ApiClient, token: str, documents: list[dict[str, Any]]) -> None:
    with st.expander("Delete a course"):
        course_id = st.selectbox("Course", sorted({d["course_id"] for d in documents}))
        sure = st.checkbox(
            "I understand this deletes the course, its lessons, its chunks and students' "
            "exercise results for it"
        )
        if st.button("Delete course", type="primary", disabled=not sure):
            try:
                client.delete_course(token, course_id)
            except ApiError as exc:
                st.error(str(exc))
                return
            # Shown after the rerun (a message drawn now would vanish with it).
            st.session_state[FLASH] = f"Deleted `{course_id}`."
            st.rerun()


def reindex(client: ApiClient, token: str) -> None:
    with st.expander("Re-index all courses"):
        st.caption(
            "Re-queues every course. Unchanged content costs no embedding quota; after "
            "changing the embedding model everything is embedded again."
        )
        if st.button("Re-index"):
            try:
                result = client.reindex(token)
            except ApiError as exc:
                st.error(str(exc))
                return
            st.success(f"Queued {result.get('queued', 0)} document(s) for indexing.")


main()
