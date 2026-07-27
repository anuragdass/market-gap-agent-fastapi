"""Assembly point for the deepagents orchestrator. All deepagents API contact
lives in this file and `subagents.py` -- a version bump touches only these two.
"""

from deepagents import CompiledSubAgent, SubAgent, create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from app.agents.llm import get_llm
from app.agents.prompts import ORCHESTRATOR_PROMPT
from app.agents.store import DocumentStore
from app.agents.subagents import (
    build_claim_extractor,
    build_pain_point_clusterer,
    build_research_subagents,
)
from app.agents.tools import build_tools
from app.config import get_settings
from app.domain.state import MarketGapState


def build_orchestrator(store: DocumentStore) -> CompiledStateGraph:
    settings = get_settings()
    subagents: list[SubAgent | CompiledSubAgent] = [
        *build_research_subagents(store),
        build_claim_extractor(),
        build_pain_point_clusterer(),
    ]
    return create_deep_agent(
        model=get_llm(),
        tools=build_tools(store),
        system_prompt=ORCHESTRATOR_PROMPT,
        subagents=subagents,
        state_schema=MarketGapState,
        checkpointer=InMemorySaver(),
        debug=settings.debug,
    )
