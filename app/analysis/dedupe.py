"""Deterministic dedupe: same claim across sources merges into one claim with
combined evidence; documents with byte-identical normalized text collapse to one.

`stance` is part of the claim identity, so opposing opinions about the same
(company, dimension) never merge into a single claim -- see conflicts.py.
"""

from app.domain.models import Claim, Document


def merge_documents(documents: list[Document]) -> list[Document]:
    by_hash: dict[str, Document] = {}
    for doc in documents:
        existing = by_hash.get(doc.content_hash)
        if existing is None:
            by_hash[doc.content_hash] = doc
        else:
            merged_companies = sorted(set(existing.companies) | set(doc.companies))
            by_hash[doc.content_hash] = existing.model_copy(update={"companies": merged_companies})
    return list(by_hash.values())


def _confidence(distinct_sources: int, distinct_platforms: int) -> float:
    return min(1.0, 0.4 + 0.2 * distinct_sources + 0.1 * distinct_platforms)


def merge_claims(claims: list[Claim]) -> list[Claim]:
    by_id: dict[str, Claim] = {}
    for claim in claims:
        existing = by_id.get(claim.id)
        if existing is None:
            by_id[claim.id] = claim
            continue

        seen_doc_ids = {e.document_id for e in existing.evidence}
        merged_evidence = list(existing.evidence) + [e for e in claim.evidence if e.document_id not in seen_doc_ids]
        distinct_sources = len({e.document_id for e in merged_evidence})
        distinct_platforms = len({e.platform for e in merged_evidence})
        by_id[claim.id] = existing.model_copy(
            update={
                "evidence": merged_evidence,
                "confidence": _confidence(distinct_sources, distinct_platforms),
            }
        )

    # Also bump confidence for claims that only ever appeared once but from
    # a single multi-evidence extraction (defensive; normal path is above).
    result = []
    for claim in by_id.values():
        distinct_sources = len({e.document_id for e in claim.evidence})
        distinct_platforms = len({e.platform for e in claim.evidence})
        if distinct_sources > 1:
            claim = claim.model_copy(update={"confidence": _confidence(distinct_sources, distinct_platforms)})
        result.append(claim)
    return result
