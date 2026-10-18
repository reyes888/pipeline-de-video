@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Pipeline de Video

echo.
echo  Pipeline de Video
echo  ======================
echo.

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo  [!] No se encontro ffmpeg, necesario para descargar y convertir videos.
  echo      Instalalo abriendo una terminal y escribiendo:
  echo      winget install Gyan.FFmpeg
  echo      Luego cierra esta ventana y vuelve a abrir el lanzador.
  echo.
  pause
  exit /b 1
)

set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY (
  where python >nul 2>nul && set PY=python
)
if not defined PY (
  echo  [!] No se encontro Python 3.
  echo      Instalalo desde https://www.python.org/downloads/
  echo      y marca la casilla "Add python.exe to PATH" durante la instalacion.
  echo.
  pause
  exit /b 1
)

if not exist "venv\Scripts\python.exe" (
  echo  Primera vez que se usa la app: preparando todo lo necesario.
  echo  Esto puede tardar varios minutos - solo pasa esta vez.
  echo.
  %PY% -m venv venv
  if errorlevel 1 ( echo  [!] No se pudo crear el entorno. & pause & exit /b 1 )
  call venv\Scripts\activate.bat
  python -m pip install --upgrade pip --quiet
  pip install -r requirements.txt
  if errorlevel 1 ( echo  [!] Fallo la instalacion de dependencias. & pause & exit /b 1 )
  echo.
  echo  Listo. A partir de ahora arrancara en segundos.
) else (
  call venv\Scripts\activate.bat
)

echo.
echo  Iniciando el servidor...
echo  Se abrira tu navegador automaticamente en un momento.
echo.
echo  Para CERRAR la app: usa el boton "Apagar" dentro de la app,
echo  o cierra esta ventana.
echo.

python app.py
pause
