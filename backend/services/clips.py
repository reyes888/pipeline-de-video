PROMPT_TEMPLATE = """Eres un editor de video especializado en contenido corto para TikTok, Reels y Shorts.
Vas a analizar la transcripción con timestamps en `{json_path}`
(formato Whisper: lista de segmentos con `start`, `end`, `text`).

Tu tarea:

1. Lee el archivo JSON completo.
2. Identifica entre 5 y 10 fragmentos con potencial viral, buscando:
   - Un "gancho" (hook) en los primeros 2-3 segundos del fragmento: pregunta
     intrigante, afirmación polémica, dato sorprendente, cambio de tono emocional.
   - Ideas completas y autocontenidas (que se entiendan sin ver el resto del video).
   - Momentos de alta emoción, humor, conflicto, revelación o consejo accionable.
   - Duración entre 20 y 90 segundos (ideal para shorts).
3. Para cada fragmento, ajusta el `start`/`end` a los timestamps reales del JSON,
   dejando 1-2 segundos de aire antes y después si es natural.
4. Da un puntaje de 1-10 en potencial viral y explica en una frase por qué.
5. Sugiere un título corto (máx 60 caracteres) tipo gancho para el clip.

Devuelve el resultado ÚNICAMENTE como JSON válido con este formato:

```json
[
  {{
    "start": 125.4,
    "end": 178.9,
    "titulo": "El error que arruina el 90% de los cortos",
    "puntaje_viral": 8,
    "razon": "Contradice una creencia común y da un dato concreto en los primeros 3 segundos."
  }}
]
```

No incluyas texto fuera del JSON. Si el video es largo (+40 min), prioriza calidad
sobre cantidad: es mejor 5 clips fuertes que 10 mediocres."""


def build_prompt(json_path: str) -> str:
    return PROMPT_TEMPLATE.format(json_path=json_path)
