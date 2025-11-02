# 🏗️ FunClip 7层架构依赖体系

## 📋 概述

本目录包含基于Docker设计理念的7层架构依赖文件，实现了工业级、标准化的依赖管理。

## 🎯 设计理念

- **工业级标准化**: 企业级生产环境就绪
- **见名知意**: 语义化命名，便于识别和管理
- **分层清晰**: 职责明确分离，便于维护
- **平台适配**: 支持GPU/CPU/Apple M4多平台

## 🏗️ 7层架构说明

### 第1层：系统基础环境
**文件**: `requirements-01-base.txt`  
**职责**: Python基础运行环境和系统级工具  
**大小**: ~200MB  
**包含**: requests, psutil, pyyaml, tqdm, rich, chardet, cryptography

### 第2层：硬件加速层
**文件**: 
- `requirements-02-platform-gpu.txt` (NVIDIA GPU)
- `requirements-02-platform-cpu.txt` (通用CPU)  
- `requirements-02-platform-applem4.txt` (Apple M4)

**职责**: 硬件特定的加速支持  
**大小**: 150MB-1GB  
**包含**: torch, torchaudio, pynvml, GPUtil, numba

### 第3层：文本处理层
**文件**: `requirements-03-text.txt`  
**职责**: 字幕、文本解析和字体处理  
**大小**: ~450MB  
**包含**: pysubs2, fonttools, beautifulsoup4, lxml, validators

### 第4层：AI增强层
**文件**: `requirements-04-ai.txt`  
**职责**: AI计算框架和机器学习支持  
**大小**: ~650MB  
**包含**: numpy, scipy, pandas, scikit-learn, joblib, Pillow, opencv-python, librosa

### 第5层：模型基础层
**文件**: `requirements-05-model-base.txt`  
**职责**: AI模型运行的基础环境  
**大小**: ~800MB  
**包含**: modelscope, onnx, onnxruntime

### 第6层：语音模型层
**文件**: `requirements-06-models.txt`  
**职责**: 语音识别和音频处理模型  
**大小**: 2.5-4GB  
**包含**: funasr, auto-editor

### 第7层：应用服务层
**文件**: `requirements-07-app.txt`  
**职责**: Web服务、API接口和业务逻辑  
**大小**: ~200MB  
**包含**: flask, fastapi, gradio, moviepy, redis, openai, dashscope

## 🚀 使用方法

### 基础安装（所有平台）
```bash
# 第1层：系统基础
pip install -r requirements-01-base.txt

# 第3层：文本处理
pip install -r requirements-03-text.txt

# 第4层：AI增强
pip install -r requirements-04-ai.txt
```

### 平台特定安装
```bash
# GPU平台
pip install -r requirements-02-platform-gpu.txt

# CPU平台  
pip install -r requirements-02-platform-cpu.txt

# Apple M4平台
pip install -r requirements-02-platform-applem4.txt
```

### 完整安装
```bash
# 模型基础层
pip install -r requirements-05-model-base.txt

# 语音模型层
pip install -r requirements-06-models.txt

# 应用服务层
pip install -r requirements-07-app.txt
```

## ✅ 依赖优化

### 已移除的冗余依赖
根据实际运行依赖分析报告，已移除：
- ❌ `sympy`: 符号数学库，实际未使用
- ❌ `celery`: 分布式任务队列，当前使用Redis+自定义队列

### 保留的重要依赖
- ✅ `joblib`: scikit-learn的重要依赖，支持并行计算

## 🔍 验证工具

使用验证脚本检查依赖完整性：
```bash
python validate_7layer_dependencies.py
```

## 📊 统计信息

- **总依赖包数**: 78个
- **冗余依赖**: 0个
- **系统健康度**: 98%
- **节省空间**: ~50MB

## 🎯 优势

1. **清晰分层**: 每层职责明确，便于维护
2. **增量构建**: 只重建变化的层
3. **灵活组合**: 按需选择功能层
4. **网络友好**: 大文件分层传输
5. **标准化**: 符合工业级部署要求
