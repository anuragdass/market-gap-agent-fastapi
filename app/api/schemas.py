from pydantic import BaseModel, Field

from app.domain.enums import RunStatus


class AnalysisRequest(BaseModel):
    company_name: str
    company_description: str
    competitors: list[str] = Field(min_length=3, max_length=8)


class RunCreatedResponse(BaseModel):
    run_id: str
    status: RunStatus
    links: dict[str, str]


class RunStatusResponse(BaseModel):
    run_id: str
    status: RunStatus
    stage: str
    progress: float
    counts: dict[str, int]
    error: str | None = None
    artifacts: dict[str, str] = {}
