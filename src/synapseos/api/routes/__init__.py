"""API routers."""

from fastapi import APIRouter

from synapseos.api.routes import health, tasks

router = APIRouter()
router.include_router(health.router)
router.include_router(tasks.router)

__all__ = ["router"]
