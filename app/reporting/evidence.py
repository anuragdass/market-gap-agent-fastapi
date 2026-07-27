"""Assembles evidence.json. This is chokepoint 2 of the anti-hallucination
control: every Evidence attached to a Claim or PainPoint is re-verified
against the actual fetched document text before the bundle is allowed to be
written. If anything fails re-verification, the run is not silently trusted.
"""

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from app.analysis.grounding import verify_quote
from app.domain.models import (
    Claim,
    Competitor,
    ConflictSet,
    Document,
    EvidenceBundle,
    Gap,
    GroundingReport,
    PainPoint,
)


class EvidenceIntegrityError(RuntimeError):
    pass


def _reverify_all(claims: list[Claim], pain_points: list[PainPoint], doc_index: dict[str, Document]) -> None:
    for claim in claims:
        for evidence in claim.evidence:
            doc = doc_index.get(evidence.document_id)
            if doc is None or verify_quote(evidence.quote, doc) is None:
                raise EvidenceIntegrityError(
                    f"claim {claim.id} evidence quote is not verifiable against document {evidence.document_id}"
                )
    for pain_point in pain_points:
        for evidence in pain_point.evidence:
            doc = doc_index.get(evidence.document_id)
            if doc is None or verify_quote(evidence.quote, doc) is None:
                raise EvidenceIntegrityError(
                    f"pain point {pain_point.id} evidence quote is not verifiable "
                    f"against document {evidence.document_id}"
                )


def build_evidence_bundle(
    run_id: str,
    target: Competitor,
    competitors: list[Competitor],
    documents: list[Document],
    claims: list[Claim],
    pain_points: list[PainPoint],
    gaps: list[Gap],
    conflicts: list[ConflictSet],
    grounding: GroundingReport,
    skipped_sources: list,
    config: dict,
) -> EvidenceBundle:
    doc_index = {d.id: d for d in documents}
    _reverify_all(claims, pain_points, doc_index)

    counts_by_platform: dict[str, int] = {}
    for doc in documents:
        counts_by_platform[doc.platform.value] = counts_by_platform.get(doc.platform.value, 0) + 1

    sources = {
        "documents": [
            {
                "id": d.id,
                "platform": d.platform.value,
                "source_name": d.source_name,
                "url": str(d.url),
                "title": d.title,
                "text_excerpt": d.text[:1000],
                "published_at": d.published_at.isoformat() if d.published_at else None,
            }
            for d in documents
        ],
        "skipped": [s.model_dump(mode="json") for s in skipped_sources],
        "counts_by_platform": counts_by_platform,
    }

    return EvidenceBundle(
        run_id=run_id,
        generated_at=datetime.now(UTC),
        target=target,
        competitors=competitors,
        sources=sources,
        claims=claims,
        pain_points=pain_points,
        gaps=gaps,
        conflicts=conflicts,
        grounding=grounding,
        config=config,
    )


def write_evidence_json(bundle: EvidenceBundle, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = bundle.model_dump(mode="json")
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
