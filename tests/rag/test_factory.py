import logging

import pytest

from app.core.config import Settings
from app.core.quota import QuotaExceededError
from app.rag.answer import AnswerService
from app.rag.factory import THRESHOLD_EMBEDDING_ID, build_answer_service, question_quota


class StubIndexing:
    def __init__(self, embedding_id: str) -> None:
        self.embedding_id = embedding_id

    async def search(self, query: str, k: int, course_id: str | None = None) -> list:
        return []


def settings(**overrides) -> Settings:
    return Settings(_env_file=None, llm_provider="fake", **overrides)


def test_builds_without_warning_in_the_measured_embedding_space(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="app.rag.factory"):
        service = build_answer_service(settings(), StubIndexing(THRESHOLD_EMBEDDING_ID))

    assert isinstance(service, AnswerService)
    assert caplog.text == ""


def test_warns_when_the_threshold_was_measured_elsewhere(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="app.rag.factory"):
        build_answer_service(settings(), StubIndexing("huggingface:bge:384"))

    assert "re-run eval/run_eval.py" in caplog.text


def test_question_quota_has_per_user_and_global_limits() -> None:
    quota = question_quota(
        settings(chat_questions_per_user_per_minute=1, chat_questions_global_per_minute=2)
    )
    quota.consume("asha")
    with pytest.raises(QuotaExceededError, match="too quickly"):
        quota.consume("asha")

    quota.consume("ravi")
    with pytest.raises(QuotaExceededError, match="busy"):
        quota.consume("meera")
