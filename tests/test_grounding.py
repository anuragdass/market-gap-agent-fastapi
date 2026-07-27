from datetime import UTC, datetime

from app.analysis.grounding import GroundingValidator, RawClaim
from app.domain.enums import Dimension, Platform, Stance
from app.domain.models import Document, content_hash, document_id


def _doc(text: str) -> Document:
    url = "https://www.reddit.com/r/saas/comments/abc/thread/"
    return Document(
        id=document_id(Platform.REDDIT, url),
        content_hash=content_hash(text.lower()),
        platform=Platform.REDDIT,
        source_name="reddit",
        url=url,
        title="thread",
        text=text,
        retrieved_at=datetime.now(UTC),
        query="q",
        companies=["asana"],
    )


def test_paraphrased_quote_is_rejected() -> None:
    doc = _doc("Asana's mobile app is genuinely fast and rarely crashes on my phone.")
    raw = RawClaim(
        company_id="asana",
        company_name="Asana",
        dimension=Dimension.PERFORMANCE,
        statement="Users say the mobile app is reliable",
        stance=Stance.POSITIVE,
        quote="The mobile app never crashes and loads instantly",  # not a substring
        document_id=doc.id,
    )
    validator = GroundingValidator()
    claims, report = validator.validate_batch([raw], {doc.id: doc})

    assert claims == []
    assert report.claims_rejected == 1
    assert "not found verbatim" in report.rejections[0].reason


def test_smart_quote_and_whitespace_variant_is_accepted() -> None:
    doc = _doc('Support told me: "we don\'t   offer refunds after 30 days" which was frustrating.')
    raw = RawClaim(
        company_id="asana",
        company_name="Asana",
        dimension=Dimension.SUPPORT,
        statement="Support does not offer refunds after 30 days",
        stance=Stance.NEGATIVE,
        # curly quotes + collapsed whitespace vs the document's straight quotes/extra spaces
        quote='"we don’t offer refunds after 30 days"',
        document_id=doc.id,
    )
    validator = GroundingValidator()
    claims, report = validator.validate_batch([raw], {doc.id: doc})

    assert len(claims) == 1
    assert report.claims_accepted == 1
    evidence = claims[0].evidence[0]
    assert doc.text[evidence.char_start:evidence.char_end] in doc.text


def test_quote_too_short_is_rejected() -> None:
    doc = _doc("This is a reasonably long sentence about pricing being confusing for teams.")
    raw = RawClaim(
        company_id="asana",
        company_name="Asana",
        dimension=Dimension.PRICING,
        statement="Pricing is confusing",
        stance=Stance.NEGATIVE,
        quote="pricing",
        document_id=doc.id,
    )
    claims, report = GroundingValidator(min_quote_chars=25).validate_batch([raw], {doc.id: doc})

    assert claims == []
    assert report.claims_rejected == 1
