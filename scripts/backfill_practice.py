"""Add `practice` (activity names and sizes) to lessons uploaded before Step 17.

New uploads get it at ingestion; this fills in courses already in a database, by reading
each course's stored JSON. Safe to run again: lessons that have it are left alone.

    python scripts/backfill_practice.py        # uses DATABASE_URL from .env
"""

import asyncio
import json
import sys
from pathlib import Path

# Make the backend package importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.db.models import Document, DocumentFile, Lesson  # noqa: E402
from app.db.session import build_database  # noqa: E402
from app.ingestion.course_json import practice_activities  # noqa: E402


def activities_by_lesson(raw: bytes) -> dict[str, list[dict]]:
    course = json.loads(raw)["course"]
    return {
        lesson["lessonId"]: practice_activities(lesson)
        for module in course["modules"]
        for lesson in module["lessons"]
    }


async def backfill(settings: Settings) -> tuple[int, int]:
    database = build_database(settings)
    updated = skipped = 0
    try:
        async with database.session() as session:
            files = await session.execute(
                select(DocumentFile.content)
                .join(Document, Document.id == DocumentFile.document_id)
                .where(Document.kind == "course")
            )
            found: dict[str, list[dict]] = {}
            for (raw,) in files:
                found |= activities_by_lesson(raw)
            lessons = await session.scalars(select(Lesson).where(Lesson.id.in_(list(found))))
            for lesson in lessons:
                if "practice" in lesson.content:
                    skipped += 1
                    continue
                # A new dict, so SQLAlchemy sees the JSONB change.
                lesson.content = {**lesson.content, "practice": found[lesson.id]}
                updated += 1
    finally:
        await database.dispose()
    return updated, skipped


def main() -> int:
    updated, skipped = asyncio.run(backfill(Settings()), loop_factory=asyncio.SelectorEventLoop)
    print(f"lessons updated: {updated}, already had practice: {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
