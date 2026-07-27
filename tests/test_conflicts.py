"""Required test: conflicting opinions about the same company/dimension are
preserved with attribution, never collapsed into a single resolved answer.
"""

from datetime import UTC, datetime

from app.analysis.conflicts import annotate_conflicts, detect_conflicts
from app.domain.enums import Dimension, Platform, Stance
from app.domain.models import Claim, Competitor, Document, Evidence, GroundingReport, claim_id
from app.reporting.brief import render_brief
from app.reporting.evidence import build_evidence_bundle


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


def test_brief_renders_both_conflicting_quotes_with_attribution() -> None:
    positive_quote = "their support team got back to me in ten minutes, genuinely great service"
    negative_quote = "support tickets sit unanswered for over a week with no response at all"
    positive = _claim(Stance.POSITIVE, positive_quote, Platform.REDDIT, "doc-reddit")
    negative = _claim(Stance.NEGATIVE, negative_quote, Platform.G2, "doc-g2")

    conflicts = detect_conflicts([positive, negative])
    claims = annotate_conflicts([positive, negative], conflicts)

    target = Competitor(id="asana", name="Asana", canonical_name="Asana", domain="asana.com", one_liner="PM tool", is_target=True)
    doc_a = Document(
        id="doc-reddit", content_hash="h1", platform=Platform.REDDIT, source_name="reddit",
        url="https://example.com/doc-reddit", text=positive_quote, retrieved_at=datetime.now(UTC),
        query="q", companies=["asana"],
    )
    doc_b = Document(
        id="doc-g2", content_hash="h2", platform=Platform.G2, source_name="serper",
        url="https://example.com/doc-g2", text=negative_quote, retrieved_at=datetime.now(UTC),
        query="q", companies=["asana"],
    )

    bundle = build_evidence_bundle(
        run_id="test-run", target=target, competitors=[target], documents=[doc_a, doc_b],
        claims=claims, pain_points=[], gaps=[], conflicts=conflicts,
        grounding=GroundingReport(claims_proposed=2, claims_accepted=2, claims_rejected=0),
        skipped_sources=[], config={},
    )

    markdown = render_brief(bundle)

    assert "Conflicting Signals" in markdown
    assert positive_quote in markdown
    assert negative_quote in markdown


def test_single_sided_opinions_produce_no_conflict() -> None:
    only_positive_a = _claim(Stance.POSITIVE, "support replied within the hour and solved my billing issue quickly", Platform.REDDIT, "doc-1")
    only_positive_b = _claim(Stance.POSITIVE, "another user also praised the fast turnaround from the support team", Platform.HACKERNEWS, "doc-2")

    conflicts = detect_conflicts([only_positive_a, only_positive_b])
    assert conflicts == []
