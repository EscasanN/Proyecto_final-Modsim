@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo No se encontro .venv. Sigue la instalacion del README antes de iniciar.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m src.macetas.presentation
if errorlevel 1 pause
