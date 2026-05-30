"""Task orchestration service for API handlers."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from synapseos.core.logging import get_logger
from synapseos.graph.workflow import WorkflowGraph
from synapseos.models.agent import (
    AgentEvent,
    AgentEventType,
    ApprovalStatus,
    CriticalDecision,
    TaskStatus,
)
from synapseos.models.conversation import (
    ApprovalAction,
    AuditLogRecord,
    ConversationRecord,
    TaskRequest,
    TaskResponse,
    TaskSnapshot,
)
from synapseos.models.workflow import WorkflowState
from synapseos.services.approvals import ApprovalService
from synapseos.services.database import DatabaseService
from synapseos.services.event_bus import EventBus
from synapseos.services.memory import MemoryService

logger = get_logger(__name__)


class TaskManager:
    """Runs workflow tasks in the background and exposes snapshots."""

    def __init__(
        self,
        *,
        workflow: WorkflowGraph,
        event_bus: EventBus,
        database: DatabaseService,
        memory: MemoryService,
        approvals: ApprovalService,
        api_prefix: str,
    ) -> None:
        self.workflow = workflow
        self.event_bus = event_bus
        self.database = database
        self.memory = memory
        self.approvals = approvals
        self.api_prefix = api_prefix
        self._snapshots: dict[str, TaskSnapshot] = {}
        self._states: dict[str, WorkflowState] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    async def submit(self, request: TaskRequest) -> TaskResponse:
        """Create and schedule a new autonomous task."""

        task_id = str(uuid4())
        snapshot = TaskSnapshot(task_id=task_id, status=TaskStatus.QUEUED, goal=request.goal)
        self._snapshots[task_id] = snapshot
        await self.memory.enqueue_task({"task_id": task_id, "goal": request.goal})
        await self.database.append_audit_log(
            AuditLogRecord(
                task_id=task_id,
                actor="api",
                action="task_created",
                details=request.model_dump(mode="json"),
            )
        )
        await self.event_bus.publish(
            AgentEvent(
                type=AgentEventType.TASK_CREATED,
                task_id=task_id,
                payload={"goal": request.goal, "metadata": request.metadata},
            )
        )
        task = asyncio.create_task(self._run_task(task_id, request))
        task.add_done_callback(self._tasks.discard)
        self._tasks.add(task)
        return TaskResponse(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            stream_url=f"{self.api_prefix}/tasks/{task_id}/stream",
        )

    async def get_snapshot(self, task_id: str) -> TaskSnapshot | None:
        """Return the latest task snapshot."""

        return self._snapshots.get(task_id)

    async def approve(self, task_id: str, decision_id: str, action: ApprovalAction) -> TaskSnapshot:
        """Resolve approval and resume or reject the workflow."""

        decision = await self.approvals.resolve(
            decision_id,
            approved=action.approved,
            reviewer=action.reviewer,
        )
        await self.database.append_audit_log(
            AuditLogRecord(
                task_id=task_id,
                actor=action.reviewer,
                action="approval_resolved",
                details={
                    "decision_id": decision_id,
                    "approved": action.approved,
                    "notes": action.notes,
                },
            )
        )
        await self.event_bus.publish(
            AgentEvent(
                type=AgentEventType.APPROVAL_RESOLVED,
                task_id=task_id,
                role=decision.agent_role,
                payload=decision.model_dump(mode="json"),
            )
        )
        if not action.approved:
            snapshot = self._snapshots[task_id]
            snapshot.status = TaskStatus.REJECTED
            self._snapshots[task_id] = snapshot
            await self._persist_snapshot(snapshot)
            return snapshot

        state = self._states[task_id]
        state["approvals"] = [
            decision if item.id == decision.id else item for item in state.get("approvals", [])
        ]
        final_state = await self.workflow.resume_after_approval(state)
        return await self._update_from_state(task_id, final_state)

    async def pending_approvals(self, task_id: str) -> list[CriticalDecision]:
        """List pending approvals for a task."""

        return await self.approvals.pending_for_task(task_id)

    async def _run_task(self, task_id: str, request: TaskRequest) -> None:
        state: WorkflowState = {
            "task_id": task_id,
            "goal": request.goal,
            "conversation_id": request.conversation_id,
            "require_human_approval": request.require_human_approval,
            "status": TaskStatus.RUNNING,
            "messages": [],
            "approvals": [],
            "risk_score": 0.0,
            "metadata": request.metadata,
        }
        self._states[task_id] = state
        try:
            final_state = await self.workflow.run(state)
            await self._update_from_state(task_id, final_state)
        except Exception as exc:
            logger.exception("task_failed", task_id=task_id)
            state["status"] = TaskStatus.FAILED
            state["error"] = str(exc)
            await self._update_from_state(task_id, state)

    async def _update_from_state(self, task_id: str, state: WorkflowState) -> TaskSnapshot:
        status = state.get("status", TaskStatus.RUNNING)
        if status == TaskStatus.RUNNING and state.get("final_response"):
            status = TaskStatus.COMPLETED
        snapshot = TaskSnapshot(
            task_id=task_id,
            status=status,
            goal=state["goal"],
            final_response=state.get("final_response"),
            messages=state.get("messages", []),
            approvals=state.get("approvals", []),
            error=state.get("error"),
        )
        self._states[task_id] = {**state, "status": status}
        self._snapshots[task_id] = snapshot
        await self._persist_snapshot(snapshot)
        if status == TaskStatus.COMPLETED:
            await self.event_bus.publish(
                AgentEvent(
                    type=AgentEventType.WORKFLOW_COMPLETED,
                    task_id=task_id,
                    content=snapshot.final_response,
                )
            )
        elif status == TaskStatus.FAILED:
            await self.event_bus.publish(
                AgentEvent(
                    type=AgentEventType.WORKFLOW_FAILED,
                    task_id=task_id,
                    content=snapshot.error,
                )
            )
        return snapshot

    async def _persist_snapshot(self, snapshot: TaskSnapshot) -> None:
        approved = [
            item
            for item in snapshot.approvals
            if item.status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}
        ]
        await self.database.save_conversation(
            ConversationRecord(
                task_id=snapshot.task_id,
                goal=snapshot.goal,
                final_response=snapshot.final_response,
                messages=snapshot.messages,
                metadata={
                    "status": snapshot.status.value,
                    "approvals_resolved": len(approved),
                },
            )
        )
