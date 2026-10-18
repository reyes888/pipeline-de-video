"""
Pipeline de Video - App local
------------------------------
Descarga videos, los convierte a H264, extrae audio, transcribe con
Whisper y ayuda a encontrar y cortar los mejores clips. Corre 100% en
local (localhost), sin exposición a internet.

Uso: python3 app.py
"""

import socket
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from backend import runtime
from backend.config import DEFAULT_PORT
from backend.main import app


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _pick_port() -> int:
    port = DEFAULT_PORT
    while not _port_is_free(port):
        port += 1
    return port


def _wait_for_health_and_open_browser(port: int) -> None:
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=0.5) as resp:
                if resp.status == 200:
                    webbrowser.open(url)
                    return
        except Exception:
            pass
        time.sleep(0.1)


def _already_running() -> bool:
    """Si ya hay una instancia de la app en el puerto por defecto, no se lanza otra
    (dos servidores sobre los mismos datos se pisarían entre sí)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{DEFAULT_PORT}/health", timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False


def main() -> None:
    if _already_running():
        print(f"La app ya está abierta en http://127.0.0.1:{DEFAULT_PORT} — abriendo el navegador.")
        webbrowser.open(f"http://127.0.0.1:{DEFAULT_PORT}")
        return
    port = _pick_port()
    threading.Thread(target=_wait_for_health_and_open_browser, args=(port,), daemon=True).start()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    runtime.server = uvicorn.Server(config)
    runtime.server.run()


if __name__ == "__main__":
    main()
