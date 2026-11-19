"""Builds the AnswerService, and the quota every AI request shares, from settings."""

import logging

from app.core.config import Settings
from app.core.quota import MINUTE, Quota, QuotaRule
from app.indexing.service import IndexingService
from app.llm.client import LLMClient
from app.rag.answer import AnswerService
from app.rag.condense import Condenser
from app.rag.retriever import Retriever

logger = logging.getLogger(__name__)

# RAG_MIN_SCORE was measured in this embedding space (eval/reports, Step 11).
THRESHOLD_EMBEDDING_ID = "gemini:gemini-embedding-001:768"


def build_answer_service(
    settings: Settings, indexing: IndexingService, llm: LLMClient, quota: Quota
) -> AnswerService:
    """`llm` and `quota` are shared with the coding assistant; the app owns and closes them."""
    if indexing.embedding_id != THRESHOLD_EMBEDDING_ID:
        logger.warning(
            "RAG_MIN_SCORE=%s was measured for %s, but embeddings are %s; "
            "re-run eval/run_eval.py and set RAG_MIN_SCORE from its report",
            settings.rag_min_score,
            THRESHOLD_EMBEDDING_ID,
            indexing.embedding_id,
        )
    return AnswerService(
        Retriever(indexing.search, settings.rag_top_k, settings.rag_min_score),
        llm,
        quota,
        Condenser(llm),
    )


def question_quota(settings: Settings) -> Quota:
    """One budget for chat questions and coding requests: both spend the same free tier."""
    return Quota(
        [
            QuotaRule(
                "You are sending requests to the assistant too quickly; wait a moment.",
                settings.chat_questions_per_user_per_minute,
                MINUTE,
            ),
            QuotaRule(
                "The assistant is busy; try again in a moment.",
                settings.chat_questions_global_per_minute,
                MINUTE,
                per_user=False,
            ),
        ]
    )
