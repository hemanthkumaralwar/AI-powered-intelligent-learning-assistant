"""In-memory FAISS index, one per course.

Postgres is the source of truth for vectors (Render's disk is wiped on restart); this
index is rebuilt from it at startup and kept in step as documents are indexed or deleted.
Vectors are unit length (EmbeddingClient normalises them), so inner product = cosine.

Not thread-safe by design: every method is synchronous and called from the event loop,
so no two calls can interleave.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

import faiss
import numpy as np


@dataclass(frozen=True)
class IndexEntry:
    chunk_id: str
    document_id: uuid.UUID
    course_id: str
    lesson_id: str | None
    section: str
    text: str
    vector: Sequence[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    score: float
    course_id: str
    lesson_id: str | None
    section: str
    text: str
    metadata: dict[str, Any]


class _CourseIndex:
    def __init__(self, dimensions: int, entries: list[IndexEntry]) -> None:
        self.entries = entries
        self.faiss = faiss.IndexFlatIP(dimensions)
        if entries:
            self.faiss.add(np.asarray([e.vector for e in entries], dtype="float32"))


class VectorIndex:
    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions
        self._courses: dict[str, _CourseIndex] = {}

    @property
    def size(self) -> int:
        return sum(len(course.entries) for course in self._courses.values())

    def course_size(self, course_id: str) -> int:
        course = self._courses.get(course_id)
        return len(course.entries) if course else 0

    def add(self, entries: Iterable[IndexEntry]) -> None:
        """Add entries, grouped by course. Replaces any entry with the same chunk id."""
        by_course: dict[str, list[IndexEntry]] = {}
        for entry in entries:
            if len(entry.vector) != self.dimensions:
                raise ValueError(
                    f"vector has {len(entry.vector)} dimensions, index expects {self.dimensions}"
                )
            by_course.setdefault(entry.course_id, []).append(entry)
        for course_id, new in by_course.items():
            new_ids = {e.chunk_id for e in new}
            kept = [e for e in self._entries(course_id) if e.chunk_id not in new_ids]
            self._rebuild(course_id, kept + new)

    def replace_document(self, document_id: uuid.UUID, entries: Sequence[IndexEntry]) -> None:
        """Swap all of a document's entries for a new set (re-indexing a document)."""
        self.remove_document(document_id)
        self.add(entries)

    def remove_document(self, document_id: uuid.UUID) -> None:
        for course_id in list(self._courses):
            kept = [e for e in self._entries(course_id) if e.document_id != document_id]
            self._rebuild(course_id, kept)

    def remove_course(self, course_id: str) -> None:
        self._courses.pop(course_id, None)

    def search(
        self, query: Sequence[float], k: int, course_id: str | None = None
    ) -> list[SearchHit]:
        """Top-k entries by cosine similarity, in one course or across all courses."""
        if len(query) != self.dimensions:
            raise ValueError(f"query has {len(query)} dimensions, index expects {self.dimensions}")
        courses = [course_id] if course_id is not None else list(self._courses)
        vector = np.asarray([query], dtype="float32")
        hits: list[SearchHit] = []
        for cid in courses:
            course = self._courses.get(cid)
            if course is None:
                continue
            scores, positions = course.faiss.search(vector, min(k, len(course.entries)))
            hits.extend(
                _hit(course.entries[pos], float(score))
                for score, pos in zip(scores[0], positions[0], strict=True)
                if pos >= 0  # FAISS pads with -1 when fewer than k results exist
            )
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:k]

    def _entries(self, course_id: str) -> list[IndexEntry]:
        course = self._courses.get(course_id)
        return course.entries if course else []

    def _rebuild(self, course_id: str, entries: list[IndexEntry]) -> None:
        # Exact flat index: rebuilding is cheap at course scale (~1,000 vectors) and
        # avoids FAISS id-mapping bookkeeping for removals.
        if entries:
            self._courses[course_id] = _CourseIndex(self.dimensions, entries)
        else:
            self._courses.pop(course_id, None)


def _hit(entry: IndexEntry, score: float) -> SearchHit:
    return SearchHit(
        chunk_id=entry.chunk_id,
        score=score,
        course_id=entry.course_id,
        lesson_id=entry.lesson_id,
        section=entry.section,
        text=entry.text,
        metadata=entry.metadata,
    )
