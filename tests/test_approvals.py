"""Unit tests for human-in-the-loop approval logic."""

from __future__ import annotations

import pytest

from synapseos.models.agent import AgentRole, ApprovalStatus
from synapseos.services import ApprovalService


@pytest.mark.asyncio
async def test_approval_lifecycle(test_settings) -> None:
    service = ApprovalService(test_settings)

    decision = await service.create_decision(
        task_id="task-approval",
        agent_role=AgentRole.REVIEWER,
        rationale="Risk exceeded threshold.",
        risk_score=0.91,
    )
    pending = await service.pending_for_task("task-approval")
    resolved = await service.resolve(decision.id, approved=True, reviewer="human-reviewer")

    assert len(pending) == 1
    assert resolved.status == ApprovalStatus.APPROVED
    assert resolved.approved_by == "human-reviewer"


def test_threshold_respects_explicit_requirement(test_settings) -> None:
    service = ApprovalService(test_settings)

    assert service.should_require_approval(0.95, explicit_requirement=True) is True
    assert service.should_require_approval(0.95, explicit_requirement=False) is False
