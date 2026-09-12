@echo off
cd /d "%~dp0"
title auto-grab
echo ============================================================
echo   Starting auto-grab (Screen OCR AutoClicker)...
echo   Global Kill-Switch: Press F8 anytime to stop
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python environment not found: .venv\Scripts\python.exe
    pause
    exit /b 1
)

".venv\Scripts\python.exe" "main.py"
if errorlevel 1 (
    echo.
    echo Application exited with error code %errorlevel%.
    pause
)
