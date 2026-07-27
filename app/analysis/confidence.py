"""Shared confidence arithmetic -- no LLM, no recency decay in this scope cut.

confidence = min(1.0, 0.4 + 0.2 * distinct_sources + 0.1 * distinct_platforms)
"""

from app.domain.models import Evidence


def score_from_evidence(evidence: list[Evidence]) -> float:
    distinct_sources = len({e.document_id for e in evidence})
    distinct_platforms = len({e.platform for e in evidence})
    return min(1.0, 0.4 + 0.2 * distinct_sources + 0.1 * distinct_platforms)
