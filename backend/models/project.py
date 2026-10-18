from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ProjectStage(str, Enum):
    NUEVO = "nuevo"
    DESCARGANDO = "descargando"
    DESCARGADO = "descargado"
    CONVIRTIENDO = "convirtiendo"
    CONVERTIDO = "convertido"
    EXTRAYENDO_AUDIO = "extrayendo_audio"
    TRANSCRIBIENDO = "transcribiendo"
    TRANSCRITO = "transcrito"
    CLIPS_IMPORTADOS = "clips_importados"
    CORTANDO = "cortando"
    COMPLETADO = "completado"
    ERROR = "error"


class TranscriptInfo(BaseModel):
    txt_path: str | None = None
    srt_path: str | None = None
    json_path: str | None = None
    model: str | None = None
    language: str | None = None


class Clip(BaseModel):
    id: str
    start: float
    end: float
    titulo: str
    puntaje_viral: int
    razon: str = ""
    selected: bool = True
    cut_path: str | None = None


class ClipIn(BaseModel):
    """Schema de validación para el clips.json importado (ver encontrar_clips.md)."""

    start: float
    end: float
    titulo: str
    puntaje_viral: int = Field(ge=1, le=10)
    razon: str = ""


class Project(BaseModel):
    id: str
    title: str
    source_type: Literal["url", "upload"] = "url"
    source_url: str | None = None
    created_at: datetime
    updated_at: datetime
    stage: ProjectStage = ProjectStage.NUEVO
    error_message: str | None = None
    video_path: str | None = None
    video_codec: str | None = None
    was_converted: bool = False
    transcript: TranscriptInfo | None = None
    clips: list[Clip] = []
    clips_source: Literal["pegado", "archivo"] | None = None


class ProjectSummary(BaseModel):
    progress: float | None = None
    progress_detail: str | None = None
    id: str
    title: str
    stage: ProjectStage
    updated_at: datetime
    error_message: str | None = None
