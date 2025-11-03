#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
论坛配置管理器
统一管理论坛相关的环境变量配置，支持多论坛监控

功能：
1. 从环境变量读取论坛配置
2. 支持多个论坛网站配置
3. 提供配置验证功能
4. 统一配置接口

使用方法：
from forum_config_manager import ForumConfigManager
config_manager = ForumConfigManager()
forum_configs = config_manager.get_all_forum_configs()
"""

import os
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

# 确保 shared 可导入
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.forum_config import load_forum_settings

@dataclass
class ForumConfig:
    """单个论坛配置"""
    name: str
    base_url: str
    target_url: str
    username: str
    password: str
    forum_id: int
    enabled: bool = True
    check_interval: int = 10  # 统一默认值为10秒
    auto_reply: bool = True
    test_mode: bool = False
    test_once: bool = False

class ForumConfigManager:
    """论坛配置管理器"""
    
    def __init__(self, env_file: Optional[str] = None):
        self.env_file = env_file or ".env"
        self.configs: Dict[str, ForumConfig] = {}
        self._load_env_file()
        self._load_configs()
    
    def _load_env_file(self):
        """加载环境变量文件"""
        env_path = Path(self.env_file)
        if env_path.exists():
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()
            except Exception as e:
                print(f"⚠️ 加载环境文件失败: {e}")
    
    def _load_configs(self):
        """从环境变量加载论坛配置"""
        # 加载主论坛配置
        main_config = self._load_main_forum_config()
        if main_config:
            self.configs['main'] = main_config
    
    def _load_main_forum_config(self) -> Optional[ForumConfig]:
        """加载主论坛配置"""
        try:
            settings = load_forum_settings()

            # 支持新的多论坛配置格式
            if 'forums' in settings and 'main' in settings['forums']:
                return self._load_forum_from_settings('main', settings)

            # 兼容旧的单论坛配置格式
            forum_cfg = settings.get('forum', {})
            credentials_cfg = settings.get('credentials', {})

            base_url = os.getenv('FORUM_BASE_URL', forum_cfg.get('base_url'))
            target_url = os.getenv('FORUM_TARGET_URL', forum_cfg.get('target_url'))
            username = os.getenv('FORUM_USERNAME', credentials_cfg.get('username'))
            password = os.getenv('FORUM_PASSWORD', credentials_cfg.get('password'))

            if not all([base_url, target_url, username, password]):
                print("⚠️ 主论坛配置不完整，跳过加载")
                return None

            return ForumConfig(
                name=settings.get('forum', {}).get('name', "懒人同城号AI"),
                base_url=base_url,
                target_url=target_url,
                username=username,
                password=password,
                forum_id=int(os.getenv('FORUM_TARGET_FORUM_ID', forum_cfg.get('forum_id', 2))),
                enabled=os.getenv('FORUM_ENABLED', 'true').lower() == 'true',
                check_interval=int(os.getenv('FORUM_CHECK_INTERVAL', '10')),
                auto_reply=os.getenv('FORUM_AUTO_REPLY_ENABLED', 'true').lower() == 'true',
                test_mode=os.getenv('FORUM_TEST_MODE', 'false').lower() == 'true',
                test_once=os.getenv('FORUM_TEST_ONCE', 'false').lower() == 'true',
            )
        except Exception as e:
            print(f"⚠️ 加载主论坛配置失败: {e}")
            return None

    def _load_forum_from_settings(self, forum_name: str, settings: dict) -> Optional[ForumConfig]:
        """从settings中加载指定论坛配置"""
        try:
            forum_cfg = settings['forums'][forum_name]
            credentials_cfg = forum_cfg.get('credentials', settings.get('credentials', {}))

            base_url = forum_cfg.get('base_url')
            target_url = forum_cfg.get('target_url')
            username = credentials_cfg.get('username')
            password = credentials_cfg.get('password')

            if not all([base_url, target_url, username, password]):
                print(f"⚠️ 论坛 {forum_name} 配置不完整，跳过加载")
                return None

            return ForumConfig(
                name=forum_cfg.get('name', forum_name),
                base_url=base_url,
                target_url=target_url,
                username=username,
                password=password,
                forum_id=forum_cfg.get('forum_id', 2),
                enabled=forum_cfg.get('enabled', True),
                check_interval=forum_cfg.get('check_interval', 10),
                auto_reply=forum_cfg.get('auto_reply', True),
                test_mode=forum_cfg.get('test_mode', False),
                test_once=forum_cfg.get('test_once', False),
            )
        except Exception as e:
            print(f"⚠️ 加载论坛 {forum_name} 配置失败: {e}")
            return None

    def load_all_forums_from_settings(self):
        """从配置文件加载所有论坛"""
        try:
            settings = load_forum_settings()

            # 支持新的多论坛配置格式
            if 'forums' in settings:
                for forum_name in settings['forums'].keys():
                    config = self._load_forum_from_settings(forum_name, settings)
                    if config:
                        self.configs[forum_name] = config
                        print(f"✅ 加载论坛配置: {config.name}")
            else:
                # 兼容旧格式
                main_config = self._load_main_forum_config()
                if main_config:
                    self.configs['main'] = main_config
                    print(f"✅ 加载主论坛配置: {main_config.name}")
        except Exception as e:
            print(f"⚠️ 加载论坛配置失败: {e}")
    
    def get_all_forum_configs(self) -> Dict[str, ForumConfig]:
        """获取所有论坛配置"""
        return self.configs.copy()
    
    def get_enabled_forum_configs(self) -> Dict[str, ForumConfig]:
        """获取启用的论坛配置"""
        return {name: config for name, config in self.configs.items() if config.enabled}
    
    def get_forum_config(self, name: str) -> Optional[ForumConfig]:
        """获取指定论坛配置"""
        return self.configs.get(name)
    
    def get_main_forum_config(self) -> Optional[ForumConfig]:
        """获取主论坛配置"""
        return self.configs.get('main')
    
    def validate_configs(self) -> Tuple[bool, List[str]]:
        """验证所有配置"""
        errors = []
        
        if not self.configs:
            errors.append("没有找到任何论坛配置")
            return False, errors
        
        for name, config in self.configs.items():
            config_errors = self._validate_single_config(name, config)
            errors.extend(config_errors)
        
        return len(errors) == 0, errors
    
    def _validate_single_config(self, name: str, config: ForumConfig) -> List[str]:
        """验证单个配置"""
        errors = []
        
        if not config.base_url:
            errors.append(f"论坛 {name}: 缺少基础URL")
        elif not config.base_url.startswith(('http://', 'https://')):
            errors.append(f"论坛 {name}: 基础URL格式不正确")
        
        if not config.target_url:
            errors.append(f"论坛 {name}: 缺少目标URL")
        elif not config.target_url.startswith(('http://', 'https://')):
            errors.append(f"论坛 {name}: 目标URL格式不正确")
        
        if not config.username:
            errors.append(f"论坛 {name}: 缺少用户名")
        
        if not config.password:
            errors.append(f"论坛 {name}: 缺少密码")
        
        if config.forum_id <= 0:
            errors.append(f"论坛 {name}: 板块ID无效")
        
        if config.check_interval < 5:
            errors.append(f"论坛 {name}: 检查间隔过短（最少5秒）")
        
        return errors
    
    def print_config_summary(self):
        """打印配置摘要"""
        print("📋 论坛配置摘要")
        print("=" * 50)
        
        if not self.configs:
            print("❌ 没有找到任何论坛配置")
            return
        
        for name, config in self.configs.items():
            status = "✅ 启用" if config.enabled else "❌ 禁用"
            mode = "🧪 测试" if config.test_mode else "🚀 生产"
            print(f"📍 {config.name} ({name})")
            print(f"   状态: {status}")
            print(f"   模式: {mode}")
            print(f"   网站: {config.base_url}")
            print(f"   板块: {config.target_url}")
            print(f"   用户: {config.username}")
            print(f"   间隔: {config.check_interval}秒")
            print()


def main():
    """主函数 - 用于测试和配置管理"""
    import argparse
    
    parser = argparse.ArgumentParser(description="论坛配置管理器")
    parser.add_argument("--show", action="store_true", help="显示当前配置")
    parser.add_argument("--validate", action="store_true", help="验证配置")
    parser.add_argument("--env-file", default=".env", help="环境文件路径")
    
    args = parser.parse_args()
    
    config_manager = ForumConfigManager(args.env_file)
    
    if args.show:
        config_manager.print_config_summary()
    
    if args.validate:
        is_valid, errors = config_manager.validate_configs()
        if is_valid:
            print("✅ 所有配置验证通过")
        else:
            print("❌ 配置验证失败:")
            for error in errors:
                print(f"   - {error}")
    
    if not any([args.show, args.validate]):
        config_manager.print_config_summary()


if __name__ == "__main__":
    main()
