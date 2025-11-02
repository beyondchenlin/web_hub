"""
TTSTaskService 封装 IndexTTS2 集成模块，为 Web Hub 提供统一的任务处理接口。

当前实现仅作为骨架，提供路径注入、模块加载和方法占位。后续可在此处
实现真正的任务消费、状态回写与错误处理逻辑。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional


class TTSTaskService:
    """封装 TTS/音色克隆任务处理的服务层接口。"""

    def __init__(self, integration_root: Optional[Path | str] = None) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        default_root = repo_root / "tts" / "custom_integration" / "integration"

        self.integration_root = Path(integration_root or default_root).resolve()
        if not self.integration_root.exists():
            raise FileNotFoundError(f"未找到 TTS 集成目录: {self.integration_root}")

        self._ensure_sys_path()

        # 延迟加载实际模块，避免在初始化时产生副作用
        self._api_service_cls = None
        self._processor_cls = None
        self._reply_uploader_cls = None

    # ------------------------------------------------------------------ #
    # 模块加载与公共工具
    # ------------------------------------------------------------------ #
    def _ensure_sys_path(self) -> None:
        """确保集成目录在 sys.path 中，便于后续按模块名导入。"""
        path_str = str(self.integration_root)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    def _load_api_service(self):
        if self._api_service_cls is None:
            from tts_api_service import TTSAPIService

            self._api_service_cls = TTSAPIService
        return self._api_service_cls()

    def _load_processor(self):
        if self._processor_cls is None:
            from tts_forum_processor import TTSForumProcessor

            self._processor_cls = TTSForumProcessor
        return self._processor_cls()

    def _load_reply_uploader(self):
        if self._reply_uploader_cls is None:
            from tts_forum_reply_uploader import TTSForumReplyUploader

            self._reply_uploader_cls = TTSForumReplyUploader
        return self._reply_uploader_cls()

    # ------------------------------------------------------------------ #
    # 任务处理占位方法
    # ------------------------------------------------------------------ #
    def handle_tts_task(self, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理语音合成任务。

        Args:
            task_payload: 统一任务结构中的 payload 字段。

        Returns:
            标准化的处理结果，具体结构待后续统一规范。
        """
        api_service = self._load_api_service()
        success, result = api_service.process_tts_request(task_payload)
        return {"success": success, "result": result}

    def handle_voice_clone_task(self, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理音色克隆任务。

        Args:
            task_payload: 统一任务结构中的 payload 字段。

        Returns:
            标准化的处理结果。
        """
        api_service = self._load_api_service()
        success, result = api_service.process_voice_clone_request(task_payload)
        return {"success": success, "result": result}

    def format_forum_reply(self, processed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用现有回复模块生成论坛回帖内容，统一封装返回结构。

        Args:
            processed_data: 需要回帖的数据。

        Returns:
            包含回帖正文与附件信息的字典。
        """
        reply_uploader = self._load_reply_uploader()
        reply_type = processed_data.get("request_type")

        if reply_type == "tts":
            reply_content = reply_uploader._generate_tts_reply(
                processed_data.get("request_id", ""),
                processed_data.get("file_name", ""),
                processed_data.get("file_size_mb", 0.0),
                processed_data.get("user_id", ""),
            )
            attachments = [processed_data.get("output_path")] if processed_data.get("output_path") else []
        elif reply_type == "voice_clone":
            reply_content = reply_uploader._generate_voice_clone_reply(
                processed_data.get("request_id", ""),
                processed_data.get("voice_id", ""),
                processed_data.get("voice_name", ""),
                processed_data.get("user_id", ""),
            )
            attachments = []
        else:
            reply_content = f"❌ 未知的任务类型: {reply_type}"
            attachments = []

        return {
            "content": reply_content,
            "attachments": attachments,
        }


__all__ = ["TTSTaskService"]
