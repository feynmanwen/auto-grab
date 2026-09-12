@echo off
chcp 65001 >nul
title auto-grab 建立桌面捷徑
cd /d "%~dp0"

echo 正在為您在 Windows 桌面上建立 [auto-grab 自動文字點選] 捷徑...

powershell -NoProfile -Command "$Wsh = New-Object -ComObject WScript.Shell; $Desk = [System.Environment]::GetFolderPath('Desktop'); $Tgt = Join-Path '%~dp0' 'run.bat'; $lnk = $Wsh.CreateShortcut((Join-Path $Desk 'auto-grab 自動文字點選.lnk')); $lnk.TargetPath = $Tgt; $lnk.WorkingDirectory = '%~dp0'; $lnk.Description = 'auto-grab 智慧文字辨識自動點選工具'; $lnk.IconLocation = 'shell32.dll,22'; $lnk.Save(); Write-Host '桌面捷徑建立成功！'"

echo.
timeout /t 3 >nul
exit /b 0
