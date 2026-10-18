import threading
import time

from fastapi import APIRouter

from backend.runtime import request_shutdown
from backend.services.job_runner import has_active_jobs

router = APIRouter(prefix="/api", tags=["system"])

_last_activity = time.time()


def touch_activity() -> None:
    global _last_activity
    _last_activity = time.time()


def _shutdown_now(delay: float = 0.3) -> None:
    time.sleep(delay)
    request_shutdown()


@router.post("/shutdown")
def shutdown() -> dict:
    threading.Thread(target=_shutdown_now, daemon=True).start()
    return {"shutting_down": True}


@router.post("/shutdown-beacon")
def shutdown_beacon() -> dict:
    beacon_time = time.time()

    def delayed_check(grace: float = 2.5) -> None:
        time.sleep(grace)
        if _last_activity > beacon_time + 0.05:
            return  # llegó actividad nueva después del aviso: la pestaña sigue en uso
        if has_active_jobs():
            return  # hay una descarga/transcripción/corte corriendo, no interrumpir
        request_shutdown()

    threading.Thread(target=delayed_check, daemon=True).start()
    return {"ok": True}
