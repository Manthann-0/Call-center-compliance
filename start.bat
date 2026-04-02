@echo off
echo ============================================
echo   CallCenter Compliance AI — Local Startup
echo ============================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo [1/5] Creating virtual environment...
    python -m venv .venv
) else (
    echo [1/5] Virtual environment already exists.
)

REM Activate virtual environment
echo [2/5] Activating virtual environment...
call .venv\Scripts\activate.bat

REM Install dependencies
echo [3/5] Installing dependencies...
pip install -r requirements.txt --quiet

REM Create uploads directory
if not exist "uploads" mkdir uploads

REM Check if .env has API keys
findstr /C:"SARVAM_API_KEY=" .env | findstr /V /C:"SARVAM_API_KEY=$" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [WARNING] SARVAM_API_KEY is empty in .env
    echo Please add your Sarvam AI API key to .env file
)

findstr /C:"LLM_API_KEY=" .env | findstr /V /C:"LLM_API_KEY=$" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [WARNING] LLM_API_KEY is empty in .env
    echo Get a FREE key at: https://cloud.cerebras.ai
)

echo.
echo [4/5] Starting Celery worker in background...
echo         (Requires Redis running on localhost:6379)
echo         (To start Redis: docker run -d -p 6379:6379 redis:alpine)
echo.
start /B celery -A celery_worker.celery_app worker --loglevel=info --pool=solo --concurrency=1

echo [5/5] Starting FastAPI server...
echo.
echo ============================================
echo   Dashboard: http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo   Health:    http://localhost:8000/health
echo ============================================
echo.
python main.py
