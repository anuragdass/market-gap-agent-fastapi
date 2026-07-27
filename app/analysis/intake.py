"""Deterministic re-validation of subagent-proposed intake: collapses exact
name/domain duplicates and enforces the minimum-competitor gate. The subagent
proposes; this function is the authoritative decision.
"""

from app.domain.enums import CompetitorStatus
from app.domain.models import Competitor, slugify


def _normalized_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    d = domain.lower().strip()
    d = d.removeprefix("https://").removeprefix("http://").removeprefix("www.")
    return d.rstrip("/")


def resolve_intake(
    target: Competitor, proposed_competitors: list[Competitor], min_competitors: int
) -> tuple[Competitor, list[Competitor], bool]:
    """Returns (target, resolved_competitors, meets_minimum)."""
    seen: dict[str, Competitor] = {}
    resolved: list[Competitor] = []

    def _keys(name: str, domain: str | None) -> list[str]:
        keys = [name.strip().lower()]
        normalized_domain = _normalized_domain(domain)
        if normalized_domain:
            keys.append(normalized_domain)
        # A bare name that is itself domain-shaped (e.g. "notion.so") should
        # match on its own normalized form too.
        keys.append(_normalized_domain(name) or name.strip().lower())
        return list(dict.fromkeys(keys))

    for key in _keys(target.canonical_name, target.domain):
        seen[key] = target

    for competitor in proposed_competitors:
        if competitor.status != CompetitorStatus.ACCEPTED:
            resolved.append(competitor)
            continue

        keys = _keys(competitor.canonical_name, competitor.domain)
        duplicate_of = next((seen[k] for k in keys if k in seen), None)

        if duplicate_of is not None:
            resolved.append(
                competitor.model_copy(
                    update={
                        "status": CompetitorStatus.SKIPPED_DUPLICATE,
                        "duplicate_of": duplicate_of.id,
                        "skip_reason": f"duplicate of {duplicate_of.name}",
                    }
                )
            )
            continue

        for key in keys:
            seen[key] = competitor
        resolved.append(competitor)

    accepted_count = sum(1 for c in resolved if c.status == CompetitorStatus.ACCEPTED)
    return target, resolved, accepted_count >= min_competitors


def make_competitor(name: str, domain: str | None, one_liner: str, is_target: bool = False) -> Competitor:
    return Competitor(
        id=slugify(name),
        name=name,
        canonical_name=name,
        domain=domain,
        one_liner=one_liner[:200],
        is_target=is_target,
    )
