import openai
from google import genai

from app.providers.gemini_sdk import make_gemini_client
from app.providers.openai_sdk import make_openai_client


def test_gemini_client_is_built_without_network() -> None:
    assert isinstance(make_gemini_client("test-key-not-real", 12.5), genai.Client)


def test_openai_client_disables_sdk_retries() -> None:
    client = make_openai_client("test-key-not-real", 12.5)

    assert client.max_retries == 0
    assert client.timeout == 12.5
    assert isinstance(client, openai.AsyncOpenAI)
