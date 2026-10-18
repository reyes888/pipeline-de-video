import json
import shutil
import threading
import uuid
from datetime import datetime, timezone

from backend.config import PROJECTS_DIR
from backend.models.project import Project, ProjectStage, ProjectSummary

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(project_id: str) -> threading.Lock:
    with _locks_guard:
        if project_id not in _locks:
            _locks[project_id] = threading.Lock()
        return _locks[project_id]


def _project_dir(project_id: str):
    return PROJECTS_DIR / project_id


def _project_json_path(project_id: str):
    return _project_dir(project_id) / "project.json"


def create_project(title: str, source_url: str | None = None, source_type: str = "url") -> Project:
    project_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    project = Project(
        id=project_id,
        title=title,
        source_type=source_type,
        source_url=source_url,
        created_at=now,
        updated_at=now,
        stage=ProjectStage.NUEVO,
    )
    project_dir = _project_dir(project_id)
    for sub in ("video", "audio", "transcripcion", "clips_finales"):
        (project_dir / sub).mkdir(parents=True, exist_ok=True)
    save_project(project)
    return project


def save_project(project: Project) -> None:
    lock = _lock_for(project.id)
    with lock:
        project.updated_at = datetime.now(timezone.utc)
        path = _project_json_path(project.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
        tmp_path.replace(path)


def get_project(project_id: str) -> Project | None:
    path = _project_json_path(project_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return Project.model_validate(data)


def update_project(project_id: str, **fields) -> Project:
    lock = _lock_for(project_id)
    with lock:
        path = _project_json_path(project_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        project = Project.model_validate(data)
        for key, value in fields.items():
            setattr(project, key, value)
        project.updated_at = datetime.now(timezone.utc)
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
        tmp_path.replace(path)
        return project


def list_projects() -> list[ProjectSummary]:
    summaries = []
    if not PROJECTS_DIR.exists():
        return summaries
    for entry in PROJECTS_DIR.iterdir():
        json_path = entry / "project.json"
        if not json_path.exists():
            continue
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            project = Project.model_validate(data)
        except (json.JSONDecodeError, OSError):
            continue
        summaries.append(
            ProjectSummary(
                id=project.id,
                title=project.title,
                stage=project.stage,
                updated_at=project.updated_at,
                error_message=project.error_message,
            )
        )
    summaries.sort(key=lambda p: p.updated_at, reverse=True)
    return summaries


def delete_project(project_id: str) -> bool:
    project_dir = _project_dir(project_id)
    if not project_dir.exists():
        return False
    shutil.rmtree(project_dir)
    with _locks_guard:
        _locks.pop(project_id, None)
    return True


# Etapas "en curso": si el servidor arranca y encuentra un proyecto así, es porque la app
# se cerró a mitad de un trabajo y ningún proceso lo está ejecutando realmente.
_RESUME_STAGE = {
    ProjectStage.DESCARGANDO: ProjectStage.NUEVO,
    ProjectStage.DESCARGADO: ProjectStage.NUEVO,
    ProjectStage.CONVIRTIENDO: ProjectStage.NUEVO,
    ProjectStage.EXTRAYENDO_AUDIO: ProjectStage.CONVERTIDO,
    ProjectStage.TRANSCRIBIENDO: ProjectStage.CONVERTIDO,
    ProjectStage.CORTANDO: ProjectStage.CLIPS_IMPORTADOS,
}


def recover_interrupted() -> list[Project]:
    """Devuelve a un estado estable los proyectos que quedaron 'en curso' por un cierre de la app."""
    recovered = []
    for summary in list_projects():
        target = _RESUME_STAGE.get(summary.stage)
        if target is None:
            continue
        recovered.append(update_project(summary.id, stage=target, error_message=None))
    return recovered
