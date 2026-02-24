#!/usr/bin/env python3
"""
集群监控系统统一启动器
合并了 start.py, start_production.py, start_standalone.py 的功能
消除代码重复，提供统一的启动接口

克隆/并行运行注意:
- 同机运行多个项目或多个克隆副本时，务必修改 --port
- 修改 monitor 端口后，需同步 cluster_monitor/machines.txt（工作节点地址）

使用方法：
  python start_unified.py --mode dev --port 8100                    # 开发模式
  python start_unified.py --mode production --port 8100             # 生产模式
  python start_unified.py --mode standalone --port 8100             # 独立模式
  python start_unified.py --install-deps                            # 安装依赖
  python start_unified.py --check-only                              # 只检查环境
"""

import os
import sys
import argparse
import threading
import subprocess
from pathlib import Path

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 导入工具函数
from utils import (
    is_port_in_use, find_available_port, create_directories, auto_open_browser,
    auto_start_monitoring, load_env_file, create_default_env_file,
    create_default_machines_config, check_wsgi_server, install_wsgi_server,
    wait_for_server_start, create_wsgi_app, create_gunicorn_config
)

# 导入统一依赖管理器
from dependency_manager import dependency_manager


def check_environment(mode: str) -> bool:
    """检查运行环境"""
    print(f"🔍 检查{mode}模式运行环境...")

    # 使用统一依赖管理器检查依赖
    success, missing, installed = dependency_manager.check_mode_dependencies(mode)

    if not success:
        print(f"\n❌ 缺少必需依赖: {', '.join(missing)}")
        print("💡 使用 --install-deps 参数自动安装依赖")
        return False

    # 检查Redis服务（可选）
    dependency_manager.check_redis_service()

    return True


def start_development_mode(port: int, auto_browser: bool = True, auto_monitor: bool = True):
    """启动开发模式"""
    print("🚀 启动开发模式（会显示Flask开发服务器警告）")
    print(f"📊 端口: {port}")
    print(f"🌐 访问地址: http://localhost:{port}")
    print("-" * 50)

    try:
        from forum_monitor import ForumMonitor
        monitor = ForumMonitor(port)

        # 在后台线程中启动服务器
        server_thread = threading.Thread(target=monitor.run, daemon=True)
        server_thread.start()

        # 等待服务器启动
        if wait_for_server_start(port, 5):
            if auto_browser:
                auto_open_browser(f"http://localhost:{port}")
            if auto_monitor:
                auto_start_monitoring(port)

        print("\n🎉 开发模式启动成功！")
        print("按 Ctrl+C 停止服务")

        # 保持主线程运行
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 正在停止服务...")

    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


def start_production_mode(port: int, workers: int = 4, daemon: bool = False,
                         auto_browser: bool = True, auto_monitor: bool = True):
    """启动生产模式"""
    # 检查WSGI服务器
    wsgi_server = check_wsgi_server()
    if not wsgi_server:
        print("❌ 未安装WSGI服务器")
        print("💡 使用 --install-deps 参数自动安装")
        sys.exit(1)

    # 创建必要文件
    create_wsgi_app()
    if wsgi_server == 'gunicorn':
        create_gunicorn_config(port, workers)

    print(f"🚀 启动生产模式（使用{wsgi_server}）")
    print(f"📊 端口: {port}")
    print(f"🌐 访问地址: http://localhost:{port}")
    print("-" * 50)

    try:
        if wsgi_server == 'waitress':
            start_with_waitress(port, auto_browser, auto_monitor)
        else:
            start_with_gunicorn(port, workers, daemon, auto_browser, auto_monitor)

    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


def start_with_waitress(port: int, auto_browser: bool = True, auto_monitor: bool = True):
    """使用Waitress启动服务（Windows推荐）"""
    try:
        print("按 Ctrl+C 停止服务")

        # 启动服务器（在后台线程中）
        import threading
        from waitress import serve
        from wsgi import application

        # 在后台线程中启动服务器
        server_thread = threading.Thread(
            target=lambda: serve(application, host='0.0.0.0', port=port),
            daemon=True
        )
        server_thread.start()

        # 等待服务器启动
        if wait_for_server_start(port, 5):
            if auto_browser:
                auto_open_browser(f"http://localhost:{port}")
            if auto_monitor:
                auto_start_monitoring(port)

        # 保持主线程运行
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 服务已停止")

    except Exception as e:
        print(f"❌ Waitress启动失败: {e}")
        sys.exit(1)


