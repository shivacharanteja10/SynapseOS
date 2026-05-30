"""Task orchestration API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from synapseos.api.dependencies import get_database, get_task_manager
from synapseos.core.exceptions import ResourceNotFoundError
from synapseos.models.agent import CriticalDecision
from synapseos.models.conversation import (
    ApprovalAction,
    AuditLogRecord,
    TaskRequest,
    TaskResponse,
    TaskSnapshot,
)
from synapseos.services.database import DatabaseService
from synapseos.services.task_manager import TaskManager

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_task(
    request: TaskRequest,
    manager: TaskManager = Depends(get_task_manager),
) -> TaskResponse:
    """Create and asynchronously execute a multi-agent task."""

    return await manager.submit(request)


@router.get("/{task_id}", response_model=TaskSnapshot)
async def get_task(
    task_id: str,
    manager: TaskManager = Depends(get_task_manager),
) -> TaskSnapshot:
    """Fetch the latest task snapshot."""

    snapshot = await manager.get_snapshot(task_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return snapshot


@router.get("/{task_id}/approvals")
async def list_task_approvals(
    task_id: str,
    manager: TaskManager = Depends(get_task_manager),
) -> list[CriticalDecision]:
    """List pending approval decisions for a task."""

    snapshot = await manager.get_snapshot(task_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return await manager.pending_approvals(task_id)


@router.post("/{task_id}/approvals/{decision_id}", response_model=TaskSnapshot)
async def resolve_approval(
    task_id: str,
    decision_id: str,
    action: ApprovalAction,
    manager: TaskManager = Depends(get_task_manager),
) -> TaskSnapshot:
    """Approve or reject a critical workflow decision."""

    snapshot = await manager.get_snapshot(task_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    try:
        return await manager.approve(task_id, decision_id, action)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{task_id}/audit")
async def get_audit_logs(
    task_id: str,
    database: DatabaseService = Depends(get_database),
    manager: TaskManager = Depends(get_task_manager),
) -> list[AuditLogRecord]:
    """Return audit logs for a task."""

    snapshot = await manager.get_snapshot(task_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return await database.list_audit_logs(task_id)


@router.websocket("/{task_id}/stream")
async def stream_task_events(websocket: WebSocket, task_id: str) -> None:
    """Stream realtime task events over WebSocket."""

    await websocket.accept()
    event_bus = websocket.app.state.event_bus
    try:
        async for event in event_bus.subscribe(task_id):
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        return
