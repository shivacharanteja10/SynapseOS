"""Researcher agent."""

from __future__ import annotations

from synapseos.agents.base import BaseAgent
from synapseos.models.agent import AgentResult, AgentRole
from synapseos.models.workflow import WorkflowState


class ResearcherAgent(BaseAgent):
    """Retrieves context from memory and vector stores, then summarizes evidence."""

    role = AgentRole.RESEARCHER
    system_prompt = (
        "You are the Researcher agent in SynapseOS. Retrieve relevant context, "
        "identify unknowns, and produce concise evidence-backed notes that other "
        "agents can safely use."
    )

    async def run(self, state: WorkflowState) -> AgentResult:
        task_id = state["task_id"]
        goal = state["goal"]
        plan = state.get("plan", "")
        related_context = await self.dependencies.vector_store.search(goal, limit=4)
        context_block = "\n".join(
            f"- {item['content'][:600]}" for item in related_context
        ) or "- No prior vector context found."
        prompt = (
            "Research this task using the plan and retrieved context.\n\n"
            f"Goal:\n{goal}\n\nPlan:\n{plan}\n\nRelated context:\n{context_block}\n\n"
            "Return key findings, risks, dependency assumptions, and implementation hints."
        )
        content = await self._complete(prompt, task_id=task_id, metadata={"phase": "research"})
        await self.dependencies.vector_store.add_text(
            task_id=task_id,
            content=content,
            metadata={"agent": self.role.value, "source": "research_notes"},
        )
        await self.dependencies.memory.remember(task_id, "researcher", content)
        return self._result(
            task_id=task_id,
            content=content,
            confidence=0.88,
            risk_score=0.28,
            artifacts={"sources_used": len(related_context)},
        )
