#!/usr/bin/env python3
"""
轻量级视频处理系统主程序
支持单机容器化部署，预留K8s扩展接口
"""

import os
import sys
import time
import signal
import logging
from typing import Dict, Optional

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)  # 项目根目录
sys.path.insert(0, current_dir)  # web_hub目录
sys.path.insert(0, project_root)  # 项目根目录（包含shared）

# 导入轻量级系统模块
from lightweight.config import get_config_manager, get_config
from lightweight.queue_manager import QueueManager, TaskPriority
from lightweight.resource_monitor import LightweightResourceMonitor
from lightweight.task_processor import TaskProcessor
from lightweight.web_server import WebServer
from lightweight.forum_integration import get_forum_integration
from lightweight.logger import init_logger, get_logger



class LightweightVideoProcessor:
    """轻量级视频处理器主类"""

    def __init__(self, config_file: Optional[str] = None):
        # 初始化配置
        self.config_manager = get_config_manager(config_file)
        self.config = self.config_manager.get_config()

        # 初始化日志
        self.logger_manager = init_logger(self.config)
        self.logger = get_logger("LightweightVideoProcessor")

        # 初始化组件
        self.queue_manager = QueueManager(self.config)
        self.resource_monitor = LightweightResourceMonitor(self.config)
        self.task_processor = TaskProcessor(
            self.config,
            self.queue_manager,
            self.resource_monitor
        )

        # Web服务器（可选）
        self.web_server = None
        if self.config.web_port > 0:
            self.web_server = WebServer(
                self.config,
                self.queue_manager,
                self.resource_monitor,
                self.task_processor
            )

        # 论坛集成 - 监控节点和工作节点都需要初始化（用途不同）
        self.forum_integration = None
        forum_parsing_enabled = getattr(self.config, 'forum_parsing_enabled', False)

        if self.config.forum_enabled or forum_parsing_enabled:
            self.forum_integration = get_forum_integration(self.queue_manager, self.config)
            if self.config.forum_enabled:
                self.logger.info("🎯 监控节点：论坛集成已初始化（用于监控和解析）")
            elif forum_parsing_enabled:
                self.logger.info("🔗 工作节点：论坛集成已初始化（仅用于解析任务）")
        else:
            self.logger.info("❌ 论坛功能完全禁用，跳过论坛集成初始化")

        # 控制变量
        self.running = False

        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.logger.info("轻量级视频处理器初始化完成")
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        self.logger.info(f"接收到信号 {signum}，开始优雅关闭...")
        self.shutdown()
    
    def start(self):
        """启动处理器"""
        if self.running:
            self.logger.warning("处理器已在运行中")
            return

        self.running = True
        self.logger.info("启动轻量级视频处理器...")

        # 启动资源监控
        self.resource_monitor.start()

        # 启动任务处理器
        self.task_processor.start()

        # 启动Web服务器（如果启用）
        if self.web_server:
            self.web_server.start()

        # 启动论坛集成（仅监控节点启动监控功能）
        if self.forum_integration and self.config.forum_enabled:
            self.forum_integration.start()
            self.logger.info("🎯 监控节点：论坛监控已启动")
        elif self.forum_integration:
            self.logger.info("🔗 工作节点：论坛集成已就绪（仅用于解析任务）")

        self.logger.info("所有组件已启动")
    
    def shutdown(self):
        """关闭处理器"""
        if not self.running:
            return

        self.logger.info("开始关闭处理器...")
        self.running = False

        # 停止任务处理器
        self.task_processor.stop()

        # 停止资源监控
        self.resource_monitor.stop()

        # 关闭Web服务器
        if self.web_server:
            self.web_server.stop()

        # 停止论坛集成（如果启动了监控）
        if self.forum_integration and self.config.forum_enabled:
            self.forum_integration.stop()
            self.logger.info("🛑 监控节点：论坛监控已停止")

        self.logger.info("处理器已关闭")
    
    def get_status(self) -> Dict:
        """获取系统状态"""
        return {
            "running": self.running,
            "mode": self.config.mode,
            "queue_stats": self.queue_manager.get_stats(),
            "resource_stats": self.resource_monitor.get_stats(),
            "processor_stats": self.task_processor.get_stats() if hasattr(self.task_processor, 'get_stats') else {}
        }
    
    def add_video_task(self, source_url: Optional[str] = None,
                      source_path: Optional[str] = None,
                      priority: str = "normal") -> str:
        """添加视频处理任务"""
        # 转换优先级
        priority_map = {
            'low': TaskPriority.LOW,
            'normal': TaskPriority.NORMAL,
            'high': TaskPriority.HIGH,
            'urgent': TaskPriority.URGENT
        }
        task_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)

        # 创建任务
        task_id = self.queue_manager.create_task(
            source_url=source_url,
            source_path=source_path,
            priority=task_priority
        )

        self.logger.info(f"添加视频任务: {task_id}")
        return task_id

    def add_forum_task(self, post_id: str, video_url: str,
                      author_id: str = None, title: str = None) -> str:
        """添加论坛视频处理任务"""
        if self.forum_integration:
            task_id = self.forum_integration.create_forum_task(
                post_id=post_id,
                video_url=video_url,
                author_id=author_id,
                title=title
            )
            self.logger.info(f"添加论坛任务: {task_id} for post {post_id}")
            return task_id
        else:
            raise RuntimeError("论坛集成未启用")


def main():
    """主函数"""
    try:
        # 创建处理器
        processor = LightweightVideoProcessor()

        # 启动处理器
        processor.start()

        processor.logger.info("轻量级视频处理系统启动成功")
        if processor.web_server:
            processor.logger.info(f"Web界面: http://{processor.config.web_host}:{processor.config.web_port}")

        # 保持主线程运行
        try:
            while processor.running:
                time.sleep(1)
        except KeyboardInterrupt:
            processor.logger.info("接收到中断信号")

        # 关闭处理器
        processor.shutdown()

    except Exception as e:
        print(f"系统启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
