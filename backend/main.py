import asyncio
import time

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.config import STATIC_DIR, TEMPLATES_DIR
from backend.routers import clips, cut, download, projects, system, transcribe, ws
from backend.routers.system import touch_activity
from backend.ws.manager import manager


class NoCacheStaticFiles(StaticFiles):
    """Fuerza a que el navegador siempre revalide los archivos estáticos.
    Sin esto, ediciones a los .js/.css durante el desarrollo pueden quedar
    invisibles porque el navegador sigue usando una copia cacheada vieja."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


app = FastAPI(title="Pipeline de Video")

app.mount("/static", NoCacheStaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
# Cambia en cada arranque del server: evita que el navegador sirva JS/CSS
# viejos desde caché después de editar archivos estáticos.
templates.env.globals["asset_version"] = str(int(time.time()))

app.include_router(projects.router)
app.include_router(download.router)
app.include_router(transcribe.router)
app.include_router(clips.router)
app.include_router(cut.router)
app.include_router(system.router)
app.include_router(ws.router)


@app.middleware("http")
async def track_activity(request: Request, call_next):
    touch_activity()
    return await call_next(request)


@app.on_event("startup")
async def bind_ws_loop() -> None:
    manager.bind_loop(asyncio.get_running_loop())
    _recover_after_restart()


def _recover_after_restart() -> None:
    from pathlib import Path

    from backend.config import PROJECTS_DIR
    from backend.services import project_store
    from backend.services.downloader import _find_existing_video
    from backend.services.uploader import start_upload_processing_job

    for project in project_store.recover_interrupted():
        manager.emit(project.id, "log", "download", {"level": "warn", "message": "La app se cerró mientras este proyecto trabajaba. Se retoma desde donde quedó."})
        if project.source_type == "upload":
            existing = _find_existing_video(PROJECTS_DIR / project.id / "video")
            if existing:
                start_upload_processing_job(project.id, existing)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {})


@app.get("/projects/{project_id}")
async def project_detail(request: Request, project_id: str):
    return templates.TemplateResponse(request, "project.html", {"project_id": project_id})
