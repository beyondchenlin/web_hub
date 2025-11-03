@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   多论坛监控系统启动脚本
echo ========================================
echo.

REM 设置Python路径
set PYTHON_PATH=tts\indextts2\py312\python.exe

REM 检查Python是否存在
if not exist "%PYTHON_PATH%" (
    echo [错误] 找不到Python: %PYTHON_PATH%
    pause
    exit /b 1
)

echo [1/3] 检查Python环境...
"%PYTHON_PATH%" --version
if errorlevel 1 (
    echo [错误] Python环境异常
    pause
    exit /b 1
)
echo [✓] Python环境正常
echo.

echo [2/3] 检查配置文件...
if not exist "config\forum_settings.yaml" (
    echo [错误] 找不到配置文件: config\forum_settings.yaml
    pause
    exit /b 1
)
echo [✓] 配置文件存在
echo.

echo [3/3] 启动多论坛监控...
echo.
echo ========================================
echo   正在启动多论坛监控系统...
echo ========================================
echo.
echo 提示：
echo - 按 Ctrl+C 停止监控
echo - 系统将并行监控所有启用的论坛
echo - 日志将输出到控制台
echo.

REM 启动多论坛监控
cd web_hub
"%PYTHON_PATH%" multi_forum_crawler.py

REM 如果异常退出，暂停以查看错误
if errorlevel 1 (
    echo.
    echo [错误] 多论坛监控异常退出
    pause
)

endlocal

