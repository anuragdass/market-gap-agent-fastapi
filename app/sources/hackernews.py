from datetime import UTC, datetime

import httpx

from app.domain.enums import Platform, SkipReason
from app.domain.models import Document, content_hash, document_id
from app.sources.base import make_skip
from app.sources.http import get_json
from app.sources.normalize import clean_text

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
SOURCE_NAME = "hackernews"


async def search(query: str, company_id: str, limit: int = 15) -> tuple[list[Document], object | None]:
    result = await get_json(
        HN_SEARCH_URL,
        params={"query": query, "tags": "(story,comment)", "hitsPerPage": limit},
    )

    if result.error is not None:
        if isinstance(result.error, httpx.TimeoutException):
            return [], make_skip(SOURCE_NAME, query, SkipReason.TIMEOUT, str(result.error))
        return [], make_skip(SOURCE_NAME, query, SkipReason.UNREACHABLE, str(result.error))

    if result.status_code == 403:
        return [], make_skip(SOURCE_NAME, query, SkipReason.BLOCKED, "HN Algolia returned 403", http_status=403)
    if result.status_code == 429:
        return [], make_skip(SOURCE_NAME, query, SkipReason.RATE_LIMITED, "HN Algolia returned 429", http_status=429)
    if result.status_code is None or result.status_code >= 400:
        return [], make_skip(SOURCE_NAME, query, SkipReason.UNREACHABLE, f"HTTP {result.status_code}", http_status=result.status_code)

    try:
        hits = result.json_body["hits"]  # type: ignore[index]
    except (KeyError, TypeError):
        return [], make_skip(SOURCE_NAME, query, SkipReason.PARSE_ERROR, "unexpected HN response shape")

    if not hits:
        return [], make_skip(SOURCE_NAME, query, SkipReason.EMPTY, "no results")

    documents = []
    for hit in hits:
        title = hit.get("title") or hit.get("story_title") or ""
        body = hit.get("comment_text") or ""
        text = clean_text(f"{title}. {body}".strip())
        if not text:
            continue
        object_id = hit.get("objectID")
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
        created_at = hit.get("created_at")
        published_at = None
        if created_at:
            try:
                published_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                published_at = None
        documents.append(
            Document(
                id=document_id(Platform.HACKERNEWS, url),
                content_hash=content_hash(text.lower()),
                platform=Platform.HACKERNEWS,
                source_name=SOURCE_NAME,
                url=url,
                title=title or None,
                text=text,
                published_at=published_at,
                author=hit.get("author"),
                retrieved_at=datetime.now(UTC),
                query=query,
                companies=[company_id],
                score=hit.get("points"),
            )
        )

    if not documents:
        return [], make_skip(SOURCE_NAME, query, SkipReason.EMPTY, "no usable text in results")

    return documents, None
