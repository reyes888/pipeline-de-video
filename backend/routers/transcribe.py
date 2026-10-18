from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.services import project_store
from backend.services.job_runner import is_running
from backend.services.transcriber import start_transcribe_job

router = APIRouter(prefix="/api/projects", tags=["transcribe"])


class TranscribeRequest(BaseModel):
    language: str = "es"
    model: str = "medium"


@router.post("/{project_id}/transcribe")
def transcribe_project(project_id: str, body: TranscribeRequest) -> dict:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado.")
    if not project.video_path:
        raise HTTPException(400, "Primero descarga el video.")
    if is_running(project_id, "transcribe"):
        raise HTTPException(409, "Ya hay una transcripción en curso para este proyecto.")
    start_transcribe_job(project_id, body.language, body.model)
    return {"started": True}


@router.get("/{project_id}/transcript/download")
def download_transcript(project_id: str, fmt: str) -> FileResponse:
    project = project_store.get_project(project_id)
    if project is None or project.transcript is None:
        raise HTTPException(404, "Transcripción no encontrada.")
    path_map = {
        "txt": project.transcript.txt_path,
        "srt": project.transcript.srt_path,
        "json": project.transcript.json_path,
    }
    path = path_map.get(fmt)
    if not path or not Path(path).exists():
        raise HTTPException(404, "Formato no disponible.")
    return FileResponse(path, filename=Path(path).name)
