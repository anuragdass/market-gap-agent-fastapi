from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel

from app.domain.enums import SkipReason
from app.domain.models import Document, SkippedSource


class DocumentPreview(BaseModel):
    document_id: str
    title: str | None
    url: str
    platform: str
    text_excerpt: str


class SearchToolResult(BaseModel):
    query: str
    source: str
    document_ids: list[str] = []
    new_documents: int = 0
    duplicates_merged: int = 0
    skipped: SkippedSource | None = None


def make_skip(
    source_name: str, query: str, reason: SkipReason, detail: str, http_status: int | None = None
) -> SkippedSource:
    return SkippedSource(
        source_name=source_name,
        query=query,
        reason=reason,
        detail=detail,
        http_status=http_status,
        occurred_at=datetime.now(UTC),
    )


class SourceAdapter(Protocol):
    name: str

    async def search(self, query: str, limit: int) -> tuple[list[Document], SkippedSource | None]:
        ...
