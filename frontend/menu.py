"""Which pages each role sees (pure, so it can be tested without running the app).

The page scripts live in `views/`, not `pages/`: Streamlit auto-lists a `pages/` folder
in the sidebar whenever `st.navigation` is not called (the login screen), which would
show every page, admin ones included, to anyone.

Hiding admin pages from students is a convenience: the admin page checks the role too, and
the API refuses admin actions from students (403) whatever the menu shows.
"""

STUDENT_PAGES = [
    ("views/courses.py", "Courses", "📚"),
    ("views/chat.py", "Ask the assistant", "💬"),
    ("views/practice.py", "Practice", "🧪"),
    ("views/coding.py", "Coding helper", "🛠️"),
    ("views/progress.py", "My progress", "📈"),
]
ADMIN_PAGES = [("views/admin_courses.py", "Manage courses", "🗂️")]


def pages_for(role: str | None) -> dict[str, list[tuple[str, str, str]]]:
    """Menu sections -> (page file, title, icon)."""
    sections = {"Learn": STUDENT_PAGES}
    if role == "admin":
        sections["Admin"] = ADMIN_PAGES
    return sections
