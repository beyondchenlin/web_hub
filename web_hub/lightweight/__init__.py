"""
轻量级视频处理系统核心模块
支持单机容器化部署，预留K8s扩展接口
"""

__version__ = "2.0.0"
__author__ = "Video Processing Team"

from .config import LightweightConfig, ConfigManager, get_config_manager, get_config
from .queue_manager import QueueManager, VideoTask, TaskStatus, TaskPriority
from .resource_monitor import LightweightResourceMonitor
from .task_processor import TaskProcessor
from .logger import init_logger, get_logger
from .web_server import WebServer

__all__ = [
    "LightweightConfig",
    "ConfigManager",
    "get_config_manager",
    "get_config",
    "QueueManager",
    "VideoTask",
    "TaskStatus",
    "TaskPriority",
    "LightweightResourceMonitor",
    "TaskProcessor",
    "init_logger",
    "get_logger",
    "WebServer"
]
