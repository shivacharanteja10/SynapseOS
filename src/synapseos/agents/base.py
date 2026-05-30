"""Base classes shared by all specialized agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, cast

from synapseos.models.agent import AgentResult, AgentRole
from synapseos.models.workflow import WorkflowState


@dataclass(frozen=True, slots=True)
class AgentDependencies:
    """Dependencies injected into every agent."""

    llm: Any
    memory: Any
    vector_store: Any


class BaseAgent(ABC):
    """Contract every SynapseOS agent must implement."""

    role: AgentRole
    system_prompt: str

    def __init__(self, dependencies: AgentDependencies) -> None:
        self.dependencies = dependencies

    async def _complete(self, user_prompt: str, *, task_id: str, metadata: dict[str, Any]) -> str:
        return cast(
            str,
            await self.dependencies.llm.complete(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                task_id=task_id,
                metadata={"agent": self.role.value, **metadata},
            ),
        )

    def _result(
        self,
        *,
        task_id: str,
        content: str,
        confidence: float,
        risk_score: float = 0.0,
        artifacts: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentResult:
        return AgentResult(
            role=self.role,
            task_id=task_id,
            content=content,
            confidence=confidence,
            risk_score=risk_score,
            requires_approval=risk_score >= 0.72,
            artifacts=artifacts or {},
            metadata=metadata or {},
        )

    @abstractmethod
    async def run(self, state: WorkflowState) -> AgentResult:
        """Run the agent against the current workflow state."""
