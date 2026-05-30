"""Executor agent."""

from __future__ import annotations

from synapseos.agents.base import BaseAgent
from synapseos.models.agent import AgentResult, AgentRole
from synapseos.models.workflow import WorkflowState


class ExecutorAgent(BaseAgent):
    """Plans controlled execution and rollout of approved work."""

    role = AgentRole.EXECUTOR
    system_prompt = (
        "You are the Executor agent in SynapseOS. Convert approved implementation "
        "and review notes into a safe execution plan, validation checklist, and rollback strategy."
    )

    async def run(self, state: WorkflowState) -> AgentResult:
        task_id = state["task_id"]
        prompt = (
            "Create a safe execution and validation plan.\n\n"
            f"Goal:\n{state['goal']}\n\n"
            f"Implementation:\n{state.get('code', '')}\n\n"
            f"Review:\n{state.get('review', '')}\n\n"
            "Return execution steps, validation commands, observability signals, and rollback."
        )
        content = await self._complete(prompt, task_id=task_id, metadata={"phase": "execution"})
        await self.dependencies.memory.remember(task_id, "executor", content)
        return self._result(
            task_id=task_id,
            content=content,
            confidence=0.84,
            risk_score=max(float(state.get("risk_score", 0.0)), _execution_risk(state["goal"])),
            artifacts={"runbook": content},
        )


def _execution_risk(goal: str) -> float:
    text = goal.lower()
    if any(term in text for term in ["production", "deploy", "kubernetes", "migration"]):
        return 0.74
    return 0.38
