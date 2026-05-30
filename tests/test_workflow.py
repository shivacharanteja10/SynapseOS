"""Unit tests for LangGraph workflow behavior."""

from __future__ import annotations

import pytest

from synapseos.core.config import Settings
from synapseos.graph.workflow import WorkflowGraph
from synapseos.models.agent import TaskStatus
from synapseos.models.workflow import WorkflowState
from synapseos.services import ApprovalService, EventBus


@pytest.mark.asyncio
async def test_workflow_completes_when_approval_not_required(
    agent_dependencies,
    test_settings,
) -> None:
    settings = test_settings.model_copy(update={"human_approval_required_risk_score": 0.99})
    graph = WorkflowGraph(
        settings=settings,
        dependencies=agent_dependencies,
        approvals=ApprovalService(settings),
        event_bus=EventBus(),
    )
    initial_state: WorkflowState = {
        "task_id": "workflow-1",
        "goal": "Build an internal runbook generator",
        "require_human_approval": True,
        "status": TaskStatus.RUNNING,
        "messages": [],
        "approvals": [],
        "risk_score": 0.0,
        "metadata": {},
    }

    final_state = await graph.run(initial_state)

    assert final_state["final_response"]
    assert len(final_state["messages"]) == 6


@pytest.mark.asyncio
async def test_workflow_pauses_for_high_risk_approval(agent_dependencies) -> None:
    settings = Settings(
        environment="test",
        llm_provider="mock",
        vector_backend="memory",
        human_approval_required_risk_score=0.55,
    )
    graph = WorkflowGraph(
        settings=settings,
        dependencies=agent_dependencies,
        approvals=ApprovalService(settings),
        event_bus=EventBus(),
    )
    initial_state: WorkflowState = {
        "task_id": "workflow-2",
        "goal": "Deploy production Kubernetes database migration",
        "require_human_approval": True,
        "status": TaskStatus.RUNNING,
        "messages": [],
        "approvals": [],
        "risk_score": 0.0,
        "metadata": {},
    }

    final_state = await graph.run(initial_state)

    assert final_state["status"] == TaskStatus.AWAITING_APPROVAL
    assert len(final_state["approvals"]) == 1
