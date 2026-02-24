@echo off
chcp 65001 >nul 2>&1
cls
echo ========================================
echo   TTS监控节点启动
echo ========================================
echo.
REM ================================================================
REM 克隆/并行运行防冲突说明:
REM 1) 同机多项目必须使用不同端口（当前 clonetts 约定 monitor=8100）
REM 2) 必须设置独立 REDIS_PREFIX（当前为 clonetts_monitor:）
REM 3) 监控Redis库建议独立（当前 MONITOR_REDIS_DB=1）
REM 4) 修改端口后，请同步 web_hub\cluster_monitor\machines.txt
REM ================================================================
set REDIS_PREFIX=clonetts_monitor:
set MONITOR_REDIS_DB=1

tts\indextts2\py312\python.exe web_hub\cluster_monitor\start_unified.py --mode production --port 8100

pause

