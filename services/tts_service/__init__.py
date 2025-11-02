"""
TTS 服务封装层。

这里负责把 Web Hub 的任务数据转换为 IndexTTS2 集成模块可以识别的格式，
并在处理完成后输出统一的结果数据结构。
"""

from .service import TTSTaskService

__all__ = ["TTSTaskService"]

