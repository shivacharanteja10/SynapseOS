"""LangGraph state machine for multi-agent coordination."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from langgraph.graph import END, START, StateGraph

from synapseos.agents import (
    AgentDependencies,
    CoderAgent,
    ExecutorAgent,
    PlannerAgent,
    ResearcherAgent,
    ReviewerAgent,
    SynthesizerAgent,
)
from synapseos.core.config import Settings
from synapseos.core.logging import get_logger
from synapseos.models.agent import AgentEvent, AgentEventType, AgentMessage, AgentResult, TaskStatus
from synapseos.models.workflow import WorkflowState
from synapseos.services.approvals import ApprovalService
from synapseos.services.event_bus import EventBus

logger = get_logger(__name__)


class WorkflowGraph:
    """Coordinates specialized agents through a LangGraph state machine."""

    def __init__(
        self,
        *,
        settings: Settings,
        dependencies: AgentDependencies,
        approvals: ApprovalService,
        event_bus: EventBus,
    ) -> None:
        self.settings = settings
        self.approvals = approvals
        self.event_bus = event_bus
        self.agents = {
            "planner": PlannerAgent(dependencies),
            "researcher": ResearcherAgent(dependencies),
            "coder": CoderAgent(dependencies),
            "reviewer": ReviewerAgent(dependencies),
            "executor": ExecutorAgent(dependencies),
            "synthesizer": SynthesizerAgent(dependencies),
        }
        self._graph = self._build_graph().compile()
        self._resume_graph = self._build_resume_graph().compile()

    async def run(self, initial_state: WorkflowState) -> WorkflowState:
        """Run the full workflow from planning to completion or approval pause."""

        logger.info("workflow_started", task_id=initial_state["task_id"])
        return cast(WorkflowState, await self._graph.ainvoke(initial_state))

    async def resume_after_approval(self, state: WorkflowState) -> WorkflowState:
        """Resume a paused workflow after human approval."""

        resumed_state = {
            **state,
            "status": TaskStatus.RUNNING,
            "error": None,
        }
        logger.info("workflow_resumed_after_approval", task_id=state["task_id"])
        return cast(WorkflowState, await self._resume_graph.ainvoke(resumed_state))

    def _build_graph(self) -> Any:
        graph = StateGraph(WorkflowState)
        graph.add_node("planner", self._agent_node("planner", "plan"))
        graph.add_node("researcher", self._agent_node("researcher", "research"))
        graph.add_node("coder", self._agent_node("coder", "code"))
        graph.add_node("reviewer", self._agent_node("reviewer", "review"))
        graph.add_node("approval_gate", self._approval_gate)
        graph.add_node("executor", self._agent_node("executor", "execution"))
        graph.add_node("synthesizer", self._agent_node("synthesizer", "final_response"))

        graph.add_edge(START, "planner")
        graph.add_edge("planner", "researcher")
        graph.add_edge("researcher", "coder")
        graph.add_edge("coder", "reviewer")
        graph.add_edge("reviewer", "approval_gate")
        graph.add_conditional_edges(
            "approval_gate",
            self._approval_route,
            {"awaiting_approval": END, "continue": "executor"},
        )
        graph.add_edge("executor", "synthesizer")
        graph.add_edge("synthesizer", END)
        return graph

    def _build_resume_graph(self) -> Any:
        graph = StateGraph(WorkflowState)
        graph.add_node("executor", self._agent_node("executor", "execution"))
        graph.add_node("synthesizer", self._agent_node("synthesizer", "final_response"))
        graph.add_edge(START, "executor")
        graph.add_edge("executor", "synthesizer")
        graph.add_edge("synthesizer", END)
        return graph

    def _agent_node(
        self,
        agent_key: str,
        state_field: str,
    ) -> Callable[[WorkflowState], Awaitable[dict[str, Any]]]:
        async def node(state: WorkflowState) -> dict[str, Any]:
            agent = self.agents[agent_key]
            task_id = state["task_id"]
            await self.event_bus.publish(
                AgentEvent(
                    type=AgentEventType.AGENT_STARTED,
                    task_id=task_id,
                    role=agent.role,
                    payload={"agent": agent_key},
                )
            )
            try:
                result = await agent.run(state)
                await self._publish_agent_result(result)
                update: dict[str, Any] = {
                    "status": TaskStatus.RUNNING,
                    "current_agent": agent_key,
                    "messages": [
                        AgentMessage(
                            role=result.role,
                            task_id=task_id,
                            content=result.content,
                            metadata=result.metadata,
                        )
                    ],
                    "risk_score": max(float(state.get("risk_score", 0.0)), result.risk_score),
                }
                update[state_field] = result.content
                return update
            except Exception as exc:
                logger.exception("agent_node_failed", agent=agent_key, task_id=task_id)
                await self.event_bus.publish(
                    AgentEvent(
                        type=AgentEventType.WORKFLOW_FAILED,
                        task_id=task_id,
                        role=agent.role,
                        content=str(exc),
                    )
                )
                return {
                    "status": TaskStatus.FAILED,
                    "current_agent": agent_key,
                    "error": str(exc),
                }

        return node

    async def _approval_gate(self, state: WorkflowState) -> WorkflowState:
        task_id = state["task_id"]
        risk_score = float(state.get("risk_score", 0.0))
        explicit_requirement = bool(state.get("require_human_approval", True))
        if not self.approvals.should_require_approval(risk_score, explicit_requirement):
            return {"status": TaskStatus.RUNNING}

        decision = await self.approvals.create_decision(
            task_id=task_id,
            agent_role=self.agents["reviewer"].role,
            rationale=(
                "Workflow risk score exceeded the configured human approval "
                "threshold before execution."
            ),
            risk_score=risk_score,
            options=[
                "Approve execution",
                "Reject execution",
                "Request more review",
            ],
        )
        await self.event_bus.publish(
            AgentEvent(
                type=AgentEventType.APPROVAL_REQUIRED,
                task_id=task_id,
                role=decision.agent_role,
                payload=decision.model_dump(mode="json"),
            )
        )
        return {
            "status": TaskStatus.AWAITING_APPROVAL,
            "current_agent": "approval_gate",
            "approvals": [decision],
        }

    @staticmethod
    def _approval_route(state: WorkflowState) -> str:
        if state.get("status") == TaskStatus.AWAITING_APPROVAL:
            return "awaiting_approval"
        return "continue"

    async def _publish_agent_result(self, result: AgentResult) -> None:
        await self.event_bus.publish(
            AgentEvent(
                type=AgentEventType.AGENT_COMPLETED,
                task_id=result.task_id,
                role=result.role,
                content=result.content,
                payload={
                    "confidence": result.confidence,
                    "risk_score": result.risk_score,
                    "requires_approval": result.requires_approval,
                    "artifacts": result.artifacts,
                },
            )
        )
