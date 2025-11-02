@echo off
REM 🚀 FunClip 依赖安装脚本 (Windows版本)
REM 更新日期：2025-07-04
REM 适用于：Python 3.10 + CUDA 12.4

echo ============================================================
echo 🚀 FunClip 依赖安装脚本 (6阶段严格顺序)
echo ============================================================
echo.

REM 检查Python版本
echo 📋 检查Python环境...
python --version
if %errorlevel% neq 0 (
    echo ❌ Python未安装或不在PATH中
    pause
    exit /b 1
)

REM 检查conda环境
echo 📋 当前conda环境：
conda info --envs | findstr "*"

echo.
echo ⚠️  请确保：
echo    1. Python版本是 3.10.x
echo    2. 已激活 zhibocut 环境
echo    3. 有本地PyTorch wheel文件
echo.
set /p confirm="确认继续安装？(y/N): "
if /i not "%confirm%"=="y" (
    echo 安装已取消
    pause
    exit /b 0
)

echo.
echo ============================================================
echo 🎯 第1阶段：核心基础层
echo ============================================================

echo 📦 Step 1.1: 安装NumPy (最关键！)
pip install "numpy==2.3.1" -i https://mirrors.aliyun.com/pypi/simple
if %errorlevel% neq 0 (
    echo ❌ NumPy安装失败
    pause
    exit /b 1
)

echo 📦 Step 1.2: 验证NumPy
python -c "import numpy; print('✅ NumPy版本:', numpy.__version__)"
if %errorlevel% neq 0 (
    echo ❌ NumPy验证失败
    pause
    exit /b 1
)

echo 📦 Step 1.3: 安装系统基础工具
pip install -r requirements/requirements-01-base.txt -i https://mirrors.aliyun.com/pypi/simple
if %errorlevel% neq 0 (
    echo ❌ 基础工具安装失败
    pause
    exit /b 1
)

echo 📦 验证第1阶段
python -c "import requests, psutil, yaml; print('✅ 基础层安装成功')"

echo.
echo ============================================================
echo 🔧 第2阶段：平台硬件层 (GPU支持)
echo ============================================================

echo 📦 Step 2.1: 卸载现有PyTorch
pip uninstall torch torchaudio torchvision -y

echo 📦 Step 2.2: 安装PyTorch GPU版本 (本地wheel文件)
echo ⚠️  请确保wheel文件路径正确
set TORCH_PATH=D:\BaiduNetdiskDownload\torch-2.6.0+cu124-cp310-cp310-win_amd64.whl
set TORCHVISION_PATH=D:\BaiduNetdiskDownload\torchvision-0.21.0+cu124-cp310-cp310-win_amd64.whl
set TORCHAUDIO_PATH=D:\BaiduNetdiskDownload\torchaudio-2.6.0+cu124-cp310-cp310-win_amd64.whl

if not exist "%TORCH_PATH%" (
    echo ❌ 找不到torch wheel文件: %TORCH_PATH%
    echo 请检查文件路径或使用在线安装
    set /p use_online="使用在线安装PyTorch？(y/N): "
    if /i "%use_online%"=="y" (
        pip install torch==2.6.0+cu124 torchvision==0.21.0+cu124 torchaudio==2.6.0+cu124 --index-url https://download.pytorch.org/whl/cu124
    ) else (
        echo 安装已取消
        pause
        exit /b 1
    )
) else (
    pip install "%TORCH_PATH%" -i https://mirrors.aliyun.com/pypi/simple
    pip install "%TORCHVISION_PATH%" -i https://mirrors.aliyun.com/pypi/simple
    pip install "%TORCHAUDIO_PATH%" -i https://mirrors.aliyun.com/pypi/simple
)

echo 📦 Step 2.3: 安装GPU监控工具
pip install "pynvml>=11.5.0,<13.0.0" "GPUtil>=1.4.0,<2.0.0" -i https://mirrors.aliyun.com/pypi/simple

echo 📦 Step 2.4: 安装GPU加速计算包
pip install "numba>=0.58.0,<1.0.0" "llvmlite>=0.40.0,<1.0.0" -i https://mirrors.aliyun.com/pypi/simple

echo 📦 验证第2阶段
python -c "import torch; print('✅ PyTorch版本:', torch.__version__); print('✅ CUDA可用:', torch.cuda.is_available())"

echo.
echo ============================================================
echo 🧮 第3阶段：科学计算层
echo ============================================================

echo 📦 Step 3.1: 安装科学计算核心包
pip install "scipy>=1.15.2,<2.0.0" -i https://mirrors.aliyun.com/pypi/simple
pip install "pandas>=2.2.3,<3.0.0" -i https://mirrors.aliyun.com/pypi/simple
pip install "scikit-learn>=1.6.1,<2.0.0" -i https://mirrors.aliyun.com/pypi/simple

