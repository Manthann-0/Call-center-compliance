@echo off
echo ============================================
echo   CallCenter Compliance AI
echo ============================================

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet

REM Create uploads directory
if not exist "uploads" mkdir uploads

REM Start Redis in Docker
echo Starting Redis...
start /B docker run --rm -p 6379:6379 redis:alpine
timeout /t 3 /nobreak >nul

REM Start Celery worker
echo Starting Celery worker...
start /B celery -A celery_worker.celery_app worker --loglevel=info --pool=solo
timeout /t 2 /nobreak >nul

REM Start FastAPI server and open browser
echo Starting server...
echo.
echo Dashboard: http://localhost:8000
echo.
start http://localhost:8000
python main.py
