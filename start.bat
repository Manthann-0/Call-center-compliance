@echo off
title CallCenter Compliance AI
color 0B
echo.
echo  =============================================
echo    CallCenter Compliance AI  -  Starting...
echo  =============================================
echo.

REM ── Change to script directory ──
cd /d "%~dp0"

REM ── Create uploads directory ──
if not exist "uploads" mkdir uploads

REM ── Check Python ──
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Please install Python 3.10+
    pause
    exit /b 1
)

REM ── Install dependencies ──
echo [1/4] Installing dependencies...
pip install -r requirements.txt --quiet 2>nul
echo       Done.

REM ── Check FFmpeg ──
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [WARN] FFmpeg not found in PATH.
    echo        Install from https://ffmpeg.org/download.html
    echo.
)

REM ── Check Redis and start Celery ──
echo [2/4] Checking Redis...
redis-cli ping >nul 2>&1
if %errorlevel%==0 (
    echo       Redis is running.
    echo [3/4] Starting Celery worker...
    start "Celery Worker" /MIN /D "%~dp0" celery -A celery_worker.celery_app worker --loglevel=info --pool=solo
    timeout /t 2 /nobreak >nul
    echo       Celery worker started.
) else (
    echo       Redis not running - skipping Celery.
    echo       POST /api/call-analytics works without Redis.
    echo [3/4] Skipped Celery.
)

REM ── Start Server ──
echo [4/4] Starting FastAPI server...
echo.
echo  =============================================
echo    Server:   http://localhost:8000
echo    API:      POST /api/call-analytics
echo    API Key:  sk_track3_987654321
echo  =============================================
echo.
echo  Press Ctrl+C to stop.
echo.

REM ── Open browser ──
start "" http://localhost:8000

REM ── Run server (blocks here) ──
python -m uvicorn main:app --host 0.0.0.0 --port 8000
