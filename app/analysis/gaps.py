"""Deterministic gap computation: "target has no claim in dimension X where a
competitor does" is a set operation, not something an LLM should be trusted
to invent. One Gap per dimension per direction, aggregating every competitor
involved.
"""

from collections import defaultdict

from app.domain.enums import Dimension, GapDirection, Stance
from app.domain.models import Claim, Gap

_NOTABLE_STANCES = {Stance.POSITIVE, Stance.NEGATIVE, Stance.MIXED}


def compute_gaps(target_id: str, claims: list[Claim]) -> list[Gap]:
    by_dimension_company: dict[Dimension, dict[str, list[Claim]]] = defaultdict(lambda: defaultdict(list))
    for claim in claims:
        if claim.stance in _NOTABLE_STANCES:
            by_dimension_company[claim.dimension][claim.company_id].append(claim)

    gaps: list[Gap] = []
    for dimension, by_company in by_dimension_company.items():
        target_claims = by_company.get(target_id, [])
        competitor_ids_with_claims = [cid for cid in by_company if cid != target_id]

        if not target_claims and competitor_ids_with_claims:
            competitor_claim_ids = [c.id for cid in competitor_ids_with_claims for c in by_company[cid]]
            gaps.append(
                Gap(
                    dimension=dimension,
                    direction=GapDirection.TARGET_BEHIND,
                    summary=(
                        f"No grounded discussion found about the target's {dimension.value}, "
                        f"while {len(competitor_ids_with_claims)} competitor(s) have documented opinions here."
                    ),
                    target_claim_ids=[],
                    competitor_claim_ids=competitor_claim_ids,
                    competitor_ids=competitor_ids_with_claims,
                )
            )
        elif target_claims and not competitor_ids_with_claims:
            gaps.append(
                Gap(
                    dimension=dimension,
                    direction=GapDirection.TARGET_AHEAD,
                    summary=(
                        f"The target has documented {dimension.value} discussion that no seed "
                        f"competitor has grounded evidence for."
                    ),
                    target_claim_ids=[c.id for c in target_claims],
                    competitor_claim_ids=[],
                    competitor_ids=[],
                )
            )
        # Both present or both absent: no gap in this dimension -- covered
        # elsewhere by the comparison matrix, not flagged as a gap.

    return gaps
