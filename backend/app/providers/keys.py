"""API key checks shared by every provider factory."""

from pydantic import SecretStr

from app.providers.errors import ProviderConfigurationError


def require_api_key(key: SecretStr | None, env_name: str, provider: str) -> str:
    """Return the key's value, or fail with a message that names the variable, never the key."""
    value = key.get_secret_value().strip() if key else ""
    if not value:
        raise ProviderConfigurationError(f"{env_name} is required to use {provider}")
    return value
