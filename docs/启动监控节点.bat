@echo off
chcp 65001 >nul
title TTS论坛集成系统 - 监控节点

echo ========================================
echo   TTS论坛集成系统 - 监控节点启动器
echo ========================================
echo.

REM 设置Python路径
set PYTHON_PATH=tts\indextts2\py312\python.exe

REM 检查Python是否存在
if not exist "%PYTHON_PATH%" (
    echo [错误] 找不到Python环境: %PYTHON_PATH%
    echo.
    echo 请确认Python路径是否正确
    pause
    exit /b 1
)

echo [1/5] 检查Python环境...
"%PYTHON_PATH%" --version
if errorlevel 1 (
    echo [错误] Python环境异常
    pause
    exit /b 1
)
echo [✓] Python环境正常
echo.

echo [2/5] 检查数据库...
if not exist "tts\custom_integration\integration\database\tts_voice_system.db" (
    echo [警告] 数据库不存在，正在初始化...
    "%PYTHON_PATH%" tts\custom_integration\integration\tts_init_db.py
    if errorlevel 1 (
        echo [错误] 数据库初始化失败
        pause
        exit /b 1
    )
    echo [✓] 数据库初始化完成
) else (
    echo [✓] 数据库已存在
)
echo.

echo [3/5] 检查Redis连接...
redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo [警告] Redis未运行或未安装
    echo [提示] 系统将继续启动，但任务队列功能可能不可用
) else (
    echo [✓] Redis连接正常
)
echo.

echo [4/5] 检查配置文件...
if not exist "config\forum_settings.yaml" (
    echo [错误] 找不到配置文件: config\forum_settings.yaml
    pause
    exit /b 1
)
echo [✓] 配置文件存在
echo.

echo [5/5] 启动监控节点...
echo.
echo ========================================
echo   监控节点启动中...
echo   端口: 8000
echo   访问地址: http://localhost:8000
echo ========================================
echo.
echo [提示] 按 Ctrl+C 停止服务
echo.

REM 切换到监控节点目录
cd web_hub\cluster_monitor

REM 启动监控节点
..\..\tts\indextts2\py312\python.exe start_unified.py --mode production --port 8000

REM 如果启动失败
if errorlevel 1 (
    echo.
    echo [错误] 监控节点启动失败
    echo 请查看日志文件: logs\forum_monitor.log
    cd ..\..
    pause
    exit /b 1
)

REM 返回根目录
cd ..\..

echo.
echo [提示] 监控节点已停止
pause

