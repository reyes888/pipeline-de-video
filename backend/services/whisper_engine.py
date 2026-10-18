"""Motor de transcripción intercambiable.

- Macs con chip Apple Silicon: `mlx-whisper` (usa la GPU del chip, es lo más rápido).
- Windows, Linux y Macs Intel: `faster-whisper` (CPU, o GPU NVIDIA si hay CUDA).

Ambos exponen la misma función `transcribe_chunk`, que devuelve segmentos con tiempos
absolutos respecto al audio completo.
"""
import platform
import sys
import threading

MLX_MODELS = {
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
}

SAMPLE_RATE = 16000
_faster_models: dict[str, object] = {}
_wav_cache: dict[str, object] = {}
_faster_lock = threading.Lock()


def _use_mlx() -> bool:
    if not (sys.platform == "darwin" and platform.machine() == "arm64"):
        return False
    try:
        import mlx_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def engine_name() -> str:
    return "mlx-whisper" if _use_mlx() else "faster-whisper"


def _faster_model(name: str):
    with _faster_lock:
        if name not in _faster_models:
            from faster_whisper import WhisperModel

            # "auto" usa la GPU NVIDIA si existe; si no, CPU con cuantización int8 (rápido y ligero).
            _faster_models[name] = WhisperModel(name, device="auto", compute_type="int8")
        return _faster_models[name]


def _load_wav(path: str):
    """Lee el .wav (16 kHz, mono, 16 bits: el formato que genera nuestro ffmpeg) como arreglo.
    Se evita el lector de audio interno de faster-whisper, que depende de la versión de PyAV."""
    import wave

    import numpy as np

    if path not in _wav_cache:
        _wav_cache.clear()
        with wave.open(path, "rb") as wf:
            _wav_cache[path] = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    return _wav_cache[path]


def transcribe_chunk(audio_path: str, model: str, language: str, start: float, end: float | None) -> dict:
    """Transcribe la ventana [start, end] del audio. Devuelve {"text", "segments", "language"}."""
    if _use_mlx():
        import mlx_whisper

        clip = f"{start},{end}" if end else f"{start},0"
        result = mlx_whisper.transcribe(
            audio_path, path_or_hf_repo=MLX_MODELS.get(model, MLX_MODELS["medium"]),
            language=language, clip_timestamps=clip,
        )
        return {
            "text": result.get("text", ""),
            "segments": result.get("segments", []),
            "language": result.get("language"),
        }

    import numpy as np

    pcm = _load_wav(audio_path)
    first = int(start * SAMPLE_RATE)
    last = int(end * SAMPLE_RATE) if end else len(pcm)
    audio = pcm[first:last].astype(np.float32) / 32768.0
    whisper = _faster_model(model if model in MLX_MODELS else "medium")
    segments_iter, info = whisper.transcribe(audio, language=language)
    segments = [
        {"id": i, "start": seg.start + start, "end": seg.end + start, "text": seg.text}
        for i, seg in enumerate(segments_iter)
    ]
    return {
        "text": "".join(s["text"] for s in segments),
        "segments": segments,
        "language": info.language,
    }
