"""Per-run in-memory store that ingestion tools write into and the
deterministic analysis stages read from afterward.

Tools are bound to one `DocumentStore` instance per run (via the factory in
`tools.py`), rather than threaded through deepagents graph state -- this keeps
tool implementations simple synchronous/async functions instead of requiring
`Command`-based state updates, at the cost of the store not being visible to
`checkpointer` replay. Acceptable for this scope: the worker owns the store
for the run's lifetime and persists artifacts from it directly.
"""

from app.analysis.dedupe import merge_documents
from app.domain.models import Competitor, Document, SkippedSource


class DocumentStore:
    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}
        self.skipped: list[SkippedSource] = []
        self.intake_target: Competitor | None = None
        self.intake_competitors: list[Competitor] = []

    def add_documents(self, documents: list[Document]) -> tuple[int, int]:
        before = len(self._documents)
        combined = list(self._documents.values()) + documents
        merged = merge_documents(combined)
        self._documents = {d.id: d for d in merged}
        new_count = len(self._documents) - before
        duplicates = len(documents) - new_count
        return new_count, max(duplicates, 0)

    def add_skip(self, skip: SkippedSource) -> None:
        self.skipped.append(skip)

    def get(self, document_id: str) -> Document | None:
        return self._documents.get(document_id)

    def list_documents(
        self, company_id: str | None = None, platform: str | None = None, limit: int = 50
    ) -> list[Document]:
        docs = list(self._documents.values())
        if company_id:
            docs = [d for d in docs if company_id in d.companies]
        if platform:
            docs = [d for d in docs if d.platform == platform]
        return docs[:limit]

    def all(self) -> list[Document]:
        return list(self._documents.values())

    def record_intake(self, target: Competitor, competitors: list[Competitor]) -> None:
        self.intake_target = target
        self.intake_competitors = competitors
