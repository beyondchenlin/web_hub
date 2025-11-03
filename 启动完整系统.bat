@echo off
chcp 65001 >nul
title TTS论坛集成系统 - 完整系统启动器

echo ========================================
echo   TTS论坛集成系统 - 完整系统启动器
echo ========================================
echo.
echo 本脚本将启动：
echo   1. 监控节点 (端口 8000)
echo   2. 工作节点 (端口 8005)
echo.
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

echo [1/6] 检查Python环境...
"%PYTHON_PATH%" --version
if errorlevel 1 (
    echo [错误] Python环境异常
    pause
    exit /b 1
)
echo [✓] Python环境正常
echo.

echo [2/6] 检查数据库...
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

echo [3/6] 检查Redis连接...
redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo [错误] Redis未运行
    echo.
    echo 系统需要Redis来管理任务队列
    echo 请先启动Redis服务
    echo.
    pause
    exit /b 1
)
echo [✓] Redis连接正常
echo.

echo [4/6] 检查配置文件...
if not exist "config\forum_settings.yaml" (
    echo [错误] 找不到配置文件: config\forum_settings.yaml
    pause
    exit /b 1
)
echo [✓] 配置文件存在
echo.

echo [5/6] 检查端口占用...
netstat -ano | findstr ":8000" >nul 2>&1
if not errorlevel 1 (
    echo [警告] 端口 8000 已被占用
    echo 请先关闭占用该端口的程序
    pause
    exit /b 1
)
netstat -ano | findstr ":8005" >nul 2>&1
if not errorlevel 1 (
    echo [警告] 端口 8005 已被占用
    echo 请先关闭占用该端口的程序
    pause
    exit /b 1
)
echo [✓] 端口可用
echo.

echo [6/6] 启动系统...
echo.
echo ========================================
echo   正在启动监控节点...
echo ========================================
echo.

REM 启动监控节点（后台）
start "TTS监控节点" cmd /c "cd web_hub\cluster_monitor && ..\..\tts\indextts2\py312\python.exe start_unified.py --mode production --port 8000"

REM 等待监控节点启动
echo 等待监控节点启动...
timeout /t 5 /nobreak >nul

REM 检查监控节点是否启动成功
curl -s http://localhost:8000/api/status >nul 2>&1
if errorlevel 1 (
    echo [错误] 监控节点启动失败
    echo 请查看监控节点窗口的错误信息
    pause
    exit /b 1
)
echo [✓] 监控节点启动成功 (http://localhost:8000)
echo.

echo ========================================
echo   正在启动工作节点...
echo ========================================
echo.

REM 启动工作节点（后台）
start "TTS工作节点" cmd /c "cd web_hub && ..\tts\indextts2\py312\python.exe start_lightweight.py --port 8005"

REM 等待工作节点启动
echo 等待工作节点启动...
timeout /t 5 /nobreak >nul

REM 检查工作节点是否启动成功
curl -s http://localhost:8005/health >nul 2>&1
if errorlevel 1 (
    echo [警告] 工作节点可能启动失败
    echo 请查看工作节点窗口的错误信息
) else (
    echo [✓] 工作节点启动成功 (http://localhost:8005)
)
echo.

echo ========================================
echo   系统启动完成！
echo ========================================
echo.
echo 监控节点: http://localhost:8000
echo 工作节点: http://localhost:8005
echo.
echo [提示] 关闭此窗口不会停止服务
echo [提示] 要停止服务，请关闭对应的窗口
echo.
echo 正在打开监控界面...
timeout /t 2 /nobreak >nul

REM 打开浏览器
start http://localhost:8000

echo.
echo 按任意键退出此窗口（服务将继续运行）...
pause >nul

