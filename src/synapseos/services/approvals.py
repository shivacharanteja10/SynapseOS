"""Human-in-the-loop approval service."""

from __future__ import annotations

from datetime import UTC, datetime

from synapseos.core.config import Settings
from synapseos.core.exceptions import ResourceNotFoundError
from synapseos.models.agent import AgentRole, ApprovalStatus, CriticalDecision


class ApprovalService:
    """Stores and resolves critical decisions that require human review."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._decisions: dict[str, CriticalDecision] = {}

    def should_require_approval(self, risk_score: float, explicit_requirement: bool = True) -> bool:
        """Return true when the workflow must pause for approval."""

        threshold = self.settings.human_approval_required_risk_score
        return explicit_requirement and risk_score >= threshold

    async def create_decision(
        self,
        *,
        task_id: str,
        agent_role: AgentRole,
        rationale: str,
        risk_score: float,
        options: list[str] | None = None,
    ) -> CriticalDecision:
        """Create a pending approval decision."""

        decision = CriticalDecision(
            task_id=task_id,
            agent_role=agent_role,
            rationale=rationale,
            risk_score=risk_score,
            options=options or ["approve", "reject", "request_changes"],
        )
        self._decisions[decision.id] = decision
        return decision

    async def get(self, decision_id: str) -> CriticalDecision:
        """Return a critical decision by id."""

        try:
            return self._decisions[decision_id]
        except KeyError as exc:
            raise ResourceNotFoundError(f"Approval decision {decision_id} not found") from exc

    async def pending_for_task(self, task_id: str) -> list[CriticalDecision]:
        """List pending approvals for a task."""

        return [
            decision
            for decision in self._decisions.values()
            if decision.task_id == task_id and decision.status == ApprovalStatus.PENDING
        ]

    async def resolve(self, decision_id: str, *, approved: bool, reviewer: str) -> CriticalDecision:
        """Resolve a pending approval."""

        decision = await self.get(decision_id)
        decision.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        decision.approved_by = reviewer
        decision.resolved_at = datetime.now(UTC)
        self._decisions[decision_id] = decision
        return decision
