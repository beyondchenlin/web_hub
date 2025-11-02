#!/usr/bin/env python3
"""
统一日志管理器
替代分散的print语句，提供统一的日志输出
"""

import logging
import os
from datetime import datetime
from typing import Optional


class LoggerManager:
    """统一日志管理器"""

    def __init__(self, name: str = "cluster_monitor", log_file: Optional[str] = None,
                 console_level: str = "INFO", file_level: str = "DEBUG"):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # 避免重复添加handler
        if not self.logger.handlers:
            # 创建格式器
            console_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

            # 控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, console_level.upper()))
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

            # 文件处理器
            if log_file:
                # 确保日志目录存在
                os.makedirs(os.path.dirname(log_file), exist_ok=True)

                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(getattr(logging, file_level.upper()))
                file_handler.setFormatter(file_formatter)
                self.logger.addHandler(file_handler)

    def info(self, message: str, emoji: str = "ℹ️"):
        """信息日志"""
        self.logger.info(f"{emoji} {message}")

    def success(self, message: str):
        """成功日志"""
        self.logger.info(f"✅ {message}")

    def warning(self, message: str):
        """警告日志"""
        self.logger.warning(f"⚠️ {message}")

    def error(self, message: str):
        """错误日志"""
        self.logger.error(f"❌ {message}")

    def debug(self, message: str):
        """调试日志"""
        self.logger.debug(f"🔍 {message}")

    def startup(self, message: str):
        """启动日志"""
        self.logger.info(f"🚀 {message}")

    def stop(self, message: str):
        """停止日志"""
        self.logger.info(f"🛑 {message}")

    def task(self, message: str):
        """任务日志"""
        self.logger.info(f"📝 {message}")

    def network(self, message: str):
        """网络日志"""
        self.logger.info(f"🌐 {message}")

    def forum(self, message: str):
        """论坛日志"""
        self.logger.info(f"📋 {message}")

    def machine(self, message: str):
        """机器状态日志"""
        self.logger.info(f"🖥️ {message}")

    def config(self, message: str):
        """配置日志"""
        self.logger.info(f"⚙️ {message}")

    def file_op(self, message: str):
        """文件操作日志"""
        self.logger.info(f"📁 {message}")


class ProductionLogger(LoggerManager):
    """生产环境日志管理器 - 减少详细输出"""

    def __init__(self, name: str = "cluster_monitor", log_file: Optional[str] = None):
        # 生产环境：控制台只显示WARNING及以上，文件记录所有
        super().__init__(name, log_file, console_level="WARNING", file_level="DEBUG")

    def debug(self, message: str):
        """生产环境下调试信息只记录到文件"""
        self.logger.debug(f"🔍 {message}")

    def task(self, message: str):
        """生产环境下任务信息只记录到文件"""
        self.logger.debug(f"📝 {message}")


class DevelopmentLogger(LoggerManager):
    """开发环境日志管理器 - 详细输出"""

    def __init__(self, name: str = "cluster_monitor", log_file: Optional[str] = None):
        # 开发环境：控制台显示INFO及以上，文件记录所有
        super().__init__(name, log_file, console_level="INFO", file_level="DEBUG")


def get_logger(mode: str = "development", name: str = "cluster_monitor",
               log_file: Optional[str] = None) -> LoggerManager:
    """获取适合的日志管理器"""
    if mode.lower() in ["production", "prod"]:
        return ProductionLogger(name, log_file)
    else:
        return DevelopmentLogger(name, log_file)


# 全局日志管理器实例
_global_logger = None


def setup_global_logger(mode: str = "development", log_file: Optional[str] = None):
    """设置全局日志管理器"""
    global _global_logger
    _global_logger = get_logger(mode, "cluster_monitor", log_file)
    return _global_logger


def get_global_logger() -> LoggerManager:
    """获取全局日志管理器"""
    global _global_logger
    if _global_logger is None:
        _global_logger = get_logger()
    return _global_logger


# 便捷函数
def log_info(message: str, emoji: str = "ℹ️"):
    """记录信息日志"""
    get_global_logger().info(message, emoji)


def log_success(message: str):
    """记录成功日志"""
    get_global_logger().success(message)


def log_warning(message: str):
    """记录警告日志"""
    get_global_logger().warning(message)


def log_error(message: str):
    """记录错误日志"""
    get_global_logger().error(message)


def log_debug(message: str):
    """记录调试日志"""
    get_global_logger().debug(message)


if __name__ == "__main__":
    # 测试代码
    print("🧪 测试日志管理器...")

    # 测试开发模式
    dev_logger = get_logger("development", log_file="logs/test_dev.log")
    dev_logger.startup("开发模式测试启动")
    dev_logger.success("测试成功")
    dev_logger.warning("测试警告")
    dev_logger.error("测试错误")
    dev_logger.debug("测试调试信息")

    # 测试生产模式
    prod_logger = get_logger("production", log_file="logs/test_prod.log")
    prod_logger.startup("生产模式测试启动")
    prod_logger.success("测试成功")
    prod_logger.warning("测试警告")
    prod_logger.error("测试错误")
    prod_logger.debug("测试调试信息（只记录到文件）")

    print("🎉 测试完成")