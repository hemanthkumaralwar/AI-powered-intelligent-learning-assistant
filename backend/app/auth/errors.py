"""Authentication failures. Messages are safe to show: they never reveal which part failed."""


class AuthConfigurationError(Exception):
    """JWT_SECRET_KEY is missing, so tokens cannot be issued or checked."""


class InvalidCredentialsError(Exception):
    """Username or password is wrong (deliberately not saying which)."""


class InvalidTokenError(Exception):
    """The bearer token is malformed, tampered with, expired, or its user no longer exists."""
