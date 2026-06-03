@echo off
title DMRE Startup
color 0A
echo.
echo  ============================================
echo   DMRE - Digital Memory Reconstruction Engine
echo  ============================================
echo.

:: ── 1. Docker Desktop ───────────────────────────────────────────────────────
echo [1/5] Starting Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"

echo      Waiting for PostgreSQL to be healthy...
:wait_docker
timeout /t 3 /nobreak >nul
docker ps --format "{{.Status}}" 2>nul | findstr /i "healthy" >nul
if errorlevel 1 goto wait_docker
echo      PostgreSQL is ready.
echo.

:: ── 2. Ganache ──────────────────────────────────────────────────────────────
echo [2/5] Starting Ganache (port 7545)...
start "DMRE — Ganache" cmd /k "title DMRE - Ganache && color 0E && npx ganache --deterministic --port 7545"

:: ── 3. ChromaDB ─────────────────────────────────────────────────────────────
echo [3/5] Starting ChromaDB (port 8001)...
start "DMRE — ChromaDB" cmd /k "title DMRE - ChromaDB && color 0B && cd /d %~dp0 && backend\.venv\Scripts\chroma.exe run --host 0.0.0.0 --port 8001 --path chroma_data"

:: ── 4. Backend ──────────────────────────────────────────────────────────────
echo [4/5] Starting Backend (port 8000)...
start "DMRE — Backend" cmd /k "title DMRE - FastAPI Backend && color 09 && cd /d %~dp0backend && set HF_HUB_OFFLINE=1 && set TRANSFORMERS_OFFLINE=1 && .venv\Scripts\uvicorn.exe app.main:app --reload --port 8000"

:: ── 5. Dashboard ────────────────────────────────────────────────────────────
echo [5/5] Starting Dashboard (port 3000)...
start "DMRE — Dashboard" cmd /k "title DMRE - React Dashboard && color 0D && cd /d %~dp0dashboard && npm run dev"

:: ── Open browser after services warm up ─────────────────────────────────────
echo.
echo  All services launching in separate windows.
echo  Opening dashboard in 12 seconds...
timeout /t 12 /nobreak >nul
start "" "http://localhost:3000"

echo.
echo  Done. Close this window any time.
