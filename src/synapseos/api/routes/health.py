"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from synapseos import __version__

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "synapseos", "version": __version__}


@router.get("/ready", summary="Readiness probe")
async def readiness_check() -> dict[str, str]:
    return {"status": "ready"}
