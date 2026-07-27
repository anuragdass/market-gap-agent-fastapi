import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.domain.enums import RunStatus


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    from app.main import create_app

    return TestClient(create_app())


async def _fake_run_pipeline(run_id: str, **kwargs: object) -> dict:
    artifacts_dir = kwargs["settings"].artifacts_dir / run_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "competitive_brief.md").write_text("# Brief\n")
    (artifacts_dir / "evidence.json").write_text('{"claims": []}')
    return {"status": RunStatus.SUCCEEDED, "counts": {"documents": 1, "claims": 0, "pain_points": 0, "skipped_sources": 0}}


def test_create_run_and_poll_until_done(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.api.routes as routes

    monkeypatch.setattr(routes, "run_pipeline", _fake_run_pipeline)

    response = client.post(
        "/api/v1/runs",
        json={
            "company_name": "Notero",
            "company_description": "AI-native note-taking app for teams",
            "competitors": ["Notion", "Coda", "Airtable", "Slab"],
        },
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]

    async def _wait() -> None:
        for _ in range(50):
            status_response = client.get(f"/api/v1/runs/{run_id}")
            if status_response.json()["status"] in ("succeeded", "partial", "failed"):
                return
            await asyncio.sleep(0.05)

    asyncio.run(_wait())

    final = client.get(f"/api/v1/runs/{run_id}").json()
    assert final["status"] == "succeeded"
    assert "brief" in final["artifacts"]
    assert "evidence" in final["artifacts"]

    brief_response = client.get(f"/api/v1/runs/{run_id}/brief")
    assert brief_response.status_code == 200
    evidence_response = client.get(f"/api/v1/runs/{run_id}/evidence")
    assert evidence_response.status_code == 200


def test_unknown_run_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/runs/does-not-exist")
    assert response.status_code == 404


def test_healthz(client: TestClient) -> None:
    response = client.get("/api/v1/healthz")
    assert response.status_code == 200
