"""Graded attempts at course exercises (bug hunts, mini challenges, interactive tasks).

Quizzes and the other activities run on the learning platform; exercises are solved in
this app's compiler panel, so their attempts are graded and recorded here.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.ai_errors import ai_errors
from app.api.deps import CurrentUser, Session
from app.api.schemas.exercises import AttemptRequest, AttemptResponse
from app.db.repositories.exercises import ExerciseRepository
from app.learning.grading import ExerciseGrader

router = APIRouter(prefix="/exercises", tags=["exercises"])


def get_grader(request: Request) -> ExerciseGrader:
    return request.app.state.grader


Grader = Annotated[ExerciseGrader, Depends(get_grader)]


@router.post("/{exercise_id}/attempts", status_code=status.HTTP_201_CREATED)
async def submit_attempt(
    exercise_id: uuid.UUID,
    body: AttemptRequest,
    user: CurrentUser,
    session: Session,
    grader: Grader,
) -> AttemptResponse:
    """Grade your code for this exercise and record the result. The feedback gives hints,
    never the solution."""
    task = await ExerciseRepository(session).task(exercise_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercise not found")
    user_id, level = user.id, body.level or user.level
    # Hand the connection back during the slow model call; the save below starts a new one.
    await session.commit()
    with ai_errors():
        grade = await grader.grade(user_id, task, body.code, level)
    attempt = await ExerciseRepository(session).add_attempt(
        user_id, exercise_id, grade.passed, grade.feedback
    )
    return AttemptResponse.model_validate(attempt)


@router.get("/{exercise_id}/attempts")
async def list_attempts(
    exercise_id: uuid.UUID, user: CurrentUser, session: Session
) -> list[AttemptResponse]:
    """Your own attempts at this exercise, newest first (nobody else's)."""
    attempts = await ExerciseRepository(session).attempts(user.id, exercise_id)
    return [AttemptResponse.model_validate(a) for a in attempts]
