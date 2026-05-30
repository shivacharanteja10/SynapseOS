"""Unit tests for core agent contracts."""

from __future__ import annotations

import pytest

from synapseos.agents import CoderAgent, PlannerAgent, ResearcherAgent
from synapseos.models.agent import AgentRole
from synapseos.models.workflow import WorkflowState


@pytest.mark.asyncio
async def test_planner_agent_returns_typed_result(agent_dependencies) -> None:
    agent = PlannerAgent(agent_dependencies)
    state: WorkflowState = {
        "task_id": "task-1",
        "goal": "Design a production multi-agent deployment workflow",
        "messages": [],
        "approvals": [],
        "risk_score": 0.0,
    }

    result = await agent.run(state)

    assert result.role == AgentRole.PLANNER
    assert result.confidence >= 0.8
    assert "SynapseOS planner output" in result.content


@pytest.mark.asyncio
async def test_researcher_uses_vector_context(agent_dependencies) -> None:
    await agent_dependencies.vector_store.add_text(
        task_id="seed",
        content="LangGraph is useful for explicit stateful agent orchestration.",
        metadata={"source": "test"},
    )
    agent = ResearcherAgent(agent_dependencies)
    state: WorkflowState = {
        "task_id": "task-2",
        "goal": "Research LangGraph orchestration options",
        "plan": "Compare state-machine approaches.",
        "messages": [],
        "approvals": [],
        "risk_score": 0.0,
    }

    result = await agent.run(state)

    assert result.role == AgentRole.RESEARCHER
    assert result.artifacts["sources_used"] >= 1


@pytest.mark.asyncio
async def test_coder_flags_high_risk_changes(agent_dependencies) -> None:
    agent = CoderAgent(agent_dependencies)
    state: WorkflowState = {
        "task_id": "task-3",
        "goal": "Deploy production Kubernetes database migration with secret rotation",
        "plan": "Coordinate deployment.",
        "research": "Requires rollout and rollback.",
        "messages": [],
        "approvals": [],
        "risk_score": 0.0,
    }

    result = await agent.run(state)

    assert result.role == AgentRole.CODER
    assert result.risk_score >= 0.72
    assert result.requires_approval is True
