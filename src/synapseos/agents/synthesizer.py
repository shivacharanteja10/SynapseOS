"""Synthesizer agent."""

from __future__ import annotations

from synapseos.agents.base import BaseAgent
from synapseos.models.agent import AgentResult, AgentRole
from synapseos.models.workflow import WorkflowState


class SynthesizerAgent(BaseAgent):
    """Produces the final user-facing answer from all agent outputs."""

    role = AgentRole.SYNTHESIZER
    system_prompt = (
        "You are the Synthesizer agent in SynapseOS. Distill all prior agent work "
        "into a clear final response with decisions, deliverables, validation, and next steps."
    )

    async def run(self, state: WorkflowState) -> AgentResult:
        task_id = state["task_id"]
        prompt = (
            "Synthesize the final answer for the user.\n\n"
            f"Goal:\n{state['goal']}\n\n"
            f"Plan:\n{state.get('plan', '')}\n\n"
            f"Research:\n{state.get('research', '')}\n\n"
            f"Implementation:\n{state.get('code', '')}\n\n"
            f"Review:\n{state.get('review', '')}\n\n"
            f"Execution:\n{state.get('execution', '')}\n\n"
            "Return a concise final report with outcome, risks, and validation evidence."
        )
        content = await self._complete(prompt, task_id=task_id, metadata={"phase": "synthesis"})
        await self.dependencies.memory.remember(task_id, "synthesizer", content)
        return self._result(
            task_id=task_id,
            content=content,
            confidence=0.9,
            risk_score=0.18,
            artifacts={"final_response": content},
        )
