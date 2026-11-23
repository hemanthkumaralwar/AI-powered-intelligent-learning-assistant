"""Which pages each visitor sees in the top navigation (pure, so it can be tested without
running the app).

Guests get LearnX (public reading) and Sign in. Signed-in students get LearnX, where each
lesson has an "Ask Nexus" tab (the course assistant). Admins also get Settings, served
at `<app URL>/admin`.

The page scripts live in `views/`, not `pages/`: Streamlit auto-lists a `pages/` folder
in the sidebar whenever `st.navigation` is not called, which would show every page,
admin ones included, to anyone.

Hiding admin pages from students is a convenience: the admin page checks the role too, and
the API refuses admin actions from students (403) whatever the menu shows.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MenuPage:
    path: str  # page script
    title: str
    icon: str  # Material icon
    url_path: str | None = None  # None: Streamlit derives it from the file name


LEARNX = MenuPage("views/learnx.py", "LearnX", ":material/menu_book:")
SIGN_IN = MenuPage("views/sign_in.py", "Sign in", ":material/login:", "signin")
SETTINGS = MenuPage("views/admin_courses.py", "Settings", ":material/settings:", "admin")


def pages_for(user: dict | None) -> list[MenuPage]:
    if user is None:
        return [LEARNX, SIGN_IN]
    if user.get("role") == "admin":
        return [LEARNX, SETTINGS]
    return [LEARNX]
