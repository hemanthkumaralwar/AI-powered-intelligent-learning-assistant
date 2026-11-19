"""Practice: a lesson's coding exercises in the compiler panel, graded on submit."""

from components.practice import show_practice
from session import current


def main() -> None:
    session = current()
    show_practice(session.client, session.token)


main()
