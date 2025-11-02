#!/usr/bin/env python3
"""
集群监控系统配置文件
"""

import os
import sys
import io
from pathlib import Path
from dotenv import load_dotenv

# Fix Windows console encoding for emoji support
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except (AttributeError, io.UnsupportedOperation):
        # If stdout/stderr don't have buffer attribute, skip
        pass

# 确保 shared 可导入
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.forum_config import load_forum_settings

# 加载.env文件
load_dotenv()


class MonitorConfig:
    """监控器配置"""
    
    def __init__(self):
        # 基本配置 - 使用.env文件中的FORUM_CHECK_INTERVAL
        self.CHECK_INTERVAL = int(os.getenv('FORUM_CHECK_INTERVAL', os.getenv('CHECK_INTERVAL', '10')))  # 检查间隔(秒)
        self.FORUM_MONITORING_ENABLED = os.getenv('FORUM_ENABLED', 'true').lower() == 'true'

        # 论坛网站配置 - 从.env文件读取
        forum_settings = load_forum_settings()
        forum_cfg = forum_settings.get('forum', {})
        credentials_cfg = forum_settings.get('credentials', {})

        self.FORUM_BASE_URL = os.getenv('FORUM_BASE_URL') or forum_cfg["base_url"]
        self.FORUM_TARGET_URL = os.getenv('FORUM_TARGET_URL') or forum_cfg["target_url"]
        self.FORUM_USERNAME = os.getenv('FORUM_USERNAME', os.getenv('AICUT_ADMIN_USERNAME', credentials_cfg.get('username', '')))
        self.FORUM_PASSWORD = os.getenv('FORUM_PASSWORD', os.getenv('AICUT_ADMIN_PASSWORD', credentials_cfg.get('password', '')))
        self.FORUM_TARGET_FORUM_ID = int(os.getenv('FORUM_TARGET_FORUM_ID') or forum_cfg["forum_id"])

        # 论坛功能配置
        self.FORUM_AUTO_REPLY_ENABLED = os.getenv('FORUM_AUTO_REPLY_ENABLED', 'true').lower() == 'true'
        self.FORUM_TEST_MODE = os.getenv('FORUM_TEST_MODE', 'false').lower() == 'true'
        self.FORUM_TEST_ONCE = os.getenv('FORUM_TEST_ONCE', 'false').lower() == 'true'

        # 爬虫配置
        self.CRAWLER_MODE = os.getenv('CRAWLER_MODE', 'TEST')
        self.MAX_POSTS_TO_PROCESS = int(os.getenv('MAX_POSTS_TO_PROCESS', '50'))

        # 网络配置
        self.REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))  # 请求超时(秒)
        self.MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))  # 最大重试次数

        # 任务分发配置
        self.TASK_DISPATCH_STRATEGY = os.getenv('TASK_DISPATCH_STRATEGY', 'least_busy')  # 分发策略
        # 可选值: 'least_busy', 'priority', 'round_robin'
        self.TASK_DISPATCH_MODE = os.getenv('TASK_DISPATCH_MODE', 'cluster').lower()
        if self.TASK_DISPATCH_MODE not in {'cluster', 'local', 'hybrid'}:
            print(f"⚠️ 未知的 TASK_DISPATCH_MODE: {self.TASK_DISPATCH_MODE}，将退回 cluster")
            self.TASK_DISPATCH_MODE = 'cluster'

        # 日志配置
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_FILE = os.getenv('LOG_FILE', 'logs/forum_monitor.log')

        # 论坛配置（兼容旧版本）
        self.FORUM_URLS = self._parse_forum_urls()
        self.FORUM_CHECK_KEYWORDS = self._parse_keywords()

        # 机器配置
        self.MACHINES_CONFIG_FILE = os.getenv('MACHINES_CONFIG_FILE', 'machines.txt')

        # Web界面配置
        self.WEB_REFRESH_INTERVAL = int(os.getenv('WEB_REFRESH_INTERVAL', '10'))  # 页面刷新间隔(秒)

        # 验证配置安全性
        self._validate_security()
        
        # 打印配置信息
        self._print_config_info()
    
    def _validate_security(self):
        """验证配置安全性"""
        warnings = []
        errors = []
        
        if self.FORUM_MONITORING_ENABLED:
            # 检查用户名
            if not self.FORUM_USERNAME:
                errors.append("论坛用户名未配置")
            
            # 检查密码安全性
            if not self.FORUM_PASSWORD:
                errors.append("论坛密码未配置")
            elif self.FORUM_PASSWORD in ['your_password_here', 'your_secure_password_here', 'password', '123456', 'admin']:
                errors.append("请设置安全的论坛密码，当前使用的是默认密码")
            elif len(self.FORUM_PASSWORD) < 8:
                warnings.append("建议密码长度至少8位")
            elif self.FORUM_PASSWORD.isdigit():
                warnings.append("建议密码包含字母和数字组合")
        
        # 输出安全检查结果
        if errors:
            print("🚨 安全检查失败:")
            for error in errors:
                print(f"   ❌ {error}")
            print("💡 请修改 .env 文件中的配置后重新启动")
        
        if warnings:
            print("⚠️ 安全建议:")
            for warning in warnings:
                print(f"   🔶 {warning}")
        
        if not errors and not warnings:
            print("🔒 安全检查通过")
    
    def _print_config_info(self):
        """打印配置信息（隐藏敏感信息）"""
        print("📋 集群监控器配置:")

        # 只显示启用的功能，禁用的功能不显示
        if self.FORUM_MONITORING_ENABLED:
            print(f"   - 论坛监控: ✅ 启用")
            print(f"   - 目标论坛: {self.FORUM_BASE_URL}")
            print(f"   - 目标板块: {self.FORUM_TARGET_URL}")
            
            # 🔒 安全处理：隐藏敏感用户信息
            if self.FORUM_USERNAME:
                username_display = f"{self.FORUM_USERNAME[:2]}***{self.FORUM_USERNAME[-1:]}" if len(self.FORUM_USERNAME) > 3 else "***"
                print(f"   - 监控用户: {username_display}")
            else:
                print(f"   - 监控用户: ❌ 未配置")
            
            # 🔒 安全处理：隐藏密码，只显示状态
            password_status = "✅ 已配置" if self.FORUM_PASSWORD and self.FORUM_PASSWORD != 'your_secure_password_here' else "❌ 未配置"
            print(f"   - 密码状态: {password_status}")
            
            print(f"   - 检查间隔: {self.CHECK_INTERVAL}秒")

            # 只在测试模式时显示
            if self.FORUM_TEST_MODE:
                print(f"   - 测试模式: ✅ 是")

            # 只在启用自动回复时显示
            if self.FORUM_AUTO_REPLY_ENABLED:
                print(f"   - 自动回复: ✅ 启用")

            dispatch_mode_map = {
                'cluster': '集群节点',
                'local': '本地队列',
                'hybrid': '集群优先 + 本地兜底'
            }
            print(f"   - 分发模式: {dispatch_mode_map.get(self.TASK_DISPATCH_MODE, '集群节点')}")

    def _parse_forum_urls(self):
        """解析论坛URL配置（兼容旧版本）"""
        urls_str = os.getenv('FORUM_URLS', '')
        if urls_str:
            return [url.strip() for url in urls_str.split(',') if url.strip()]
        # 如果没有配置FORUM_URLS，使用新的配置
        if self.FORUM_TARGET_URL:
            return [self.FORUM_TARGET_URL]
        return []
    
    def _parse_keywords(self):
        """解析关键词配置"""
        keywords_str = os.getenv('FORUM_KEYWORDS', '视频,音频,处理,剪辑')
        return [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
    
    def get_task_dispatch_strategy(self):
        """获取任务分发策略"""
        return self.TASK_DISPATCH_STRATEGY

    def get_task_dispatch_mode(self):
        """获取任务分发模式"""
        return self.TASK_DISPATCH_MODE
    
    def is_forum_monitoring_enabled(self):
        """是否启用论坛监控"""
        return self.FORUM_MONITORING_ENABLED
    
    def get_check_interval(self):
        """获取检查间隔"""
        return self.CHECK_INTERVAL
    
    def to_dict(self):
        """转换为字典"""
        return {
            'check_interval': self.CHECK_INTERVAL,
            'forum_monitoring_enabled': self.FORUM_MONITORING_ENABLED,
            'forum_base_url': self.FORUM_BASE_URL,
            'forum_target_url': self.FORUM_TARGET_URL,
            'forum_username': self.FORUM_USERNAME,
            'forum_target_forum_id': self.FORUM_TARGET_FORUM_ID,
            'forum_auto_reply_enabled': self.FORUM_AUTO_REPLY_ENABLED,
            'forum_test_mode': self.FORUM_TEST_MODE,
            'forum_test_once': self.FORUM_TEST_ONCE,
            'crawler_mode': self.CRAWLER_MODE,
            'max_posts_to_process': self.MAX_POSTS_TO_PROCESS,
            'request_timeout': self.REQUEST_TIMEOUT,
            'max_retries': self.MAX_RETRIES,
            'task_dispatch_strategy': self.TASK_DISPATCH_STRATEGY,
            'log_level': self.LOG_LEVEL,
            'forum_urls': self.FORUM_URLS,
            'forum_keywords': self.FORUM_CHECK_KEYWORDS,
            'web_refresh_interval': self.WEB_REFRESH_INTERVAL
        }


class ConfigManager:
    """统一配置管理器"""

    @staticmethod
    def load_env_file(env_file: str = ".env"):
        """加载环境变量文件"""
        if os.path.exists(env_file):
            print(f"📋 加载环境配置文件: {env_file}")
            load_dotenv(env_file, override=True)
            print("✅ 环境配置加载完成")
            return True
        else:
            print(f"⚠️ 环境配置文件不存在: {env_file}")
            return False

    @staticmethod
    def create_default_env_file(env_file: str = ".env"):
        """创建默认环境配置文件"""
        if not os.path.exists(env_file):
            default_config = """# 集群监控系统配置

# 论坛监控配置
FORUM_ENABLED=true
FORUM_CHECK_INTERVAL=10
FORUM_BASE_URL=https://tts.lrtcai.com
FORUM_TARGET_URL=https://tts.lrtcai.com/forum-2-1.html
FORUM_USERNAME=AI剪辑助手
FORUM_PASSWORD=your_password_here

# 论坛功能配置
FORUM_AUTO_REPLY_ENABLED=true
FORUM_TEST_MODE=false
FORUM_TEST_ONCE=false

# 任务分发配置
TASK_DISPATCH_STRATEGY=least_busy
REQUEST_TIMEOUT=30
MAX_RETRIES=3

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=logs/forum_monitor.log

# Web界面配置
WEB_REFRESH_INTERVAL=10

# 机器配置文件
MACHINES_CONFIG_FILE=machines.txt

# Redis配置（可选）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=1
REDIS_PASSWORD=

# 数据库配置
DATABASE_TYPE=sqlite
DATABASE_PATH=data/cluster_monitor.db
"""

            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(default_config)

            print(f"✅ 已创建默认配置文件: {env_file}")
            print("💡 请编辑 .env 文件配置论坛账号信息")
            return True
        else:
            print(f"⚠️ 配置文件已存在: {env_file}")
            return False

    @staticmethod
    def create_default_machines_config(machines_file: str = "machines.txt"):
        """创建默认机器配置"""
        if not os.path.exists(machines_file):
            default_machines = """# ================================================================
# 集群工作节点配置文件
# ================================================================
#
# 配置格式: IP地址:端口:优先级
#
# 说明:
# - IP地址: 工作节点的IP地址或主机名
# - 端口: 工作节点的HTTP服务端口
# - 优先级: 数字越小优先级越高 (1=最高优先级, 5=默认优先级)
#
# 示例配置:
# localhost:8003:1        # 本地节点1，最高优先级
# 192.168.1.100:8003:2   # 局域网节点1，高优先级
# 192.168.1.101:8003:3   # 局域网节点2，中等优先级
# ================================================================

# 当前配置的工作节点:
localhost:8003:1    # 本地工作节点1 - 高优先级
localhost:8004:2    # 本地工作节点2 - 中等优先级

# 添加更多节点示例 (取消注释并修改IP地址):
# 192.168.1.100:8003:3
# 192.168.1.101:8003:4
"""

            with open(machines_file, 'w', encoding='utf-8') as f:
                f.write(default_machines)

            print(f"✅ 已创建默认机器配置: {machines_file}")
            return True
        else:
            print(f"⚠️ 机器配置文件已存在: {machines_file}")
            return False

    @staticmethod
    def validate_config(config: MonitorConfig) -> bool:
        """验证配置是否有效"""
        errors = []

        # 检查必需的配置
        if config.FORUM_MONITORING_ENABLED:
            if not config.FORUM_BASE_URL:
                errors.append("FORUM_BASE_URL 不能为空")
            if not config.FORUM_TARGET_URL:
                errors.append("FORUM_TARGET_URL 不能为空")
            if not config.FORUM_USERNAME:
                errors.append("FORUM_USERNAME 不能为空")
            if not config.FORUM_PASSWORD:
                errors.append("FORUM_PASSWORD 不能为空")

        # 检查数值配置
        if config.CHECK_INTERVAL <= 0:
            errors.append("CHECK_INTERVAL 必须大于0")
        if config.REQUEST_TIMEOUT <= 0:
            errors.append("REQUEST_TIMEOUT 必须大于0")
        if config.MAX_RETRIES < 0:
            errors.append("MAX_RETRIES 不能小于0")

        # 检查文件路径
        if not os.path.exists(os.path.dirname(config.LOG_FILE)):
            try:
                os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
            except Exception as e:
                errors.append(f"无法创建日志目录: {e}")

        if errors:
            print("❌ 配置验证失败:")
            for error in errors:
                print(f"   - {error}")
            return False
        else:
            print("✅ 配置验证通过")
            return True

    @staticmethod
    def setup_directories(config: MonitorConfig):
        """创建必要的目录"""
        directories = [
            os.path.dirname(config.LOG_FILE),
            'data',
            'templates',
            'static/css'
        ]

        for directory in directories:
            if directory:  # 避免空字符串
                os.makedirs(directory, exist_ok=True)
                print(f"📁 确保目录存在: {directory}")


# 全局配置管理器实例
config_manager = ConfigManager()

# 默认配置实例
default_config = MonitorConfig()
