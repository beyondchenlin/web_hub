@echo off
chcp 65001 >nul 2>&1
cls
echo ========================================
echo   TTS工作节点启动
echo ========================================
echo.

cd web_hub
..\tts\indextts2\py312\python.exe start_lightweight.py --port 8005

pause

