"""In-process run registry. Wiped on restart -- intentional for this scope;
a durable store (Redis/Postgres) is the noted production upgrade.
"""

import asyncio
from datetime import UTC, datetime

from pydantic import BaseModel

from app.domain.enums import RunStatus


class RunRecord(BaseModel):
    run_id: str
    status: RunStatus = RunStatus.QUEUED
    stage: str = "queued"
    created_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
    counts: dict[str, int] = {}


class RunStore:
    def __init__(self) -> None:
        self._records: dict[str, RunRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, run_id: str) -> RunRecord:
        record = RunRecord(run_id=run_id, created_at=datetime.now(UTC))
        async with self._lock:
            self._records[run_id] = record
        return record

    async def update(self, run_id: str, **fields: object) -> None:
        async with self._lock:
            record = self._records[run_id]
            self._records[run_id] = record.model_copy(update=fields)

    async def get(self, run_id: str) -> RunRecord | None:
        async with self._lock:
            return self._records.get(run_id)

    async def list(self) -> list[RunRecord]:
        async with self._lock:
            return list(self._records.values())


_run_store = RunStore()


def get_run_store() -> RunStore:
    return _run_store
