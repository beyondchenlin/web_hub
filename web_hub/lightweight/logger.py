#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
轻量级视频处理系统 - 日志系统

主要功能：
- 结构化日志记录
- 多格式输出支持（JSON/文本）
- 日志轮转和清理
- 统一日志接口
"""

import os
import json
import logging
import logging.handlers
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """JSON格式化器"""
    
    def format(self, record):
        """格式化日志记录为JSON"""
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if hasattr(record, 'task_id'):
            log_data['task_id'] = record.task_id
        if hasattr(record, 'component'):
            log_data['component'] = record.component
        if hasattr(record, 'duration'):
            log_data['duration'] = record.duration
        if hasattr(record, 'resource_usage'):
            log_data['resource_usage'] = record.resource_usage
        
        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """彩色文本格式化器"""
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
        'RESET': '\033[0m'      # 重置
    }
    
    def format(self, record):
        """格式化日志记录为彩色文本"""
        # 获取颜色
        color = self.COLORS.get(record.levelname, '')
        reset = self.COLORS['RESET']
        
        # 基本格式
        formatted = super().format(record)
        
        # 添加颜色
        if color:
            formatted = f"{color}{formatted}{reset}"
        
        return formatted


class LightweightLogger:
    """轻量级日志管理器 - 高性能版本"""

    def __init__(self, config):
        self.config = config
        self.loggers: Dict[str, logging.Logger] = {}
        self.console_enabled = getattr(config, 'console_logging', True)
        self.verbose_mode = getattr(config, 'verbose_logging', False)
        self.production_mode = getattr(config, 'production_mode', False)
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志系统"""
        # 确保日志目录存在
        Path(self.config.log_dir).mkdir(parents=True, exist_ok=True)
        
        # 设置根日志级别
        logging.getLogger().setLevel(getattr(logging, self.config.log_level.upper()))
        
        # 创建主日志文件处理器
        self._create_main_handler()
        
        # 创建错误日志处理器
        self._create_error_handler()
        
        # 创建控制台处理器
        self._create_console_handler()
    
    def _create_main_handler(self):
        """创建主日志文件处理器"""
        log_file = os.path.join(self.config.log_dir, "lightweight.log")
        
        # 使用轮转文件处理器
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self._parse_size(self.config.log_max_size),
            backupCount=self.config.log_backup_count,
            encoding='utf-8'
        )
        
        # 设置格式化器
        if self.config.log_format.lower() == 'json':
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)
        
        # 添加到根日志器
        logging.getLogger().addHandler(handler)
    
    def _create_error_handler(self):
        """创建错误日志处理器"""
        error_log_file = os.path.join(self.config.log_dir, "error.log")
        
        handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=self._parse_size(self.config.log_max_size),
            backupCount=self.config.log_backup_count,
            encoding='utf-8'
        )
        
        # 只记录ERROR及以上级别
        handler.setLevel(logging.ERROR)
        
        # 设置格式化器
        if self.config.log_format.lower() == 'json':
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n'
                '%(pathname)s:%(lineno)d in %(funcName)s\n'
            )
        
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)
    
    def _create_console_handler(self):
        """创建控制台处理器 - 性能优化版本"""
        # 生产模式下禁用控制台输出以提升性能
        if self.production_mode or not self.console_enabled:
            return

        # 只在调试模式或详细模式下启用控制台输出
        if not (self.config.debug or self.verbose_mode):
            return

        handler = logging.StreamHandler()

        # 生产环境使用简化格式，减少格式化开销
        if self.production_mode:
            formatter = logging.Formatter('%(levelname)s: %(message)s')
        else:
            # 开发环境使用彩色格式化器
            formatter = ColoredFormatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

        handler.setFormatter(formatter)

        # 生产模式下只显示WARNING及以上级别
        if self.production_mode:
            handler.setLevel(logging.WARNING)
        else:
            handler.setLevel(getattr(logging, self.config.log_level.upper()))

        logging.getLogger().addHandler(handler)
    
    def _parse_size(self, size_str: str) -> int:
        """解析大小字符串"""
        size_str = size_str.upper()
        
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    def get_logger(self, name: str) -> logging.Logger:
        """获取日志器"""
        if name not in self.loggers:
            logger = logging.getLogger(name)
            self.loggers[name] = logger
        
        return self.loggers[name]
    
    def log_task_start(self, task_id: str, task_type: str, **kwargs):
        """记录任务开始"""
        logger = self.get_logger("TaskManager")
        
        extra = {
            'task_id': task_id,
            'component': 'task_manager'
        }
        extra.update(kwargs)
        
        logger.info(f"任务开始: {task_type}", extra=extra)
    
    def log_task_complete(self, task_id: str, task_type: str, duration: float, **kwargs):
        """记录任务完成"""
        logger = self.get_logger("TaskManager")
        
        extra = {
            'task_id': task_id,
            'component': 'task_manager',
            'duration': duration
        }
        extra.update(kwargs)
        
        logger.info(f"任务完成: {task_type} (耗时: {duration:.2f}秒)", extra=extra)
    
    def log_task_error(self, task_id: str, task_type: str, error: str, **kwargs):
        """记录任务错误"""
        logger = self.get_logger("TaskManager")
        
        extra = {
            'task_id': task_id,
            'component': 'task_manager'
        }
        extra.update(kwargs)
        
        logger.error(f"任务失败: {task_type} - {error}", extra=extra)
    
    def log_resource_usage(self, component: str, usage_data: Dict[str, Any]):
        """记录资源使用情况"""
        logger = self.get_logger("ResourceMonitor")
        
        extra = {
            'component': component,
            'resource_usage': usage_data
        }
        
        logger.info("资源使用情况", extra=extra)
    
    def log_step_resource(self, step_number: int, step_name: str, 
                         usage_data: Dict[str, Any], duration: Optional[float] = None):
        """记录步骤资源使用情况"""
        logger = self.get_logger("Pipeline")
        
        extra = {
            'component': 'pipeline',
            'resource_usage': usage_data
        }
        
        if duration:
            extra['duration'] = duration
        
        message = f"步骤{step_number}: {step_name} 资源使用情况"
        logger.info(message, extra=extra)
    
    def set_production_mode(self, enabled: bool = True):
        """设置生产模式 - 优化性能"""
        self.production_mode = enabled

        if enabled:
            # 生产模式：减少日志输出，提升性能
            self.console_enabled = False
            self.verbose_mode = False

            # 调整日志级别为WARNING以上
            for handler in logging.getLogger().handlers:
                if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                    handler.setLevel(logging.WARNING)

            print("🚀 生产模式已启用 - 日志输出已优化")
        else:
            # 开发模式：恢复详细日志
            self.console_enabled = True
            print("🔧 开发模式已启用 - 详细日志输出")

    def set_console_logging(self, enabled: bool):
        """动态控制控制台日志输出"""
        self.console_enabled = enabled

        # 移除现有的控制台处理器
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                root_logger.removeHandler(handler)

        # 如果启用，重新创建控制台处理器
        if enabled:
            self._create_console_handler()
            print("✅ 控制台日志已启用")
        else:
            print("🔇 控制台日志已禁用 - 性能优化")

    def get_performance_optimized_logger(self, name: str) -> logging.Logger:
        """获取性能优化的日志器"""
        logger = self.get_logger(name)

        # 在生产模式下，只记录重要信息
        if self.production_mode:
            logger.setLevel(logging.WARNING)

        return logger

    def log_important_only(self, level: str, message: str, **kwargs):
        """只记录重要日志 - 性能优化"""
        if self.production_mode and level.upper() not in ['WARNING', 'ERROR', 'CRITICAL']:
            return

        logger = self.get_logger("System")
        getattr(logger, level.lower())(message, extra=kwargs)

    def cleanup_old_logs(self, max_age_days: int = 30):
        """清理旧日志文件"""
        try:
            log_dir = Path(self.config.log_dir)
            cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 3600)

            cleaned_count = 0
            for log_file in log_dir.glob("*.log*"):
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    cleaned_count += 1

            if cleaned_count > 0:
                print(f"🧹 清理了 {cleaned_count} 个旧日志文件")

        except Exception as e:
            print(f"❌ 清理日志文件失败: {e}")


