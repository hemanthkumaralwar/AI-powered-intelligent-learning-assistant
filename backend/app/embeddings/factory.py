"""Builds the configured `EmbeddingClient` from settings."""

from app.core.config import Settings
from app.embeddings.base import EmbeddingModel
from app.embeddings.client import EmbeddingClient
from app.embeddings.fake import FakeEmbeddingModel
from app.embeddings.gemini import GeminiEmbeddingModel
from app.embeddings.huggingface import HuggingFaceEmbeddingModel, load_sentence_transformer
from app.embeddings.openai import OpenAIEmbeddingModel
from app.providers.gemini_sdk import make_gemini_client
from app.providers.keys import require_api_key
from app.providers.openai_sdk import make_openai_client
from app.providers.rate_limit import RateLimiter
from app.providers.retry import RetryPolicy


def build_embedding_client(settings: Settings) -> EmbeddingClient:
    return EmbeddingClient(
        build_embedding_model(settings),
        batch_size=settings.embedding_batch_size,
        timeout_seconds=settings.embedding_timeout_seconds,
        retry_policy=RetryPolicy(max_attempts=settings.embedding_max_attempts),
        rate_limiter=RateLimiter(settings.embedding_document_texts_per_minute),
        query_rate_limiter=RateLimiter(settings.embedding_query_texts_per_minute),
    )


def build_embedding_model(settings: Settings) -> EmbeddingModel:
    timeout = settings.embedding_timeout_seconds
    dimensions = settings.embedding_dimensions
    match settings.embedding_provider:
        case "gemini":
            key = require_api_key(settings.gemini_api_key, "GEMINI_API_KEY", "gemini")
            client = make_gemini_client(key, timeout)
            return GeminiEmbeddingModel(client, settings.gemini_embedding_model, dimensions)
        case "openai":
            key = require_api_key(settings.openai_api_key, "OPENAI_API_KEY", "openai")
            client = make_openai_client(key, timeout)
            return OpenAIEmbeddingModel(client, settings.openai_embedding_model, dimensions)
        case "huggingface":
            # Uses the model's native size; EMBEDDING_DIMENSIONS does not apply.
            encoder = load_sentence_transformer(settings.hf_embedding_model)
            return HuggingFaceEmbeddingModel(encoder, settings.hf_embedding_model)
        case "fake":
            return FakeEmbeddingModel(dimensions)
