"""
TTS 任务适配器。

适配器负责把 Web Hub 的任务调度层与 `services.tts_service` 对接，
并输出统一的任务状态事件。
"""

from .adapter import TTSModuleAdapter

__all__ = ["TTSModuleAdapter"]

