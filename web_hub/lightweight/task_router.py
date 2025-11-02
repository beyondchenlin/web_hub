#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Route unified tasks to the appropriate module adapter."""

from __future__ import annotations

from typing import Any, Dict, Optional

from shared.task_model import TaskType, UnifiedTask
from .logger import get_logger


class TaskRouter:
    """Dispatch tasks to adapters based on task type."""

    def __init__(self, config) -> None:
        self.config = config
        self.logger = get_logger("TaskRouter")
        self.adapters: Dict[TaskType, Any] = {}
        self._load_adapters()

    def _load_adapters(self) -> None:
        try:
            from modules.tts_adapter import TTSModuleAdapter

            adapter = TTSModuleAdapter()
            self.adapters[TaskType.TTS] = adapter
            self.adapters[TaskType.VOICE_CLONE] = adapter
            self.logger.info("TTS适配器已加载")
        except Exception as exc:  # pragma: no cover - protective logging
            self.logger.error(f"TTS适配器加载失败: {exc}")

        # 预留：可在此处注册其他任务类型适配器（视频、图片等）

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def can_handle(self, task: UnifiedTask) -> bool:
        return task.task_type in self.adapters

    def route(self, task: UnifiedTask) -> Dict[str, Any]:
        adapter = self.adapters.get(task.task_type)
        if not adapter:
            error = f"没有可用的适配器处理任务类型: {task.task_type.value}"
            self.logger.error(error)
            return {"success": False, "error": error}

        try:
            result = adapter.consume(task.task_type, {**task.payload, **task.metadata})
            return {
                "success": result.success,
                "result": result.payload,
                "reply": result.payload.get("reply"),
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.exception(f"任务路由异常: {exc}")
            return {"success": False, "error": str(exc)}


__all__ = ["TaskRouter"]

