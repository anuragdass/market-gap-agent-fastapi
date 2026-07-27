from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.domain.enums import Platform, SkipReason
from app.domain.models import Document, content_hash, document_id
from app.sources.base import make_skip
from app.sources.http import post_json
from app.sources.normalize import clean_text

SERPER_SEARCH_URL = "https://google.serper.dev/search"
SOURCE_NAME = "serper"


def _platform_for_domain(url: str) -> Platform:
    host = urlparse(url).netloc.lower()
    if "linkedin.com" in host:
        return Platform.LINKEDIN
    if "g2.com" in host or "capterra.com" in host:
        return Platform.G2
    if any(term in host for term in ("techcrunch", "news", "theverge", "reuters", "forbes")):
        return Platform.NEWS
    return Platform.WEB


async def search(query: str, company_id: str, limit: int = 10) -> tuple[list[Document], object | None]:
    settings = get_settings()
    if not settings.serper_api_key:
        return [], make_skip(SOURCE_NAME, query, SkipReason.NO_API_KEY, "SERPER_API_KEY not configured")

    result = await post_json(
        SERPER_SEARCH_URL,
        json_body={"q": query, "num": limit},
        headers={"X-API-KEY": settings.serper_api_key},
    )

    if result.error is not None:
        if isinstance(result.error, httpx.TimeoutException):
            return [], make_skip(SOURCE_NAME, query, SkipReason.TIMEOUT, str(result.error))
        return [], make_skip(SOURCE_NAME, query, SkipReason.UNREACHABLE, str(result.error))

    if result.status_code == 403:
        return [], make_skip(SOURCE_NAME, query, SkipReason.BLOCKED, "Serper returned 403", http_status=403)
    if result.status_code == 429:
        return [], make_skip(SOURCE_NAME, query, SkipReason.RATE_LIMITED, "Serper returned 429", http_status=429)
    if result.status_code is None or result.status_code >= 400:
        return [], make_skip(SOURCE_NAME, query, SkipReason.UNREACHABLE, f"HTTP {result.status_code}", http_status=result.status_code)

    try:
        organic = result.json_body["organic"]  # type: ignore[index]
    except (KeyError, TypeError):
        return [], make_skip(SOURCE_NAME, query, SkipReason.PARSE_ERROR, "unexpected Serper response shape")

    if not organic:
        return [], make_skip(SOURCE_NAME, query, SkipReason.EMPTY, "no results")

    documents = []
    for item in organic:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        text = clean_text(f"{title}. {snippet}".strip())
        if not text:
            continue
        url = item.get("link")
        if not url:
            continue
        platform = _platform_for_domain(url)
        documents.append(
            Document(
                id=document_id(platform, url),
                content_hash=content_hash(text.lower()),
                platform=platform,
                source_name=SOURCE_NAME,
                url=url,
                title=title or None,
                text=text,
                published_at=None,
                author=None,
                retrieved_at=datetime.now(UTC),
                query=query,
                companies=[company_id],
                score=None,
            )
        )

    if not documents:
        return [], make_skip(SOURCE_NAME, query, SkipReason.EMPTY, "no usable text in results")

    return documents, None
