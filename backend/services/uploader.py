import shutil
from pathlib import Path

from backend.config import PROJECTS_DIR
from backend.services.job_runner import make_reporter, run_in_background
from backend.services.video_prep import finalize_video


def save_uploaded_file(project_id: str, filename: str, file_obj) -> Path:
    """Guarda un archivo subido dentro de data/projects/<id>/video/.
    Sanea el nombre (solo el basename) para evitar path traversal."""
    safe_name = Path(filename).name or "video.mp4"
    dest_dir = PROJECTS_DIR / project_id / "video"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / safe_name
    with open(dest_path, "wb") as out:
        shutil.copyfileobj(file_obj, out)
    return dest_path


def _do_prepare_uploaded_video(project_id: str, filepath: Path) -> None:
    report = make_reporter(project_id, "download")
    report("log", None, {"level": "info", "message": f"Video subido: {filepath.name}"})
    finalize_video(project_id, filepath, report, job_stage="download")


def start_upload_processing_job(project_id: str, filepath: Path) -> None:
    run_in_background(project_id, "download", lambda: _do_prepare_uploaded_video(project_id, filepath))
