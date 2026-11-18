import pytest

from app.core.config import Settings
from app.llm.base import ChatMessage
from app.llm.factory import build_chat_model, build_llm_client
from app.llm.fake import DEFAULT_REPLY, FakeChatModel
from app.llm.gemini import GeminiChatModel
from app.llm.openai import OpenAIChatModel
from app.providers.errors import ProviderConfigurationError

DUMMY_KEY = "test-key-not-real"


def settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_builds_gemini_by_default() -> None:
    model = build_chat_model(settings(gemini_api_key=DUMMY_KEY, gemini_model="gemini-x"))

    assert isinstance(model, GeminiChatModel)
    assert model.model == "gemini-x"


def test_switching_provider_selects_openai() -> None:
    model = build_chat_model(settings(llm_provider="openai", openai_api_key=DUMMY_KEY))

    assert isinstance(model, OpenAIChatModel)


def test_fake_needs_no_key() -> None:
    assert isinstance(build_chat_model(settings(llm_provider="fake")), FakeChatModel)


@pytest.mark.parametrize(
    ("provider", "key_field", "env_name"),
    [
        ("gemini", "gemini_api_key", "GEMINI_API_KEY"),
        ("openai", "openai_api_key", "OPENAI_API_KEY"),
    ],
)
@pytest.mark.parametrize("key", [None, "", "   "], ids=["missing", "empty", "blank"])
def test_missing_key_is_a_configuration_error(
    provider: str, key_field: str, env_name: str, key: str | None
) -> None:
    with pytest.raises(ProviderConfigurationError, match=env_name):
        build_chat_model(settings(llm_provider=provider, **{key_field: key}))


@pytest.mark.anyio
async def test_client_answers_with_configured_provider() -> None:
    client = build_llm_client(settings(llm_provider="fake"))

    response = await client.chat([ChatMessage(role="user", content="hi")])

    assert client.provider == "fake"
    assert response.text == DEFAULT_REPLY