# 全局日志管理器实例
_logger_manager = None


def init_logger(config):
    """初始化日志系统"""
    global _logger_manager
    _logger_manager = LightweightLogger(config)
    return _logger_manager


def get_logger(name: str = "Lightweight") -> logging.Logger:
    """获取日志器的便捷函数"""
    if _logger_manager is None:
        # 如果未初始化，创建基本日志器
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    return _logger_manager.get_logger(name)


def log_task_start(task_id: str, task_type: str, **kwargs):
    """记录任务开始的便捷函数"""
    if _logger_manager:
        _logger_manager.log_task_start(task_id, task_type, **kwargs)


def log_task_complete(task_id: str, task_type: str, duration: float, **kwargs):
    """记录任务完成的便捷函数"""
    if _logger_manager:
        _logger_manager.log_task_complete(task_id, task_type, duration, **kwargs)


def log_task_error(task_id: str, task_type: str, error: str, **kwargs):
    """记录任务错误的便捷函数"""
    if _logger_manager:
        _logger_manager.log_task_error(task_id, task_type, error, **kwargs)


def log_resource_usage(component: str, usage_data: Dict[str, Any]):
    """记录资源使用情况的便捷函数"""
    if _logger_manager:
        _logger_manager.log_resource_usage(component, usage_data)


def log_step_resource(step_number: int, step_name: str, 
                     usage_data: Dict[str, Any], duration: Optional[float] = None):
    """记录步骤资源使用情况的便捷函数"""
    if _logger_manager:
        _logger_manager.log_step_resource(step_number, step_name, usage_data, duration)
