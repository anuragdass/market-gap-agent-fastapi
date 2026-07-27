"""Run registry backed by Postgres (via SQLAlchemy async) in production,
SQLite in bare/local/test runs -- see `app/db/session.py`. Schema is owned by
Alembic migrations (`migrations/`), not by this module.

Change notification for SSE is a per-run, in-process `asyncio.Condition`:
`update()` wakes any subscriber immediately instead of the subscriber
polling on an interval. This is process-local -- a multi-replica deployment
would need Postgres LISTEN/NOTIFY or a pub/sub broker instead, noted as a
scaling limitation for this scope.
"""

import asyncio
import contextlib
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select

from app.db.models import Run
from app.db.session import get_session_factory
from app.domain.enums import RunStatus


class RunRecord(BaseModel):
    run_id: str
    status: RunStatus = RunStatus.QUEUED
    stage: str = "queued"
    created_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
    counts: dict[str, int] = {}

    @classmethod
    def from_orm_row(cls, row: Run) -> "RunRecord":
        return cls(
            run_id=row.run_id,
            status=RunStatus(row.status),
            stage=row.stage,
            created_at=row.created_at,
            finished_at=row.finished_at,
            error=row.error,
            counts=row.counts or {},
        )


class RunStore:
    def __init__(self) -> None:
        self._conditions: dict[str, asyncio.Condition] = {}

    async def create(self, run_id: str) -> RunRecord:
        record = RunRecord(run_id=run_id, created_at=datetime.now(UTC))
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                Run(
                    run_id=record.run_id,
                    status=record.status.value,
                    stage=record.stage,
                    created_at=record.created_at,
                    counts=record.counts,
                )
            )
            await session.commit()
        self._conditions[run_id] = asyncio.Condition()
        return record

    async def update(self, run_id: str, **fields: object) -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            row = await session.get(Run, run_id)
            if row is None:
                raise KeyError(run_id)
            for key, value in fields.items():
                if key == "status" and isinstance(value, RunStatus):
                    value = value.value
                setattr(row, key, value)
            await session.commit()

        condition = self._conditions.setdefault(run_id, asyncio.Condition())
        async with condition:
            condition.notify_all()

    async def get(self, run_id: str) -> RunRecord | None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            row = await session.get(Run, run_id)
            return RunRecord.from_orm_row(row) if row else None

    async def list(self) -> list[RunRecord]:
        session_factory = get_session_factory()
        async with session_factory() as session:
            rows = (await session.execute(select(Run).order_by(Run.created_at.desc()))).scalars().all()
            return [RunRecord.from_orm_row(row) for row in rows]

    async def wait_for_change(self, run_id: str, timeout: float) -> RunRecord | None:
        """Block until `update()` fires for this run or the timeout elapses.

        The timeout is a heartbeat interval, not an error condition.
        """
        condition = self._conditions.get(run_id)
        if condition is not None:
            async with condition:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(condition.wait(), timeout=timeout)
        return await self.get(run_id)


_run_store = RunStore()


def get_run_store() -> RunStore:
    return _run_store
