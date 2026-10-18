import asyncio
from collections import deque
from datetime import datetime, timezone

from fastapi import WebSocket

LOG_LIMIT = 80
PARTIAL_LIMIT = 300


class ConnectionManager:
    """Mantiene conexiones WS por project_id y, además, una "memoria" del estado en vivo
    (últimos logs, progreso y texto parcial) para que una página que se abre o se recarga
    mientras un trabajo corre vea de inmediato dónde va, en vez de una pantalla vacía."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._progress: dict[str, dict[str, dict]] = {}   # project_id -> stage -> último progress
        self._logs: dict[str, dict[str, deque]] = {}      # project_id -> stage -> logs recientes
        self._partials: dict[str, deque] = {}             # project_id -> texto parcial transcripción

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    # ---- memoria de estado en vivo ----
    def reset_stage(self, project_id: str, stage: str) -> None:
        self._progress.get(project_id, {}).pop(stage, None)
        self._logs.setdefault(project_id, {})[stage] = deque(maxlen=LOG_LIMIT)
        if stage == "transcribe":
            self._partials[project_id] = deque(maxlen=PARTIAL_LIMIT)

    def snapshot(self, project_id: str) -> dict:
        return {
            "progress": dict(self._progress.get(project_id, {})),
            "logs": {s: list(d) for s, d in self._logs.get(project_id, {}).items()},
            "partials": list(self._partials.get(project_id, [])),
        }

    def live_progress(self, project_id: str) -> dict | None:
        """Progreso más reciente de cualquier etapa activa (para las tarjetas del dashboard)."""
        items = self._progress.get(project_id, {})
        if not items:
            return None
        latest = max(items.values(), key=lambda m: m["timestamp"])
        return {"percent": latest["payload"].get("percent"), "detail": latest["payload"].get("detail")}

    # ---- conexiones ----
    async def connect(self, project_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        # Se permite más de una conexión por proyecto (p. ej. dos pestañas); cerrar la anterior
        # "al vuelo" provocó guerras de reconexión, así que cada socket se limpia al desconectarse.
        self._connections.setdefault(project_id, set()).add(websocket)
        try:
            await websocket.send_json({"type": "snapshot", "project_id": project_id, "payload": self.snapshot(project_id)})
        except Exception:
            pass

    def disconnect(self, project_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(project_id)
        if conns:
            conns.discard(websocket)
            if not conns:
                self._connections.pop(project_id, None)

    async def _broadcast(self, project_id: str, message: dict) -> None:
        for ws in list(self._connections.get(project_id, ())):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(project_id, ws)

    def emit(self, project_id: str, event_type: str, stage: str | None = None, payload: dict | None = None) -> None:
        """Thread-safe: se puede llamar desde un worker thread de background."""
        message = {
            "type": event_type,
            "project_id": project_id,
            "stage": stage,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload or {},
        }
        if stage:
            if event_type == "progress":
                self._progress.setdefault(project_id, {})[stage] = message
            elif event_type == "log":
                self._logs.setdefault(project_id, {}).setdefault(stage, deque(maxlen=LOG_LIMIT)).append(message)
            elif event_type == "partial_result":
                self._partials.setdefault(project_id, deque(maxlen=PARTIAL_LIMIT)).append(message["payload"].get("text", ""))
            elif event_type in ("done", "error"):
                self._progress.get(project_id, {}).pop(stage, None)
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(project_id, message), self._loop)


manager = ConnectionManager()
