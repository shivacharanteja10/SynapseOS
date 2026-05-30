"""Coder agent."""

from __future__ import annotations

from synapseos.agents.base import BaseAgent
from synapseos.models.agent import AgentResult, AgentRole
from synapseos.models.workflow import WorkflowState


class CoderAgent(BaseAgent):
    """Designs implementation steps, patches, commands, and test strategy."""

    role = AgentRole.CODER
    system_prompt = (
        "You are the Coder agent in SynapseOS. Produce production-ready technical "
        "implementation details with explicit files, interfaces, commands, and test plans."
    )

    async def run(self, state: WorkflowState) -> AgentResult:
        task_id = state["task_id"]
        prompt = (
            "Design the implementation for this task.\n\n"
            f"Goal:\n{state['goal']}\n\n"
            f"Plan:\n{state.get('plan', '')}\n\n"
            f"Research:\n{state.get('research', '')}\n\n"
            "Return concrete modules, code-level decisions, migration concerns, and tests."
        )
        content = await self._complete(prompt, task_id=task_id, metadata={"phase": "coding"})
        await self.dependencies.memory.remember(task_id, "coder", content)
        risk_score = _estimate_change_risk(state["goal"], content)
        return self._result(
            task_id=task_id,
            content=content,
            confidence=0.86,
            risk_score=risk_score,
            artifacts={"implementation_blueprint": content},
        )


def _estimate_change_risk(goal: str, content: str) -> float:
    text = f"{goal} {content}".lower()
    risk_terms = [
        "delete",
        "drop table",
        "payment",
        "production",
        "deploy",
        "credential",
        "secret",
        "database migration",
        "kubernetes",
    ]
    matches = sum(term in text for term in risk_terms)
    return min(0.35 + matches * 0.08, 0.88)
