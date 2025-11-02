#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
日志性能优化配置
专为高并发场景设计的日志管理配置
"""

import os
import logging
from typing import Dict, Any

class LogPerformanceConfig:
    """日志性能配置管理器"""
    
    def __init__(self):
        self.mode = os.getenv('LOG_MODE', 'development')  # development, production, silent
        self.console_enabled = self._get_console_setting()
        self.file_logging_enabled = True
        self.verbose_logging = self._get_verbose_setting()
        
    def _get_console_setting(self) -> bool:
        """根据模式确定控制台日志设置"""
        if self.mode == 'production':
            return False  # 生产模式禁用控制台输出
        elif self.mode == 'silent':
            return False  # 静默模式禁用控制台输出
        else:
            return True   # 开发模式启用控制台输出
    
    def _get_verbose_setting(self) -> bool:
        """根据模式确定详细日志设置"""
        return self.mode == 'development'
    
    def get_log_levels(self) -> Dict[str, str]:
        """获取不同组件的日志级别"""
        if self.mode == 'production':
            return {
                'console': 'WARNING',
                'file': 'INFO',
                'error_file': 'ERROR',
                'forum_monitor': 'WARNING',  # 论坛监控只记录警告以上
                'video_processor': 'INFO',   # 视频处理记录信息以上
                'uploader': 'WARNING',       # 上传器只记录警告以上
                'performance': 'INFO'        # 性能监控记录信息
            }
        elif self.mode == 'silent':
            return {
                'console': 'CRITICAL',
                'file': 'WARNING',
                'error_file': 'ERROR',
                'forum_monitor': 'ERROR',
                'video_processor': 'WARNING',
                'uploader': 'ERROR',
                'performance': 'WARNING'
            }
        else:  # development
            return {
                'console': 'INFO',
                'file': 'DEBUG',
                'error_file': 'ERROR',
                'forum_monitor': 'INFO',
                'video_processor': 'DEBUG',
                'uploader': 'INFO',
                'performance': 'DEBUG'
            }
    
    def get_log_filters(self) -> Dict[str, list]:
        """获取日志过滤规则"""
        if self.mode == 'production':
            return {
                'suppress_patterns': [
                    'Redis连接检查',
                    '队列状态检查',
                    '资源监控更新',
                    'HTTP请求日志',
                    '定时任务执行'
                ],
                'important_only': [
                    '任务开始',
                    '任务完成',
                    '任务失败',
                    '系统启动',
                    '系统关闭',
                    '错误发生'
                ]
            }
        else:
            return {
                'suppress_patterns': [],
                'important_only': []
            }
    
    def get_performance_settings(self) -> Dict[str, Any]:
        """获取性能优化设置"""
        return {
            'async_logging': self.mode == 'production',  # 生产模式使用异步日志
            'buffer_size': 8192 if self.mode == 'production' else 1024,
            'flush_interval': 5.0 if self.mode == 'production' else 1.0,
            'max_queue_size': 1000 if self.mode == 'production' else 100,
            'batch_write': self.mode == 'production'
        }

class HighPerformanceLogFilter(logging.Filter):
    """高性能日志过滤器"""
    
    def __init__(self, config: LogPerformanceConfig):
        super().__init__()
        self.config = config
        self.filters = config.get_log_filters()
        self.suppress_patterns = self.filters['suppress_patterns']
        self.important_only = self.filters['important_only']
    
    def filter(self, record) -> bool:
        """过滤日志记录"""
        message = record.getMessage()
        
        # 生产模式下过滤掉不重要的日志
        if self.config.mode == 'production':
            # 检查是否为需要抑制的模式
            for pattern in self.suppress_patterns:
                if pattern in message:
                    return False
            
            # 如果设置了只记录重要信息，检查是否为重要信息
            if self.important_only:
                for pattern in self.important_only:
                    if pattern in message:
                        return True
                # 如果不是重要信息且级别低于WARNING，过滤掉
                return record.levelno >= logging.WARNING
        
        return True

def setup_performance_logging():
    """设置高性能日志配置"""
    config = LogPerformanceConfig()
    
    # 创建过滤器
    log_filter = HighPerformanceLogFilter(config)
    
    # 应用到所有处理器
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(log_filter)
    
    # 日志性能优化已启用
    logging.info(f"日志性能优化已启用 - 模式: {config.mode}")

    if config.mode == 'production':
        logging.info("生产模式优化: 控制台日志禁用, 文件日志仅INFO及以上")
    
    return config

def set_log_mode(mode: str):
    """动态设置日志模式"""
    os.environ['LOG_MODE'] = mode
    config = setup_performance_logging()
    
    if mode == 'production':
        logging.info("已切换到生产模式 - 最小日志输出")
    elif mode == 'silent':
        logging.info("已切换到静默模式 - 仅错误日志")
    else:
        logging.info("已切换到开发模式 - 详细日志输出")
    
    return config

def get_optimized_logger(name: str, component_type: str = 'general'):
    """获取优化的日志器"""
    config = LogPerformanceConfig()
    levels = config.get_log_levels()
    
    logger = logging.getLogger(name)
    
    # 根据组件类型设置日志级别
    if component_type in levels:
        level_name = levels[component_type]
        logger.setLevel(getattr(logging, level_name))
    
    return logger

# 预定义的组件日志器
def get_forum_logger():
    """获取论坛监控日志器"""
    return get_optimized_logger("ForumMonitor", "forum_monitor")

def get_processor_logger():
    """获取视频处理日志器"""
    return get_optimized_logger("VideoProcessor", "video_processor")

def get_uploader_logger():
    """获取上传器日志器"""
    return get_optimized_logger("Uploader", "uploader")

def get_performance_logger():
    """获取性能监控日志器"""
    return get_optimized_logger("Performance", "performance")

# 便捷的日志记录函数
def log_important(message: str, level: str = 'info'):
    """记录重要信息（在所有模式下都会记录）"""
    logger = logging.getLogger("Important")
    getattr(logger, level.lower())(f"⭐ {message}")

def log_performance_metric(metric_name: str, value: Any, unit: str = ""):
    """记录性能指标"""
    config = LogPerformanceConfig()
    if config.mode != 'silent':
        logger = get_performance_logger()
        logger.info(f"📊 {metric_name}: {value} {unit}")

def log_task_milestone(task_id: str, milestone: str):
    """记录任务里程碑（重要事件）"""
    logger = logging.getLogger("TaskMilestone")
    logger.info(f"🎯 任务 {task_id}: {milestone}")

# 性能监控装饰器
def log_execution_time(func):
    """装饰器：记录函数执行时间"""
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            log_performance_metric(f"{func.__name__}_duration", f"{duration:.2f}", "秒")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger = logging.getLogger("Performance")
            logger.error(f"❌ {func.__name__} 执行失败 (耗时: {duration:.2f}秒): {e}")
            raise
    
    return wrapper
