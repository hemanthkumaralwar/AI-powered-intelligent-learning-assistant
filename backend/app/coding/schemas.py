"""What the model must return for each task. Sent as the response JSON schema, then
validated; `concepts` feeds the related-lesson search and is not shown to students.

Lengths are not constrained here (not every provider's schema subset supports them);
the service trims and range-checks the parsed result instead.
"""

from pydantic import BaseModel


class CodingOutput(BaseModel):
    concepts: list[str]


class LineNote(BaseModel):
    line: int
    explanation: str


class ExplainOutput(CodingOutput):
    summary: str
    lines: list[LineNote]


class Issue(BaseModel):
    line: int
    problem: str
    fix_hint: str


class DebugOutput(CodingOutput):
    summary: str
    issues: list[Issue]
    # Null in hint mode (the code is a course exercise).
    corrected_code: str | None


class ExampleOutput(CodingOutput):
    title: str
    code: str
    explanation: str


class PracticeQuestion(BaseModel):
    question: str
    hints: list[str]
    expected_output: str | None


class PracticeOutput(CodingOutput):
    # Deliberately no solution field: practice is for the student to solve.
    questions: list[PracticeQuestion]
