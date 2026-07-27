import asyncio

import httpx

USER_AGENT = "market-gap-agent/0.1 (competitive research bot; contact: research@example.com)"

_DEFAULT_TIMEOUT = httpx.Timeout(8.0)


class HttpResult:
    def __init__(
        self, status_code: int | None, json_body: object | None = None, error: Exception | None = None
    ) -> None:
        self.status_code = status_code
        self.json_body = json_body
        self.error = error


async def get_json(
    url: str,
    params: dict[str, str | int] | None = None,
    headers: dict[str, str] | None = None,
    retry_on_429: bool = True,
) -> HttpResult:
    merged_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            response = await client.get(url, params=params, headers=merged_headers)
            if response.status_code == 429 and retry_on_429:
                await asyncio.sleep(1.5)
                response = await client.get(url, params=params, headers=merged_headers)
            if response.status_code >= 400:
                return HttpResult(status_code=response.status_code)
            return HttpResult(status_code=response.status_code, json_body=response.json())
    except httpx.TimeoutException as exc:
        return HttpResult(status_code=None, error=exc)
    except httpx.HTTPError as exc:
        return HttpResult(status_code=None, error=exc)


async def post_json(url: str, json_body: dict[str, object], headers: dict[str, str] | None = None) -> HttpResult:
    merged_headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json", **(headers or {})}
    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            response = await client.post(url, json=json_body, headers=merged_headers)
            if response.status_code >= 400:
                return HttpResult(status_code=response.status_code)
            return HttpResult(status_code=response.status_code, json_body=response.json())
    except httpx.TimeoutException as exc:
        return HttpResult(status_code=None, error=exc)
    except httpx.HTTPError as exc:
        return HttpResult(status_code=None, error=exc)
