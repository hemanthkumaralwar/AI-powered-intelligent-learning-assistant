"""Sign-in, the profile menu in the top bar (account, explanation level, log out)."""

import streamlit as st

from api_client import ApiClient, ApiError, SessionExpiredError
from session import TOKEN_KEY, USER_KEY, sign_out

LEVELS = ["beginner", "intermediate", "advanced"]


def show_login(client: ApiClient) -> None:
    st.subheader("Log in")
    # clear_on_submit: the password must not linger in widget state after submitting.
    with st.form("login", clear_on_submit=True):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", type="primary")
    if not submitted:
        return
    try:
        st.session_state[TOKEN_KEY] = client.login(username, password)
    except ApiError as exc:
        st.error(str(exc))
        return
    st.rerun()


def load_user(client: ApiClient, token: str) -> dict | None:
    """The signed-in account, or None (with a message) when the session cannot be used."""
    try:
        user = client.me(token)
    except SessionExpiredError as exc:
        sign_out()
        st.warning(str(exc))
        st.button("Back to login")
        return None
    except ApiError as exc:
        st.error(str(exc))
        return None
    st.session_state[USER_KEY] = user
    return user


def show_profile(client: ApiClient, token: str, user: dict) -> None:
    with st.popover(user["username"], icon=":material/account_circle:", width="stretch"):
        st.markdown(f"Signed in as **{user['username']}** ({user['role']})")
        show_level(client, token, user.get("level", LEVELS[0]))
        st.caption("Light or dark: the ⋮ menu at the top right.")
        if st.button("Log out", key="account:logout", icon=":material/logout:"):
            sign_out()
            st.rerun()


def show_level(client: ApiClient, token: str, current: str) -> None:
    """Explanation depth for chat and coding answers, saved to the profile on change."""
    chosen = st.selectbox(
        "Explanation level",
        LEVELS,
        index=LEVELS.index(current) if current in LEVELS else 0,
        format_func=str.capitalize,
        help="How deep the assistant's explanations go.",
        key="account:level",
    )
    if chosen == current:
        return
    try:
        client.set_level(token, chosen)
    except ApiError as exc:
        st.error(str(exc))
        return
    st.session_state[USER_KEY] = {**st.session_state.get(USER_KEY, {}), "level": chosen}
    st.toast(f"Explanations set to {chosen}.")
