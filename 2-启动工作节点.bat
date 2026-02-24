@echo off
chcp 65001 >nul 2>&1
cls
echo ========================================
echo   TTS工作节点启动
echo ========================================
echo.
REM ================================================================
REM 克隆/并行运行防冲突说明:
REM 1) 同机多项目必须使用不同端口（当前 clonetts 约定 worker=8105）
REM 2) 修改 worker 端口后，请同步 web_hub\cluster_monitor\machines.txt
REM 3) 如与其他副本并行，建议端口按实例递增（如 8115/8125）
REM ================================================================

tts\indextts2\py312\python.exe web_hub\start_lightweight.py --port 8105

pause

