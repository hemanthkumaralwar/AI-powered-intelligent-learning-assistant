"""Run student code on a remote sandbox, or create a public share link for it."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import CurrentUser
from app.api.schemas.code import (
    RunCodeRequest,
    RunCodeResponse,
    ShareCodeRequest,
    ShareCodeResponse,
)
from app.core.quota import QuotaExceededError
from app.runner.base import RunRequest
from app.runner.service import (
    CodeRunnerService,
    RunnerUnavailableError,
    UnsupportedLanguageError,
)

router = APIRouter(prefix="/code", tags=["code"])


def get_code_runner(request: Request) -> CodeRunnerService:
    return request.app.state.code_runner


Runner = Annotated[CodeRunnerService, Depends(get_code_runner)]


@router.post("/run")
async def run_code(body: RunCodeRequest, user: CurrentUser, runner: Runner) -> RunCodeResponse:
    """Run code remotely. Compile errors, crashes and timeouts are normal results (200)."""
    try:
        result = await runner.run(user.id, RunRequest(body.language, body.code, body.stdin))
    except QuotaExceededError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            str(exc),
            headers={"Retry-After": str(max(1, round(exc.retry_after)))},
        ) from exc
    except UnsupportedLanguageError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except RunnerUnavailableError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The code runner is unavailable. Please try again shortly.",
        ) from exc
    return RunCodeResponse(**asdict(result))


@router.post("/share")
async def share_code(
    body: ShareCodeRequest, user: CurrentUser, runner: Runner
) -> ShareCodeResponse:
    """Create a public, permanent Compiler Explorer link (C, C++, Java, Python only)."""
    try:
        url = await runner.share(RunRequest(body.language, body.code))
    except UnsupportedLanguageError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except RunnerUnavailableError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The share service is unavailable. Please try again shortly.",
        ) from exc
    return ShareCodeResponse(url=url)
