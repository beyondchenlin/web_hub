@echo off
rem 切到脚本自身目录：脚本内大量使用 %cd%\py312 和 %cd%\logs，
rem 若从父进程 cwd 启动可能找不到 python / 写不出日志
cd /d %~dp0

set GRADIO_TEMP_DIR=%cd%\tmp\
SET PYTHON_PATH=%cd%\py312\
rem overriding default python env vars in order not to interfere with any system python installation
set DS_BUILD_AIO=0
set DS_BUILD_SPARSE_ATTN=0
SET PYTHONHOME=
SET PYTHONPATH=
SET PYTHONEXECUTABLE=%PYTHON_PATH%\python.exe
SET PYTHONWEXECUTABLE=%PYTHON_PATH%pythonw.exe
SET PYTHON_EXECUTABLE=%PYTHON_PATH%\python.exe
SET PYTHONW_EXECUTABLE=%PYTHON_PATH%pythonw.exe
SET PYTHON_BIN_PATH=%PYTHON_EXECUTABLE%
SET PYTHON_LIB_PATH=%PYTHON_PATH%\Lib\site-packages
set CU_PATH=%PYTHON_PATH%\Lib\site-packages\torch\lib
set cuda_PATH=%PYTHON_PATH%\Library\bin
SET FFMPEG_PATH=%cd%\py312\ffmpeg\bin
SET PATH=%PYTHON_PATH%;%PYTHON_PATH%\Scripts;%FFMPEG_PATH%;%CU_PATH%;%cuda_PATH%;%PATH%
set HF_ENDPOINT=https://hf-mirror.com
set HF_HOME=%CD%\checkpoints
set TRANSFORMERS_CACHE=%CD%\tf_download
set XFORMERS_FORCE_DISABLE_TRITON=1
@REM set CUDA_VISIBLE_DEVICES=0
@REM set PYTHONPATH=third_party/AcademiCodec;third_party/Matcha-TTS

if not exist logs mkdir logs
"%PYTHON_EXECUTABLE%" -s app.py >> "%cd%\logs\api_run.log" 2>&1
pause
