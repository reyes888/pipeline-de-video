from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.models.project import Project, ProjectSummary
from backend.services import project_store
from backend.utils.platform import open_folder as open_in_file_manager
from backend.ws.manager import manager
from backend.services.uploader import save_uploaded_file, start_upload_processing_job

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectsRequest(BaseModel):
    urls: list[str]


class UpdateProjectRequest(BaseModel):
    title: str | None = None


@router.get("", response_model=list[ProjectSummary])
def list_projects() -> list[ProjectSummary]:
    summaries = project_store.list_projects()
    for item in summaries:
        live = manager.live_progress(item.id)
        if live:
            item.progress = live["percent"]
            item.progress_detail = live["detail"]
    return summaries


@router.post("", response_model=list[Project])
def create_projects(body: CreateProjectsRequest) -> list[Project]:
    urls = [u.strip() for u in body.urls if u.strip()]
    if not urls:
        raise HTTPException(400, "Pega al menos un link.")
    created = []
    for url in urls:
        project = project_store.create_project(title=url, source_url=url)
        created.append(project)
    return created


@router.post("/upload", response_model=list[Project])
def upload_projects(files: list[UploadFile] = File(...)) -> list[Project]:
    if not files:
        raise HTTPException(400, "Sube al menos un archivo.")
    created = []
    for f in files:
        title = Path(f.filename or "video").stem
        project = project_store.create_project(title=title, source_type="upload")
        filepath = save_uploaded_file(project.id, f.filename or "video.mp4", f.file)
        start_upload_processing_job(project.id, filepath)
        created.append(project_store.get_project(project.id))
    return created


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str) -> Project:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado.")
    return project


@router.patch("/{project_id}", response_model=Project)
def update_project(project_id: str, body: UpdateProjectRequest) -> Project:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado.")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    return project_store.update_project(project_id, **fields)


@router.delete("/{project_id}")
def delete_project(project_id: str) -> dict:
    ok = project_store.delete_project(project_id)
    if not ok:
        raise HTTPException(404, "Proyecto no encontrado.")
    return {"deleted": True}


@router.post("/{project_id}/open-folder")
def open_folder(project_id: str) -> dict:
    from backend.config import PROJECTS_DIR

    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado.")
    folder = PROJECTS_DIR / project_id
    folder.mkdir(parents=True, exist_ok=True)
    open_in_file_manager(folder)
    return {"opened": str(folder)}
