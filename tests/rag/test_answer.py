import logging

import pytest

from app.core.quota import MINUTE, Quota, QuotaExceededError, QuotaRule
from app.llm.base import ChatMessage
from app.llm.client import LLMClient
from app.llm.fake import FakeChatModel
from app.providers.errors import ProviderUnavailableError
from app.providers.retry import RetryPolicy
from app.rag.answer import REFUSAL, AnswerService, Citation, ground
from app.rag.condense import Condenser
from app.rag.prompts import NOT_IN_COURSE
from app.rag.retriever import Retriever, Source

pytestmark = pytest.mark.anyio


@pytest.fixture
def service(fake_search):
    """Builds (AnswerService, its fake chat model, its fake search) from hits and replies."""

    def build(hits: list, *replies, per_minute: int = 100):
        model = FakeChatModel(replies)
        search = fake_search(hits)
        llm = LLMClient(model, timeout_seconds=5, retry_policy=RetryPolicy(max_attempts=1))
        quota = Quota([QuotaRule("slow down", per_minute, MINUTE)])
        service = AnswerService(Retriever(search, 5, 0.63), llm, quota, Condenser(llm))
        return service, model, search

    return build


async def test_grounded_answer_with_server_built_citations(service, hit) -> None:
    answers, model, _ = service(
        [hit(0.8), hit(0.7, section="Summary", lesson_id=None)],
        "`let` is block-scoped [1]. Modules recap it [2]. Not real [5].",
    )

    answer = await answers.ask("asha", "What is let?", "javascript-beginner-v1")

    assert answer.grounded and answer.outcome == "answered"
    assert answer.text == "`let` is block-scoped [1]. Modules recap it [2]. Not real ."
    first, second = answer.citations
    assert first.link == "/lessons/javascript-beginner-mod-1-lesson-1"
    assert (first.lesson_title, first.section) == ("Variables", "Explanation")
    assert second.link is None  # module overview: no lesson page
    (request,) = model.requests
    assert "<question>\nWhat is let?\n</question>" in request.messages[1].content


async def test_no_relevant_material_refuses_without_calling_the_llm(service, hit) -> None:
    answers, model, _ = service([hit(0.5)])

    answer = await answers.ask("asha", "Explain Docker")

    assert (answer.text, answer.outcome, answer.citations) == (REFUSAL, "no_relevant_material", ())
    assert not answer.grounded
    assert model.requests == []


@pytest.mark.parametrize(
    ("reply", "outcome"),
    [
        (NOT_IN_COURSE, "not_in_sources"),
        (f"  {NOT_IN_COURSE}.", "not_in_sources"),
        ("Docker is a container tool.", "uncited"),
        ("Docker is a container tool [9].", "uncited"),
    ],
)
async def test_unsupported_replies_become_refusals(reply: str, outcome: str, service, hit) -> None:
    answers, _, _ = service([hit(0.8)], reply)

    answer = await answers.ask("asha", "What is Docker?")

    assert (answer.text, answer.outcome) == (REFUSAL, outcome)


async def test_quota_is_checked_before_any_provider_call(service, hit) -> None:
    answers, model, search = service([hit(0.8)], "a [1]", per_minute=1)
    await answers.ask("asha", "q")

    with pytest.raises(QuotaExceededError):
        await answers.ask("asha", "q")
    assert len(search.calls) == 1 and len(model.requests) == 1


async def test_provider_errors_propagate(service, hit) -> None:
    answers, _, _ = service([hit(0.8)], ProviderUnavailableError("down"))

    with pytest.raises(ProviderUnavailableError):
        await answers.ask("asha", "q")


async def test_logs_metadata_never_text(caplog: pytest.LogCaptureFixture, service, hit) -> None:
    answers, _, _ = service([hit(0.8)], "secret answer [1]")

    with caplog.at_level(logging.INFO, logger="app.rag.answer"):
        await answers.ask("asha", "my private question")

    assert "outcome=answered sources=1 cited=1" in caplog.text
    assert "private" not in caplog.text and "secret" not in caplog.text


async def test_follow_up_is_rewritten_before_retrieval_and_answering(service, hit) -> None:
    answers, model, search = service([hit(0.8)], "How do I loop over an array?", "Use for-of [1].")
    history = [
        ChatMessage(role="user", content="What is an array?"),
        ChatMessage(role="assistant", content="An ordered list."),
    ]

    answer = await answers.ask("asha", "How do I loop over it?", None, history)

    assert answer.standalone == "How do I loop over an array?"
    assert search.calls == [("How do I loop over an array?", 5, None)]
    rewrite, reply = model.requests
    assert "Student: What is an array?" in rewrite.messages[1].content
    assert "<question>\nHow do I loop over an array?\n</question>" in reply.messages[1].content


async def test_first_question_is_not_rewritten(service, hit) -> None:
    answers, model, _ = service([hit(0.8)], "let is block-scoped [1].")

    answer = await answers.ask("asha", "What is let?")

    assert answer.standalone is None
    assert len(model.requests) == 1


def test_ground_keeps_first_cited_order(hit) -> None:
    sources = [Source.from_hit(1, hit(0.9)), Source.from_hit(2, hit(0.8, section="Summary"))]

    answer = ground("B [2]. A [1].", sources)

    assert [c.number for c in answer.citations] == [2, 1]
    assert isinstance(answer.citations[0], Citation)
