import asyncio

from app.config import Settings, get_settings
from app.runs.store import RunStore, get_run_store

_run_semaphore: asyncio.Semaphore | None = None


def get_run_semaphore(settings: Settings | None = None) -> asyncio.Semaphore:
    global _run_semaphore
    if _run_semaphore is None:
        settings = settings or get_settings()
        _run_semaphore = asyncio.Semaphore(settings.max_concurrent_runs)
    return _run_semaphore


def get_deps() -> tuple[Settings, RunStore]:
    return get_settings(), get_run_store()
