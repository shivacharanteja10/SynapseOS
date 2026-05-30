"""Reviewer agent."""

from __future__ import annotations

from synapseos.agents.base import BaseAgent
from synapseos.models.agent import AgentResult, AgentRole
from synapseos.models.workflow import WorkflowState


class ReviewerAgent(BaseAgent):
    """Reviews the proposed implementation for correctness, security, and test gaps."""

    role = AgentRole.REVIEWER
    system_prompt = (
        "You are the Reviewer agent in SynapseOS. Act like a staff engineer: find "
        "bugs, missing tests, security flaws, operational risk, and unclear acceptance criteria."
    )

    async def run(self, state: WorkflowState) -> AgentResult:
        task_id = state["task_id"]
        prompt = (
            "Review the proposed implementation.\n\n"
            f"Goal:\n{state['goal']}\n\n"
            f"Plan:\n{state.get('plan', '')}\n\n"
            f"Research:\n{state.get('research', '')}\n\n"
            f"Implementation:\n{state.get('code', '')}\n\n"
            "Return approval status, critical issues, recommended changes, and test gaps."
        )
        content = await self._complete(prompt, task_id=task_id, metadata={"phase": "review"})
        await self.dependencies.memory.remember(task_id, "reviewer", content)
        risk_score = max(float(state.get("risk_score", 0.0)), _review_risk(content))
        return self._result(
            task_id=task_id,
            content=content,
            confidence=0.89,
            risk_score=risk_score,
            artifacts={"review": content},
        )


def _review_risk(content: str) -> float:
    text = content.lower()
    blockers = ["critical", "security", "data loss", "approval required", "unsafe"]
    if any(item in text for item in blockers):
        return 0.76
    return 0.42
