"""Practice pointers in API responses (shared by /chat and /coding)."""

from pydantic import BaseModel

from app.learning.practice import PracticePointer


class ActivityResponse(BaseModel):
    kind: str
    title: str
    count: int


class PracticePointerResponse(BaseModel):
    lesson_id: str
    lesson_title: str
    # Run on the learning platform; `url` is set when PLATFORM_LESSON_URL is configured.
    activities: list[ActivityResponse]
    url: str | None

    @classmethod
    def from_pointer(cls, pointer: PracticePointer) -> "PracticePointerResponse":
        return cls(
            lesson_id=pointer.lesson_id,
            lesson_title=pointer.lesson_title,
            activities=[
                ActivityResponse(kind=a.kind, title=a.title, count=a.count)
                for a in pointer.activities
            ],
            url=pointer.url,
        )
