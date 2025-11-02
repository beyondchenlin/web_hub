#!/bin/bash
# 🚀 FunClip 依赖一键安装脚本
# 严格按照正确顺序安装，避免依赖冲突

set -e  # 遇到错误立即退出

echo "🚀 FunClip 依赖安装脚本"
echo "=========================="

# 检查Python环境
echo "📋 检查Python环境..."
python --version || { echo "❌ Python未安装或不在PATH中"; exit 1; }
pip --version || { echo "❌ pip未安装或不在PATH中"; exit 1; }

# 配置镜像源
echo "🔧 配置阿里云镜像源..."
MIRROR="https://mirrors.aliyun.com/pypi/simple"

# 第1步：核心基础包（必须首先安装）
echo "📦 第1步：安装NumPy（核心依赖）..."
pip install "numpy==2.3.1" -i $MIRROR
python -c "import numpy; print('✅ NumPy版本:', numpy.__version__)"

# 第2步：科学计算包
echo "📦 第2步：安装科学计算包..."
pip install "scipy>=1.15.2,<2.0.0" "pandas>=2.2.3,<3.0.0" -i $MIRROR
pip install "scikit-learn>=1.6.1,<2.0.0" -i $MIRROR
python -c "import scipy, pandas, sklearn; print('✅ 科学计算包安装成功')"

# 第3步：视频音频处理包
echo "📦 第3步：安装视频音频处理包..."
pip install "moviepy==1.0.3" imageio imageio-ffmpeg -i $MIRROR
python -c "from moviepy.editor import VideoFileClip; print('✅ MoviePy安装成功')"

pip install "librosa>=0.10.0,<0.12.0" soundfile -i $MIRROR

# 第4步：auto-editor
echo "📦 第4步：安装auto-editor..."
pip install "auto-editor==28.0.2" -i $MIRROR

echo "📦 修复auto-editor GPU编码支持..."
python -c "
import shutil, auto_editor, os
print('🔧 修复auto-editor GPU编码支持...')
ffmpeg_path = shutil.which('ffmpeg')
if ffmpeg_path:
    ae_path = os.path.dirname(auto_editor.__file__)
    target_path = os.path.join(ae_path, 'ffmpeg')
    shutil.copy2(ffmpeg_path, target_path)
    print('✅ GPU编码修复完成')
    print(f'   源: {ffmpeg_path}')
    print(f'   目标: {target_path}')
else:
    print('❌ 未找到系统FFmpeg，GPU编码可能无法工作')
"

python -c "import auto_editor; print('✅ auto-editor版本:', auto_editor.__version__)"

# 第5步：语音识别包
echo "📦 第5步：安装FunASR..."
pip install "funasr>=1.2.0,<2.0.0" -i $MIRROR
python -c "from funasr import AutoModel; print('✅ FunASR安装成功')"

# 第6步：其他依赖
echo "📦 第6步：安装其他依赖..."
pip install -r requirements-01-base.txt -i $MIRROR
pip install -r requirements-03-text.txt -i $MIRROR

# 检查GPU支持
echo "🔍 检查GPU支持..."
if python -c "import torch; print('CUDA可用:', torch.cuda.is_available())" 2>/dev/null; then
    echo "✅ PyTorch已安装，GPU支持检查完成"
else
    echo "⚠️ 需要安装PyTorch GPU版本"
    echo "请运行: pip install -r requirements-02-platform-gpu.txt"
fi

# 最终验证
echo "🧪 最终验证..."
python -c "
try:
    from funclip.videoclipper import VideoClipper
    from funasr import AutoModel
    import auto_editor
    from moviepy.editor import VideoFileClip
    import numpy as np
    print('🎉 所有核心模块导入成功！')
    print(f'NumPy: {np.__version__}')
    print(f'auto-editor: {auto_editor.__version__}')
except Exception as e:
    print(f'❌ 验证失败: {e}')
    exit(1)
"

echo ""
echo "🎉 安装完成！"
echo "✅ 所有依赖已按正确顺序安装"
echo "✅ 系统已就绪，可以启动FunClip"
echo ""
echo "🚀 启动命令："
echo "python start_lightweight.py --port 8005"
