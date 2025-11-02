#!/usr/bin/env python3
"""
集群监控系统工具函数
提供通用的工具函数，避免代码重复
"""

import os
import sys
import socket
import subprocess
import webbrowser
import time
import requests
from pathlib import Path


def is_port_in_use(port: int) -> bool:
    """检查端口是否被占用"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
    except OSError:
        return False


def find_available_port(start_port: int = 8000, max_attempts: int = 10) -> int:
    """查找可用端口"""
    for port in range(start_port, start_port + max_attempts):
        if not is_port_in_use(port):
            return port
    raise Exception(f"无法在{start_port}-{start_port+max_attempts}范围内找到可用端口")


def check_dependencies(packages: list) -> tuple:
    """
    检查依赖是否安装

    Args:
        packages: 包列表，格式为 [(import_name, package_name), ...]

    Returns:
        (success: bool, missing: list, installed: list)
    """
    missing = []
    installed = []

    for import_name, package_name in packages:
        try:
            __import__(import_name.replace('-', '_'))
            installed.append(package_name)
            print(f"✅ {package_name}")
        except ImportError:
            missing.append(package_name)
            print(f"❌ {package_name}")

    return len(missing) == 0, missing, installed


def install_dependencies(requirements_file: str = "requirements.txt") -> bool:
    """安装依赖"""
    try:
        print(f"📦 正在安装依赖包...")

        if not os.path.exists(requirements_file):
            print(f"❌ 找不到依赖文件: {requirements_file}")
            return False

        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", requirements_file
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ 依赖安装成功")
            return True
        else:
            print(f"❌ 依赖安装失败: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ 安装依赖时出错: {e}")
        return False


def create_directories(*dirs):
    """创建必要的目录"""
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)
        print(f"📁 确保目录存在: {dir_path}")


def auto_open_browser(url: str) -> bool:
    """自动打开浏览器"""
    try:
        print(f"🌐 自动打开浏览器: {url}")
        webbrowser.open(url)
        return True
    except Exception as e:
        print(f"⚠️ 无法自动打开浏览器: {e}")
        return False


def auto_start_monitoring(port: int) -> bool:
    """自动启动论坛监控"""
    try:
        monitor_url = f"http://localhost:{port}/api/start-monitoring"
        print("🔍 自动启动论坛监控...")
        response = requests.post(monitor_url, timeout=10)
        if response.status_code == 200:
            print("✅ 论坛监控已自动启动")
            return True
        else:
            print(f"⚠️ 论坛监控启动失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠️ 无法自动启动论坛监控: {e}")
        print("💡 请手动访问Web界面启动监控")
        return False


# 配置管理功能已移至config.py中的ConfigManager
# 这里保留兼容性函数
def load_env_file(env_file: str = ".env"):
    """加载环境变量文件（兼容性函数）"""
    from config import config_manager
    return config_manager.load_env_file(env_file)


def create_default_env_file(env_file: str = ".env"):
    """创建默认环境配置文件（兼容性函数）"""
    from config import config_manager
    return config_manager.create_default_env_file(env_file)


def create_default_machines_config(machines_file: str = "machines.txt"):
    """创建默认机器配置（兼容性函数）"""
    from config import config_manager
    return config_manager.create_default_machines_config(machines_file)


def check_wsgi_server():
    """检查WSGI服务器是否安装（Windows优先使用Waitress）"""
    import platform
    is_windows = platform.system().lower() == 'windows'

    if is_windows:
        # Windows系统优先使用Waitress
        try:
            import waitress
            print("✅ Waitress已安装（Windows推荐）")
            return 'waitress'
        except ImportError:
            print("❌ Waitress未安装")
            return None
    else:
        # Unix系统使用Gunicorn
        try:
            import gunicorn
            print("✅ Gunicorn已安装")
            return 'gunicorn'
        except ImportError:
            print("❌ Gunicorn未安装")
            return None


def install_wsgi_server():
    """安装适合当前系统的WSGI服务器"""
    import platform
    is_windows = platform.system().lower() == 'windows'

    if is_windows:
        print("📦 安装Waitress（Windows推荐）...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "waitress"])
            print("✅ Waitress安装完成")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Waitress安装失败: {e}")
            return False
    else:
        print("📦 安装Gunicorn...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "gunicorn"])
            print("✅ Gunicorn安装完成")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Gunicorn安装失败: {e}")
            return False


def wait_for_server_start(port: int, timeout: int = 10):
    """等待服务器启动"""
    print(f"⏳ 等待服务器启动...")
    for i in range(timeout):
        if is_port_in_use(port):
            print(f"✅ 服务器已启动")
            return True
        time.sleep(1)
    print(f"⚠️ 服务器启动超时")
    return False


def create_wsgi_app():
    """创建WSGI应用入口文件"""
    wsgi_content = '''#!/usr/bin/env python3
"""
WSGI应用入口文件
用于Gunicorn等WSGI服务器
"""

import os
import sys

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from forum_monitor import ForumMonitor

# 创建应用实例
def create_app(port=8000):  # 改为默认8000端口
    """创建Flask应用实例"""
    monitor = ForumMonitor(port)
    return monitor.app

# WSGI应用对象
application = create_app()
app = application

if __name__ == "__main__":
    # 直接运行时使用开发服务器，从环境变量获取端口或使用默认8000
    import os
    port = int(os.getenv('PORT', 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
'''

    with open("wsgi.py", "w", encoding="utf-8") as f:
        f.write(wsgi_content)

    print("✅ WSGI入口文件已创建: wsgi.py")


def create_gunicorn_config(port: int, workers: int = 4):
    """创建Gunicorn配置文件"""
    config_content = f"""# Gunicorn配置文件
# 生产环境配置

# 服务器socket
bind = "0.0.0.0:{port}"
backlog = 2048

# Worker进程
workers = {workers}
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# 重启
max_requests = 1000
max_requests_jitter = 50
preload_app = True

# 日志
accesslog = "logs/gunicorn_access.log"
errorlog = "logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%%(h)s %%(l)s %%(u)s %%(t)s "%%(r)s" %%(s)s %%(b)s "%%(f)s" "%%(a)s"'

# 进程命名
proc_name = "cluster_monitor"

# 安全
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
"""

    with open("gunicorn.conf.py", "w", encoding="utf-8") as f:
        f.write(config_content)

    print("✅ Gunicorn配置文件已创建: gunicorn.conf.py")