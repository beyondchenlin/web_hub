@echo off
chcp 65001 >nul 2>&1
cls
echo ========================================
echo   TTS监控节点启动
echo ========================================
echo.

tts\indextts2\py312\python.exe web_hub\cluster_monitor\start_unified.py --mode production --port 8000

pause

