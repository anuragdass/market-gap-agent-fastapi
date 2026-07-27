"""Structured-output schemas forced on the compiled claim/pain-point
subagents via `response_format`. These are intentionally the ONLY shapes an
LLM is allowed to hand back for grounded facts -- everything here still runs
through `GroundingValidator` before it becomes a `Claim`.
"""

from pydantic import BaseModel, Field

from app.domain.enums import Dimension, Stance


class RawClaimOut(BaseModel):
    company_id: str = Field(description="id of the company this claim is about")
    dimension: Dimension
    statement: str = Field(max_length=300, description="your paraphrase of the claim, not a quote")
    stance: Stance
    quote: str = Field(description="verbatim contiguous span copied exactly from the source document")


class ClaimBatch(BaseModel):
    claims: list[RawClaimOut] = Field(default_factory=list, description="0-8 claims; empty list if none found")


class PainPointCluster(BaseModel):
    label: str = Field(max_length=60)
    description: str
    claim_ids: list[str] = Field(description="only ids from the supplied claim list -- never invent an id")


class PainPointBatch(BaseModel):
    clusters: list[PainPointCluster] = Field(default_factory=list)
