# 🎬 Pipeline de Video

Herramienta **local** que convierte un video largo en clips cortos listos para TikTok, Reels y Shorts.
Todo corre en tu computadora (`127.0.0.1`): nada se sube a ningún servidor, salvo la descarga de los videos
y el paso manual en el que le pides a una IA que elija los mejores momentos.

## Qué hace

1. **Consigue el video** — pega uno o varios links, o sube archivos de tu computadora.
   Si el códec no es compatible (VP9/AV1), lo convierte a H264.
2. **Lo transcribe** con Whisper (local) y genera `.txt`, `.srt` y `.json`.
3. **Encuentra los mejores momentos** — la app arma un prompt con la transcripción; lo pegas en Claude
   (u otra IA) y vuelves a pegar el `clips.json` que te devuelva. Puedes editar o descartar clips.
4. **Corta los clips** en horizontal (16:9) o vertical (9:16) y los previsualizas en la misma página.

Cada video es un *proyecto* con su avance visible (barra, porcentaje y tiempo restante). Puedes tener varios
a la vez: la app ordena los trabajos pesados para no saturar tu equipo.

## Requisitos

| | macOS | Windows |
|---|---|---|
| **Python 3.10 o superior** | [python.org](https://www.python.org/downloads/) | [python.org](https://www.python.org/downloads/) — marca *Add python.exe to PATH* |
| **ffmpeg** | `brew install ffmpeg` | `winget install Gyan.FFmpeg` |

El motor de transcripción se elige solo: `mlx-whisper` en Macs con chip Apple (usa la GPU, el más rápido) y
`faster-whisper` en Windows, Linux y Macs Intel (CPU, o GPU NVIDIA si hay).
La primera transcripción descarga el modelo de Whisper (cientos de MB).

## Cómo encenderla

**macOS:** doble clic en `Iniciar Pipeline de Video.command`
(si macOS lo bloquea: clic derecho → *Abrir* → *Abrir*, solo la primera vez).

**Windows:** doble clic en `Iniciar Pipeline de Video.bat`.

La primera vez prepara el entorno e instala dependencias (varios minutos); después arranca en segundos y abre
el navegador en `http://127.0.0.1:8000`.

**A mano (cualquier sistema):**

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Para apagarla usa el botón **⏻ Apagar** dentro de la app. Si se cierra a mitad de un trabajo, al volver a abrirla
los proyectos retoman desde donde quedaron.

## Dónde se guardan los archivos

Todo queda en `data/projects/<id>/` (video, transcripción y clips finales) hasta que borras el proyecto.
Esa carpeta está en `.gitignore`: nunca se sube al repositorio.

## Aviso de uso

Descarga y procesa solo contenido **propio o que tengas permiso de usar**. Respeta los términos de servicio de cada
plataforma y los derechos de autor. Este proyecto no está afiliado a ninguna de ellas, y quien lo usa es
responsable de lo que descarga.

## Solución de problemas

- **`HTTP Error 403` al descargar:** yt-dlp se desactualizó. Ejecuta `pip install -U yt-dlp` (con el entorno activado).
- **No encuentra `ffmpeg`:** instálalo (ver Requisitos) y abre una terminal nueva.
- **Compatibilidad:** desarrollado y probado en macOS (Apple Silicon). El soporte de Windows/Linux está
  implementado pero se ha probado menos; si encuentras un problema, abre un *issue*.

## Estructura

```
app.py                 entrada: levanta el servidor y abre el navegador
backend/               API (FastAPI), jobs en segundo plano, WebSocket de progreso
  services/            descarga, conversión, transcripción, clips, corte
frontend/              plantillas Jinja2 + Alpine.js (sin build)
data/                  proyectos del usuario (ignorado por git)
```

## Licencia

[MIT](LICENSE)
