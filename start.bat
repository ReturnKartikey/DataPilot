@echo off
title DataPilot Launcher
echo ========================================================
echo               DATAPILOT FULLSTACK SYSTEM
echo   LangGraph Workflow + Agentic Analytics Workspace
echo ========================================================
echo.
echo Launching Backend REST API Server (Port 8000)...
start "DataPilot Backend" cmd /k "%~dp0run_backend.bat"

echo Launching Frontend Web Client (Port 5173)...
start "DataPilot Frontend" cmd /k "%~dp0run_frontend.bat"

echo.
echo ========================================================
echo Application launching:
echo  - Frontend Web UI: http://localhost:5173
echo  - Backend REST API: http://127.0.0.1:8000
echo  - API Docs (Swagger): http://127.0.0.1:8000/docs
echo ========================================================
echo.
