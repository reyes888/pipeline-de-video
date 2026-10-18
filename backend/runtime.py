"""Referencia al servidor uvicorn en ejecución, para poder apagarlo de forma limpia
(igual que Control+C) en cualquier sistema operativo."""
import os
import signal

server = None  # lo asigna app.py


def request_shutdown() -> None:
    if server is not None:
        server.should_exit = True
    else:
        os.kill(os.getpid(), signal.SIGTERM)
