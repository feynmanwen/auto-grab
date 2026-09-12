@echo off
cd /d "%~dp0"
echo Starting Screen OCR AutoClicker...
"%~dp0.venv\Scripts\python.exe" "%~dp0main.py"
if errorlevel 1 (
    echo.
    echo Application exited with error code %errorlevel%.
    pause
)
