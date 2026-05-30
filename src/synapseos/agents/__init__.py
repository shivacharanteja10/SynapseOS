"""Specialized autonomous agents."""

from synapseos.agents.base import AgentDependencies, BaseAgent
from synapseos.agents.coder import CoderAgent
from synapseos.agents.executor import ExecutorAgent
from synapseos.agents.planner import PlannerAgent
from synapseos.agents.researcher import ResearcherAgent
from synapseos.agents.reviewer import ReviewerAgent
from synapseos.agents.synthesizer import SynthesizerAgent

__all__ = [
    "AgentDependencies",
    "BaseAgent",
    "PlannerAgent",
    "ResearcherAgent",
    "CoderAgent",
    "ReviewerAgent",
    "ExecutorAgent",
    "SynthesizerAgent",
]
