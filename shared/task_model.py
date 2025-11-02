"""Unified task model shared across monitoring and worker components."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import json
from typing import Any, Dict, List, Optional


class TaskType(Enum):
    """Supported task types."""

    VIDEO = "video"
    TTS = "tts"
    VOICE_CLONE = "voice_clone"
    IMAGE = "image"


class TaskStatus(Enum):
    """Task lifecycle states."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority definition (lower value == higher priority)."""

    URGENT = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class UnifiedTask:
    """Unified representation for every task handled by the platform."""

    task_id: str
    task_type: TaskType
    source: str
    source_url: Optional[str] = None
    source_path: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    worker_id: Optional[str] = None
    worker_url: Optional[str] = None
    output_path: Optional[str] = None
    output_files: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.task_type, str):
            self.task_type = TaskType(self.task_type)
        if isinstance(self.status, str):
            self.status = TaskStatus(self.status)
        if isinstance(self.priority, str):
            self.priority = TaskPriority[self.priority.upper()]
        elif isinstance(self.priority, int):
            self.priority = TaskPriority(self.priority)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize task to a JSON-friendly dictionary."""

        data = asdict(self)
        data["task_type"] = self.task_type.value
        data["status"] = self.status.value
        data["priority"] = self.priority.value
        data["created_at"] = self.created_at.isoformat()
        data["assigned_at"] = (
            self.assigned_at.isoformat() if self.assigned_at else None
        )
        data["started_at"] = (
            self.started_at.isoformat() if self.started_at else None
        )
        data["completed_at"] = (
            self.completed_at.isoformat() if self.completed_at else None
        )
        return data

    def to_json(self) -> str:
        """Serialize task to JSON string."""

        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnifiedTask":
        """Re-create task from dictionary."""

        for key in ("created_at", "assigned_at", "started_at", "completed_at"):
            if data.get(key) and isinstance(data[key], str):
                data[key] = datetime.fromisoformat(data[key])
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "UnifiedTask":
        """Re-create task from JSON string."""

        return cls.from_dict(json.loads(json_str))

    def is_video_task(self) -> bool:
        return self.task_type == TaskType.VIDEO

    def is_tts_task(self) -> bool:
        return self.task_type in {TaskType.TTS, TaskType.VOICE_CLONE}

    def get_forum_info(self) -> Dict[str, Any]:
        return {
            "forum_name": self.metadata.get("forum_name", ""),
            "post_id": self.metadata.get("post_id", ""),
            "author_id": self.metadata.get("author_id", ""),
            "author_name": self.metadata.get("author_name", ""),
        }

    def __lt__(self, other: "UnifiedTask") -> bool:  # pragma: no cover - container ordering helper
        return (self.priority.value, self.created_at) < (
            other.priority.value,
            other.created_at,
        )


# Backward compatibility alias for legacy video pipeline.
VideoTask = UnifiedTask


__all__ = [
    "UnifiedTask",
    "VideoTask",
    "TaskType",
    "TaskStatus",
    "TaskPriority",
]

