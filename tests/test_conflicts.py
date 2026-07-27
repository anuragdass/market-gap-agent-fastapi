"""Required test: conflicting opinions about the same company/dimension are
preserved with attribution, never collapsed into a single resolved answer.
"""

from app.analysis.conflicts import annotate_conflicts, detect_conflicts
from app.domain.enums import Dimension, Platform, Stance
from app.domain.models import Claim, Evidence, claim_id


def _claim(stance: Stance, quote: str, platform: Platform, doc_id: str) -> Claim:
    evidence = Evidence(
        document_id=doc_id, url=f"https://example.com/{doc_id}", platform=platform,
        source_name=platform.value, quote=quote, char_start=0, char_end=len(quote), verified=True,
    )
    return Claim(
        id=claim_id("asana", Dimension.SUPPORT, f"support-{stance.value}", stance),
        company_id="asana", company_name="Asana", dimension=Dimension.SUPPORT,
        statement=f"support opinions are {stance.value}", stance=stance,
        evidence=[evidence], confidence=0.5,
    )


def test_conflicting_opinions_survive_dedupe_and_are_flagged() -> None:
    positive = _claim(
        Stance.POSITIVE,
        "their support team got back to me in ten minutes, genuinely great service",
        Platform.REDDIT, "doc-reddit",
    )
    negative = _claim(
        Stance.NEGATIVE,
        "support tickets sit unanswered for over a week with no response at all",
        Platform.G2, "doc-g2",
    )

    # Different stance -> different claim id -> dedupe never merges these.
    assert positive.id != negative.id

    conflicts = detect_conflicts([positive, negative])
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.subject == "asana|support"

    stances_in_conflict = {p.stance for p in conflict.positions}
    assert stances_in_conflict == {Stance.POSITIVE, Stance.NEGATIVE}

    all_quotes = {e.quote for p in conflict.positions for e in p.evidence}
    assert positive.evidence[0].quote in all_quotes
    assert negative.evidence[0].quote in all_quotes

    annotated = annotate_conflicts([positive, negative], conflicts)
    by_id = {c.id: c for c in annotated}
    assert by_id[negative.id].id in by_id[positive.id].conflicts_with
    assert by_id[positive.id].id in by_id[negative.id].conflicts_with


def test_single_sided_opinions_produce_no_conflict() -> None:
    only_positive_a = _claim(Stance.POSITIVE, "support replied within the hour and solved my billing issue quickly", Platform.REDDIT, "doc-1")
    only_positive_b = _claim(Stance.POSITIVE, "another user also praised the fast turnaround from the support team", Platform.HACKERNEWS, "doc-2")

    conflicts = detect_conflicts([only_positive_a, only_positive_b])
    assert conflicts == []
