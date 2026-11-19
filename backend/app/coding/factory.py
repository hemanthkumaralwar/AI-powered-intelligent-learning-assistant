"""Builds the CodingService on the LLM client and quota it shares with chat."""

from app.coding.service import CodingService
from app.core.config import Settings
from app.core.quota import Quota
from app.indexing.service import IndexingService
from app.llm.client import LLMClient
from app.rag.retriever import Retriever


def build_coding_service(
    settings: Settings, indexing: IndexingService, llm: LLMClient, quota: Quota
) -> CodingService:
    retriever = Retriever(indexing.search, settings.rag_top_k, settings.rag_min_score)
    return CodingService(llm, quota, retriever)
