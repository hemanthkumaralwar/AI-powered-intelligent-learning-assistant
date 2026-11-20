"""Which pages each role sees in the left rail (pure, so it can be tested without running
the app).

The rail follows the LearnX platform: Arc (the course assistant) and LearnX (courses and
lessons, with practice, the coding helper and progress inside them). Admins also get
Settings (managing courses), last in the rail.

The page scripts live in `views/`, not `pages/`: Streamlit auto-lists a `pages/` folder
in the sidebar whenever `st.navigation` is not called (the login screen), which would
show every page, admin ones included, to anyone.

Hiding admin pages from students is a convenience: the admin page checks the role too, and
the API refuses admin actions from students (403) whatever the menu shows.
"""

type MenuPage = tuple[str, str, str]  # (page file, title, Material icon)

STUDENT_PAGES: list[MenuPage] = [
    ("views/arc.py", "Arc", ":material/chat_bubble_outline:"),
    ("views/learnx.py", "LearnX", ":material/menu_book:"),
]
ADMIN_PAGES: list[MenuPage] = [("views/admin_courses.py", "Settings", ":material/settings:")]


def pages_for(role: str | None) -> list[MenuPage]:
    return STUDENT_PAGES + ADMIN_PAGES if role == "admin" else list(STUDENT_PAGES)
