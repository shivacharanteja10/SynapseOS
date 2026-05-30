"""API request and persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from synapseos.models.agent import AgentMessage, CriticalDecision, TaskStatus, utc_now


class TaskRequest(BaseModel):
    """Request to run an autonomous multi-agent workflow."""

    goal: str = Field(min_length=8, max_length=8000)
    conversation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    require_human_approval: bool = True


class TaskResponse(BaseModel):
    """Response returned when a task is created."""

    task_id: str
    status: TaskStatus
    stream_url: str


class TaskSnapshot(BaseModel):
    """Current known state for a workflow task."""

    task_id: str
    status: TaskStatus
    goal: str
    final_response: str | None = None
    messages: list[AgentMessage] = Field(default_factory=list)
    approvals: list[CriticalDecision] = Field(default_factory=list)
    error: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class ApprovalAction(BaseModel):
    """Human approval action for a pending critical decision."""

    approved: bool
    reviewer: str = Field(min_length=2, max_length=128)
    notes: str | None = Field(default=None, max_length=2000)


class ConversationRecord(BaseModel):
    """Conversation history item persisted to PostgreSQL."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    goal: str
    final_response: str | None = None
    messages: list[AgentMessage] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AuditLogRecord(BaseModel):
    """Structured audit log persisted for compliance and debugging."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    actor: str
    action: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
