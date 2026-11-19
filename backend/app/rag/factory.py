"""Builds the AnswerService from settings and the running IndexingService."""

import logging

from app.core.config import Settings
from app.core.quota import MINUTE, Quota, QuotaRule
from app.indexing.service import IndexingService
from app.llm.factory import build_llm_client
from app.rag.answer import AnswerService
from app.rag.condense import Condenser
from app.rag.retriever import Retriever

logger = logging.getLogger(__name__)

# RAG_MIN_SCORE was measured in this embedding space (eval/reports, Step 11).
THRESHOLD_EMBEDDING_ID = "gemini:gemini-embedding-001:768"


def build_answer_service(settings: Settings, indexing: IndexingService) -> AnswerService:
    if indexing.embedding_id != THRESHOLD_EMBEDDING_ID:
        logger.warning(
            "RAG_MIN_SCORE=%s was measured for %s, but embeddings are %s; "
            "re-run eval/run_eval.py and set RAG_MIN_SCORE from its report",
            settings.rag_min_score,
            THRESHOLD_EMBEDDING_ID,
            indexing.embedding_id,
        )
    llm = build_llm_client(settings)
    return AnswerService(
        Retriever(indexing.search, settings.rag_top_k, settings.rag_min_score),
        llm,
        question_quota(settings),
        Condenser(llm),
    )


def question_quota(settings: Settings) -> Quota:
    return Quota(
        [
            QuotaRule(
                "You are asking questions too quickly; wait a moment.",
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
