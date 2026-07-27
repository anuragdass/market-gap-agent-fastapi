import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Block real network calls in every test unless a test opts in with `respx`.

    `respx` patches httpx transports directly, so tests using the `respx_mock`
    fixture (or `respx.mock` decorator) are unaffected by this guard.
    """
    if "respx_mock" in request.fixturenames:
        return

    import httpx

    async def _blocked_send(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("network disabled in tests -- use respx to mock httpx calls")

    monkeypatch.setattr(httpx.AsyncClient, "send", _blocked_send)
