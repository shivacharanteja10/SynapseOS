"""Planner agent."""

from __future__ import annotations

from synapseos.agents.base import BaseAgent
from synapseos.models.agent import AgentResult, AgentRole
from synapseos.models.workflow import WorkflowState


class PlannerAgent(BaseAgent):
    """Breaks a user goal into an executable multi-agent strategy."""

    role = AgentRole.PLANNER
    system_prompt = (
        "You are the Planner agent in SynapseOS. Convert ambiguous goals into "
        "clear phases, acceptance criteria, constraints, and handoff notes for "
        "Researcher, Coder, Reviewer, Executor, and Synthesizer agents."
    )

    async def run(self, state: WorkflowState) -> AgentResult:
        task_id = state["task_id"]
        goal = state["goal"]
        prompt = (
            "Create an execution plan for this autonomous task.\n\n"
            f"Goal:\n{goal}\n\n"
            "Return: objectives, assumptions, agent handoffs, risks, and done criteria."
        )
        content = await self._complete(prompt, task_id=task_id, metadata={"phase": "planning"})
        await self.dependencies.memory.remember(task_id, "planner", content)
        return self._result(
            task_id=task_id,
            content=content,
            confidence=0.91,
            risk_score=0.22,
            artifacts={"plan": content},
        )
