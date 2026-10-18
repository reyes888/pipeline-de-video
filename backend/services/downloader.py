import re
import time
from pathlib import Path

import yt_dlp

from backend.config import ARCHIVE_PATH, PROJECTS_DIR
from backend.models.project import ProjectStage
from backend.services import project_store
from backend.services.job_runner import DOWNLOAD_SLOTS, acquire_slot, make_reporter, run_in_background
from backend.services.video_prep import finalize_video
from backend.ws.manager import manager


def _make_progress_hook(report):
    state = {"t": 0.0}

    def hook(d):
        if d.get("status") == "downloading":
            done = d.get("downloaded_bytes") or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            speed_bps = d.get("speed")
            eta = d.get("eta")
            parts = []
            if speed_bps:
                parts.append(f"{speed_bps / 1048576:.1f} MB/s")
            if eta:
                parts.append(f"faltan ~{int(eta) // 60}:{int(eta) % 60:02d}")
            if done:
                parts.append(f"{done / 1048576:.0f} MB descargados")
            now = time.time()
            if now - state["t"] >= 1.0:
                state["t"] = now
                pct = min(100.0, done / total * 100) if total else 0
                report("progress", None, {"percent": round(pct, 1), "detail": " · ".join(parts)})
        elif d.get("status") == "finished":
            report("log", None, {"level": "info", "message": "Descarga completa, procesando archivo..."})

    return hook


def _find_existing_video(dest: Path) -> Path | None:
    """Si una ejecución anterior se interrumpió, reutiliza lo ya descargado/convertido."""
    files = [f for f in dest.glob("*.mp4") if not re.search(r"\.f\d+\.", f.name)]
    sources = [f for f in files if not f.name.endswith("_H264.mp4")]
    converted = [f for f in files if f.name.endswith("_H264.mp4")]
    if sources:
        for f in converted:  # conversión a medias: se descarta y se rehace
            f.unlink(missing_ok=True)
        return sources[0]
    return converted[0] if converted else None


def _do_download_and_convert(project_id: str) -> None:
    report = make_reporter(project_id, "download")
    project = project_store.get_project(project_id)
    if project is None or not project.source_url:
        return

    project_store.update_project(project_id, stage=ProjectStage.DESCARGANDO)
    manager.emit(project_id, "stage_change", "download", {"from": "nuevo", "to": "descargando"})

    dest = PROJECTS_DIR / project_id / "video"
    dest.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "outtmpl": str(dest / "%(id)s.%(ext)s"),
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "noprogress": True,
        "no_color": True,
        "no_warnings": True,
        "download_archive": str(ARCHIVE_PATH),
        "progress_hooks": [_make_progress_hook(report)],
    }

    existing = _find_existing_video(dest)
    if existing:
        report("log", None, {"level": "info", "message": f"Se encontró el video ya descargado ({existing.name}); se continúa desde ahí."})
        finalize_video(project_id, existing, report)
        return

    acquire_slot(DOWNLOAD_SLOTS, report, "Hay otras descargas en curso; esperando turno…")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(project.source_url, download=True)
            if info is None:
                report("log", None, {"level": "warn", "message": "Ya estaba descargado previamente (omitido)."})
                report("error", "download", {"message": "Este video ya fue descargado antes (revisa el archivo de proyectos)."})
                project_store.update_project(
                    project_id, stage=ProjectStage.ERROR,
                    error_message="Este video ya fue descargado antes.",
                )
                return
            filepath = Path(ydl.prepare_filename(info))
            if filepath.suffix != ".mp4":
                filepath = filepath.with_suffix(".mp4")
            title = info.get("title") or project.source_url
    except yt_dlp.utils.DownloadError as e:
        message = re.sub(r"\x1b\[[0-9;]*m", "", str(e)).replace("ERROR: ", "")
        report("error", "download", {"message": f"No se pudo descargar: {message}"})
        project_store.update_project(project_id, stage=ProjectStage.ERROR, error_message=message)
        return
    except Exception as e:
        report("error", "download", {"message": f"Error inesperado: {e}"})
        project_store.update_project(project_id, stage=ProjectStage.ERROR, error_message=str(e))
        return
    finally:
        DOWNLOAD_SLOTS.release()

    if not filepath.exists():
        message = "No se encontró el archivo final descargado."
        report("error", "download", {"message": message})
        project_store.update_project(project_id, stage=ProjectStage.ERROR, error_message=message)
        return

    report("log", None, {"level": "info", "message": f"Descargado: {filepath.name}"})
    project_store.update_project(project_id, stage=ProjectStage.DESCARGADO, title=title)
    manager.emit(project_id, "stage_change", "download", {"from": "descargando", "to": "descargado"})

    finalize_video(project_id, filepath, report)


def start_download_job(project_id: str) -> None:
    run_in_background(project_id, "download", lambda: _do_download_and_convert(project_id))
