#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

clear 2>/dev/null || true
echo "🎬 Pipeline de Video"
echo "======================"
echo ""

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "⚠️  No se encontró ffmpeg, que es necesario para descargar y convertir videos."
  echo "    Instálalo abriendo la Terminal y escribiendo:"
  echo "    brew install ffmpeg"
  echo ""
  read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "⚠️  No se encontró Python 3."
  echo "    Instálalo desde https://www.python.org/downloads/ y vuelve a intentar."
  echo ""
  read -n 1 -s -r -p "Presiona cualquier tecla para cerrar..."
  exit 1
fi

if [ ! -d "venv" ]; then
  echo "Primera vez que se usa la app: preparando todo lo necesario."
  echo "Esto puede tardar varios minutos — solo pasa esta vez."
  echo ""
  python3 -m venv venv
  source venv/bin/activate
  pip install --upgrade pip --quiet
  pip install -r requirements.txt
  echo ""
  echo "✔ Listo. A partir de ahora arrancará en segundos."
else
  source venv/bin/activate
fi

echo ""
echo "Iniciando el servidor..."
echo "Se abrirá tu navegador automáticamente en un momento."
echo ""
echo "Para CERRAR la app: cierra esta ventana o presiona Control + C."
echo ""

python3 app.py
