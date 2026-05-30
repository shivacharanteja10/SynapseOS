"""LLM adapter with LangSmith-ready metadata propagation."""

from __future__ import annotations

import asyncio
from typing import Any

from synapseos.core.config import Settings
from synapseos.core.logging import get_logger

logger = get_logger(__name__)


class LLMService:
    """Async completion service used by all agents.

    The service defaults to a deterministic local mock so SynapseOS can be run in
    CI and demos without secrets. Set LLM_PROVIDER=openai and OPENAI_API_KEY to
    use LangChain's ChatOpenAI integration in production.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        task_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Generate a completion using the configured provider."""

        metadata = metadata or {}
        if self.settings.llm_provider == "openai" and self.settings.openai_api_key:
            return await self._complete_openai(system_prompt, user_prompt, task_id, metadata)
        return await self._complete_mock(system_prompt, user_prompt, task_id, metadata)

    async def _complete_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        task_id: str,
        metadata: dict[str, Any],
    ) -> str:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            logger.warning("openai_provider_missing_dependencies", error=str(exc))
            return await self._complete_mock(system_prompt, user_prompt, task_id, metadata)

        model = ChatOpenAI(
            model=self.settings.llm_model,
            temperature=self.settings.llm_temperature,
            api_key=self.settings.openai_api_key,
            tags=["synapseos", metadata.get("agent", "unknown")],
            metadata={"task_id": task_id, **metadata},
        )
        response = await model.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )
        return str(response.content)

    async def _complete_mock(
        self,
        system_prompt: str,
        user_prompt: str,
        task_id: str,
        metadata: dict[str, Any],
    ) -> str:
        await asyncio.sleep(0)
        agent = metadata.get("agent", "agent")
        phase = metadata.get("phase", "analysis")
        goal = _extract_goal(user_prompt)
        return (
            f"SynapseOS {agent} output for task {task_id}.\n\n"
            f"Phase: {phase}\n"
            f"Objective: {goal}\n"
            "Decisions:\n"
            "- Preserve auditability with explicit state transitions and durable events.\n"
            "- Prefer reversible actions until human approval resolves critical risk.\n"
            "- Keep outputs typed so downstream agents can validate assumptions.\n"
            "Validation:\n"
            "- Unit-test agent contracts, state reducers, and approval branches.\n"
            "- Stream progress events for every major node transition."
        )


def _extract_goal(prompt: str) -> str:
    marker = "Goal:"
    if marker not in prompt:
        return prompt.strip().splitlines()[0][:180]
    after = prompt.split(marker, maxsplit=1)[1].strip()
    return after.splitlines()[0][:180]
