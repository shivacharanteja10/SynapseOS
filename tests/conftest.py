"""Shared test fixtures for SynapseOS."""

from __future__ import annotations

import pytest

from synapseos.agents import AgentDependencies
from synapseos.core.config import Settings
from synapseos.services import LLMService, MemoryService, VectorStoreService


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        environment="test",
        llm_provider="mock",
        vector_backend="memory",
        human_approval_required_risk_score=0.9,
    )


@pytest.fixture
def agent_dependencies(test_settings: Settings) -> AgentDependencies:
    memory = MemoryService(test_settings)
    vector_store = VectorStoreService(test_settings)
    llm = LLMService(test_settings)
    return AgentDependencies(llm=llm, memory=memory, vector_store=vector_store)
