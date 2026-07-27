"""Conflict detection: preserve opposing opinions about the same (company,
dimension) with full attribution instead of resolving them into one answer.
"""

from collections import defaultdict

from app.domain.enums import Stance
from app.domain.models import Claim, ConflictPosition, ConflictSet

_OPPOSING_PAIRS = {
    frozenset({Stance.POSITIVE, Stance.NEGATIVE}),
}


def detect_conflicts(claims: list[Claim]) -> list[ConflictSet]:
    by_subject: dict[str, list[Claim]] = defaultdict(list)
    for claim in claims:
        subject = f"{claim.company_id}|{claim.dimension}"
        by_subject[subject].append(claim)

    conflicts: list[ConflictSet] = []
    for subject, subject_claims in by_subject.items():
        stances_present = {c.stance for c in subject_claims}
        if not any(pair <= stances_present for pair in _OPPOSING_PAIRS):
            continue

        by_stance: dict[Stance, list[Claim]] = defaultdict(list)
        for c in subject_claims:
            by_stance[c.stance].append(c)

        positions = [
            ConflictPosition(
                stance=stance,
                claim_ids=[c.id for c in stance_claims],
                evidence=[e for c in stance_claims for e in c.evidence],
            )
            for stance, stance_claims in by_stance.items()
            if stance in (Stance.POSITIVE, Stance.NEGATIVE)
        ]
        if len(positions) >= 2:
            conflicts.append(ConflictSet(subject=subject, positions=positions))

    return conflicts


def annotate_conflicts(claims: list[Claim], conflicts: list[ConflictSet]) -> list[Claim]:
    """Set `conflicts_with` on each claim involved in a ConflictSet."""
    claim_to_conflicting: dict[str, set[str]] = defaultdict(set)
    for conflict in conflicts:
        all_ids = [cid for pos in conflict.positions for cid in pos.claim_ids]
        for cid in all_ids:
            claim_to_conflicting[cid].update(i for i in all_ids if i != cid)

    updated = []
    for claim in claims:
        others = claim_to_conflicting.get(claim.id)
        if others:
            updated.append(claim.model_copy(update={"conflicts_with": sorted(others)}))
        else:
            updated.append(claim)
    return updated
