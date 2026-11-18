"""Liveness endpoint used by the host's health checks and keep-alive pings."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    # Deliberately minimal: no version, environment, or dependency details.
    status: Literal["ok"] = "ok"


@router.get("/health")
def health() -> HealthResponse:
    """Report that the process is up and serving requests."""
    return HealthResponse()
