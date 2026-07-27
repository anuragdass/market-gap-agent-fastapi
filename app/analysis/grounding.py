"""Anti-hallucination control: every claim's quote must be a verbatim substring
of the exact document it was extracted from. No fuzzy matching, no embedding
similarity -- a similarity threshold is exactly how a paraphrase sneaks in.
"""

import unicodedata
from dataclasses import dataclass

from pydantic import BaseModel

from app.domain.enums import Dimension, Stance
from app.domain.models import Claim, Document, Evidence, GroundingRejection, GroundingReport, claim_id

_QUOTE_CHAR_MAP = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...",
}


def _norm_with_index(text: str) -> tuple[str, list[int]]:
    """Normalize text for comparison, tracking the original offset of each output char."""
    mapped = "".join(_QUOTE_CHAR_MAP.get(ch, ch) for ch in text)
    normalized_chars: list[str] = []
    index_map: list[int] = []
    prev_was_space = True  # collapse leading whitespace too
    for i, ch in enumerate(mapped):
        nfkc = unicodedata.normalize("NFKC", ch)
        for out_ch in nfkc:
            if out_ch.isspace():
                if prev_was_space:
                    continue
                normalized_chars.append(" ")
                index_map.append(i)
                prev_was_space = True
            else:
                normalized_chars.append(out_ch.casefold())
                index_map.append(i)
                prev_was_space = False
    norm = "".join(normalized_chars).strip()
    # strip() may drop leading/trailing entries; recompute index_map to match norm length
    lstripped = "".join(normalized_chars)
    lead_trim = len(lstripped) - len(lstripped.lstrip())
    trail_trim = len(lstripped) - len(lstripped.rstrip())
    trimmed_index_map = index_map[lead_trim: len(index_map) - trail_trim] if trail_trim else index_map[lead_trim:]
    return norm, trimmed_index_map


@dataclass
class QuoteMatch:
    char_start: int
    char_end: int


def verify_quote(quote: str, document: Document) -> QuoteMatch | None:
    # Tier A: exact substring match.
    idx = document.text.find(quote)
    if idx != -1:
        return QuoteMatch(char_start=idx, char_end=idx + len(quote))

    # Tier B: normalized-whitespace / smart-quote tolerant match.
    norm_quote, _ = _norm_with_index(quote)
    norm_doc, doc_index_map = _norm_with_index(document.text)
    norm_idx = norm_doc.find(norm_quote)
    if norm_idx == -1 or not norm_quote:
        return None

    start = doc_index_map[norm_idx]
    end_pos = norm_idx + len(norm_quote) - 1
    end = doc_index_map[end_pos] + 1 if end_pos < len(doc_index_map) else doc_index_map[-1] + 1
    return QuoteMatch(char_start=start, char_end=min(end, len(document.text)))


class RawClaim(BaseModel):
    company_id: str
    company_name: str
    dimension: Dimension
    statement: str
    stance: Stance
    quote: str
    document_id: str


class GroundingValidator:
    def __init__(self, min_quote_chars: int = 25, max_quote_chars: int = 600) -> None:
        self.min_quote_chars = min_quote_chars
        self.max_quote_chars = max_quote_chars

    def validate_batch(
        self, raws: list[RawClaim], doc_index: dict[str, Document]
    ) -> tuple[list[Claim], GroundingReport]:
        accepted: list[Claim] = []
        rejections: list[GroundingRejection] = []

        for raw in raws:
            rejection_reason = self._reject_reason(raw, doc_index)
            if rejection_reason is not None:
                rejections.append(
                    GroundingRejection(
                        claim_statement=raw.statement,
                        quote=raw.quote,
                        document_id=raw.document_id,
                        reason=rejection_reason,
                    )
                )
                continue

            document = doc_index[raw.document_id]
            match = verify_quote(raw.quote, document)
            if match is None:
                rejections.append(
                    GroundingRejection(
                        claim_statement=raw.statement,
                        quote=raw.quote,
                        document_id=raw.document_id,
                        reason="quote not found verbatim in the source document",
                    )
                )
                continue

            evidence = Evidence(
                document_id=document.id,
                url=document.url,
                platform=document.platform,
                source_name=document.source_name,
                quote=raw.quote,
                char_start=match.char_start,
                char_end=match.char_end,
                published_at=document.published_at,
                author=document.author,
                verified=True,
            )
            normalized_statement = raw.statement.strip().lower()
            accepted.append(
                Claim(
                    id=claim_id(raw.company_id, raw.dimension, normalized_statement, raw.stance),
                    company_id=raw.company_id,
                    company_name=raw.company_name,
                    dimension=raw.dimension,
                    statement=raw.statement,
                    stance=raw.stance,
                    evidence=[evidence],
                    confidence=0.5,
                )
            )

        report = GroundingReport(
            claims_proposed=len(raws),
            claims_accepted=len(accepted),
            claims_rejected=len(rejections),
            rejections=rejections,
        )
        return accepted, report

    def _reject_reason(self, raw: RawClaim, doc_index: dict[str, Document]) -> str | None:
        if raw.document_id not in doc_index:
            return "referenced document was not fetched in this run"
        if len(raw.quote) < self.min_quote_chars:
            return f"quote shorter than {self.min_quote_chars} characters"
        if len(raw.quote) > self.max_quote_chars:
            return f"quote longer than {self.max_quote_chars} characters"
        return None
