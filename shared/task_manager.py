"""Shared task manager coordinating tasks across the system."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import redis  # type: ignore

    _REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover - redis optional in dev envs
    redis = None  # type: ignore
    _REDIS_AVAILABLE = False

from .task_model import TaskPriority, TaskStatus, TaskType, UnifiedTask


class UnifiedTaskManager:
    """Thread-safe task manager with optional Redis persistence."""

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None,
        redis_namespace: str = "webhub",
    ) -> None:
        self._lock = threading.RLock()
        self._tasks: Dict[str, UnifiedTask] = {}
        self._namespace = redis_namespace.rstrip(":") + ":"

        self._redis_client = None
        if _REDIS_AVAILABLE:
            try:
                self._redis_client = redis.Redis(  # type: ignore[attr-defined]
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    password=redis_password,
                    decode_responses=True,
                )
                self._redis_client.ping()
            except Exception:
                self._redis_client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def create_task(
        self,
        task_type: TaskType | str,
        source: str,
        source_url: Optional[str] = None,
        source_path: Optional[str] = None,
        payload: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> str:
        with self._lock:
            task_id = str(uuid.uuid4())
            task = UnifiedTask(
                task_id=task_id,
                task_type=task_type if isinstance(task_type, TaskType) else TaskType(task_type),
                source=source,
                source_url=source_url,
                source_path=source_path,
                priority=priority,
                payload=payload or {},
                metadata=metadata or {},
                status=TaskStatus.PENDING,
            )

            self._save_task(task)
            return task_id

    def get_task(self, task_id: str) -> Optional[UnifiedTask]:
        with self._lock:
            if self._redis_client:
                task = self._load_task_from_redis(task_id)
                if task:
                    self._tasks[task_id] = task
                    return task
            return self._tasks.get(task_id)

    def assign_task(self, task_id: str, worker_id: str, worker_url: str) -> bool:
        with self._lock:
            task = self.get_task(task_id)
            if not task:
                return False
            task.worker_id = worker_id
            task.worker_url = worker_url
            task.status = TaskStatus.ASSIGNED
            task.assigned_at = datetime.now()
            self._save_task(task)
            return True

    def save_task(self, task: UnifiedTask) -> None:
        """Persist full task state (status, metadata, payload, etc.)."""

        with self._lock:
            self._tasks[task.task_id] = task
            self._save_task(task)

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus | str,
        result: Optional[Dict] = None,
        error: Optional[str] = None,
    ) -> bool:
        with self._lock:
            task = self.get_task(task_id)
            if not task:
                return False

            task.status = status if isinstance(status, TaskStatus) else TaskStatus(status)
            if task.status == TaskStatus.PROCESSING and task.started_at is None:
                task.started_at = datetime.now()
            if task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
                task.completed_at = datetime.now()

            if result is not None:
                task.result = result
            if error is not None:
                task.error_message = error

            self._save_task(task)
            return True

    def get_pending_tasks(
        self, task_type: Optional[TaskType] = None, limit: int = 100
    ) -> List[UnifiedTask]:
        with self._lock:
            tasks = self._load_pending_from_redis(limit) if self._redis_client else None
            if tasks is None:
                tasks = [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
            if task_type:
                task_type = task_type if isinstance(task_type, TaskType) else TaskType(task_type)
                tasks = [t for t in tasks if t.task_type == task_type]
            tasks.sort(key=lambda t: (t.priority.value, t.created_at))
            return tasks[:limit]

    def get_tasks_by_status(
        self, status: TaskStatus | str, limit: int = 100
    ) -> List[UnifiedTask]:
        status = status if isinstance(status, TaskStatus) else TaskStatus(status)
        with self._lock:
            tasks = list(self._tasks.values())
            tasks = [t for t in tasks if t.status == status]
            tasks.sort(key=lambda t: t.created_at, reverse=True)
            return tasks[:limit]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            tasks = list(self._tasks.values())
            return {
                "total": len(tasks),
                "pending": sum(1 for t in tasks if t.status == TaskStatus.PENDING),
                "processing": sum(
                    1 for t in tasks if t.status in {TaskStatus.PROCESSING, TaskStatus.DOWNLOADING, TaskStatus.UPLOADING}
                ),
                "completed": sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
                "failed": sum(1 for t in tasks if t.status == TaskStatus.FAILED),
                "by_type": {
                    t.value: sum(1 for task in tasks if task.task_type == t) for t in TaskType
                },
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _redis_key(self, suffix: str) -> str:
        return f"{self._namespace}{suffix}"

    def _save_task(self, task: UnifiedTask) -> None:
        self._tasks[task.task_id] = task
        if not self._redis_client:
            return

        try:
            self._redis_client.set(
                self._redis_key(f"task:{task.task_id}"),
                task.to_json(),
                ex=7 * 24 * 3600,
            )

            if task.status == TaskStatus.PENDING:
                self._redis_client.zadd(
                    self._redis_key("tasks:pending"),
                    {task.task_id: float(task.priority.value)},
                )
            else:
                self._redis_client.zrem(self._redis_key("tasks:pending"), task.task_id)
        except Exception:
            # Fall back to in-memory only
            self._redis_client = None

    def _load_task_from_redis(self, task_id: str) -> Optional[UnifiedTask]:
        try:
            task_json = self._redis_client.get(self._redis_key(f"task:{task_id}"))  # type: ignore[assignment]
            if not task_json:
                return None
            return UnifiedTask.from_json(task_json)
        except Exception:
            return None

    def _load_pending_from_redis(self, limit: int) -> Optional[List[UnifiedTask]]:
        try:
            task_ids = self._redis_client.zrange(  # type: ignore[assignment]
                self._redis_key("tasks:pending"), 0, limit - 1
            )
            tasks: List[UnifiedTask] = []
            for task_id in task_ids:
                task = self._load_task_from_redis(task_id)
                if task:
                    tasks.append(task)
            return tasks
        except Exception:
            return None


_TASK_MANAGER_SINGLETON: Optional[UnifiedTaskManager] = None
_TASK_MANAGER_LOCK = threading.Lock()


def get_task_manager(**kwargs) -> UnifiedTaskManager:
    """Return singleton instance of task manager."""

    global _TASK_MANAGER_SINGLETON
    if _TASK_MANAGER_SINGLETON is None:
        with _TASK_MANAGER_LOCK:
            if _TASK_MANAGER_SINGLETON is None:
                _TASK_MANAGER_SINGLETON = UnifiedTaskManager(**kwargs)
    return _TASK_MANAGER_SINGLETON


__all__ = ["UnifiedTaskManager", "get_task_manager"]

