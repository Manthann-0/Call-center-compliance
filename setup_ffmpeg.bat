@echo off
echo ============================================
echo   FFmpeg PATH Setup for Windows
echo ============================================
echo.

REM Check if ffmpeg is already in PATH
ffmpeg -version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] ffmpeg is already installed and in PATH
    echo.
    ffmpeg -version | findstr "ffmpeg version"
    pause
    exit /b 0
)

echo [INFO] ffmpeg not found in PATH
echo.
echo Please follow these steps:
echo.
echo 1. Download ffmpeg from: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
echo 2. Extract to C:\ffmpeg
echo 3. Run this script again to add to PATH automatically
echo.

REM Check if ffmpeg exists in C:\ffmpeg
if exist "C:\ffmpeg\bin\ffmpeg.exe" (
    echo [FOUND] ffmpeg detected at C:\ffmpeg\bin\
    echo.
    echo Adding to PATH...
    
    REM Add to user PATH (requires admin for system PATH)
    setx PATH "%PATH%;C:\ffmpeg\bin"
    
    echo.
    echo [SUCCESS] ffmpeg added to PATH!
    echo.
    echo IMPORTANT: Close this window and restart your terminal/IDE
    echo Then run start.bat again
    echo.
) else (
    echo [NOT FOUND] C:\ffmpeg\bin\ffmpeg.exe does not exist
    echo.
    echo Quick Install Option:
    echo   Run: choco install ffmpeg
    echo   (Requires Chocolatey package manager)
    echo.
)

pause
