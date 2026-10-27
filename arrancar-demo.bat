@echo off
title Lumen demo
cd /d "%~dp0"
echo Arrancando Lumen (API + worker)...
start "Lumen - API (daphne)" cmd /k venv\Scripts\daphne.exe -b 127.0.0.1 -p 8000 config.asgi:application
start "Lumen - Worker (celery)" cmd /k venv\Scripts\celery.exe -A config worker -l info --pool=solo
echo Listo. Dos ventanas abiertas: daphne y celery.
echo La API queda en http://127.0.0.1:8000
timeout /t 6
