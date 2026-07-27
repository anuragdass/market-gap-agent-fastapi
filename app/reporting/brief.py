"""Renders competitive_brief.md. Comparison tables, gap list, conflicts, and
the references/citation index are template-generated from already-grounded
data -- never LLM-generated -- so citation integrity here is 100% by
construction, not by hope.
"""

import os
import re
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.domain.enums import CompetitorStatus
from app.domain.models import EvidenceBundle

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), trim_blocks=True, lstrip_blocks=True)


def _build_citation_index(bundle: EvidenceBundle) -> dict[str, int]:
    index: dict[str, int] = {}
    for claim in bundle.claims:
        for e in claim.evidence:
            key = f"{e.document_id}|{e.quote}"
            if key not in index:
                index[key] = len(index) + 1
    for pp in bundle.pain_points:
        for e in pp.evidence:
            key = f"{e.document_id}|{e.quote}"
            if key not in index:
                index[key] = len(index) + 1
    return index


def _cited_quotes(evidence: list, citation_index: dict[str, int]) -> str:
    parts = [f'"{e.quote}" [{citation_index[f"{e.document_id}|{e.quote}"]}]' for e in evidence]
    return "; ".join(parts)


def _build_conflict_views(bundle: EvidenceBundle, citation_index: dict[str, int]) -> list[dict]:
    views = []
    for conflict in bundle.conflicts:
        views.append(
            {
                "subject": conflict.subject,
                "positions": [
                    {"stance": p.stance.value, "quotes": _cited_quotes(p.evidence, citation_index)}
                    for p in conflict.positions
                ],
            }
        )
    return views


def _build_pain_point_views(bundle: EvidenceBundle, citation_index: dict[str, int]) -> list[dict]:
    views = []
    for pp in bundle.pain_points:
        views.append(
            {
                "label": pp.label,
                "description": pp.description,
                "scope": pp.scope.value,
                "company_ids": pp.company_ids,
                "platforms": [p.value for p in pp.platforms],
                "quotes": _cited_quotes(pp.evidence, citation_index),
            }
        )
    return views


def _build_comparison_matrix(bundle: EvidenceBundle, citation_index: dict[str, int]) -> dict[str, list[dict]]:
    matrix: dict[str, list[dict]] = {}
    for claim in bundle.claims:
        rows = matrix.setdefault(claim.dimension.value, [])
        citation_indices = [citation_index[f"{e.document_id}|{e.quote}"] for e in claim.evidence]
        rows.append(
            {
                "company_name": claim.company_name,
                "stance": claim.stance.value,
                "statement": claim.statement,
                "citation_indices": citation_indices,
            }
        )
    return matrix


def _references_section(bundle: EvidenceBundle, citation_index: dict[str, int]) -> str:
    doc_by_id = {d["id"]: d for d in bundle.sources["documents"]}
    lines = ["## References", ""]
    for key, idx in sorted(citation_index.items(), key=lambda kv: kv[1]):
        document_id, quote = key.split("|", 1)
        doc = doc_by_id.get(document_id, {})
        url = doc.get("url", "unknown")
        platform = doc.get("platform", "unknown")
        lines.append(f'[{idx}] {platform} -- {url} -- "{quote}"')
    return "\n".join(lines) + "\n"


def render_brief(bundle: EvidenceBundle, narrative_markdown: str | None = None) -> str:
    citation_index = _build_citation_index(bundle)
    comparison_matrix = _build_comparison_matrix(bundle, citation_index)
    accepted = [c for c in bundle.competitors if c.status == CompetitorStatus.ACCEPTED and not c.is_target]
    skipped = [c for c in bundle.competitors if c.status != CompetitorStatus.ACCEPTED]
    conflict_views = _build_conflict_views(bundle, citation_index)
    pain_point_views = _build_pain_point_views(bundle, citation_index)

    template = _env.get_template("brief.md.j2")
    rendered = template.render(
        target=bundle.target,
        accepted_competitors=accepted,
        skipped_competitors=skipped,
        comparison_matrix=comparison_matrix,
        conflicts=conflict_views,
        pain_points=pain_point_views,
        gaps=bundle.gaps,
        grounding=bundle.grounding,
        skipped_sources=bundle.sources.get("skipped", []),
        citation_index=citation_index,
        run_id=bundle.run_id,
        generated_at=bundle.generated_at.isoformat(),
    )

    if narrative_markdown:
        rendered = _splice_narrative(rendered, narrative_markdown, citation_index)

    rendered += "\n" + _references_section(bundle, citation_index)
    return rendered


def _splice_narrative(template_markdown: str, narrative_markdown: str, citation_index: dict[str, int]) -> str:
    """Insert an optional LLM-written narrative section, stripping any
    citation marker that doesn't correspond to a real entry in the index --
    a dangling citation is worse than no citation.
    """
    valid_indices = set(citation_index.values())

    def _strip_dangling(match: re.Match) -> str:
        n = int(match.group(1))
        return match.group(0) if n in valid_indices else ""

    cleaned = re.sub(r"\[(\d+)\]", _strip_dangling, narrative_markdown)
    return f"{cleaned}\n\n{template_markdown}"


def write_brief(markdown: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(markdown)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
