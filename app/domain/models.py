import hashlib
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.domain.enums import (
    CompetitorStatus,
    Dimension,
    GapDirection,
    Platform,
    Scope,
    SkipReason,
    Stance,
)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "unknown"


def document_id(platform: Platform, canonical_url: str) -> str:
    return hashlib.sha256(f"{platform}|{canonical_url}".encode()).hexdigest()[:16]


def content_hash(normalized_text: str) -> str:
    return hashlib.sha256(normalized_text.encode()).hexdigest()


def claim_id(company_id: str, dimension: Dimension, normalized_statement: str, stance: Stance) -> str:
    return hashlib.sha256(f"{company_id}|{dimension}|{normalized_statement}|{stance}".encode()).hexdigest()[:16]


class Competitor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    canonical_name: str
    domain: str | None = None
    one_liner: str = Field(max_length=200)
    is_target: bool = False
    status: CompetitorStatus = CompetitorStatus.ACCEPTED
    duplicate_of: str | None = None
    skip_reason: str | None = None


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    content_hash: str
    platform: Platform
    source_name: str
    url: HttpUrl
    title: str | None = None
    text: str
    published_at: datetime | None = None
    author: str | None = None
    retrieved_at: datetime
    query: str
    companies: list[str] = Field(default_factory=list)
    score: int | None = None


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    url: HttpUrl
    platform: Platform
    source_name: str
    quote: str
    char_start: int
    char_end: int
    published_at: datetime | None = None
    author: str | None = None
    verified: bool = True


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    company_id: str
    company_name: str
    dimension: Dimension
    statement: str = Field(max_length=300)
    stance: Stance
    evidence: list[Evidence]
    confidence: float = Field(ge=0.0, le=1.0)
    conflicts_with: list[str] = Field(default_factory=list)
    extracted_by: str = "claim_extractor"

    @field_validator("evidence")
    @classmethod
    def _evidence_non_empty_and_verified(cls, v: list[Evidence]) -> list[Evidence]:
        if not v:
            raise ValueError("claim must have at least one evidence entry")
        if not all(e.verified for e in v):
            raise ValueError("all evidence on a claim must be verified")
        return v


class PainPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str = Field(max_length=60)
    description: str
    scope: Scope
    company_ids: list[str]
    claim_ids: list[str]
    evidence: list[Evidence]
    platforms: list[Platform]
    mention_count: int
    confidence: float = Field(ge=0.0, le=1.0)


class Gap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: Dimension
    direction: GapDirection
    summary: str
    target_claim_ids: list[str] = Field(default_factory=list)
    competitor_claim_ids: list[str] = Field(default_factory=list)
    competitor_ids: list[str] = Field(default_factory=list)


class ConflictPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stance: Stance
    claim_ids: list[str]
    evidence: list[Evidence]


class ConflictSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    positions: list[ConflictPosition]


class SkippedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    query: str
    reason: SkipReason
    detail: str
    http_status: int | None = None
    occurred_at: datetime


class GroundingRejection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_statement: str
    quote: str
    document_id: str
    reason: str


class GroundingReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims_proposed: int = 0
    claims_accepted: int = 0
    claims_rejected: int = 0
    rejections: list[GroundingRejection] = Field(default_factory=list)


class EvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    run_id: str
    generated_at: datetime
    target: Competitor
    competitors: list[Competitor]
    sources: dict[str, Any]
    claims: list[Claim]
    pain_points: list[PainPoint]
    gaps: list[Gap]
    conflicts: list[ConflictSet]
    grounding: GroundingReport
    config: dict[str, Any]
