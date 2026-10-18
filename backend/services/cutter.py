import subprocess
from pathlib import Path

from backend.config import PROJECTS_DIR
from backend.models.project import ProjectStage
from backend.services import project_store
from backend.services.job_runner import CPU_SLOTS, acquire_slot, make_reporter, run_in_background
from backend.utils.platform import low_priority_cmd, subprocess_kwargs
from backend.utils.slugify import slugify
from backend.ws.manager import manager

VERTICAL_FILTER = "crop=ih*9/16:ih,scale=1080:1920"


def _cut_one(video_path: Path, out_dir: Path, index: int, clip, vertical: bool, report) -> tuple[bool, str]:
    duration = clip.end - clip.start
    suffix = "_9x16" if vertical else ""
    filename = f"{index}_puntaje{clip.puntaje_viral}_{slugify(clip.titulo)}{suffix}.mp4"
    output_path = out_dir / filename

    cmd = ["ffmpeg", "-y", "-ss", str(clip.start), "-i", str(video_path), "-t", str(duration)]
    if vertical:
        cmd += ["-vf", VERTICAL_FILTER]
    cmd += [
        "-c:v", "libx264", "-c:a", "aac", "-preset", "fast",
        "-movflags", "+faststart",
        str(output_path), "-loglevel", "error",
    ]

    report("log", None, {"level": "info", "message": f"Cortando clip {index}: {clip.titulo} ({clip.start:.1f}s → {clip.end:.1f}s)"})
    acquire_slot(CPU_SLOTS, report, "Hay otra conversión/corte en curso; esperando turno…")
    try:
        result = subprocess.run(low_priority_cmd(cmd), capture_output=True, **subprocess_kwargs(low_priority=True))
    finally:
        CPU_SLOTS.release()
    if result.returncode != 0:
        report("log", None, {"level": "error", "message": f"Error al cortar clip {index}: {result.stderr[-300:]}"})
        return False, ""
    report("log", None, {"level": "info", "message": f"Listo: {filename}"})
    return True, str(output_path)


def _do_cut(project_id: str, vertical: bool) -> None:
    report = make_reporter(project_id, "cut")
    project = project_store.get_project(project_id)
    if project is None or not project.video_path:
        return

    selected = [c for c in project.clips if c.selected]
    if not selected:
        report("error", "cut", {"message": "No hay clips seleccionados para cortar."})
        return

    project_store.update_project(project_id, stage=ProjectStage.CORTANDO)
    manager.emit(project_id, "stage_change", "cut", {"to": "cortando"})

    video_path = Path(project.video_path)
    out_dir = PROJECTS_DIR / project_id / "clips_finales"
    out_dir.mkdir(parents=True, exist_ok=True)

    total = len(selected)
    updated_clips = list(project.clips)
    ok_count = 0
    for i, clip in enumerate(selected, start=1):
        ok, out_path = _cut_one(video_path, out_dir, i, clip, vertical, report)
        if ok:
            ok_count += 1
            for j, c in enumerate(updated_clips):
                if c.id == clip.id:
                    updated_clips[j].cut_path = out_path
        report("progress", None, {"percent": round(i / total * 100)})

    project_store.update_project(project_id, stage=ProjectStage.COMPLETADO, clips=updated_clips)
    manager.emit(project_id, "stage_change", "cut", {"to": "completado"})
    report("log", None, {"level": "info", "message": f"Listo. {ok_count}/{total} clip(s) cortado(s)."})
    report("done", "cut", {"count": ok_count})


def start_cut_job(project_id: str, vertical: bool) -> None:
    run_in_background(project_id, "cut", lambda: _do_cut(project_id, vertical))
