"""Admin retrieval check: what the RAG system would find for a question."""

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    course_id: str | None = None
    k: int = Field(default=5, ge=1, le=20)


class SearchHitResponse(BaseModel):
    chunk_id: str
    score: float
    course_id: str
    lesson_id: str | None
    section: str
    text: str


class ReindexResponse(BaseModel):
    queued: int
