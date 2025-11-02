"""Utilities to post replies back to forums in a unified way."""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from .forum_crawler_manager import get_forum_crawler_manager
from .task_model import TaskType, UnifiedTask


class ForumReplyManager:
    """Helper responsible for formatting and sending forum replies."""

    def __init__(self) -> None:
        self._crawler_manager = get_forum_crawler_manager()

    # ------------------------------------------------------------------
    # Low level API
    # ------------------------------------------------------------------
    def reply_to_post(
        self,
        post_id: str,
        content: str,
        attachments: Optional[List[str]] = None,
        forum_name: str = "main",
    ) -> bool:
        crawler = self._crawler_manager.get_crawler(forum_name)
        if not getattr(crawler, "logged_in", False):
            crawler.login()
        return crawler.reply_to_thread(post_id, content, attachments or None)

    # ------------------------------------------------------------------
    # High level helpers
    # ------------------------------------------------------------------
    def reply_with_task_result(
        self,
        task: UnifiedTask,
        reply_payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        payload = reply_payload or self._build_reply_payload(task)
        content = payload.get("content") or "任务处理完成。"
        attachments = payload.get("attachments") or payload.get("files") or []
        forum_info = task.get_forum_info()
        forum_name = forum_info.get("forum_name") or "main"
        post_id = forum_info.get("post_id")
        if not post_id:
            return False
        return self.reply_to_post(post_id, content, attachments, forum_name)

    def _build_reply_payload(self, task: UnifiedTask) -> Dict[str, Any]:
        if task.is_tts_task():
            from services.tts_service import TTSTaskService

            service = TTSTaskService()
            return service.format_forum_reply(
                {
                    **task.metadata,
                    **(task.result or {}),
                    "request_type": task.task_type.value,
                }
            )
        if task.task_type == TaskType.VIDEO:
            return {
                "content": self._build_video_reply_text(task),
                "attachments": task.output_files,
            }
        # Fallback generic reply
        return {"content": "任务处理完成。"}

    def _build_video_reply_text(self, task: UnifiedTask) -> str:
        lines = ["✅ 视频处理完成！"]
        if task.source_url:
            lines.append(f"原始链接：{task.source_url}")
        if task.output_files:
            lines.append(f"输出文件数量：{len(task.output_files)}")
        lines.append("感谢使用自动化处理服务。")
        return "\n".join(lines)


_REPLY_MANAGER_SINGLETON: Optional[ForumReplyManager] = None
_REPLY_MANAGER_LOCK = threading.Lock()


def get_forum_reply_manager() -> ForumReplyManager:
    global _REPLY_MANAGER_SINGLETON
    if _REPLY_MANAGER_SINGLETON is None:
        with _REPLY_MANAGER_LOCK:
            if _REPLY_MANAGER_SINGLETON is None:
                _REPLY_MANAGER_SINGLETON = ForumReplyManager()
    return _REPLY_MANAGER_SINGLETON


__all__ = ["ForumReplyManager", "get_forum_reply_manager"]