echo 📦 Step 3.2: 安装图像和绘图包
pip install "matplotlib>=3.7.0,<4.0.0" -i https://mirrors.aliyun.com/pypi/simple
pip install "pillow>=10.0.0,<12.0.0" -i https://mirrors.aliyun.com/pypi/simple

echo 📦 验证第3阶段
python -c "import scipy, pandas, sklearn, matplotlib; print('✅ 科学计算层安装成功')"

echo.
echo ============================================================
echo 🎵 第4阶段：音视频处理层
echo ============================================================

echo 📦 Step 4.1: 安装FFmpeg系统依赖
conda install ffmpeg -c conda-forge -y

echo 📦 Step 4.2: 重新安装MoviePy稳定版本
pip uninstall moviepy imageio imageio-ffmpeg -y
pip install "moviepy==1.0.3" "imageio>=2.31.0,<3.0.0" "imageio-ffmpeg>=0.6.0" -i https://mirrors.aliyun.com/pypi/simple

echo 📦 Step 4.3: 安装音频处理包
pip install "librosa>=0.10.0,<0.12.0" "soundfile>=0.12.0,<1.0.0" -i https://mirrors.aliyun.com/pypi/simple
pip install "resampy>=0.4.0,<1.0.0" -i https://mirrors.aliyun.com/pypi/simple

echo 📦 验证第4阶段
python -c "from moviepy.editor import VideoFileClip; import librosa; print('✅ 音视频处理层安装成功')"

echo.
echo ============================================================
echo 🤖 第5阶段：AI和语音识别层
echo ============================================================

echo 📦 Step 5.1: 安装auto-editor
pip install "auto-editor==28.0.2" -i https://mirrors.aliyun.com/pypi/simple

echo 📦 Step 5.2: 修复auto-editor GPU编码支持 (重要！)
echo ⚠️  修复NVIDIA GPU编码器支持...
python -c "
import shutil, auto_editor, os
print('🔧 修复auto-editor GPU编码支持...')
ffmpeg_path = shutil.which('ffmpeg')
if ffmpeg_path:
    ae_path = os.path.dirname(auto_editor.__file__)
    target_path = os.path.join(ae_path, 'ffmpeg.exe')
    shutil.copy2(ffmpeg_path, target_path)
    print('✅ GPU编码修复完成')
    print(f'   源: {ffmpeg_path}')
    print(f'   目标: {target_path}')
else:
    print('❌ 未找到系统FFmpeg，GPU编码可能无法工作')
"

echo 📦 Step 5.3: 安装语音识别包
pip install "funasr>=1.2.0,<2.0.0" -i https://mirrors.aliyun.com/pypi/simple

echo 📦 验证第5阶段
python -c "import auto_editor; from funasr import AutoModel; print('✅ AI层安装成功')"

echo.
echo ============================================================
echo 🌐 第6阶段：应用服务层
echo ============================================================

echo 📦 Step 6.1: 安装Web框架
pip install "flask>=2.3.3,<4.0.0" "werkzeug>=2.3.7,<4.0.0" -i https://mirrors.aliyun.com/pypi/simple

echo 📦 Step 6.2: 安装AI接口
pip install "dashscope>=1.14.0,<2.0.0" "openai>=1.0.0,<2.0.0" -i https://mirrors.aliyun.com/pypi/simple

echo 📦 Step 6.3: 安装可选Redis支持
set /p install_redis="是否安装Redis支持？(y/N): "
if /i "%install_redis%"=="y" (
    pip install "redis>=5.0.0,<6.0.0" "hiredis>=2.2.0,<3.0.0" -i https://mirrors.aliyun.com/pypi/simple
)

echo 📦 验证第6阶段
python -c "import flask, dashscope; print('✅ 应用服务层安装成功')"

echo.
echo ============================================================
echo ✅ 最终系统验证
echo ============================================================

echo 📦 运行完整功能测试...
python -c "
import numpy as np
import torch
import moviepy.editor
import auto_editor
from funasr import AutoModel
import flask
import dashscope

print('🎉 所有核心模块导入成功！')
print(f'✅ Python: {__import__('sys').version_info[:2]}')
print(f'✅ NumPy: {np.__version__}')
print(f'✅ PyTorch: {torch.__version__}')
print(f'✅ CUDA可用: {torch.cuda.is_available()}')
print(f'✅ auto-editor: {auto_editor.__version__}')
print('✅ MoviePy: 可用')
print('✅ FunASR: 可用')
print('✅ Flask: 可用')
print('✅ DashScope: 可用')
"

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo 🎉 安装完成！
    echo ============================================================
    echo ✅ 所有依赖安装成功
    echo 🚀 可以运行: python start_lightweight.py --port 8005
    echo 🌐 Web界面: http://localhost:8005
    echo ============================================================
) else (
    echo.
    echo ❌ 系统验证失败，请检查错误信息
)

echo.
pause
