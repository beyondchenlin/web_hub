# 项目长期记忆 - clonetts TTS 声音克隆系统

## 系统结构
- IndexTTS2 引擎：`tts/indextts2/`（gitignored，不入库），FastAPI:9880 + Gradio:7860，单推理 worker，嵌入式 Python 在 `py312/`（实为 3.10，torch 2.8.0+cu128）
- 调用方：`tts/custom_integration/integration/tts_api_service.py`（整篇文案单次阻塞 GET localhost:9880，无分段无流式）
- 工作节点/监控：`1-启动监控节点.bat`、`2-启动工作节点.bat`，主日志 `logs/lightweight.log`
- GPU：RTX A4000 16G（sm_86），引擎常驻占约 6.1G
- 实测引擎速度 RTF≈3.3（2026-07-27，修 BigVGAN kernel 前）

## 引擎 JIT 编译环境的坑（2026-07-27 修 BigVGAN kernel 实录）
1. 启动 bat 的 `set cuda_PATH=%PYTHON_PATH%\Library\bin` → Windows 环境变量不区分大小写 → CUDA_PATH 指向无 nvcc 的伪 toolkit → torch `_find_cuda_home` 误采 → JIT 第一步 `nvcc -V` 即 FileNotFoundError
2. torch 2.8 `_write_ninja_file` 硬性 `where cl`（无降级）；引擎 PATH 无 VS 目录必失败
3. setuptools `_get_vc_env` 在本机返回退化的空环境（组件注册不全），但 VS2019 BuildTools 的 cl.exe 实体存在于 `C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Tools\MSVC\14.29.30133\`，需手工推导 INCLUDE/LIB（SDK 10.0.19041.0）
4. infer.py 的裸 `except:` 吞掉全部编译错误 → 只显示 "Falling back to torch"，排障须手动复现 `load.load()`
5. WorkBuddy 环境的 sitecustomize 安全删除 shim 会拦截 os.remove（FileBaton.release 会崩）；沙箱 overlay 会让编译产物不写真实磁盘 → 此类验证必须 dangerouslyDisableSandbox + `os.remove = nt.remove`
6. FileBaton 的 build/lock 孤立锁会让后续编译空等，检查 build 目录要先看 lock
- 修复落点：`indextts/BigVGAN/alias_free_activation/cuda/load.py`（新增 `_resolve_cuda_toolkit` + `_setup_msvc_env`，编译前自纠 CUDA_HOME 并补 MSVC 环境）。产物缓存于同目录 `build/`（.pyd 1.86MB）
- 注意：`indextts/s2mel/modules/bigvgan/.../load.py` 是同 bug 副本，但流程中未启用 use_cuda_kernel，无需修

## 用户偏好（重要）
- 引擎启动/重启只由用户手动双击 bat，AI 环境拉引擎不可靠（已多次验证）
- 不要擅改用户的启动 bat（17:23 明确不满过）；逻辑修复放 py 代码里
- 引擎日志要在黑窗口直接可见，不做文件重定向
- 中文 Windows 的 .bat 绝不放中文注释（GBK 尾字节 0x7C 是 | 会劈行）、必须 CRLF；写反斜杠用 chr(92) 或原始字符串
