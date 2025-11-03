@echo off
chcp 65001 >nul
echo ============================================================
echo   TTS论坛自动化系统 - 启动监控节点
echo ============================================================
echo.

set PYTHON=tts\indextts2\py312\python.exe

echo 检查Python环境...
if not exist "%PYTHON%" (
    echo ❌ Python环境不存在: %PYTHON%
    pause
    exit /b 1
)
echo ✅ Python环境: %PYTHON%
echo.

echo 检查数据库...
if not exist "tts\custom_integration\integration\database\tts_voice_system.db" (
    echo ❌ TTS数据库不存在，请先运行初始化
    echo    运行: cd tts\custom_integration\integration ^&^& ..\..\..\tts\indextts2\py312\python.exe tts_init_db.py
    pause
    exit /b 1
)
echo ✅ TTS数据库已就绪
echo.

echo ============================================================
echo   启动监控节点 (端口: 8000)
echo ============================================================
echo.
echo 监控节点将会:
echo   1. 监控论坛新帖 (https://tts.lrtcai.com/forum-2-1.html)
echo   2. 自动处理【音色克隆】和【制作AI声音】请求
echo   3. 验证用户权限和配额
echo   4. 调用TTS引擎生成音频
echo   5. 自动回复论坛
echo.
echo 按 Ctrl+C 停止监控
echo.

"%PYTHON%" web_hub\cluster_monitor\start_unified.py --mode production --port 8000

pause

