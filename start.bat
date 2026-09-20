@echo off
chcp 65001 >nul
title TermGuard - Game L10n QA Tool
cd /d %~dp0

echo ============================================
echo   TermGuard 术语卫士 - Game L10n QA
echo   http://127.0.0.1:8010
echo   按 Ctrl+C 停止服务
echo ============================================
echo.

start "" http://127.0.0.1:8010
backend\.venv\Scripts\python.exe backend\main.py

pause
