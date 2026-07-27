import asyncio
import json
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.api.deps import get_run_semaphore
from app.api.schemas import AnalysisRequest, RunCreatedResponse, RunStatusResponse
from app.config import get_settings
from app.domain.enums import RunStatus
from app.logging import get_logger
from app.runs.store import get_run_store
from app.runs.worker import run_pipeline

router = APIRouter()
logger = get_logger(__name__)


async def _execute(run_id: str, request: AnalysisRequest) -> None:
    settings = get_settings()
    run_store = get_run_store()
    semaphore = get_run_semaphore(settings)

    async with semaphore:
        await run_store.update(run_id, status=RunStatus.RUNNING, stage="ingesting")
        try:
            result = await asyncio.wait_for(
                run_pipeline(
                    run_id=run_id,
                    company_name=request.company_name,
                    company_description=request.company_description,
                    seed_competitors=request.competitors,
                    settings=settings,
                ),
                timeout=settings.run_timeout_seconds,
            )
            await run_store.update(
                run_id,
                status=result["status"],
                stage="done",
                counts=result["counts"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("run_failed", run_id=run_id, error=str(exc))
            await run_store.update(run_id, status=RunStatus.FAILED, stage="failed", error=str(exc))


@router.post("/runs", response_model=RunCreatedResponse, status_code=202)
async def create_run(request: AnalysisRequest) -> RunCreatedResponse:
    run_id = str(uuid.uuid4())
    run_store = get_run_store()
    await run_store.create(run_id)
    asyncio.create_task(_execute(run_id, request))
    return RunCreatedResponse(
        run_id=run_id,
        status=RunStatus.QUEUED,
        links={"status": f"/api/v1/runs/{run_id}", "brief": f"/api/v1/runs/{run_id}/brief", "evidence": f"/api/v1/runs/{run_id}/evidence"},
    )


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
async def get_run(run_id: str) -> RunStatusResponse:
    run_store = get_run_store()
    record = await run_store.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="unknown run_id")

    settings = get_settings()
    run_dir = settings.artifacts_dir / run_id
    artifacts = {}
    if (run_dir / "competitive_brief.md").exists():
        artifacts["brief"] = f"/api/v1/runs/{run_id}/brief"
    if (run_dir / "evidence.json").exists():
        artifacts["evidence"] = f"/api/v1/runs/{run_id}/evidence"

    return RunStatusResponse(
        run_id=record.run_id,
        status=record.status,
        stage=record.stage,
        counts=record.counts,
        error=record.error,
        artifacts=artifacts,
    )


@router.get("/runs")
async def list_runs() -> list[RunStatusResponse]:
    run_store = get_run_store()
    records = await run_store.list()
    return [
        RunStatusResponse(run_id=r.run_id, status=r.status, stage=r.stage, counts=r.counts, error=r.error)
        for r in records
    ]


@router.get("/runs/{run_id}/brief")
async def get_brief(run_id: str) -> FileResponse:
    settings = get_settings()
    path = settings.artifacts_dir / run_id / "competitive_brief.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="brief not available yet")
    return FileResponse(path, media_type="text/markdown")


@router.get("/runs/{run_id}/evidence")
async def get_evidence(run_id: str) -> JSONResponse:
    settings = get_settings()
    path = settings.artifacts_dir / run_id / "evidence.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="evidence not available yet")
    return JSONResponse(content=json.loads(path.read_text()))


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict[str, str]:
    settings = get_settings()
    key = settings.anthropic_api_key if settings.llm_provider == "anthropic" else settings.openai_api_key
    if not key:
        raise HTTPException(status_code=503, detail=f"no API key configured for provider {settings.llm_provider}")
    return {"status": "ready"}
