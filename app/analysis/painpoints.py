"""Turns LLM-proposed pain-point clusters (label/description/claim_ids) into
grounded `PainPoint` models. The LLM never decides scope -- domain_wide vs
company_specific is a countable fact (>= N distinct companies touched), not
a judgment call.
"""

import hashlib

from app.analysis.confidence import score_from_evidence
from app.domain.enums import Scope
from app.domain.models import Claim, Evidence, PainPoint


def build_pain_points(
    clusters: list[dict],
    claims_by_id: dict[str, Claim],
    domain_wide_min_companies: int = 2,
) -> list[PainPoint]:
    pain_points: list[PainPoint] = []
    for cluster in clusters:
        claim_ids = [cid for cid in cluster.get("claim_ids", []) if cid in claims_by_id]
        if not claim_ids:
            continue

        cluster_claims = [claims_by_id[cid] for cid in claim_ids]
        company_ids = sorted({c.company_id for c in cluster_claims})
        seen_doc_quote: set[tuple[str, str]] = set()
        evidence: list[Evidence] = []
        for claim in cluster_claims:
            for e in claim.evidence:
                key = (e.document_id, e.quote)
                if key not in seen_doc_quote:
                    seen_doc_quote.add(key)
                    evidence.append(e)

        platforms = sorted({e.platform for e in evidence}, key=lambda p: p.value)
        scope = Scope.DOMAIN_WIDE if len(company_ids) >= domain_wide_min_companies else Scope.COMPANY_SPECIFIC

        pain_points.append(
            PainPoint(
                id=hashlib.sha256(cluster["label"].encode()).hexdigest()[:16],
                label=cluster["label"][:60],
                description=cluster.get("description", ""),
                scope=scope,
                company_ids=company_ids,
                claim_ids=claim_ids,
                evidence=evidence,
                platforms=platforms,
                mention_count=len(evidence),
                confidence=score_from_evidence(evidence),
            )
        )
    return pain_points
