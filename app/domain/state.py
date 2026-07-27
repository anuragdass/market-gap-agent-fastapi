import operator
from typing import Annotated, Any, NotRequired

from deepagents.graph import DeepAgentState

from app.domain.models import Claim, Competitor, Document, PainPoint, SkippedSource


def _merge_by_id(existing: list[Any] | None, new: list[Any] | None) -> list[Any]:
    existing = existing or []
    new = new or []
    by_id: dict[str, Any] = {item["id"] if isinstance(item, dict) else item.id: item for item in existing}
    for item in new:
        key = item["id"] if isinstance(item, dict) else item.id
        by_id[key] = item
    return list(by_id.values())


class MarketGapState(DeepAgentState):
    """Custom deepagents state carrying the run's accumulated evidence."""

    run_id: NotRequired[str]
    target: NotRequired[Competitor | None]
    competitors: NotRequired[list[Competitor]]
    documents: NotRequired[Annotated[list[Document], _merge_by_id]]
    claims: NotRequired[Annotated[list[Claim], _merge_by_id]]
    pain_points: NotRequired[Annotated[list[PainPoint], _merge_by_id]]
    skipped_sources: NotRequired[Annotated[list[SkippedSource], operator.add]]
