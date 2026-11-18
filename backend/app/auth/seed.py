"""Create the first admin account from ADMIN_USERNAME / ADMIN_PASSWORD at startup."""

import logging

from pydantic import SecretStr

from app.auth.service import AuthService
from app.db.errors import DuplicateError
from app.db.repositories.users import UserRepository
from app.db.session import Database

logger = logging.getLogger(__name__)


async def seed_admin(
    database: Database, auth: AuthService, username: str, password: SecretStr
) -> bool:
    """Create the admin if no account has that username. Returns True if one was created.

    Never modifies an existing account: re-running is safe, and an existing student with
    that name is never silently promoted.
    """
    async with database.session() as session:
        existing = await UserRepository(session).get_by_username(username)
        if existing is not None:
            if existing.role != "admin":
                logger.warning("ADMIN_USERNAME belongs to a non-admin account; not changed")
            return False
        try:
            await auth.register(session, username, password.get_secret_value(), role="admin")
        except DuplicateError:
            # Another instance created it between our check and insert.
            return False
    return True
