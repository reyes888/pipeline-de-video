import json
import math
import threading
from pathlib import Path

from backend.config import PROJECTS_DIR
from backend.models.project import ProjectStage, TranscriptInfo
from backend.services import project_store
from backend.services.job_runner import make_reporter, run_in_background
from backend.services.whisper_engine import engine_name, transcribe_chunk
from backend.utils.ffmpeg import extract_audio_with_progress, get_duration
from backend.ws.manager import manager

CHUNK_SECONDS = 60

# El motor usa la GPU/CPU de forma intensiva: solo una transcripción a la vez.
_transcribe_semaphore = threading.Semaphore(1)


def _format_srt_timestamp(seconds: float) -> str:
    ms_total = round(seconds * 1000)
    hours, ms_total = divmod(ms_total, 3_600_000)
    minutes, ms_total = divmod(ms_total, 60_000)
    secs, ms = divmod(ms_total, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _write_outputs(text: str, segments: list[dict], language: str | None, out_dir: Path, stem: str) -> TranscriptInfo:
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_path = out_dir / f"{stem}.txt"
    srt_path = out_dir / f"{stem}.srt"
    json_path = out_dir / f"{stem}.json"

    txt_path.write_text(text.strip() + "\n", encoding="utf-8")

    srt_lines = []
    for i, seg in enumerate(segments, start=1):
        srt_lines.append(str(i))
        srt_lines.append(
            f"{_format_srt_timestamp(seg['start'])} --> {_format_srt_timestamp(seg['end'])}"
        )
        srt_lines.append(seg["text"].strip())
        srt_lines.append("")
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")

    json_path.write_text(
        json.dumps({"text": text, "segments": segments, "language": language}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return TranscriptInfo(
        txt_path=str(txt_path), srt_path=str(srt_path), json_path=str(json_path),
    )


def _do_transcribe(project_id: str, language: str, model: str) -> None:
    report = make_reporter(project_id, "transcribe")
    project = project_store.get_project(project_id)
    if project is None or not project.video_path:
        return

    video_path = Path(project.video_path)
    audio_dir = PROJECTS_DIR / project_id / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / f"{video_path.stem}.wav"

    project_store.update_project(project_id, stage=ProjectStage.EXTRAYENDO_AUDIO)
    manager.emit(project_id, "stage_change", "transcribe", {"to": "extrayendo_audio"})
    report("log", None, {"level": "info", "message": "Extrayendo audio..."})

    video_duration = get_duration(video_path)
    ok, stderr = extract_audio_with_progress(video_path, audio_path, video_duration, report)
    if not ok:
        message = f"No se pudo extraer el audio: {stderr[-300:]}"
        report("error", "transcribe", {"message": message})
        project_store.update_project(project_id, stage=ProjectStage.ERROR, error_message=message)
        return

    project_store.update_project(project_id, stage=ProjectStage.TRANSCRIBIENDO)
    manager.emit(project_id, "stage_change", "transcribe", {"to": "transcribiendo"})
    report("log", None, {"level": "info", "message": f"Transcribiendo con Whisper ({engine_name()}, modelo {model}, idioma: {language})..."})

    audio_duration = get_duration(audio_path) or video_duration or 0.0
    num_chunks = max(1, math.ceil(audio_duration / CHUNK_SECONDS)) if audio_duration else 1

    all_segments: list[dict] = []
    all_text_parts: list[str] = []
    detected_language = language

    _transcribe_semaphore.acquire()
    try:
        for i in range(num_chunks):
            report("progress", None, {"percent": round(i / num_chunks * 100), "detail": f"Transcribiendo trozo {i + 1} de {num_chunks}"})
            start = i * CHUNK_SECONDS
            end = min(start + CHUNK_SECONDS, audio_duration) if audio_duration else None
            try:
                result = transcribe_chunk(str(audio_path), model, language, start, end)
            except Exception as e:
                message = f"Error al transcribir (trozo {i + 1}/{num_chunks}): {e}"
                report("error", "transcribe", {"message": message})
                project_store.update_project(project_id, stage=ProjectStage.ERROR, error_message=message)
                return

            chunk_segments = result.get("segments", [])
            chunk_text = result.get("text", "").strip()
            detected_language = result.get("language") or detected_language
            all_segments.extend(chunk_segments)
            if chunk_text:
                all_text_parts.append(chunk_text)

            percent = round((i + 1) / num_chunks * 100)
            report("progress", None, {"percent": percent, "detail": f"Trozo {i + 1} de {num_chunks} listo"})
            if chunk_text:
                report("partial_result", None, {"text": chunk_text, "percent": percent})
    finally:
        _transcribe_semaphore.release()

    full_text = " ".join(all_text_parts)
    transcript_dir = PROJECTS_DIR / project_id / "transcripcion"
    transcript_info = _write_outputs(full_text, all_segments, detected_language, transcript_dir, video_path.stem)
    transcript_info.model = model
    transcript_info.language = language

    audio_path.unlink(missing_ok=True)

    project_store.update_project(project_id, stage=ProjectStage.TRANSCRITO, transcript=transcript_info)
    manager.emit(project_id, "stage_change", "transcribe", {"to": "transcrito"})
    report("log", None, {"level": "info", "message": "Transcripción lista (.txt, .srt, .json)."})
    report("done", "transcribe", {"json_path": transcript_info.json_path})


def start_transcribe_job(project_id: str, language: str, model: str) -> None:
    run_in_background(project_id, "transcribe", lambda: _do_transcribe(project_id, language, model))
