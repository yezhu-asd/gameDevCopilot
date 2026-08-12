"""GameDevCopilot web routes."""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from core import config
from web.jobs import job_store

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

# Where generated games are written. Sanitize the spec into a folder name.
OUTPUTS_DIR = config.PROJECT_ROOT / "outputs"


def _slugify(text: str) -> str:
    import re
    cleaned = re.sub(r"[^\w一-鿿]+", "_", text).strip("_")
    return cleaned[:24] or "game"


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@router.post("/api/generate")
async def generate(request: Request):
    body = await request.json()
    spec = (body.get("spec") or "").strip()
    if not spec:
        return JSONResponse({"error": "请输入游戏描述"}, status_code=400)

    job = job_store.create(spec)
    out_dir = OUTPUTS_DIR / _slugify(spec)

    def _run():
        try:
            from core.pipeline import run_pipeline

            run_pipeline(spec, out_dir, on_progress=job_store.on_progress(job))
        except Exception as exc:  # noqa: BLE001
            logger.exception("job %s failed", job.id)
            job_store.mark_error(job, str(exc))

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"job_id": job.id, "output_dir": str(out_dir)})


@router.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    job = job_store.get(job_id)
    if job is None:
        return JSONResponse({"error": "job not found"}, status_code=404)
    return JSONResponse(job.to_dict())


@router.get("/api/jobs/{job_id}/files")
async def job_files(job_id: str):
    job = job_store.get(job_id)
    if job is None:
        return JSONResponse({"error": "job not found"}, status_code=404)
    if not job.final_dir or not Path(job.final_dir).exists():
        return JSONResponse({"files": [], "dir": None})

    base = Path(job.final_dir)
    files = []
    for p in sorted(base.rglob("*")):
        if p.is_file() and ".godot" not in p.parts and p.suffix in {".gd", ".tscn", ".godot"}:
            rel = p.relative_to(base).as_posix()
            files.append({
                "path": rel,
                "content": p.read_text(encoding="utf-8", errors="replace"),
            })
    return JSONResponse({"files": files, "dir": str(base)})