def start_with_gunicorn(port: int, workers: int = 4, daemon: bool = False,
                       auto_browser: bool = True, auto_monitor: bool = True):
    """使用Gunicorn启动服务"""
    # 构建启动命令
    cmd = [
        sys.executable, "-m", "gunicorn",
        "--config", "gunicorn.conf.py",
        "wsgi:application"
    ]

    if daemon:
        cmd.extend(["--daemon"])

    try:
        if daemon:
            # 后台运行
            subprocess.Popen(cmd)
            print("✅ 服务已在后台启动")

            # 等待服务器启动
            if wait_for_server_start(port, 10):
                if auto_browser:
                    auto_open_browser(f"http://localhost:{port}")
                if auto_monitor:
                    auto_start_monitoring(port)

            print("使用以下命令查看状态:")
            print("  ps aux | grep gunicorn")
            print("使用以下命令停止服务:")
            print("  pkill -f 'gunicorn.*wsgi:application'")
        else:
            # 前台运行
            print("按 Ctrl+C 停止服务")

            # 在后台启动Gunicorn
            server_thread = threading.Thread(
                target=lambda: subprocess.run(cmd),
                daemon=True
            )
            server_thread.start()

            # 等待服务器启动
            if wait_for_server_start(port, 10):
                if auto_browser:
                    auto_open_browser(f"http://localhost:{port}")
                if auto_monitor:
                    auto_start_monitoring(port)

            # 保持主线程运行
            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 服务已停止")

    except Exception as e:
        print(f"❌ Gunicorn启动失败: {e}")
        sys.exit(1)


def start_standalone_mode(port: int, auto_browser: bool = True, auto_monitor: bool = True):
    """启动独立模式"""
    print("🚀 启动独立模式（自动配置）")
    print(f"📊 端口: {port}")
    print(f"🌐 访问地址: http://localhost:{port}")
    print("-" * 50)

    # 创建默认配置
    create_default_env_file()
    create_default_machines_config()

    try:
        from forum_monitor import ForumMonitor
        monitor = ForumMonitor(port)

        # 在后台线程中启动服务器
        server_thread = threading.Thread(target=monitor.run, daemon=True)
        server_thread.start()

        # 等待服务器启动
        if wait_for_server_start(port, 5):
            if auto_browser:
                auto_open_browser(f"http://localhost:{port}")
            if auto_monitor:
                auto_start_monitoring(port)

        print("\n🎉 独立模式启动成功！")
        print("按 Ctrl+C 停止服务")

        # 保持主线程运行
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 正在停止服务...")

    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='集群监控系统统一启动器')
    parser.add_argument('--mode', choices=['dev', 'production', 'standalone'],
                       default='standalone', help='启动模式 (默认: standalone)')
    # 克隆项目并行运行时请显式传 --port，避免与其他副本冲突
    parser.add_argument('--port', type=int, default=8100, help='监听端口 (默认: 8100)')
    parser.add_argument('--workers', type=int, default=4, help='Worker进程数 (默认: 4)')
    parser.add_argument('--daemon', action='store_true', help='后台运行（仅生产模式）')
    parser.add_argument('--install-deps', action='store_true', help='自动安装依赖')
    parser.add_argument('--check-only', action='store_true', help='只检查环境，不启动')
    parser.add_argument('--no-browser', action='store_true', help='不自动打开浏览器')
    parser.add_argument('--no-auto-monitor', action='store_true', help='不自动启动监控')

    args = parser.parse_args()

    print("🚀 集群监控系统统一启动器")
    print("=" * 50)

    # 加载环境变量
    load_env_file()

    # 创建必要目录
    create_directories("logs", "data")

    # 安装依赖
    if args.install_deps:
        # 检查缺失的依赖
        success, missing, installed = dependency_manager.check_mode_dependencies(args.mode)
        if missing:
            if dependency_manager.install_packages(missing):
                print("✅ 依赖安装完成")
            else:
                print("❌ 依赖安装失败")
                sys.exit(1)
        else:
            print("✅ 所有依赖都已安装")

    # 检查环境
    if not check_environment(args.mode):
        if not args.install_deps:
            print("💡 使用 --install-deps 参数自动安装依赖")
        sys.exit(1)

    if args.check_only:
        print("✅ 环境检查完成")
        return

    # 检查端口冲突
    if is_port_in_use(args.port):
        available_port = find_available_port(args.port)
        print(f"⚠️ 端口{args.port}已被占用，自动使用端口{available_port}")
        args.port = available_port

    # 启动相应模式
    auto_browser = not args.no_browser
    auto_monitor = not args.no_auto_monitor

    if args.mode == 'dev':
        start_development_mode(args.port, auto_browser, auto_monitor)
    elif args.mode == 'production':
        start_production_mode(args.port, args.workers, args.daemon, auto_browser, auto_monitor)
    elif args.mode == 'standalone':
        start_standalone_mode(args.port, auto_browser, auto_monitor)


if __name__ == "__main__":
    main()
