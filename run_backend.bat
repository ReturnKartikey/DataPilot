@echo off
title DataPilot - Backend REST Server
cd /d "%~dp0backend"
echo [DataPilot] Starting Python FastAPI Backend Server on http://127.0.0.1:8000 ...
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
pause
