"""Tool factory: builds the ingestion/store tools bound to one run's
`DocumentStore`. Every tool returns a JSON-serializable summary and never
raises -- adapter failures already come back as a structured skip.

There is deliberately no `record_claim` tool: claims only ever enter the
system via `response_format` on the compiled `claim_extractor` subagent,
followed by `GroundingValidator`, giving one validation chokepoint.
"""

from typing import Any

from langchain_core.tools import BaseTool, tool

from app.agents.store import DocumentStore
from app.analysis.intake import make_competitor
from app.domain.enums import CompetitorStatus
from app.sources.registry import get_source


def _search_tool(source_name: str, store: DocumentStore) -> Any:
    source_fn = get_source(source_name)

    async def _run(query: str, company_id: str, limit: int = 10) -> dict[str, Any]:
        documents, skipped = await source_fn(query, company_id, limit)
        new_count, dup_count = store.add_documents(documents)
        if skipped is not None:
            store.add_skip(skipped)
        return {
            "query": query,
            "source": source_name,
            "document_ids": [d.id for d in documents],
            "new_documents": new_count,
            "duplicates_merged": dup_count,
            "skipped": skipped.model_dump(mode="json") if skipped else None,
        }

    return _run


def build_tools(store: DocumentStore) -> list[BaseTool]:
    search_reddit = tool(
        "search_reddit",
        description="Search Reddit's public JSON search endpoint for discussion mentioning a company.",
    )(_search_tool("reddit", store))

    search_serper = tool(
        "search_serper",
        description=(
            "Search the web via Serper.dev for reviews/news/LinkedIn/G2 snippets about a company. "
            "Returns a no_api_key skip if SERPER_API_KEY is not configured -- never fabricates results."
        ),
    )(_search_tool("serper", store))

    search_hackernews = tool(
        "search_hackernews",
        description="Search Hacker News (Algolia API) for stories/comments mentioning a company. Keyless fallback.",
    )(_search_tool("hackernews", store))

    @tool
    def list_documents(
        company_id: str | None = None, platform: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List documents already fetched this run, optionally filtered by company or platform."""
        docs = store.list_documents(company_id=company_id, platform=platform, limit=limit)
        return [
            {
                "document_id": d.id,
                "title": d.title,
                "url": str(d.url),
                "platform": d.platform.value,
                "text_excerpt": d.text[:300],
            }
            for d in docs
        ]

    @tool
    def get_document(document_id: str) -> dict[str, Any]:
        """Fetch the full cleaned text of a previously stored document by id."""
        doc = store.get(document_id)
        if doc is None:
            return {"error": "unknown_document_id"}
        return {"document_id": doc.id, "url": str(doc.url), "platform": doc.platform.value, "text": doc.text}

    @tool
    def record_intake(target: dict[str, Any], competitors: list[dict[str, Any]]) -> dict[str, Any]:
        """Record the resolved target company and competitor list.

        `target` and each entry in `competitors` need: name, domain (nullable),
        one_liner. This is re-validated deterministically (duplicate/domain
        collapse) -- the returned accepted/skipped split is authoritative.
        """
        from app.analysis.intake import resolve_intake
        from app.config import get_settings

        target_competitor = make_competitor(
            target["name"], target.get("domain"), target.get("one_liner", ""), is_target=True
        )
        proposed = [
            make_competitor(c["name"], c.get("domain"), c.get("one_liner", ""))
            for c in competitors
        ]
        settings = get_settings()
        _, resolved, meets_minimum = resolve_intake(target_competitor, proposed, settings.min_competitors)
        store.record_intake(target_competitor, resolved)
        return {
            "target": target_competitor.model_dump(mode="json"),
            "accepted": [c.model_dump(mode="json") for c in resolved if c.status == CompetitorStatus.ACCEPTED],
            "skipped": [c.model_dump(mode="json") for c in resolved if c.status != CompetitorStatus.ACCEPTED],
            "meets_minimum": meets_minimum,
        }

    return [search_reddit, search_serper, search_hackernews, list_documents, get_document, record_intake]
