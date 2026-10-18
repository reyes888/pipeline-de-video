import subprocess
import threading

from backend.utils.platform import low_priority_cmd, subprocess_kwargs
from pathlib import Path


def get_codec(filepath: Path) -> str | None:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1", str(filepath),
            ],
            capture_output=True, timeout=30, **subprocess_kwargs(),
        )
        codec = result.stdout.strip()
        return codec if codec else None
    except Exception:
        return None


def get_duration(filepath: Path) -> float | None:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(filepath),
            ],
            capture_output=True, timeout=30, **subprocess_kwargs(),
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def _parse_ffmpeg_time(time_str: str) -> float | None:
    try:
        h, m, s = time_str.strip().split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except (ValueError, AttributeError):
        return None


def extract_audio_with_progress(video_path: Path, audio_path: Path, total_duration: float | None, report) -> tuple[bool, str]:
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        "-progress", "pipe:1", "-nostats",
        str(audio_path),
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **subprocess_kwargs())

    stderr_chunks: list[str] = []

    def drain_stderr():
        for line in process.stderr:
            stderr_chunks.append(line)

    stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
    stderr_thread.start()

    last_reported = {"pct": -10.0}
    for line in process.stdout:
        line = line.strip()
        if line.startswith("out_time="):
            seconds = _parse_ffmpeg_time(line.split("=", 1)[1])
            if seconds is not None and total_duration:
                pct = min(100.0, seconds / total_duration * 100)
                if pct - last_reported["pct"] >= 2:
                    last_reported["pct"] = pct
                    report("progress", None, {"percent": round(pct), "detail": "Extrayendo audio"})

    process.wait()
    stderr_thread.join(timeout=2)
    return process.returncode == 0, "".join(stderr_chunks)[-1500:]


def run_with_progress(cmd: list[str], total_duration: float | None, report, label: str = "") -> tuple[bool, str]:
    """Ejecuta un comando ffmpeg (sin flags de progreso; el último elemento es el archivo de salida)
    y reporta el % real (con velocidad y tiempo restante) leyendo `-progress pipe:1`."""
    import time

    full = low_priority_cmd(cmd[:-1] + ["-progress", "pipe:1", "-nostats", cmd[-1]])
    process = subprocess.Popen(full, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **subprocess_kwargs(low_priority=True))
    stderr_chunks: list[str] = []
    t = threading.Thread(target=lambda: [stderr_chunks.append(l) for l in process.stderr], daemon=True)
    t.start()
    started = time.time()
    last_emit = 0.0
    for line in process.stdout:
        line = line.strip()
        if line.startswith("out_time="):
            secs = _parse_ffmpeg_time(line.split("=", 1)[1])
            now = time.time()
            if secs is not None and total_duration and now - last_emit >= 1.0:
                last_emit = now
                pct = min(100.0, secs / total_duration * 100)
                detail = label
                elapsed = now - started
                if pct > 1 and elapsed > 3:
                    remaining = int(elapsed / pct * (100 - pct))
                    detail = f"{label + ' · ' if label else ''}faltan ~{remaining // 60}:{remaining % 60:02d}"
                report("progress", None, {"percent": round(pct, 1), "detail": detail})
    process.wait()
    t.join(timeout=2)
    return process.returncode == 0, "".join(stderr_chunks)[-1500:]
