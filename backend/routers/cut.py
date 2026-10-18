from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.config import PROJECTS_DIR
from backend.services import project_store
from backend.services.cutter import start_cut_job
from backend.services.job_runner import is_running
from backend.utils.ffmpeg import get_duration

router = APIRouter(prefix="/api/projects", tags=["cut"])


class CutRequest(BaseModel):
    vertical_9_16: bool = False


@router.post("/{project_id}/cut")
def cut_project(project_id: str, body: CutRequest) -> dict:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado.")
    if not any(c.selected for c in project.clips):
        raise HTTPException(400, "Selecciona al menos un clip.")
    if is_running(project_id, "cut"):
        raise HTTPException(409, "Ya hay un corte en curso para este proyecto.")
    start_cut_job(project_id, body.vertical_9_16)
    return {"started": True}


@router.get("/{project_id}/clips_finales")
def list_final_clips(project_id: str) -> list[dict]:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado.")
    out_dir = PROJECTS_DIR / project_id / "clips_finales"
    if not out_dir.exists():
        return []
    files = []
    for f in sorted(out_dir.glob("*.mp4")):
        files.append({"filename": f.name, "duration": get_duration(f)})
    return files


@router.get("/{project_id}/clips_finales/{filename}")
def get_final_clip(project_id: str, filename: str) -> FileResponse:
    out_dir = PROJECTS_DIR / project_id / "clips_finales"
    path = (out_dir / filename).resolve()
    if not str(path).startswith(str(out_dir.resolve())) or not path.exists():
        raise HTTPException(404, "Clip no encontrado.")
    return FileResponse(path, media_type="video/mp4")
