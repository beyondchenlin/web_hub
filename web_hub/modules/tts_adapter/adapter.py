"""
面向 Web Hub 的 TTS 任务适配器。

后续可以把该适配器注册到统一的任务调度中心，由调度器根据 task_type
调用对应的 `consume` 方法。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from services.tts_service import TTSTaskService


@dataclass
class AdapterResult:
    """任务适配处理后的返回结果。"""

    success: bool
    payload: Dict[str, Any]


class TTSModuleAdapter:
    """对接 Web Hub 与 TTS 服务层的适配器。"""

    supported_task_types = {"tts", "voice_clone"}

    def __init__(self, service: TTSTaskService | None = None) -> None:
        self.service = service or TTSTaskService()

    def consume(self, task_type: str, payload: Dict[str, Any]) -> AdapterResult:
        """
        消费调度层派发的任务。

        Args:
            task_type: 统一任务类型，例如 "tts" 或 "voice_clone"。
            payload: 任务载荷。

        Returns:
            AdapterResult: 标准化结果，供调度层继续后续流程。
        """
        if task_type not in self.supported_task_types:
            return AdapterResult(False, {"error": f"不支持的任务类型: {task_type}"})

        if task_type == "tts":
            result = self.service.handle_tts_task(payload)
        else:
            result = self.service.handle_voice_clone_task(payload)

        # 统一封装回复内容，方便后续回帖或状态上报
        formatted_reply = self.service.format_forum_reply(
            {
                **payload,
                **result.get("result", {}),
                "request_type": task_type,
            }
        )

        merged_payload = {
            "raw_result": result,
            "reply": formatted_reply,
        }

        return AdapterResult(result.get("success", False), merged_payload)

