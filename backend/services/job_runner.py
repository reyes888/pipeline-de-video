import threading
from collections.abc import Callable

from backend.ws.manager import manager

Reporter = Callable[[str, str | None, dict | None], None]

_active_jobs: dict[str, dict] = {}
_jobs_guard = threading.Lock()


def make_reporter(project_id: str, stage: str) -> Reporter:
    def report(event_type: str, sub_stage: str | None = None, payload: dict | None = None) -> None:
        manager.emit(project_id, event_type, sub_stage or stage, payload)
    return report


def run_in_background(project_id: str, job_key: str, target: Callable[[], None]) -> None:
    def wrapper():
        try:
            target()
        finally:
            with _jobs_guard:
                _active_jobs.pop(f"{project_id}:{job_key}", None)

    manager.reset_stage(project_id, job_key)
    thread = threading.Thread(target=wrapper, daemon=True)
    with _jobs_guard:
        _active_jobs[f"{project_id}:{job_key}"] = {"thread": thread}
    thread.start()


def is_running(project_id: str, job_key: str) -> bool:
    with _jobs_guard:
        return f"{project_id}:{job_key}" in _active_jobs


def has_active_jobs() -> bool:
    with _jobs_guard:
        return len(_active_jobs) > 0


# Límites para no saturar la Mac: las descargas usan poca CPU (2 a la vez está bien);
# convertir/cortar video con ffmpeg es lo que enciende el ventilador (1 a la vez).
DOWNLOAD_SLOTS = threading.Semaphore(2)
CPU_SLOTS = threading.Semaphore(1)


def acquire_slot(sem: threading.Semaphore, report, message: str) -> None:
    if not sem.acquire(blocking=False):
        report("log", None, {"level": "info", "message": message})
        sem.acquire()
