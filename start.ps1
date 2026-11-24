Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "              DATAPILOT FULLSTACK SYSTEM                " -ForegroundColor Cyan
Write-Host "  Autonomous Decision Agents + Editorial Interface       " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Starting Python FastAPI Backend (Port 8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$ScriptDir\backend'; python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload"

Write-Host "Starting React Vite Frontend (Port 5173)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$ScriptDir\frontend'; npm run dev"

Write-Host "`nDataPilot is now starting:" -ForegroundColor Green
Write-Host " - Frontend UI:  http://localhost:5173" -ForegroundColor White
Write-Host " - Backend API:  http://127.0.0.1:8000" -ForegroundColor White
Write-Host " - Swagger Docs: http://127.0.0.1:8000/docs`n" -ForegroundColor White
