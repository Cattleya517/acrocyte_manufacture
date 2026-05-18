@echo off
chcp 65001 >nul
REM acrocyte_manufacture - Windows 雙擊安裝入口
REM 雙擊此檔案即可開始安裝，無需手動處理 PowerShell 執行原則
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
echo.
echo 按任意鍵關閉此視窗...
pause >nul
