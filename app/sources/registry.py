from collections.abc import Awaitable, Callable

from app.domain.models import Document, SkippedSource
from app.sources import hackernews, reddit, serper

SourceFn = Callable[[str, str, int], Awaitable[tuple[list[Document], SkippedSource | None]]]

_REGISTRY: dict[str, SourceFn] = {
    "reddit": reddit.search,
    "serper": serper.search,
    "hackernews": hackernews.search,
}

REQUIRED_SOURCE = "reddit"
FALLBACK_SOURCE = "hackernews"


def get_source(name: str) -> SourceFn:
    return _REGISTRY[name]


def available_sources() -> list[str]:
    return list(_REGISTRY.keys())


def register_source(name: str, fn: SourceFn) -> None:
    """Register or override a source adapter, e.g. for tests or new platforms."""
    _REGISTRY[name] = fn
