@echo off
chcp 65001 >nul 2>&1
cls
echo ========================================
echo   TTS监控节点启动
echo ========================================
echo.

cd web_hub\cluster_monitor
..\..\tts\indextts2\py312\python.exe start_unified.py --mode production --port 8000

pause

