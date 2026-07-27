"""Required test: unreachable, blocked, rate-limited, and empty sources are
skipped with a logged reason -- never a crash, never fabricated documents.
"""

import httpx
import pytest
import respx

from app.domain.enums import SkipReason
from app.sources import hackernews, reddit, serper
from app.sources.reddit import REDDIT_SEARCH_URL


@pytest.mark.parametrize(
    "mock_kwargs,expected_reason",
    [
        ({"side_effect": httpx.ConnectError("boom")}, SkipReason.UNREACHABLE),
        ({"return_value": httpx.Response(403, text="blocked")}, SkipReason.BLOCKED),
        ({"return_value": httpx.Response(429)}, SkipReason.RATE_LIMITED),
        ({"return_value": httpx.Response(200, json={"data": {"children": []}})}, SkipReason.EMPTY),
    ],
)
async def test_reddit_failure_modes(respx_mock: respx.MockRouter, mock_kwargs: dict, expected_reason: SkipReason) -> None:
    respx_mock.get(REDDIT_SEARCH_URL).mock(**mock_kwargs)

    documents, skipped = await reddit.search("project management complaints", "asana")

    assert documents == []
    assert skipped is not None
    assert skipped.reason == expected_reason


async def test_hackernews_unreachable(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(hackernews.HN_SEARCH_URL).mock(side_effect=httpx.ConnectError("down"))

    documents, skipped = await hackernews.search("clickup pricing", "clickup")

    assert documents == []
    assert skipped is not None
    assert skipped.reason == SkipReason.UNREACHABLE


async def test_serper_missing_api_key_skips_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("SERPER_API_KEY", "")

    documents, skipped = await serper.search("monday.com reviews", "monday")

    assert documents == []
    assert skipped is not None
    assert skipped.reason == SkipReason.NO_API_KEY
    config.get_settings.cache_clear()


async def test_serper_blocked(respx_mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("SERPER_API_KEY", "test-key")
    respx_mock.post(serper.SERPER_SEARCH_URL).mock(return_value=httpx.Response(403))

    documents, skipped = await serper.search("notion reviews", "notion")

    assert documents == []
    assert skipped is not None
    assert skipped.reason == SkipReason.BLOCKED
    config.get_settings.cache_clear()
