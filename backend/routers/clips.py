import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError

from backend.models.project import Clip, ClipIn, ProjectStage
from backend.services import project_store
from backend.services.clips import build_prompt

router = APIRouter(prefix="/api/projects", tags=["clips"])


class ImportClipsRequest(BaseModel):
    clips: list[dict]


@router.get("/{project_id}/clips/prompt")
def get_prompt(project_id: str) -> dict:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado.")
    if not project.transcript or not project.transcript.json_path:
        raise HTTPException(400, "Primero genera la transcripción.")
    return {"prompt": build_prompt(project.transcript.json_path)}


@router.post("/{project_id}/clips/import")
def import_clips(project_id: str, body: ImportClipsRequest) -> list[Clip]:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado.")

    validated: list[Clip] = []
    for i, raw in enumerate(body.clips):
        try:
            clip_in = ClipIn.model_validate(raw)
        except ValidationError as e:
            raise HTTPException(400, f"Clip #{i + 1} inválido: {e.errors()[0]['msg']}")
        validated.append(Clip(id=uuid.uuid4().hex, **clip_in.model_dump()))

    if not validated:
        raise HTTPException(400, "No se encontraron clips en el JSON.")

    project_store.update_project(
        project_id,
        clips=validated,
        clips_source="pegado",
        stage=ProjectStage.CLIPS_IMPORTADOS,
    )
    return validated


@router.get("/{project_id}/clips")
def list_clips(project_id: str) -> list[Clip]:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado.")
    return project.clips


@router.put("/{project_id}/clips/{clip_id}")
def update_clip(project_id: str, clip_id: str, body: Clip) -> Clip:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado.")
    for i, clip in enumerate(project.clips):
        if clip.id == clip_id:
            body.id = clip_id
            project.clips[i] = body
            project_store.update_project(project_id, clips=project.clips)
            return body
    raise HTTPException(404, "Clip no encontrado.")


@router.delete("/{project_id}/clips/{clip_id}")
def delete_clip(project_id: str, clip_id: str) -> dict:
    project = project_store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado.")
    remaining = [c for c in project.clips if c.id != clip_id]
    if len(remaining) == len(project.clips):
        raise HTTPException(404, "Clip no encontrado.")
    project_store.update_project(project_id, clips=remaining)
    return {"deleted": True}
