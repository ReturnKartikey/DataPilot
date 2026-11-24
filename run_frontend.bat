@echo off
title DataPilot - Frontend Dev Server
cd /d "%~dp0frontend"
echo [DataPilot] Starting React Vite Frontend Server on http://localhost:5173 ...
npm run dev
pause
