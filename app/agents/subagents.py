"""Subagent definitions for the deepagents orchestrator.

`intake_validator` and `research_scout` are declarative dict `SubAgent`s that
share the main agent's tool set (bound to the run's `DocumentStore`).
`claim_extractor` and `pain_point_clusterer` are `CompiledSubAgent`s wrapping
a `create_agent` graph with a forced `response_format` -- pure structured
transforms with no tools, which is stricter and cheaper than a tool-looping
agent for this kind of extraction.
"""

from deepagents import CompiledSubAgent, SubAgent
from langchain.agents import create_agent

from app.agents.llm import get_llm
from app.agents.prompts import BRIEF_WRITER_PROMPT, INTAKE_VALIDATOR_PROMPT, RESEARCH_SCOUT_PROMPT
from app.agents.schemas import ClaimBatch, PainPointBatch
from app.agents.store import DocumentStore
from app.agents.tools import build_tools

CLAIM_EXTRACTOR_PROMPT = """You extract claims about ONE named company from ONE
source document's text, across dimensions: features, pricing, ux, support,
positioning, integrations, performance, reliability.

For each claim you find:
- `quote` MUST be copied character-for-character from the document text you
  were given -- do not paraphrase, trim with ellipses, or fix typos in it.
  If you cannot find a genuinely verbatim span that supports a claim, do not
  emit that claim.
- `statement` is your own short paraphrase (this is NOT checked against the
  document, only `quote` is -- so keep `statement` accurate to the quote).
- Only claim things this specific document actually says. Do not use outside
  knowledge about the company.

If the document supports no claims about the named company, return an empty
list. An empty list is a correct and expected answer for irrelevant documents.
"""

PAIN_POINT_CLUSTERER_PROMPT = """You are given a list of claims (id, company_id,
dimension, statement, stance) that are negative or neutral. Group claims that
describe the same underlying complaint or unmet need into clusters, even
across different companies -- that is how domain-wide pain points are found.

For each cluster:
- `label`: a short (<=60 char) name for the complaint.
- `description`: 1-2 sentences.
- `claim_ids`: ONLY ids from the list you were given. Never invent an id and
  never include a claim whose statement doesn't actually match the cluster.

Small, tight clusters are better than one big vague cluster. It is fine to
leave a claim out of every cluster if it doesn't share a theme with others.
"""


def build_research_subagents(store: DocumentStore) -> list[SubAgent]:
    tools = build_tools(store)
    intake_validator: SubAgent = {
        "name": "intake_validator",
        "description": "Resolve the target company and seed competitor list into distinct, real entities.",
        "system_prompt": INTAKE_VALIDATOR_PROMPT,
        "tools": tools,
    }
    research_scout: SubAgent = {
        "name": "research_scout",
        "description": "Gather Reddit/Serper/Hacker News discussion about one company.",
        "system_prompt": RESEARCH_SCOUT_PROMPT,
        "tools": tools,
    }
    brief_writer: SubAgent = {
        "name": "brief_writer",
        "description": "Write the narrative sections of the competitive brief from grounded, pre-computed context.",
        "system_prompt": BRIEF_WRITER_PROMPT,
        "tools": [],
    }
    return [intake_validator, research_scout, brief_writer]


def build_claim_extractor() -> CompiledSubAgent:
    runnable = create_agent(
        model=get_llm(),
        tools=[],
        system_prompt=CLAIM_EXTRACTOR_PROMPT,
        response_format=ClaimBatch,
    )
    return CompiledSubAgent(
        name="claim_extractor",
        description="Extract grounded claims about one company from one document's text.",
        runnable=runnable,
    )


def build_pain_point_clusterer() -> CompiledSubAgent:
    runnable = create_agent(
        model=get_llm(),
        tools=[],
        system_prompt=PAIN_POINT_CLUSTERER_PROMPT,
        response_format=PainPointBatch,
    )
    return CompiledSubAgent(
        name="pain_point_clusterer",
        description="Cluster negative/neutral claims into domain-wide or company-specific pain points.",
        runnable=runnable,
    )
