"""Required test: the same claim appearing across multiple sources merges into
one Claim with combined evidence, not duplicate claims.
"""

from datetime import UTC, datetime

from app.analysis.dedupe import merge_claims, merge_documents
from app.domain.enums import Dimension, Platform, Stance
from app.domain.models import Claim, Document, Evidence, claim_id, content_hash, document_id


def _evidence(doc_id: str, url: str, platform: Platform, quote: str) -> Evidence:
    return Evidence(
        document_id=doc_id,
        url=url,
        platform=platform,
        source_name=platform.value,
        quote=quote,
        char_start=0,
        char_end=len(quote),
        verified=True,
    )


def test_same_claim_from_two_sources_merges_with_combined_evidence() -> None:
    cid = claim_id("clickup", Dimension.PRICING, "pricing tiers are confusing for growing teams", Stance.NEGATIVE)

    reddit_evidence = _evidence(
        "doc-reddit", "https://reddit.com/r/saas/1", Platform.REDDIT,
        "the pricing tiers are genuinely confusing once your team grows past 10 people",
    )
    hn_evidence = _evidence(
        "doc-hn", "https://news.ycombinator.com/item?id=1", Platform.HACKERNEWS,
        "their tiered pricing gets confusing fast as soon as you scale the team",
    )

    claim_from_reddit = Claim(
        id=cid, company_id="clickup", company_name="ClickUp", dimension=Dimension.PRICING,
        statement="pricing tiers are confusing for growing teams", stance=Stance.NEGATIVE,
        evidence=[reddit_evidence], confidence=0.5,
    )
    claim_from_hn = Claim(
        id=cid, company_id="clickup", company_name="ClickUp", dimension=Dimension.PRICING,
        statement="pricing tiers are confusing for growing teams", stance=Stance.NEGATIVE,
        evidence=[hn_evidence], confidence=0.5,
    )

    merged = merge_claims([claim_from_reddit, claim_from_hn])

    assert len(merged) == 1
    result = merged[0]
    assert len(result.evidence) == 2
    doc_ids = {e.document_id for e in result.evidence}
    platforms = {e.platform for e in result.evidence}
    assert doc_ids == {"doc-reddit", "doc-hn"}
    assert platforms == {Platform.REDDIT, Platform.HACKERNEWS}
    quotes = {e.quote for e in result.evidence}
    assert reddit_evidence.quote in quotes
    assert hn_evidence.quote in quotes
    assert result.confidence > claim_from_reddit.confidence


def test_identical_text_at_two_urls_collapses_to_one_document() -> None:
    text = "clickup support takes days to respond to tickets"
    doc_a = Document(
        id=document_id(Platform.REDDIT, "https://reddit.com/a"),
        content_hash=content_hash(text.lower()),
        platform=Platform.REDDIT, source_name="reddit", url="https://reddit.com/a",
        text=text, retrieved_at=datetime.now(UTC), query="q", companies=["clickup"],
    )
    doc_b = Document(
        id=document_id(Platform.REDDIT, "https://reddit.com/b"),
        content_hash=content_hash(text.lower()),
        platform=Platform.REDDIT, source_name="reddit", url="https://reddit.com/b",
        text=text, retrieved_at=datetime.now(UTC), query="q", companies=["asana"],
    )

    merged = merge_documents([doc_a, doc_b])

    assert len(merged) == 1
    assert set(merged[0].companies) == {"clickup", "asana"}
