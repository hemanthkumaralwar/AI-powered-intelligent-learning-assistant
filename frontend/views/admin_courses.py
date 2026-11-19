"""Admin: upload course JSON, watch indexing, delete courses, re-index.

Only admins get this page in the menu; the check below and the API's own 403 back that up.
"""

from typing import Any

import streamlit as st

from api_client import ApiClient, ApiError
from components.compiler import LANGUAGES
from session import current

STATUS_ICONS = {"pending": "⏳", "processing": "⚙️", "ready": "✅", "failed": "❌"}


def main() -> None:
    session = current()
    if not session.is_admin:
        st.error("This page is for admins.")
        st.stop()
    st.title("Manage courses")
    upload(session.client, session.token)
    documents = show_documents(session.client, session.token)
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
            st.success(f"Deleted `{course_id}`.")
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
