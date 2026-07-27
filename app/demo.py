"""Runs the committed sample_input.json through the pipeline and writes
competitive_brief.md + evidence.json to artifacts/demo/.

Usage: `python -m app.demo` (requires ANTHROPIC_API_KEY or OPENAI_API_KEY;
SERPER_API_KEY is optional -- Hacker News is used as a keyless fallback).
"""

import asyncio
import json
import uuid
from pathlib import Path

from app.config import get_settings
from app.logging import configure_logging
from app.runs.worker import run_pipeline


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.debug)

    sample = json.loads((Path(__file__).parent.parent / "sample_input.json").read_text())
    run_id = f"demo-{uuid.uuid4().hex[:8]}"
    artifacts_dir = Path(__file__).parent.parent / "artifacts" / "demo"

    result = await run_pipeline(
        run_id=run_id,
        company_name=sample["company_name"],
        company_description=sample["company_description"],
        seed_competitors=sample["competitors"],
        settings=settings,
        artifacts_dir=artifacts_dir,
    )
    print(f"Run complete: {result}")
    print(f"Artifacts written to: {artifacts_dir}")


if __name__ == "__main__":
    asyncio.run(main())
