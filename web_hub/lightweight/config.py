#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
轻量级视频处理系统 - 配置管理模块

主要功能：
- 环境变量配置管理
- 运行模式配置（单机/K8s）
- 系统参数配置
- 配置验证和默认值处理
"""

import os
import yaml
import json
import subprocess
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


def check_gpu_available():
    """
    检查系统是否有可用的NVIDIA GPU

    Returns:
        bool: 是否有可用的GPU
    """
    try:
        # 尝试运行nvidia-smi命令
        result = subprocess.run(
            ["nvidia-smi"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=2,
            check=False
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


@dataclass
class LightweightConfig:
    """轻量级系统配置类"""

    # 运行模式配置
    mode: str = "standalone"  # standalone, kubernetes
    debug: bool = os.getenv('DEBUG', 'false').lower() == 'true'

    # Redis配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None

    # 并发控制
    max_concurrent_videos: int = 5
    max_download_workers: int = 1
    max_upload_workers: int = 1

    # 资源监控
    monitor_interval: int = 5  # 秒
    resource_check_interval: int = 10  # 秒
    memory_limit_gb: float = 50.0  # 调整为50GB (80% = 40GB)
    disk_limit_gb: float = 500.0   # 调整为500GB

    # 任务配置
    task_timeout: int = 3600  # 秒
    retry_attempts: int = 3
    retry_delay: int = 60  # 秒

    # 文件路径配置
    input_dir: str = "input"
    output_dir: str = "output"
    temp_dir: str = "temp"
    log_dir: str = "logs"

    # Web服务配置
    web_host: str = "0.0.0.0"
    web_port: int = 8000
    web_debug: bool = False

    # 论坛检测配置 - 从环境变量读取，统一配置源
    forum_check_interval: int = 10  # 秒 - 默认10秒高频监控（从FORUM_CHECK_INTERVAL环境变量读取）
    forum_enabled: bool = False  # 默认为工作节点模式（不主动监控论坛）
    forum_parsing_enabled: bool = False  # 工作节点模式：启用论坛解析功能
    forum_test_mode: bool = False  # 默认生产模式：持久化去重；测试模式：重启后处理所有帖子
    forum_test_once: bool = False  # 测试模式单次运行：处理一轮后停止

    # GPU配置
    use_gpu: bool = False  # 是否启用GPU加速
    gpu_auto_detect: bool = True  # 是否自动检测GPU

    # 日志配置
    log_level: str = "DEBUG"
    log_format: str = "json"  # json, text
    log_max_size: str = "100MB"
    log_backup_count: int = 5

    # 原有pipeline配置集成
    pipeline_config: Dict[str, Any] = field(default_factory=dict)


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self.config = LightweightConfig()
        self._load_config()

    def _load_config(self):
        """加载配置"""
        # 1. 加载默认配置
        self._load_defaults()

        # 2. 加载.env文件到环境变量
        self._load_env_file()

        # 3. 加载配置文件
        if self.config_file and os.path.exists(self.config_file):
            self._load_from_file(self.config_file)

        # 4. 加载环境变量
        self._load_from_env()

        # 4. 验证配置
        self._validate_config()

        # 5. 创建必要目录
        self._ensure_directories()

        # 6. 检测GPU并更新配置
        self._detect_gpu()



    def _load_env_file(self):
        """加载.env文件到环境变量"""
        env_file = ".env"
        if os.path.exists(env_file):
            try:
                # 尝试使用python-dotenv
                try:
                    from dotenv import load_dotenv
                    load_dotenv(env_file)
                    print("✅ 已使用python-dotenv加载.env文件")
                    return
                except ImportError:
                    pass

                # 手动加载.env文件
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()

                            # 移除引号
                            if value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]
                            elif value.startswith("'") and value.endswith("'"):
                                value = value[1:-1]

                            os.environ[key] = value

                print("✅ 已手动加载.env文件到环境变量")

            except Exception as e:
                print(f"⚠️ 加载.env文件失败: {e}")
        else:
            print("ℹ️ 未找到.env文件，使用系统环境变量")

    def _load_defaults(self):
        """加载默认配置"""
        # 从原有config.py加载pipeline配置
        try:
            import sys
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'pre', 'stage'))
            from config import get_config
            self.config.pipeline_config = get_config()
        except ImportError:
            # 如果无法导入，使用基本默认配置
            self.config.pipeline_config = {
                "enable_step0": True,
                "enable_step1": False,
                "enable_step2": True,
                "enable_step3": False,
                "enable_step4": False,
                "enable_step5": True,
                "enable_step6": True,
                "enable_step7": True,
                "enable_step8": True,
                "enable_step9": True,
                "stop_on_error": True,
                "show_command": False,
                "output_dir": "output"
            }

    def _load_from_file(self, config_file: str):
        """从配置文件加载"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                if config_file.endswith('.yaml') or config_file.endswith('.yml'):
                    file_config = yaml.safe_load(f)
                else:
                    file_config = json.load(f)

            # 更新配置
            for key, value in file_config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)

        except Exception as e:
            print(f"警告: 加载配置文件失败 {config_file}: {e}")

    def _load_from_env(self):
        """从环境变量加载配置"""
        env_mappings = {
            'MODE': 'mode',
            'DEBUG': ('debug', bool),
            'REDIS_HOST': 'redis_host',
            'REDIS_PORT': ('redis_port', int),
            'REDIS_DB': ('redis_db', int),
            'REDIS_PASSWORD': 'redis_password',
            'MAX_CONCURRENT_VIDEOS': ('max_concurrent_videos', int),
            'MAX_DOWNLOAD_WORKERS': ('max_download_workers', int),
            'MAX_UPLOAD_WORKERS': ('max_upload_workers', int),
            'MONITOR_INTERVAL': ('monitor_interval', int),
            'RESOURCE_CHECK_INTERVAL': ('resource_check_interval', int),
            'MEMORY_LIMIT_GB': ('memory_limit_gb', float),
            'DISK_LIMIT_GB': ('disk_limit_gb', float),
            'TASK_TIMEOUT': ('task_timeout', int),
            'RETRY_ATTEMPTS': ('retry_attempts', int),
            'RETRY_DELAY': ('retry_delay', int),
            'INPUT_DIR': 'input_dir',
            'OUTPUT_DIR': 'output_dir',
            'TEMP_DIR': 'temp_dir',
            'LOG_DIR': 'log_dir',
            'WEB_HOST': 'web_host',
            'WEB_PORT': ('web_port', int),
            'WEB_DEBUG': ('web_debug', bool),
            'FORUM_CHECK_INTERVAL': ('forum_check_interval', int),
            'FORUM_ENABLED': ('forum_enabled', bool),
            'FORUM_PARSING_ENABLED': ('forum_parsing_enabled', bool),
            'FORUM_TEST_MODE': ('forum_test_mode', bool),
            'FORUM_TEST_ONCE': ('forum_test_once', bool),
            'LOG_LEVEL': 'log_level',
            'LOG_FORMAT': 'log_format',
            'LOG_MAX_SIZE': 'log_max_size',
            'LOG_BACKUP_COUNT': ('log_backup_count', int),
            'USE_GPU': ('use_gpu', bool),
            'GPU_AUTO_DETECT': ('gpu_auto_detect', bool),
        }

        for env_key, config_mapping in env_mappings.items():
            env_value = os.getenv(env_key)
            if env_value is not None:
                if isinstance(config_mapping, tuple):
                    config_key, value_type = config_mapping
                    try:
                        if value_type == bool:
                            value = env_value.lower() in ('true', '1', 'yes', 'on')
                        else:
                            value = value_type(env_value)
                        setattr(self.config, config_key, value)
                    except ValueError:
                        print(f"警告: 环境变量 {env_key} 值无效: {env_value}")
                else:
                    setattr(self.config, config_mapping, env_value)

    def _validate_config(self):
        """验证配置"""
        # 验证并发数
        if self.config.max_concurrent_videos <= 0:
            self.config.max_concurrent_videos = 1
        elif self.config.max_concurrent_videos > 10:
            print("警告: 最大并发数过高，建议不超过10")

        # 验证资源限制
        if self.config.memory_limit_gb < 2.0:
            print("警告: 内存限制过低，建议至少2GB")
            self.config.memory_limit_gb = 2.0

        if self.config.disk_limit_gb < 10.0:
            print("警告: 磁盘限制过低，建议至少10GB")
            self.config.disk_limit_gb = 10.0

        # 验证超时设置
        if self.config.task_timeout < 300:
            print("警告: 任务超时时间过短，建议至少5分钟")
            self.config.task_timeout = 300

    def _ensure_directories(self):
        """确保必要目录存在"""
        directories = [
            self.config.input_dir,
            self.config.output_dir,
            self.config.temp_dir,
            self.config.log_dir
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

    def _detect_gpu(self):
        """检测GPU并更新配置"""
        if self.config.gpu_auto_detect:
            has_gpu = check_gpu_available()
            if has_gpu:
                print("检测到NVIDIA GPU，已启用GPU加速")
                self.config.use_gpu = True
                # 更新pipeline配置中的GPU设置
                self.config.pipeline_config["use_gpu"] = True
                # 如果检测到GPU，确保使用GPU编码器
                if self.config.pipeline_config.get("silence_codec_v") == "libx264":
                    self.config.pipeline_config["silence_codec_v"] = "h264_nvenc"
            else:
                print("未检测到NVIDIA GPU，使用CPU模式")
                self.config.use_gpu = False
                self.config.pipeline_config["use_gpu"] = False
                # 如果没有GPU，将编码器改回CPU版本
                if self.config.pipeline_config.get("silence_codec_v") == "h264_nvenc":
                    self.config.pipeline_config["silence_codec_v"] = "libx264"

    def _disable_asr_by_default(self):
        """默认关闭 ASR 相关步骤（识别）。如需启用，可在后续配置中显式打开。"""
        # 关闭预设的语音识别步骤（Step4）
        self.config.pipeline_config["enable_step4"] = False
        # 若存在通用开关名称，同步关闭
        for k in ("enable_asr", "asr_enabled"):
            if k in self.config.pipeline_config:
                self.config.pipeline_config[k] = False



    def get_config(self) -> LightweightConfig:
        """                                                                                                                                                                         "
        pass

    def get_pipeline_config(self) -> Dict[str, Any]:
        """获取pipeline配置"""
        # 合并轻量级配置到pipeline配置中
        pipeline_config = self.config.pipeline_config.copy()
        pipeline_config.update({
            'output_dir': self.config.output_dir,
            'temp_dir': self.config.temp_dir,
            'debug': self.config.debug,
            'use_gpu': self.config.use_gpu,
        })
        return pipeline_config

    def get_config(self) -> LightweightConfig:
        """获取配置对象"""
        return self.config


    def update_config(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self._validate_config()

    def save_config(self, config_file: Optional[str] = None):
        """保存配置到文件"""
        if not config_file:
            config_file = self.config_file

        if not config_file:
            raise ValueError("未指定配置文件路径")

        config_dict = {
            key: getattr(self.config, key)
            for key in self.config.__dataclass_fields__.keys()
            if not key.startswith('_')
        }

        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                if config_file.endswith('.yaml') or config_file.endswith('.yml'):
                    yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
                else:
                    json.dump(config_dict, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise RuntimeError(f"保存配置文件失败: {e}")


# 全局配置管理器实例
_config_manager = None


def get_config_manager(config_file: Optional[str] = None) -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_file)
    return _config_manager


def get_config() -> LightweightConfig:
    """获取配置对象的便捷函数"""
    return get_config_manager().get_config()


def get_pipeline_config() -> Dict[str, Any]:
    """获取pipeline配置的便捷函数"""
    return get_config_manager().get_pipeline_config()
