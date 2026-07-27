"""Deterministic pipeline orchestration ("pipeline" mode): every stage is a
direct Python/LLM-structured-output call with no agent tool-loop in between.
This is the reliable default -- a flaky agent loop can never lose the
artifacts -- and it is what the demo, API, and tests exercise.

"agent" mode (`app.agents.graph.build_orchestrator`) exercises the same
adapters/validators through the deepagents subagent topology described in
the README, but is not required for artifact correctness.
"""

from pathlib import Path

from langchain_core.messages import HumanMessage

from app.agents.schemas import ClaimBatch, PainPointBatch
from app.agents.store import DocumentStore
from app.agents.subagents import build_claim_extractor, build_pain_point_clusterer
from app.analysis.conflicts import annotate_conflicts, detect_conflicts
from app.analysis.dedupe import merge_claims
from app.analysis.gaps import compute_gaps
from app.analysis.grounding import GroundingValidator, RawClaim
from app.analysis.intake import make_competitor, resolve_intake
from app.analysis.painpoints import build_pain_points
from app.config import Settings
from app.domain.enums import CompetitorStatus, RunStatus, Stance
from app.domain.models import Claim, Competitor, Document
from app.reporting.brief import render_brief, write_brief
from app.reporting.evidence import build_evidence_bundle, write_evidence_json
from app.sources.registry import available_sources, get_source


def _query_templates(company_name: str) -> list[str]:
    return [
        f"{company_name} review",
        f"{company_name} pricing complaints",
        f"{company_name} alternatives",
        f"{company_name} vs",
        f"{company_name} support experience",
    ]


async def _ingest_company(company_id: str, company_name: str, store: DocumentStore, settings: Settings) -> None:
    for query in _query_templates(company_name):
        for source_name in available_sources():
            if source_name == "serper" and not settings.serper_api_key:
                # avoid spamming a guaranteed no_api_key skip per query
                continue
            documents, skipped = await get_source(source_name)(query, company_id, 10)
            store.add_documents(documents)
            if skipped is not None:
                store.add_skip(skipped)


def _rank_and_cap(documents: list[Document], company_id: str, limit: int) -> list[Document]:
    company_docs = [d for d in documents if company_id in d.companies]
    company_docs.sort(key=lambda d: d.score or 0, reverse=True)
    return company_docs[:limit]


async def _extract_claims_for_document(
    extractor: object, company: Competitor, document: Document, validator: GroundingValidator
) -> tuple[list[Claim], int, list]:
    prompt = f"Company: {company.name} (id: {company.id})\n\nDocument text:\n{document.text}"
    result = await extractor.ainvoke({"messages": [HumanMessage(content=prompt)]})  # type: ignore[attr-defined]
    structured = result.get("structured_response")
    batch: ClaimBatch = (
        structured if isinstance(structured, ClaimBatch) else ClaimBatch.model_validate(structured or {})
    )

    raws = [
        RawClaim(
            company_id=company.id,
            company_name=company.name,
            dimension=c.dimension,
            statement=c.statement,
            stance=c.stance,
            quote=c.quote,
            document_id=document.id,
        )
        for c in batch.claims
    ]
    claims, report = validator.validate_batch(raws, {document.id: document})
    return claims, report.claims_proposed, report.rejections


async def run_pipeline(
    run_id: str,
    company_name: str,
    company_description: str,
    seed_competitors: list[str],
    settings: Settings,
    artifacts_dir: Path | None = None,
) -> dict:
    store = DocumentStore()
    target = make_competitor(company_name, None, company_description, is_target=True)
    proposed = [make_competitor(name, None, f"Seed competitor: {name}") for name in seed_competitors]
    _, resolved_competitors, meets_minimum = resolve_intake(target, proposed, settings.min_competitors)
    store.record_intake(target, resolved_competitors)

    accepted = [c for c in resolved_competitors if c.status == CompetitorStatus.ACCEPTED]
    companies_to_research = [target, *accepted]

    for company in companies_to_research:
        await _ingest_company(company.id, company.name, store, settings)

    validator = GroundingValidator(min_quote_chars=settings.min_quote_chars, max_quote_chars=settings.max_quote_chars)
    extractor_runnable = build_claim_extractor()["runnable"]

    all_claims: list[Claim] = []
    claims_proposed_total = 0
    rejections_total: list = []

    for company in companies_to_research:
        docs = _rank_and_cap(store.all(), company.id, settings.max_documents_per_company)
        for document in docs:
            claims, proposed_count, rejections = await _extract_claims_for_document(
                extractor_runnable, company, document, validator
            )
            all_claims.extend(claims)
            claims_proposed_total += proposed_count
            rejections_total.extend(rejections)

    merged_claims = merge_claims(all_claims)
    conflicts = detect_conflicts(merged_claims)
    merged_claims = annotate_conflicts(merged_claims, conflicts)

    negative_or_neutral = [c for c in merged_claims if c.stance in (Stance.NEGATIVE, Stance.NEUTRAL, Stance.MIXED)]
    pain_points = []
    if negative_or_neutral:
        clusterer_runnable = build_pain_point_clusterer()["runnable"]
        claim_summaries = "\n".join(
            f"- id={c.id} company_id={c.company_id} dimension={c.dimension.value} "
            f"stance={c.stance.value}: {c.statement}"
            for c in negative_or_neutral
        )
        result = await clusterer_runnable.ainvoke({"messages": [HumanMessage(content=claim_summaries)]})
        structured = result.get("structured_response")
        batch: PainPointBatch = (
            structured
            if isinstance(structured, PainPointBatch)
            else PainPointBatch.model_validate(structured or {})
        )
        claims_by_id = {c.id: c for c in merged_claims}
        pain_points = build_pain_points(
            [c.model_dump() for c in batch.clusters], claims_by_id, settings.domain_wide_min_companies
        )

    gaps = compute_gaps(target.id, merged_claims)

    from app.domain.models import GroundingReport

    grounding_report = GroundingReport(
        claims_proposed=claims_proposed_total,
        claims_accepted=len(all_claims),
        claims_rejected=len(rejections_total),
        rejections=rejections_total,
    )

    bundle = build_evidence_bundle(
        run_id=run_id,
        target=target,
        competitors=resolved_competitors,
        documents=store.all(),
        claims=merged_claims,
        pain_points=pain_points,
        gaps=gaps,
        conflicts=conflicts,
        grounding=grounding_report,
        skipped_sources=store.skipped,
        config={
            "orchestration_mode": "pipeline",
            "model": settings.llm_model,
            "sources_enabled": available_sources(),
            "competitor_count": len(accepted),
            "meets_minimum_competitors": meets_minimum,
        },
    )

    artifacts_dir = artifacts_dir or (settings.artifacts_dir / run_id)
    write_evidence_json(bundle, artifacts_dir / "evidence.json")
    markdown = render_brief(bundle)
    write_brief(markdown, artifacts_dir / "competitive_brief.md")

    status = RunStatus.SUCCEEDED
    if store.skipped or not meets_minimum:
        status = RunStatus.PARTIAL

    return {
        "status": status,
        "counts": {
            "documents": len(store.all()),
            "claims": len(merged_claims),
            "pain_points": len(pain_points),
            "skipped_sources": len(store.skipped),
        },
        "artifacts_dir": str(artifacts_dir),
    }
