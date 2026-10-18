import subprocess
from pathlib import Path

from backend.models.project import ProjectStage
from backend.services import project_store
from backend.services.job_runner import CPU_SLOTS, acquire_slot
from backend.utils.ffmpeg import get_codec, get_duration, run_with_progress
from backend.ws.manager import manager


def convert_to_h264(filepath: Path, report) -> Path:
    output_path = filepath.with_name(filepath.stem + "_H264.mp4")
    report("log", None, {"level": "info", "message": "Convirtiendo a H.264 (puede tardar unos minutos)..."})
    cmd = [
        "ffmpeg", "-y", "-i", str(filepath),
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-movflags", "+faststart", str(output_path),
    ]
    acquire_slot(CPU_SLOTS, report, "Hay otra conversión/corte en curso; esperando turno para no saturar la Mac…")
    try:
        report("progress", None, {"percent": 0, "detail": "Convirtiendo a H264"})
        ok, stderr = run_with_progress(cmd, get_duration(filepath), report, "Convirtiendo a H264")
    finally:
        CPU_SLOTS.release()
    if ok:
        filepath.unlink(missing_ok=True)
        report("log", None, {"level": "info", "message": f"Conversion lista: {output_path.name}"})
        return output_path
    report("log", None, {"level": "error", "message": f"No se pudo convertir (se conserva el original): {stderr[-300:]}"})
    return filepath


def finalize_video(project_id: str, filepath: Path, report, job_stage: str = "download") -> None:
    """Detecta códec, convierte a H264 si hace falta, y deja el proyecto en stage=CONVERTIDO.
    Compartido entre la descarga por link (yt-dlp) y la subida de archivos propios."""
    codec = get_codec(filepath)
    was_converted = False
    report("log", None, {"level": "info", "message": f"Códec detectado: {codec or 'desconocido'}"})
    if codec in ("vp9", "av1"):
        project_store.update_project(project_id, stage=ProjectStage.CONVIRTIENDO)
        manager.emit(project_id, "stage_change", job_stage, {"to": "convirtiendo"})
        filepath = convert_to_h264(filepath, report)
        codec = "h264"
        was_converted = True

    project_store.update_project(
        project_id,
        stage=ProjectStage.CONVERTIDO,
        video_path=str(filepath),
        video_codec=codec,
        was_converted=was_converted,
    )
    manager.emit(project_id, "stage_change", job_stage, {"to": "convertido"})
    report("done", job_stage, {"video_path": str(filepath), "codec": codec})
