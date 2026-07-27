from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.config import get_settings
from app.db.session import init_db_schema
from app.logging import configure_logging
from app.web.routes import router as web_router

_STATIC_DIR = Path(__file__).parent / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    settings = get_settings()
    configure_logging(settings.debug)
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    await init_db_schema()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Market Gap Agent", lifespan=lifespan)
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(web_router)
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    return app


app = create_app()
