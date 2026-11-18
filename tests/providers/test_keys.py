import pytest
from pydantic import SecretStr

from app.providers.errors import ProviderConfigurationError
from app.providers.keys import require_api_key


def test_returns_stripped_key() -> None:
    assert require_api_key(SecretStr("  abc123  "), "GEMINI_API_KEY", "gemini") == "abc123"


@pytest.mark.parametrize("key", [None, SecretStr(""), SecretStr("   ")])
def test_missing_key_names_the_variable_only(key: SecretStr | None) -> None:
    with pytest.raises(ProviderConfigurationError, match="GEMINI_API_KEY is required") as exc:
        require_api_key(key, "GEMINI_API_KEY", "gemini")
    assert "SecretStr" not in str(exc.value)
