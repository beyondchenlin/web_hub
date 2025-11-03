@echo off
chcp 65001 >nul
title TTS论坛集成系统 - 工作节点

echo ========================================
echo   TTS论坛集成系统 - 工作节点启动器
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

echo [2/5] 检查Waitress（生产级服务器）...
"%PYTHON_PATH%" -c "import waitress" >nul 2>&1
if errorlevel 1 (
    echo [警告] Waitress未安装，将使用Flask开发服务器
    echo [提示] 建议安装: "%PYTHON_PATH%" -m pip install waitress
) else (
    echo [✓] Waitress已安装（生产级服务器）
)
echo.

echo [3/5] 检查Redis连接...
redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo [错误] Redis未运行
    echo.
    echo 工作节点需要Redis来接收任务队列
    echo 请先启动Redis服务
    pause
    exit /b 1
)
echo [✓] Redis连接正常
echo.

echo [4/5] 检查监控节点...
curl -s http://localhost:8000/api/status >nul 2>&1
if errorlevel 1 (
    echo [警告] 监控节点未运行 (http://localhost:8000)
    echo.
    echo 建议先启动监控节点: 启动监控节点.bat
    echo.
    set /p continue="是否继续启动工作节点? (Y/N): "
    if /i not "%continue%"=="Y" (
        echo 已取消启动
        pause
        exit /b 0
    )
) else (
    echo [✓] 监控节点运行正常
)
echo.

echo [5/5] 启动工作节点...
echo.
echo ========================================
echo   工作节点启动中...
echo   端口: 8005
echo   访问地址: http://localhost:8005
echo ========================================
echo.
echo [提示] 按 Ctrl+C 停止服务
echo.

REM 切换到web_hub目录
cd web_hub

REM 启动工作节点
..\tts\indextts2\py312\python.exe start_lightweight.py --port 8005

REM 如果启动失败
if errorlevel 1 (
    echo.
    echo [错误] 工作节点启动失败
    echo 请查看日志文件: logs\lightweight.log
    cd ..
    pause
    exit /b 1
)

REM 返回根目录
cd ..

echo.
echo [提示] 工作节点已停止
pause

