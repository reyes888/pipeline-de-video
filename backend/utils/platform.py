"""Diferencias entre sistemas operativos (macOS / Windows / Linux) en un solo lugar."""
import os
import subprocess
import sys

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"


def low_priority_cmd(cmd: list[str]) -> list[str]:
    """En macOS/Linux baja la prioridad con `nice`; en Windows se hace con creationflags."""
    return cmd if IS_WINDOWS else ["nice", "-n", "10"] + cmd


def subprocess_kwargs(low_priority: bool = False) -> dict:
    """Opciones comunes para subprocess: texto UTF-8 tolerante (los nombres con acentos
    rompen la codificación por defecto de Windows) y, si se pide, prioridad baja."""
    kwargs: dict = {"text": True, "encoding": "utf-8", "errors": "replace"}
    if IS_WINDOWS:
        flags = subprocess.CREATE_NO_WINDOW
        if low_priority:
            flags |= subprocess.BELOW_NORMAL_PRIORITY_CLASS
        kwargs["creationflags"] = flags
    return kwargs


def open_folder(path) -> None:
    if IS_WINDOWS:
        os.startfile(str(path))  # noqa: S606
    elif IS_MAC:
        subprocess.run(["open", str(path)])
    else:
        subprocess.run(["xdg-open", str(path)])
