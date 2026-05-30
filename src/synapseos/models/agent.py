"""Agent domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class AgentRole(StrEnum):
    """Specialized agent roles in the orchestration graph."""

    PLANNER = "planner"
    RESEARCHER = "researcher"
    CODER = "coder"
    REVIEWER = "reviewer"
    EXECUTOR = "executor"
    SYNTHESIZER = "synthesizer"


class TaskStatus(StrEnum):
    """Lifecycle states for an autonomous task."""

    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class ApprovalStatus(StrEnum):
    """Human-in-the-loop approval state."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AgentEventType(StrEnum):
    """Event types streamed through WebSockets."""

    TASK_CREATED = "task_created"
    AGENT_STARTED = "agent_started"
    AGENT_TOKEN = "agent_token"
    AGENT_COMPLETED = "agent_completed"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_RESOLVED = "approval_resolved"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"


class AgentMessage(BaseModel):
    """A durable message emitted by an agent."""

    role: AgentRole
    content: str
    task_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class AgentResult(BaseModel):
    """Standard output contract for every agent implementation."""

    role: AgentRole
    task_id: str
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    requires_approval: bool = False
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class CriticalDecision(BaseModel):
    """A critical autonomous decision that requires human approval."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    agent_role: AgentRole
    rationale: str
    risk_score: float = Field(ge=0.0, le=1.0)
    options: list[str] = Field(default_factory=list)
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None


class AgentEvent(BaseModel):
    """Realtime event payload sent to API clients."""

    type: AgentEventType
    task_id: str
    role: AgentRole | None = None
    content: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
