@echo off
chcp 65001 >nul 2>&1
cls
echo ========================================
echo   TTS工作节点启动
echo ========================================
echo.

tts\indextts2\py312\python.exe web_hub\start_lightweight.py --port 8005

pause

