#!/usr/bin/env python3
"""
统一依赖管理器
合并了分散在各个文件中的依赖检查逻辑
"""

import sys
import subprocess
from typing import List, Tuple, Dict


class DependencyManager:
    """依赖管理器"""

    # 定义不同模式的依赖包
    PACKAGE_GROUPS = {
        'base': [
            ('flask', 'Flask'),
            ('werkzeug', 'Werkzeug'),
            ('requests', 'requests'),
            ('urllib3', 'urllib3'),
            ('dotenv', 'python-dotenv'),
            ('psutil', 'psutil'),
            ('bs4', 'beautifulsoup4'),
            ('lxml', 'lxml')
        ],
        'production': [
            ('waitress', 'waitress'),  # Windows推荐
            ('gunicorn', 'gunicorn')   # Unix推荐
        ],
        'optional': [
            ('redis', 'redis')
        ],
        'cluster_monitor': [
            ('flask', 'Flask'),
            ('werkzeug', 'Werkzeug'),
            ('requests', 'requests'),
            ('urllib3', 'urllib3'),
            ('dotenv', 'python-dotenv'),
            ('psutil', 'psutil'),
            ('bs4', 'beautifulsoup4'),
            ('lxml', 'lxml'),
            ('redis', 'redis'),
            ('waitress', 'waitress')
        ]
    }

    def __init__(self):
        self.results = {}

    def check_package(self, import_name: str, package_name: str) -> bool:
        """检查单个包是否安装"""
        try:
            __import__(import_name.replace('-', '_'))
            print(f"✅ {package_name}")
            return True
        except ImportError:
            print(f"❌ {package_name}")
            return False

    def check_packages(self, packages: List[Tuple[str, str]]) -> Tuple[bool, List[str], List[str]]:
        """
        检查多个包是否安装

        Args:
            packages: 包列表，格式为 [(import_name, package_name), ...]

        Returns:
            (success: bool, missing: list, installed: list)
        """
        missing = []
        installed = []

        for import_name, package_name in packages:
            if self.check_package(import_name, package_name):
                installed.append(package_name)
            else:
                missing.append(package_name)

        return len(missing) == 0, missing, installed

    def check_group(self, group_name: str) -> Tuple[bool, List[str], List[str]]:
        """检查预定义的包组"""
        if group_name not in self.PACKAGE_GROUPS:
            raise ValueError(f"未知的包组: {group_name}")

        packages = self.PACKAGE_GROUPS[group_name]
        return self.check_packages(packages)

    def check_mode_dependencies(self, mode: str) -> Tuple[bool, List[str], List[str]]:
        """根据模式检查依赖"""
        if mode == 'cluster_monitor':
            return self.check_group('cluster_monitor')
        elif mode == 'production':
            # 检查基础包 + 生产包
            base_success, base_missing, base_installed = self.check_group('base')

            # 检查WSGI服务器（根据系统选择）
            import platform
            is_windows = platform.system().lower() == 'windows'

            if is_windows:
                wsgi_success, wsgi_missing, wsgi_installed = self.check_packages([('waitress', 'waitress')])
            else:
                wsgi_success, wsgi_missing, wsgi_installed = self.check_packages([('gunicorn', 'gunicorn')])

            all_missing = base_missing + wsgi_missing
            all_installed = base_installed + wsgi_installed

            return len(all_missing) == 0, all_missing, all_installed
        else:
            # 默认检查基础包
            return self.check_group('base')

    def install_packages(self, packages: List[str], requirements_file: str = None) -> bool:
        """安装依赖包"""
        try:
            if requirements_file and packages == ['requirements']:
                # 从requirements文件安装
                print(f"📦 从 {requirements_file} 安装依赖...")
                result = subprocess.run([
                    sys.executable, "-m", "pip", "install", "-r", requirements_file
                ], capture_output=True, text=True)
            else:
                # 安装指定包
                print(f"📦 安装依赖包: {', '.join(packages)}")
                result = subprocess.run([
                    sys.executable, "-m", "pip", "install"
                ] + packages, capture_output=True, text=True)

            if result.returncode == 0:
                print("✅ 依赖安装成功")
                return True
            else:
                print(f"❌ 依赖安装失败: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ 安装依赖时出错: {e}")
            return False

    def check_redis_service(self) -> bool:
        """检查Redis服务是否可用"""
        try:
            import redis
            client = redis.Redis(host='localhost', port=6379, db=1, socket_timeout=3)
            client.ping()
            print("✅ Redis服务可用")
            return True
        except ImportError:
            print("⚠️ Redis模块未安装，将使用SQLite模式")
            return False
        except Exception as e:
            print(f"⚠️ Redis服务不可用: {e}")
            print("💡 系统将降级到SQLite模式")
            return False

    def get_installation_command(self, missing_packages: List[str]) -> str:
        """获取安装命令"""
        if missing_packages:
            return f"pip install {' '.join(missing_packages)}"
        return ""

    def print_summary(self, success: bool, missing: List[str], installed: List[str]):
        """打印检查结果摘要"""
        print(f"\n📊 依赖检查结果:")
        print(f"   - 已安装: {len(installed)}")
        print(f"   - 缺失: {len(missing)}")

        if missing:
            print(f"\n❌ 缺少以下依赖:")
            for pkg in missing:
                print(f"   - {pkg}")
            print(f"\n💡 安装命令:")
            print(f"   {self.get_installation_command(missing)}")
        else:
            print(f"\n🎉 所有依赖都已安装！")


# 全局实例
dependency_manager = DependencyManager()


def check_dependencies_for_mode(mode: str) -> Tuple[bool, List[str], List[str]]:
    """为指定模式检查依赖（便捷函数）"""
    return dependency_manager.check_mode_dependencies(mode)


def install_missing_dependencies(missing_packages: List[str]) -> bool:
    """安装缺失的依赖（便捷函数）"""
    return dependency_manager.install_packages(missing_packages)


if __name__ == "__main__":
    # 测试代码
    print("🧪 测试依赖管理器...")

    # 测试集群监控模式
    success, missing, installed = dependency_manager.check_mode_dependencies('cluster_monitor')
    dependency_manager.print_summary(success, missing, installed)

    # 测试Redis服务
    dependency_manager.check_redis_service()

    print("🎉 测试完成")