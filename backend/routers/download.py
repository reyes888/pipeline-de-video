from fastapi import APIRouter, HTTPException

from backend.services import project_store
from backend.services.downloader import start_download_job
from backend.services.job_runner import is_running

router = APIRouter(prefix="/api/projects", tags=["download"])


@router.post("/{project_id}/download")
def download_project(project_id: str) -> dict:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado.")
    if is_running(project_id, "download"):
        raise HTTPException(409, "Ya hay una descarga en curso para este proyecto.")
    start_download_job(project_id)
    return {"started": True}
