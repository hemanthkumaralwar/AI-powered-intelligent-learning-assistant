import pytest

from app.core.config import Settings
from app.embeddings import factory
from app.embeddings.factory import build_embedding_client, build_embedding_model
from app.embeddings.fake import FakeEmbeddingModel
from app.embeddings.gemini import GeminiEmbeddingModel
from app.embeddings.huggingface import HuggingFaceEmbeddingModel
from app.embeddings.openai import OpenAIEmbeddingModel
from app.providers.errors import ProviderConfigurationError

DUMMY_KEY = "test-key-not-real"


def settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_builds_gemini_by_default() -> None:
    model = build_embedding_model(settings(gemini_api_key=DUMMY_KEY))

    assert isinstance(model, GeminiEmbeddingModel)
    assert (model.model, model.dimensions) == ("gemini-embedding-001", 768)


def test_switching_provider_selects_openai() -> None:
    model = build_embedding_model(
        settings(embedding_provider="openai", openai_api_key=DUMMY_KEY, embedding_dimensions=512)
    )

    assert isinstance(model, OpenAIEmbeddingModel)
    assert model.dimensions == 512


def test_huggingface_loads_the_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubEncoder:
        def get_embedding_dimension(self) -> int:
            return 384

    loaded: list[str] = []
    monkeypatch.setattr(
        factory, "load_sentence_transformer", lambda name: loaded.append(name) or StubEncoder()
    )

    model = build_embedding_model(settings(embedding_provider="huggingface"))

    assert isinstance(model, HuggingFaceEmbeddingModel)
    assert loaded == ["BAAI/bge-small-en-v1.5"]
    assert model.dimensions == 384


@pytest.mark.parametrize(
    ("provider", "env_name"), [("gemini", "GEMINI_API_KEY"), ("openai", "OPENAI_API_KEY")]
)
def test_missing_key_is_a_configuration_error(provider: str, env_name: str) -> None:
    with pytest.raises(ProviderConfigurationError, match=env_name):
        build_embedding_model(settings(embedding_provider=provider))


def test_client_exposes_vector_space_id() -> None:
    client = build_embedding_client(settings(embedding_provider="fake", embedding_dimensions=32))

    assert isinstance(
        build_embedding_model(settings(embedding_provider="fake")), FakeEmbeddingModel
    )
    assert client.embedding_id == "fake:fake-embedding:32"
