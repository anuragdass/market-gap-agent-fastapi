"""Server-rendered UI: one page, a real HTML form, and the sample input
values for a "load sample" convenience. Results are shown by linking to the
existing JSON/markdown API endpoints -- no client-side markdown rendering.
"""

import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_SAMPLE_INPUT_PATH = Path(__file__).parent.parent.parent / "sample_input.json"


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    sample = json.loads(_SAMPLE_INPUT_PATH.read_text())
    return templates.TemplateResponse(request, "index.html", {"sample": sample})
