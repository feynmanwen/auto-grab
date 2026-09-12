@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 自動文字偵測點選工具 (Screen OCR AutoClicker)
echo ============================================================
echo   正在啟動 自動文字偵測點選工具 (auto-grab)...
echo   全域緊急停止快捷鍵: F8
echo ============================================================
echo.

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [錯誤] 找不到虛擬環境 Python: %~dp0.venv\Scripts\python.exe
    pause
    exit /b 1
)

"%~dp0.venv\Scripts\python.exe" "%~dp0main.py"
if errorlevel 1 (
    echo.
    echo 程式異常結束，結束代碼: %errorlevel%
    pause
)
