"""LangGraph workflow state schema."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from synapseos.models.agent import AgentMessage, CriticalDecision, TaskStatus


def append_messages(
    existing: list[AgentMessage] | None, new: list[AgentMessage] | None
) -> list[AgentMessage]:
    """LangGraph reducer for accumulating agent messages."""

    return [*(existing or []), *(new or [])]


def append_approvals(
    existing: list[CriticalDecision] | None, new: list[CriticalDecision] | None
) -> list[CriticalDecision]:
    """LangGraph reducer for accumulating critical decisions."""

    return [*(existing or []), *(new or [])]


class WorkflowState(TypedDict, total=False):
    """State shared across all nodes in the agent graph."""

    task_id: str
    goal: str
    conversation_id: str | None
    require_human_approval: bool
    status: TaskStatus
    current_agent: str | None
    messages: Annotated[list[AgentMessage], append_messages]
    approvals: Annotated[list[CriticalDecision], append_approvals]
    plan: str
    research: str
    code: str
    review: str
    execution: str
    final_response: str
    risk_score: float
    error: str | None
    metadata: dict[str, Any]
