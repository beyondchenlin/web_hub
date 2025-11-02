#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Unified task queue manager for lightweight worker nodes."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from queue import Empty, PriorityQueue
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from shared.task_manager import UnifiedTaskManager, get_task_manager
from shared.task_model import (
    TaskPriority as SharedTaskPriority,
    TaskStatus as SharedTaskStatus,
    TaskType,
    UnifiedTask,
)

TaskStatus = SharedTaskStatus
TaskPriority = SharedTaskPriority
VideoTask = UnifiedTask

_ACTIVE_STATUSES = {
    TaskStatus.PENDING,
    TaskStatus.ASSIGNED,
    TaskStatus.DOWNLOADING,
    TaskStatus.PROCESSING,
    TaskStatus.UPLOADING,
}

_TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}


class QueueManager:
    """Coordinate download / process / upload stages for unified tasks."""

    def __init__(self, config: Optional[Any] = None) -> None:
        self.config = config or self._build_default_config()
        self.task_manager: UnifiedTaskManager = get_task_manager(
            redis_host=getattr(self.config, "redis_host", "localhost"),
            redis_port=getattr(self.config, "redis_port", 6379),
            redis_db=getattr(self.config, "redis_db", 0),
            redis_password=getattr(self.config, "redis_password", None),
        )

        self.download_queue: PriorityQueue[UnifiedTask] = PriorityQueue()
        self.process_queue: PriorityQueue[UnifiedTask] = PriorityQueue()
        self.upload_queue: PriorityQueue[UnifiedTask] = PriorityQueue()

        self.lock = threading.RLock()
        self.tasks: Dict[str, UnifiedTask] = {}
        self.stats: Dict[str, int] = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "active_tasks": 0,
        }

        self._recover_existing_tasks()

    def create_task(
        self,
        source_url: Optional[str] = None,
        source_path: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        task_type: Any = TaskType.VIDEO,
    ) -> str:
        metadata = (metadata or {}).copy()
        payload_override = metadata.pop("payload", None)
        if payload is None:
            payload = payload_override
        source_label = metadata.pop("source", "manual")

        normalized_type = self._normalize_task_type(task_type)

        if not self._should_skip_duplicate_check():
            duplicate_id = self._find_duplicate(source_url, source_path, metadata)
            if duplicate_id:
                return duplicate_id

        task_id = self.task_manager.create_task(
            task_type=normalized_type,
            source=source_label,
            source_url=source_url,
            source_path=source_path,
            payload=payload,
            metadata=metadata,
            priority=priority,
        )

        task = self.task_manager.get_task(task_id)
        if task is None:
            raise RuntimeError("Failed to retrieve task after creation")

        if source_label:
            task.metadata.setdefault("source", source_label)

        with self.lock:
            self.tasks[task_id] = task
            self.stats["total_tasks"] += 1
            if task.status in _ACTIVE_STATUSES:
                self.stats["active_tasks"] += 1

        self._persist_task(task)
        self._enqueue_for_stage(task)
        return task_id

    def submit_task(self, task_data: Dict[str, Any]) -> str:
        video_urls: List[str] = task_data.get("video_urls") or []
        source_url = video_urls[0] if video_urls else task_data.get("thread_url")
        normalized_type = self._normalize_task_type(task_data.get("task_type", TaskType.VIDEO))

        metadata = {
            "post_id": task_data.get("thread_id"),
            "author_id": task_data.get("author_id"),
            "author_name": task_data.get("author"),
            "forum_name": task_data.get("forum_name"),
            "title": task_data.get("title"),
            "content": task_data.get("content"),
            "original_filenames": task_data.get("original_filenames", []),
            "cover_info": task_data.get("cover_info"),
            "source": task_data.get("source", "forum"),
            "task_type": normalized_type.value,
        }

        return self.create_task(
            source_url=source_url,
            priority=TaskPriority.NORMAL,
            metadata=metadata,
            payload=task_data.get("payload"),
            task_type=normalized_type,
        )

    def get_task(self, task_id: str) -> Optional[UnifiedTask]:
        task = self.task_manager.get_task(task_id)
        if task is not None:
            with self.lock:
                self.tasks[task_id] = task
        return task

    def get_next_download_task(self, timeout: Optional[float] = None) -> Optional[UnifiedTask]:
        return self._get_from_queue(self.download_queue, TaskStatus.DOWNLOADING, timeout)

    def get_next_process_task(self, timeout: Optional[float] = None) -> Optional[UnifiedTask]:
        return self._get_from_queue(self.process_queue, TaskStatus.PROCESSING, timeout)

    def get_next_upload_task(self, timeout: Optional[float] = None) -> Optional[UnifiedTask]:
        return self._get_from_queue(self.upload_queue, TaskStatus.UPLOADING, timeout)

    def complete_download(self, task_id: str, local_path: str) -> None:
        task = self.get_task(task_id)
        if task is None:
            return
        task.source_path = local_path
        task.status = TaskStatus.PENDING
        self._persist_task(task)
        self._enqueue_for_stage(task)

    def complete_process(self, task_id: str, output_path: str) -> None:
        task = self.get_task(task_id)
        if task is None:
            return
        task.output_path = output_path
        if output_path and output_path not in task.output_files:
            task.output_files.append(output_path)
        task.status = TaskStatus.PENDING
        self._persist_task(task)
        self._enqueue_for_stage(task)

    def complete_upload(self, task_id: str) -> None:
        self.update_task_status(task_id, TaskStatus.COMPLETED)

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        error_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        task = self.get_task(task_id)
        if task is None:
            return False

        new_status = status if isinstance(status, TaskStatus) else TaskStatus(status)
        old_status = task.status

        if error_message is not None:
            task.error_message = error_message
        if result is not None:
            task.result = result

        task.status = new_status
        if new_status in {TaskStatus.DOWNLOADING, TaskStatus.PROCESSING, TaskStatus.UPLOADING} and not task.started_at:
            task.started_at = datetime.now()
        if new_status in _TERMINAL_STATUSES:
            task.completed_at = datetime.now()

        self._update_stats_on_transition(old_status, new_status)
        self._persist_task(task)
        return True

    def update_task_metadata(self, task_id: str, metadata: Dict[str, Any]) -> bool:
        task = self.get_task(task_id)
        if task is None:
            return False
        task.metadata = metadata
        self._persist_task(task)
        return True

    def fail_task(self, task_id: str, error_message: str, retry: bool = True) -> None:
        task = self.get_task(task_id)
        if task is None:
            return

        task.retry_count += 1
        task.error_message = error_message

        if retry and task.retry_count < task.max_retries:
            delay = min(30, 5 * (2 ** (task.retry_count - 1)))
            old_status = task.status
            task.status = TaskStatus.PENDING
            self._update_stats_on_transition(old_status, TaskStatus.PENDING)
            self._persist_task(task)

            def _retry() -> None:
                time.sleep(delay)
                retried = self.get_task(task_id)
                if retried is None or retried.status == TaskStatus.CANCELLED:
                    return
                self._enqueue_for_stage(retried)

            threading.Thread(target=_retry, daemon=True).start()
        else:
            old_status = task.status
            task.status = TaskStatus.FAILED
            self._update_stats_on_transition(old_status, TaskStatus.FAILED)
            self._persist_task(task)

    def cancel_task(self, task_id: str) -> None:
        self.update_task_status(task_id, TaskStatus.CANCELLED)

    def get_queue_sizes(self) -> Dict[str, int]:
        return {
            "download": self.download_queue.qsize(),
            "process": self.process_queue.qsize(),
            "upload": self.upload_queue.qsize(),
        }

    def get_stats(self) -> Dict[str, Any]:
        stats = dict(self.stats)
        stats["queue_sizes"] = self.get_queue_sizes()
        stats["timestamp"] = datetime.now().isoformat()
        return stats

    def get_status(self) -> Dict[str, int]:
        counts = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
        with self.lock:
            for task in self.tasks.values():
                if task.status in {TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.DOWNLOADING}:
                    counts["pending"] += 1
                elif task.status in {TaskStatus.PROCESSING, TaskStatus.UPLOADING}:
                    counts["processing"] += 1
                elif task.status == TaskStatus.COMPLETED:
                    counts["completed"] += 1
                elif task.status == TaskStatus.FAILED:
                    counts["failed"] += 1
        return counts

    def is_empty(self) -> bool:
        return all(size == 0 for size in self.get_queue_sizes().values())

    def get_active_tasks(self) -> List[UnifiedTask]:
        with self.lock:
            return [task for task in self.tasks.values() if task.status in _ACTIVE_STATUSES]

    def cleanup_old_tasks(self, max_age_hours: int = 24) -> None:
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        with self.lock:
            for task_id, task in list(self.tasks.items()):
                if task.completed_at and task.completed_at < cutoff and task.status in _TERMINAL_STATUSES:
                    self.tasks.pop(task_id, None)

    def _enqueue_for_stage(self, task: UnifiedTask) -> None:
        if task.status not in _ACTIVE_STATUSES:
            return
        if task.task_type in {TaskType.TTS, TaskType.VOICE_CLONE}:
            self.process_queue.put(task)
            return
        if task.source_url and not task.source_path:
            self.download_queue.put(task)
        elif task.source_path and not task.output_path:
            self.process_queue.put(task)
        elif task.output_path and task.status != TaskStatus.UPLOADING:
            self.upload_queue.put(task)

    def _recover_existing_tasks(self) -> None:
        for status in list(TaskStatus):
            tasks = self.task_manager.get_tasks_by_status(status, limit=1000)
            for task in tasks:
                if task.task_id in self.tasks:
                    continue
                self.tasks[task.task_id] = task
                self.stats["total_tasks"] += 1
                if status in _ACTIVE_STATUSES:
                    self.stats["active_tasks"] += 1
                    self._enqueue_for_stage(task)
                elif status == TaskStatus.COMPLETED:
                    self.stats["completed_tasks"] += 1
                elif status == TaskStatus.FAILED:
                    self.stats["failed_tasks"] += 1

    def _get_from_queue(
        self,
        queue: PriorityQueue,
        new_status: TaskStatus,
        timeout: Optional[float],
    ) -> Optional[UnifiedTask]:
        while True:
            try:
                task: UnifiedTask = queue.get(timeout=timeout)
            except Empty:
                return None

            fresh_task = self.get_task(task.task_id)
            if fresh_task is None:
                continue
            if fresh_task.status in _TERMINAL_STATUSES:
                continue

            self.update_task_status(fresh_task.task_id, new_status)
            return fresh_task

    def _persist_task(self, task: UnifiedTask) -> None:
        self.task_manager.save_task(task)
        with self.lock:
            self.tasks[task.task_id] = task

    def _update_stats_on_transition(self, old: TaskStatus, new: TaskStatus) -> None:
        if old == new:
            return

        was_active = old in _ACTIVE_STATUSES
        will_be_active = new in _ACTIVE_STATUSES

        if was_active and not will_be_active:
            self.stats["active_tasks"] = max(0, self.stats["active_tasks"] - 1)
        elif not was_active and will_be_active:
            self.stats["active_tasks"] += 1

        if new == TaskStatus.COMPLETED:
            self.stats["completed_tasks"] += 1
        elif new == TaskStatus.FAILED:
            self.stats["failed_tasks"] += 1

    def _should_skip_duplicate_check(self) -> bool:
        return bool(
            getattr(self.config, "forum_test_mode", False)
            or getattr(self.config, "forum_test_once", False)
        )

    def _normalize_task_type(self, value: Any) -> TaskType:
        if isinstance(value, TaskType):
            return value
        if isinstance(value, str):
            lowered = value.lower()
            try:
                return TaskType(lowered)
            except ValueError:
                try:
                    return TaskType[value.upper()]
                except KeyError:
                    return TaskType.VIDEO
        return TaskType.VIDEO

    def _find_duplicate(
        self,
        source_url: Optional[str],
        source_path: Optional[str],
        metadata: Dict[str, Any],
    ) -> Optional[str]:
        with self.lock:
            for task in self.tasks.values():
                if task.status in _TERMINAL_STATUSES:
                    continue
                if source_url and task.source_url == source_url:
                    return task.task_id
                if source_path and task.source_path == source_path:
                    return task.task_id
                original_filename = metadata.get("original_filename")
                if original_filename and task.metadata.get("original_filename") == original_filename:
                    return task.task_id
                post_id = metadata.get("post_id")
                if post_id and task.metadata.get("post_id") == post_id:
                    return task.task_id
        return None

    def _build_default_config(self) -> SimpleNamespace:
        return SimpleNamespace(
            redis_host="localhost",
            redis_port=6379,
            redis_db=0,
            redis_password=None,
            forum_test_mode=False,
            forum_test_once=False,
            input_dir="input",
        )


__all__ = [
    "QueueManager",
    "VideoTask",
    "TaskStatus",
    "TaskPriority",
]
