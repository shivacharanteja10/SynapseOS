"""FastAPI dependency helpers."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from synapseos.services.approvals import ApprovalService
from synapseos.services.database import DatabaseService
from synapseos.services.event_bus import EventBus
from synapseos.services.task_manager import TaskManager


def get_task_manager(request: Request) -> TaskManager:
    return cast(TaskManager, request.app.state.task_manager)


def get_event_bus(request: Request) -> EventBus:
    return cast(EventBus, request.app.state.event_bus)


def get_database(request: Request) -> DatabaseService:
    return cast(DatabaseService, request.app.state.database)


def get_approvals(request: Request) -> ApprovalService:
    return cast(ApprovalService, request.app.state.approvals)
