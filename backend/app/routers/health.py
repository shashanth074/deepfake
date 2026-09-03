"""Health and service metadata."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.config import settings
from app.ml.registry import describe
from app.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    """Liveness probe plus which model versions this deployment is serving."""
    return HealthOut(
        status="ok",
        version=__version__,
        queue_enabled=settings.queue_enabled,
        models=describe(),
    )
