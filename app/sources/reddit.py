from datetime import UTC, datetime

import httpx

from app.domain.enums import Platform, SkipReason
from app.domain.models import Document, SkippedSource, content_hash, document_id
from app.sources.base import make_skip
from app.sources.http import get_json
from app.sources.normalize import clean_text

REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
SOURCE_NAME = "reddit"


async def search(query: str, company_id: str, limit: int = 15) -> tuple[list[Document], SkippedSource | None]:
    result = await get_json(
        REDDIT_SEARCH_URL,
        params={"q": query, "limit": limit, "sort": "relevance"},
    )

    if result.error is not None:
        if isinstance(result.error, httpx.TimeoutException):
            return [], make_skip(SOURCE_NAME, query, SkipReason.TIMEOUT, str(result.error))
        return [], make_skip(SOURCE_NAME, query, SkipReason.UNREACHABLE, str(result.error))

    if result.status_code == 403:
        return [], make_skip(SOURCE_NAME, query, SkipReason.BLOCKED, "Reddit returned 403", http_status=403)
    if result.status_code == 429:
        return [], make_skip(SOURCE_NAME, query, SkipReason.RATE_LIMITED, "Reddit returned 429", http_status=429)
    if result.status_code is None or result.status_code >= 400:
        return [], make_skip(
            SOURCE_NAME, query, SkipReason.UNREACHABLE, f"HTTP {result.status_code}", http_status=result.status_code
        )

    try:
        children = result.json_body["data"]["children"]  # type: ignore[index]
    except (KeyError, TypeError):
        return [], make_skip(SOURCE_NAME, query, SkipReason.PARSE_ERROR, "unexpected Reddit response shape")

    if not children:
        return [], make_skip(SOURCE_NAME, query, SkipReason.EMPTY, "no results")

    documents = []
    for child in children:
        post = child.get("data", {})
        title = post.get("title", "")
        body = post.get("selftext", "")
        text = clean_text(f"{title}. {body}".strip())
        if not text:
            continue
        permalink = post.get("permalink", "")
        url = f"https://www.reddit.com{permalink}"
        created_utc = post.get("created_utc")
        published_at = datetime.fromtimestamp(created_utc, tz=UTC) if created_utc else None
        documents.append(
            Document(
                id=document_id(Platform.REDDIT, url),
                content_hash=content_hash(text.lower()),
                platform=Platform.REDDIT,
                source_name=SOURCE_NAME,
                url=url,
                title=title or None,
                text=text,
                published_at=published_at,
                author=post.get("author"),
                retrieved_at=datetime.now(UTC),
                query=query,
                companies=[company_id],
                score=post.get("score"),
            )
        )

    if not documents:
        return [], make_skip(SOURCE_NAME, query, SkipReason.EMPTY, "no usable text in results")

    return documents, None
