"""A lesson's quiz, taken in this app and marked on the server. Scores count toward the
student's progress next to exercise results. No AI is involved."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, Session
from app.api.schemas.quizzes import (
    QuestionResultResponse,
    QuizAttemptRequest,
    QuizAttemptResponse,
    QuizAttemptSummary,
    QuizOption,
    QuizQuestionResponse,
    QuizResponse,
)
from app.db.models import QuizQuestion
from app.db.repositories.quizzes import QuizRepository
from app.learning.quiz import InvalidAnswersError, mark, option_order

router = APIRouter(prefix="/lessons", tags=["quizzes"])

NO_QUIZ = "This lesson has no quiz"


@router.get("/{lesson_id}/quiz")
async def get_quiz(lesson_id: str, user: CurrentUser, session: Session) -> QuizResponse:
    """The lesson's questions with shuffled options, without the answers."""
    questions = await _questions(session, lesson_id)
    return QuizResponse(
        lesson_id=lesson_id,
        questions=[_question(str(user.id), question) for question in questions],
    )


@router.post("/{lesson_id}/quiz/attempts", status_code=status.HTTP_201_CREATED)
async def submit_quiz(
    lesson_id: str, body: QuizAttemptRequest, user: CurrentUser, session: Session
) -> QuizAttemptResponse:
    """Mark your answers, record the score, and return the right answers with their
    explanations. A question left out counts as wrong."""
    questions = await _questions(session, lesson_id)
    try:
        marked = mark(questions, {str(key): value for key, value in body.answers.items()})
    except InvalidAnswersError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    attempt = await QuizRepository(session).add_attempt(
        user.id, lesson_id, marked.correct, marked.total, marked.answers()
    )
    return QuizAttemptResponse(
        id=attempt.id,
        correct=attempt.correct,
        total=attempt.total,
        created_at=attempt.created_at,
        results=[
            QuestionResultResponse(
                question_id=result.question_id,
                chosen=result.chosen,
                correct_option=result.correct_option,
                correct=result.correct,
                explanation=result.explanation,
            )
            for result in marked.results
        ],
    )


@router.get("/{lesson_id}/quiz/attempts")
async def list_quiz_attempts(
    lesson_id: str, user: CurrentUser, session: Session
) -> list[QuizAttemptSummary]:
    """Your own scores on this lesson's quiz, newest first (nobody else's)."""
    attempts = await QuizRepository(session).attempts(user.id, lesson_id)
    return [QuizAttemptSummary.model_validate(attempt) for attempt in attempts]


async def _questions(session: AsyncSession, lesson_id: str) -> list[QuizQuestion]:
    questions = await QuizRepository(session).questions(lesson_id)
    if not questions:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_QUIZ)
    return questions


def _question(student_id: str, question: QuizQuestion) -> QuizQuestionResponse:
    return QuizQuestionResponse(
        id=question.id,
        position=question.position,
        question=question.question,
        options=[
            QuizOption(id=index, text=question.options[index])
            for index in option_order(student_id, question)
        ],
    )
