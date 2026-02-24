#!/usr/bin/env python3
"""
集群监控系统
功能：监控论坛新帖 → 选择最空闲机器 → 发送任务

使用方法：
1. 修改 machines.txt 配置处理机器列表
2. 修改 config.py 配置论坛监控参数
3. 运行: python forum_monitor.py --port 8000
"""

import os
import sys
import time
import uuid
import requests
import threading
from flask import Flask, jsonify, request, render_template_string, render_template
from datetime import datetime
from typing import List, Dict, Optional
import json
import logging

from shared.forum_config import load_forum_settings
from shared.task_model import TaskType
from web_hub.lightweight.queue_manager import QueueManager

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 添加父目录到路径以导入论坛爬虫
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入配置
from config import MonitorConfig

# 模拟数据管理器（默认禁用；仅当 ENABLE_MOCK_DATA=true 或 ENV=development 时启用）
MOCK_DATA_AVAILABLE = False
_ENABLE_MOCK = os.getenv("ENABLE_MOCK_DATA", "").lower() == "true" or os.getenv("ENV", "").lower() in ("dev", "development")
if _ENABLE_MOCK:
    try:
        from test_utils.mock_data_manager import get_mock_data_manager
        MOCK_DATA_AVAILABLE = True
        print("✅ 模拟数据管理器导入成功")
    except ImportError:
        print("ℹ️ 模拟数据管理器不可用（开发功能），不影响生产")
        MOCK_DATA_AVAILABLE = False

# 🎯 导入完整版论坛爬虫
try:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from aicut_forum_crawler import AicutForumCrawler
    from shared.forum_crawler_manager import get_forum_crawler_manager
    FORUM_CRAWLER_AVAILABLE = True
    print("✅ 论坛爬虫模块导入成功")
except ImportError as e:
    print(f"❌ 论坛爬虫导入失败: {e}")
    FORUM_CRAWLER_AVAILABLE = False


class SimpleMachine:
    """简单机器信息"""
    def __init__(self, host: str, port: int, priority: int = 5):
        self.host = host
        self.port = port
        self.priority = priority  # 数字越小优先级越高
        self.url = f"http://{host}:{port}"
        self.is_online = False
        self.is_busy = False
        self.current_tasks = 0
        self.last_check = None


class ForumMonitor:
    """集群监控器"""
    
    def __init__(self, port: int = 8000):
        self.port = port
        self.app = Flask(__name__)
        self.config = MonitorConfig()
        self.dispatch_mode = getattr(self.config, 'TASK_DISPATCH_MODE', 'cluster').lower()
        self.queue_manager: Optional[QueueManager] = None
        if self.dispatch_mode in {'local', 'hybrid'}:
            try:
                self.queue_manager = QueueManager()
                print(f"✅ 本地队列管理器初始化成功 (模式: {self.dispatch_mode})")
            except Exception as exc:
                print(f"⚠️ 本地队列管理器初始化失败: {exc}")
                self.queue_manager = None
                if self.dispatch_mode == 'local':
                    print("❌ 分发模式设置为 local 但队列初始化失败，将回退到 cluster")
                    self.dispatch_mode = 'cluster'
        
        # 设置日志
        self.setup_logging()
        
        # 处理机器列表
        self.machines: List[SimpleMachine] = []
        self.load_machines()
        
        # 论坛监控
        self.monitoring_active = False
        self.monitor_thread = None

        # 初始化SQLite + Redis数据管理器
        try:
            from enhanced_data_manager import get_sqlite_redis_data_manager
            self.data_manager = get_sqlite_redis_data_manager()
            print("✅ SQLite + Redis 数据管理器初始化成功")
        except Exception as e:
            print(f"⚠️ 数据管理器初始化失败: {e}")
            # 降级到独立数据管理器
            try:
                from standalone_data_manager import get_standalone_data_manager
                self.data_manager = get_standalone_data_manager()
                print("✅ 降级到独立数据管理器")
            except Exception as e2:
                print(f"⚠️ 独立数据管理器也初始化失败: {e2}")
                self.data_manager = None

        # 论坛爬虫
        self.forum_crawler = None
        if FORUM_CRAWLER_AVAILABLE and self.config.FORUM_MONITORING_ENABLED:
            try:
                # 获取论坛账号信息
                username = self.config.FORUM_USERNAME
                password = self.config.FORUM_PASSWORD

                # 集群监控系统使用生产模式，避免重复处理
                test_mode = self.config.FORUM_TEST_MODE  # 从配置读取，默认false
                test_once = self.config.FORUM_TEST_ONCE  # 从配置读取，默认false

                print(f"🔧 论坛爬虫配置:")
                print(f"   - 用户名: {username}")

                # 只在测试模式时显示
                if test_mode:
                    print(f"   - 测试模式: ✅ 是")

                # 只在单次运行时显示
                if test_once:
                    print(f"   - 单次运行: ✅ 是")

                # 🎯 使用 ForumCrawlerManager 获取爬虫实例
                print("📋 使用 ForumCrawlerManager 获取论坛爬虫实例...")
                self.forum_crawler_manager = get_forum_crawler_manager()
                self.forum_crawler = self.forum_crawler_manager.get_crawler("main")

                # 🎯 使用Manager的_ensure_logged_in方法确保登录（避免重复登录）
                print("🔐 确保论坛爬虫已登录...")
                self.forum_crawler_manager._ensure_logged_in(self.forum_crawler)

                if self.forum_crawler.logged_in:
                    print("✅ 论坛爬虫已就绪（已登录）")
                else:
                    print("⚠️ 论坛登录失败，将以游客模式运行")

                print("✅ 论坛爬虫初始化成功")

            except Exception as e:
                print(f"⚠️ 论坛爬虫初始化失败: {e}")
                self.forum_crawler = None
        
        # 初始化模拟数据管理器
        self.mock_data_manager = None
        if MOCK_DATA_AVAILABLE:
            try:
                self.mock_data_manager = get_mock_data_manager()
                # 启动模拟数据更新
                self.mock_data_manager.start_mock_updates()
                print("✅ 模拟数据管理器初始化成功并启动更新")
            except Exception as e:
                print(f"⚠️ 模拟数据管理器初始化失败: {e}")
                self.mock_data_manager = None

        # 统计信息（现在从模拟数据管理器获取）
        if self.mock_data_manager:
            # 使用模拟数据管理器的合并数据
            self.stats = self.mock_data_manager.get_combined_stats()
            print("📊 使用模拟数据管理器的统计数据")
        else:
            # 降级到原始统计数据
            self.stats = {
                'total_tasks_sent': 0,
                'successful_tasks': 0,
                'failed_tasks': 0,
                'last_forum_check': None,
                'new_posts_found': 0,
                'start_time': datetime.now(),
                'local_tasks_queued': 0
            }
            print("📊 使用原始统计数据")

        # 集群监控系统的已处理任务记录
        self.dispatched_tasks = set()  # 记录已分发的任务，避免重复分发
        
        # 设置路由
        self.setup_routes()

        # 设置改进版API
        try:
            from improved_api import setup_improved_task_api
            setup_improved_task_api(self.app, self)
            print("✅ 改进版API已启用")
        except ImportError:
            print("⚠️ 改进版API模块不可用，使用基础API")
        
        print("🚀 集群监控器初始化完成")
    
    def get_current_stats(self) -> Dict:
        """获取当前统计数据（模拟数据与真实数据合并）"""
        if self.mock_data_manager:
            # 从模拟数据管理器获取最新的合并数据
            return self.mock_data_manager.get_combined_stats()
        else:
            # 返回原始统计数据
            return self.stats.copy()
    
    def add_real_stat(self, key: str, value: int = 1):
        """添加真实统计数据"""
        if self.mock_data_manager:
            # 添加到模拟数据管理器的真实数据偏移中
            self.mock_data_manager.add_real_data(key, value)
        else:
            # 直接更新原始统计数据
            if key in self.stats:
                self.stats[key] += value
    
    def setup_logging(self):
        """设置日志"""
        import sys
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # 🎯 确保控制台输出使用UTF-8编码
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        # 设置控制台编码为UTF-8
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'{log_dir}/forum_monitor.log', encoding='utf-8'),
                console_handler
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_machines(self):
        """从配置文件加载机器列表"""
        # 使用当前脚本所在目录的 machines.txt，而不是工作目录
        machines_file = os.path.join(os.path.dirname(__file__), "machines.txt")
        if not os.path.exists(machines_file):
            # 创建示例配置文件
            with open(machines_file, 'w', encoding='utf-8') as f:
                f.write("# 处理机器列表 (IP:端口:优先级)\n")
                f.write("# 优先级数字越小越优先，不写默认为5\n")
                f.write("# 示例配置：\n")
                f.write("localhost:8001:1\n")
                f.write("localhost:8002:2\n")
                f.write("# 192.168.1.100:8001:1  # 高性能GPU机器\n")
                f.write("# 192.168.1.101:8001:2  # 普通处理机器\n")
            print(f"📝 已创建示例配置文件: {machines_file}")
        
        try:
            line_number = 0
            valid_machines = 0

            with open(machines_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line_number += 1
                    line = line.strip()

                    # 跳过空行和注释
                    if not line or line.startswith('#'):
                        continue

                    # 验证配置格式
                    parts = line.split(':')
                    if len(parts) < 2:
                        print(f"⚠️ 第{line_number}行格式错误: {line}")
                        print("   正确格式: IP地址:端口:优先级")
                        continue

                    try:
                        host = parts[0].strip()
                        port = int(parts[1].strip())

                        # 处理优先级字段，去除注释
                        priority_str = parts[2].strip() if len(parts) > 2 else "5"
                        # 如果有注释，只取注释前的部分
                        if '#' in priority_str:
                            priority_str = priority_str.split('#')[0].strip()
                        priority = int(priority_str) if priority_str else 5

                        # 验证端口范围
                        if not (1 <= port <= 65535):
                            print(f"⚠️ 第{line_number}行端口无效: {port} (应在1-65535之间)")
                            continue

                        # 验证优先级范围
                        if not (1 <= priority <= 10):
                            print(f"⚠️ 第{line_number}行优先级建议在1-10之间: {priority}")

                        machine = SimpleMachine(host, port, priority)
                        self.machines.append(machine)
                        valid_machines += 1

                    except ValueError as e:
                        print(f"⚠️ 第{line_number}行数据格式错误: {line} - {e}")
                        continue

            if valid_machines > 0:
                print(f"📋 成功加载 {valid_machines} 台处理机器:")
                for machine in self.machines:
                    print(f"   - {machine.url} (优先级: {machine.priority})")
            else:
                print("⚠️ 未找到有效的工作节点配置")
                print("📝 请检查 machines.txt 文件格式")

        except Exception as e:
            print(f"❌ 加载机器列表失败: {e}")
            self.logger.error(f"加载机器列表失败: {e}")
    
    def setup_routes(self):
        """设置API路由"""
        
        @self.app.route('/')
        def index():
            """主页 - 显示监控状态"""
            current_stats = self.get_current_stats()
            uptime = datetime.now() - current_stats['start_time']
            uptime_seconds = int(uptime.total_seconds())
            uptime_str = f"{uptime_seconds//3600}h {(uptime_seconds%3600)//60}m {uptime_seconds%60}s"
            online_machines = sum(1 for m in self.machines if m.is_online)

            return render_template('index.html',
                                 monitoring_active=self.monitoring_active,
                                 stats=current_stats,
                                 machines=self.machines,
                                 port=self.port,
                                        uptime_str=uptime_str,
                                        online_machines=online_machines,
                                        total_machines=len(self.machines))

        @self.app.route('/map')
        def map_dashboard():
            """地图监控页面 - 石家庄中心化视图"""
            current_stats = self.get_current_stats()
            uptime = datetime.now() - current_stats['start_time']
            uptime_seconds = int(uptime.total_seconds())
            uptime_str = f"{uptime_seconds//3600}h {(uptime_seconds%3600)//60}m {uptime_seconds%60}s"
            online_machines = sum(1 for m in self.machines if m.is_online)

            # 准备机器数据的JSON格式
            machines_json = []
            for machine in self.machines:
                machines_json.append({
                    'url': machine.url,
                    'host': machine.host,
                    'port': machine.port,
                    'priority': machine.priority,
                    'is_online': machine.is_online,
                    'is_busy': machine.is_busy,
                    'current_tasks': machine.current_tasks,
                    'last_check': machine.last_check
                })

            return render_template('map_dashboard.html',
                                 monitoring_active=self.monitoring_active,
                                 stats=current_stats,
                                 machines=self.machines,
                                 machines_json=machines_json,
                                 port=self.port,
                                 uptime_str=uptime_str,
                                 online_machines=online_machines,
                                 total_machines=len(self.machines))

        @self.app.route('/map-test')
        def map_test():
            """地图测试页面"""
            return render_template('map_test.html')

        @self.app.route('/professional')
        def professional_flyline():
            """专业版飞线图页面"""
            return render_template('professional_flyline.html')
        
        @self.app.route('/api/machines')
        def get_machines():
            """获取机器列表"""
            machines_data = []
            for machine in self.machines:
                machines_data.append({
                    'url': machine.url,
                    'host': machine.host,
                    'port': machine.port,
                    'priority': machine.priority,
                    'is_online': machine.is_online,
                    'is_busy': machine.is_busy,
                    'current_tasks': machine.current_tasks,
                    'last_check': machine.last_check
                })
            return jsonify({'machines': machines_data})
        
        @self.app.route('/api/start-monitoring', methods=['POST'])
        def start_monitoring():
            """启动论坛监控"""
            if self.start_forum_monitoring():
                return jsonify({'status': 'started', 'message': '论坛监控已启动'})
            else:
                return jsonify({'error': '论坛监控启动失败'}), 500
        
        @self.app.route('/api/stop-monitoring', methods=['POST'])
        def stop_monitoring():
            """停止论坛监控"""
            self.stop_forum_monitoring()
            return jsonify({'status': 'stopped', 'message': '论坛监控已停止'})
        
        @self.app.route('/api/check-machines', methods=['POST'])
        def check_machines():
            """检查所有机器状态"""
            self.check_all_machines()
            return jsonify({'status': 'checked', 'message': '机器状态已更新'})
        
        @self.app.route('/api/send-task', methods=['POST'])
        def send_task_manual():
            """手动发送任务（测试用）"""
            try:
                task_data = request.json
                if not task_data:
                    return jsonify({
                        'success': False,
                        'error': '缺少任务数据',
                        'code': 'MISSING_TASK_DATA'
                    }), 400

                # 检查必需字段
                if 'title' not in task_data and 'source_url' not in task_data:
                    return jsonify({
                        'success': False,
                        'error': '缺少必需字段: title 或 source_url',
                        'code': 'MISSING_REQUIRED_FIELDS'
                    }), 400

                # 转换任务数据格式以匹配工作节点期望的格式
                formatted_task = self._format_task_data(task_data)

                machine = self.select_best_machine()
                if machine:
                    success = self.send_task_to_machine(machine, formatted_task)
                    if success:
                        return jsonify({
                            'success': True,
                            'status': 'sent',
                            'machine': machine.url,
                            'task_data': formatted_task
                        })
                    else:
                        return jsonify({
                            'success': False,
                            'error': 'Failed to send task to machine',
                            'machine': machine.url
                        }), 500
                else:
                    return jsonify({
                        'success': False,
                        'error': 'No available machines',
                        'code': 'NO_AVAILABLE_MACHINES'
                    }), 503

            except Exception as e:
                self.logger.error(f"发送任务异常: {e}")
                return jsonify({
                    'success': False,
                    'error': f'Internal server error: {str(e)}',
                    'code': 'INTERNAL_ERROR'
                }), 500
        
        @self.app.route('/api/status')
        def get_status():
            """获取监控器状态"""
            current_stats = self.get_current_stats()
            uptime = datetime.now() - current_stats['start_time']

            # 获取数据管理器统计
            data_stats = {}
            if self.data_manager:
                data_stats = self.data_manager.get_statistics()

            # 获取模拟数据管理器状态
            mock_stats = {}
            if self.mock_data_manager:
                mock_stats = self.mock_data_manager.get_status()

            return jsonify({
                'monitoring_active': self.monitoring_active,
                'uptime_seconds': int(uptime.total_seconds()),
                'machines_count': len(self.machines),
                'online_machines': sum(1 for m in self.machines if m.is_online),
                'stats': current_stats,
                'data_stats': data_stats,
                'mock_stats': mock_stats,
                'config': {
                    'check_interval': self.config.CHECK_INTERVAL,
                    'forum_enabled': self.config.FORUM_MONITORING_ENABLED,
                    'mock_data_enabled': self.mock_data_manager is not None
                }
            })

        @self.app.route('/api/posts')
        def get_posts():
            """获取帖子列表"""
            if not self.data_manager:
                return jsonify({'error': '数据管理器不可用'}), 503

            status = request.args.get('status', 'all')
            limit = int(request.args.get('limit', 50))

            if status == 'all':
                # 获取所有状态的统计
                stats = self.data_manager.get_statistics()
                return jsonify({
                    'statistics': stats,
                    'status_counts': stats.get('status_counts', {})
                })
            else:
                # 获取特定状态的帖子
                posts = self.data_manager.get_posts_by_status(status, limit)
                posts_data = [post.to_dict() for post in posts]
                return jsonify({
                    'posts': posts_data,
                    'count': len(posts_data),
                    'status': status
                })
        
        # 模拟数据管理API
        @self.app.route('/api/mock-data/status')
        def get_mock_data_status():
            """获取模拟数据状态"""
            if not self.mock_data_manager:
                return jsonify({'error': '模拟数据管理器不可用'}), 503
            
            return jsonify(self.mock_data_manager.get_status())
        
        @self.app.route('/api/mock-data/start', methods=['POST'])
        def start_mock_data():
            """启动模拟数据更新"""
            if not self.mock_data_manager:
                return jsonify({'error': '模拟数据管理器不可用'}), 503
            
            self.mock_data_manager.start_mock_updates()
            return jsonify({'status': 'started', 'message': '模拟数据更新已启动'})
        
        @self.app.route('/api/mock-data/stop', methods=['POST'])
        def stop_mock_data():
            """停止模拟数据更新"""
            if not self.mock_data_manager:
                return jsonify({'error': '模拟数据管理器不可用'}), 503
            
            self.mock_data_manager.stop_mock_updates()
            return jsonify({'status': 'stopped', 'message': '模拟数据更新已停止'})
        
        @self.app.route('/api/mock-data/reset', methods=['POST'])
        def reset_mock_data():
            """重置模拟数据"""
            if not self.mock_data_manager:
                return jsonify({'error': '模拟数据管理器不可用'}), 503
            
            reset_type = request.json.get('type', 'mock') if request.json else 'mock'
            
            if reset_type == 'mock':
                self.mock_data_manager.reset_mock_data()
                return jsonify({'status': 'reset', 'message': '模拟数据已重置'})
            elif reset_type == 'real':
                self.mock_data_manager.reset_real_data()
                return jsonify({'status': 'reset', 'message': '真实数据累计已重置'})
            elif reset_type == 'all':
                self.mock_data_manager.reset_mock_data()
                self.mock_data_manager.reset_real_data()
                return jsonify({'status': 'reset', 'message': '所有数据已重置'})
            else:
                return jsonify({'error': '无效的重置类型'}), 400
    
    def start_forum_monitoring(self):
        """启动论坛监控"""
        try:
            if self.monitoring_active:
                return True

            self.monitoring_active = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()

            print("🔍 论坛监控已启动")
            print("🔍 机器状态检查已集成到监控循环中")
            self.logger.info("论坛监控已启动")
            self.logger.info("机器状态检查已启动")
            return True

        except Exception as e:
            print(f"❌ 启动论坛监控失败: {e}")
            self.logger.error(f"启动论坛监控失败: {e}")
            return False
    
    def stop_forum_monitoring(self):
        """停止论坛监控"""
        self.monitoring_active = False
        print("🛑 论坛监控已停止")
        self.logger.info("论坛监控已停止")
    
    def _monitor_loop(self):
        """监控主循环"""
        while self.monitoring_active:
            try:
                # 检查机器状态
                self.check_all_machines()
                
                # 检查论坛新帖（这里可以集成真实的论坛监控逻辑）
                if self.config.FORUM_MONITORING_ENABLED:
                    new_posts = self.check_forum_posts()
                    self.stats['last_forum_check'] = datetime.now().strftime('%H:%M:%S')
                    
                    if new_posts:
                        # 使用新的统计方法
                        self.add_real_stat('new_posts_found', len(new_posts))
                        print(f"🆕 发现 {len(new_posts)} 个新帖")
                        self.logger.info(f"发现 {len(new_posts)} 个新帖")
                        
                        # 为每个新帖分发任务
                        for post in new_posts:
                            self.dispatch_task(post)
                
                # 等待指定间隔
                time.sleep(self.config.CHECK_INTERVAL)
                
            except Exception as e:
                print(f"❌ 监控循环异常: {e}")
                self.logger.error(f"监控循环异常: {e}")
                time.sleep(30)
    
    def check_forum_posts(self):
        """检查论坛新帖（真实实现）"""
        try:
            if not self.forum_crawler:
                print("⚠️ 论坛爬虫未初始化")
                return []

            print(f"🔍 检查论坛新帖: {self.config.FORUM_TARGET_URL}")

            # 🎯 使用完整版论坛爬虫获取详细信息（包括封面标题、视频/音频链接等）
            print("📋 使用完整版论坛爬虫获取帖子详细信息")
            new_posts = self.forum_crawler.monitor_new_posts()

            if new_posts:
                print(f"✅ 发现 {len(new_posts)} 个新帖子")
                # 🎯 处理每个帖子，构建任务数据
                tasks = []
                for post in new_posts:
                    # 🎯 从cover_info中提取封面标题
                    cover_info = post.get('cover_info', {})
                    cover_title_up = cover_info.get('cover_title_up', '')
                    cover_title_down = cover_info.get('cover_title_down', '')

                    # 🎯 监控节点：只传递URL和基本信息，让工作节点自己处理
                    task = {
                        'title': post.get('title', '未知标题'),
                        'source_url': post.get('thread_url'),  # 统一使用 source_url
                        'video_urls': post.get('video_urls', []),
                        'audio_urls': post.get('audio_urls', []),  # 🎯 音频链接
                        'original_filenames': post.get('original_filenames', []),
                        'category': post.get('category', ''),  # 🎯 Discuz分类信息字段
                        'metadata': {
                            'post_id': post.get('thread_id'),
                            'source_url': post.get('thread_url'),  # 统一使用 source_url
                            'thread_id': post.get('thread_id'),
                            'discovered_at': datetime.now().isoformat(),
                            'forum_name': post.get('forum_name', '智能剪口播'),
                            'source': 'forum',
                            'category': post.get('category', '')  # 🎯 Discuz分类信息字段
                        }
                    }

                    # 🎯 监控节点只负责传递原始数据，不做任务类型判断
                    # 工作节点会根据category字段自己判断任务类型并处理

                    print(f"📦 准备分发任务: {task.get('title')}")
                    if task.get('category'):
                        print(f"   分类: {task.get('category')}")
                    print(f"   视频: {len(task.get('video_urls', []))} 个")
                    print(f"   音频: {len(task.get('audio_urls', []))} 个")

                    # 🎯 所有任务都添加到列表，由工作节点决定如何处理
                    tasks.append(task)

                return tasks
            else:
                print("📭 暂无新帖子")
                return []

        except Exception as e:
            print(f"❌ 检查论坛新帖失败: {e}")
            self.logger.error(f"检查论坛新帖失败: {e}")
            return []



    def check_all_machines(self):
        """检查所有机器状态"""
        print("🔍 检查所有机器状态...")
        for machine in self.machines:
            self.check_machine_status(machine)
    
    def check_machine_status(self, machine: SimpleMachine):
        """检查单个机器状态 - 优化版本"""
        try:
            start_time = time.time()
            # 🎯 关键修复：使用正确的工作节点状态端点
            response = requests.get(f"{machine.url}/api/worker/status", timeout=3)
            response_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                machine.is_online = True
                machine.is_busy = data.get('is_busy', False)
                machine.current_tasks = data.get('total_queue_size', 0)  # 使用正确的字段名
                machine.last_check = datetime.now().strftime('%H:%M:%S')
                machine.response_time = round(response_time * 1000, 2)  # 毫秒
                machine.last_error = None

                # 🎯 调试信息：显示工作节点状态
                queue_sizes = data.get('queue_sizes', {})
                if queue_sizes:
                    print(f"📊 工作节点 {machine.url} 队列状态: {queue_sizes}")
            else:
                machine.is_online = False
                machine.last_error = f"HTTP {response.status_code}"
                
        except Exception as e:
            machine.is_online = False
            machine.is_busy = False
            machine.current_tasks = 0
            machine.last_error = str(e)[:100]  # 限制错误信息长度
    
    def _detect_task_type_from_category(self, category: str) -> str:
        """根据论坛分类判断任务类型"""
        if not category:
            return TaskType.VIDEO.value

        category = category.strip()

        # 音色克隆
        if '音色克隆' in category:
            return TaskType.VOICE_CLONE.value

        # TTS
        if '制作AI声音' in category or '制作ai声音' in category:
            return TaskType.TTS.value

        # 默认为视频
        return TaskType.VIDEO.value

    def _build_queue_payload(self, post_data: Dict, formatted_task: Dict) -> Dict:
        metadata = post_data.get('metadata', {})

        # 🎯 根据category判断任务类型
        category = post_data.get('category', '') or metadata.get('category', '')
        task_type = self._detect_task_type_from_category(category)

        payload = {
            'thread_id': metadata.get('post_id') or metadata.get('thread_id'),
            'thread_url': post_data.get('source_url') or formatted_task.get('url'),  # 统一使用 source_url
            'video_urls': post_data.get('video_urls', []),
            'original_filenames': post_data.get('original_filenames', []),
            'author_id': metadata.get('author_id'),
            'author': post_data.get('author') or metadata.get('author'),
            'forum_name': metadata.get('forum_name'),
            'title': post_data.get('title'),
            'content': post_data.get('content'),
            'cover_info': post_data.get('cover_info') or metadata.get('cover_info'),
            'source': post_data.get('source', metadata.get('source', 'forum')),
            'payload': post_data.get('payload'),
            'task_type': task_type,  # 使用检测到的任务类型
        }

        if not payload['thread_url']:
            payload['thread_url'] = formatted_task.get('url') or metadata.get('source_url')  # 统一使用 source_url

        if not payload['video_urls'] and formatted_task.get('metadata', {}).get('video_urls'):
            payload['video_urls'] = formatted_task['metadata']['video_urls']

        return payload

    def _submit_to_local_queue(self, post_data: Dict, formatted_task: Dict) -> Optional[str]:
        if not self.queue_manager:
            self.logger.error("本地队列管理器不可用，无法提交任务")
            return None

        queue_payload = self._build_queue_payload(post_data, formatted_task)
        try:
            task_id = self.queue_manager.submit_task(queue_payload)
            return task_id
        except Exception as exc:
            self.logger.error(f"提交任务到本地队列失败: {exc}")
            return None

    def _format_task_data(self, task_data: Dict) -> Dict:
        """格式化任务数据以匹配工作节点期望的格式"""
        formatted_task = {}

        # 🎯 关键修复：工作节点期望 'url' 字段
        # 处理URL字段 - 优先使用帖子URL让工作节点自己解析
        if 'source_url' in task_data:
            # 帖子URL - 让工作节点解析视频链接
            formatted_task['url'] = task_data['source_url']
            print(f"📝 发送帖子URL给工作节点: {task_data['source_url']}")
        elif 'video_urls' in task_data and task_data['video_urls']:
            # 如果有video_urls，使用第一个
            formatted_task['url'] = task_data['video_urls'][0]
        elif 'url' in task_data:
            formatted_task['url'] = task_data['url']
        else:
            # 如果没有URL，返回错误
            raise ValueError("任务数据中缺少URL信息")

        # 🎯 关键修复：确保任务ID存在
        if 'task_id' not in task_data:
            # 生成唯一的任务ID
            task_id = f"cluster-{uuid.uuid4().hex[:8]}"
            formatted_task['task_id'] = task_id
            print(f"📝 生成集群任务ID: {task_id}")
        else:
            formatted_task['task_id'] = task_data['task_id']

        formatted_task['task_type'] = task_data.get('task_type', TaskType.VIDEO.value)
        if 'payload' in task_data and task_data['payload'] is not None:
            formatted_task['payload'] = task_data['payload']

        # 处理metadata字段
        metadata = {}
        if 'title' in task_data:
            metadata['title'] = task_data['title']
        if 'description' in task_data:
            metadata['description'] = task_data['description']
        if 'tags' in task_data:
            metadata['tags'] = task_data['tags']

        # 🎯 关键修复：传递封面标题信息
        if 'cover_title_up' in task_data:
            metadata['cover_title_up'] = task_data['cover_title_up']
            print(f"📝 传递封面标题上: {metadata['cover_title_up']}")
        if 'cover_title_middle' in task_data:
            metadata['cover_title_middle'] = task_data['cover_title_middle']
            print(f"📝 传递封面标题中: {metadata['cover_title_middle']}")
        if 'cover_title_down' in task_data:
            metadata['cover_title_down'] = task_data['cover_title_down']
            print(f"📝 传递封面标题下: {metadata['cover_title_down']}")
        if 'cover_info_raw' in task_data:
            metadata['cover_info_raw'] = task_data['cover_info_raw']
            print(f"📝 传递原始封面信息: {len(task_data['cover_info_raw'])} 字符")

        # 🎯 关键修复：传递原始文件名信息
        # 处理原始文件名 - 从视频链接描述中提取
        if 'original_filenames' in task_data and task_data['original_filenames']:
            # 如果有原始文件名列表，使用第一个
            metadata['original_filename'] = task_data['original_filenames'][0]
            print(f"📝 传递原始文件名: {metadata['original_filename']}")
        elif 'video_names' in task_data and task_data['video_names']:
            # 如果有视频名称列表，使用第一个
            metadata['original_filename'] = task_data['video_names'][0]
            print(f"📝 传递视频名称: {metadata['original_filename']}")
        elif formatted_task.get('source_url'):
            # 从URL中提取文件名作为备用
            try:
                import urllib.parse
                import os
                parsed_url = urllib.parse.urlparse(formatted_task['source_url'])
                filename = os.path.basename(parsed_url.path)
                if filename:
                    filename = urllib.parse.unquote(filename, encoding='utf-8')
                    metadata['original_filename'] = filename
                    print(f"📝 从URL提取文件名: {filename}")
            except Exception as e:
                print(f"⚠️ 无法从URL提取文件名: {e}")

        # 传递帖子URL用于解析
        if 'source_url' in task_data:
            metadata['source_url'] = task_data['source_url']

        # 🎯 关键修复：标识这是论坛任务，启用热词功能
        metadata['is_forum_task'] = True
        metadata['forum_source'] = 'aicut_forum'

        # 🎯 关键修复：传递category字段用于任务类型判断
        if 'category' in task_data:
            metadata['category'] = task_data['category']
            print(f"📝 传递论坛分类: {task_data['category']}")

        # 🎯 关键修复：传递完整帖子数据给工作节点数据库
        forum_post_data = {}
        if 'content' in task_data:
            forum_post_data['content'] = task_data['content']
            print(f"📝 传递帖子内容: {len(task_data['content'])} 字符")

        if 'core_text' in task_data:
            forum_post_data['core_text'] = task_data['core_text']
            print(f"📝 传递核心文本: {len(task_data['core_text'])} 字符")

        if 'cover_title_up' in task_data:
            forum_post_data['cover_title_up'] = task_data['cover_title_up']
            print(f"📝 传递封面标题上: {task_data['cover_title_up']}")

        if 'cover_title_middle' in task_data:
            forum_post_data['cover_title_middle'] = task_data['cover_title_middle']
            print(f"📝 传递封面标题中: {task_data['cover_title_middle']}")

        if 'cover_title_down' in task_data:
            forum_post_data['cover_title_down'] = task_data['cover_title_down']
            print(f"📝 传递封面标题下: {task_data['cover_title_down']}")

        # 将论坛帖子数据添加到metadata中
        if forum_post_data:
            metadata['forum_post_data'] = forum_post_data
            print(f"📝 传递论坛帖子数据: {len(forum_post_data)} 个字段")

            # 🎯 调试：显示传递的具体内容
            if 'content' in task_data:
                content_preview = task_data['content'][:200] + "..." if len(task_data['content']) > 200 else task_data['content']
                print(f"📄 传递的帖子内容预览: {content_preview}")

            if 'core_text' in task_data:
                core_text_preview = task_data['core_text'][:200] + "..." if len(task_data['core_text']) > 200 else task_data['core_text']
                print(f"🎯 传递的核心文本预览: {core_text_preview}")

        # 如果没有title，生成一个默认的
        if 'title' not in metadata:
            metadata['title'] = f"集群任务 - {datetime.now().strftime('%Y%m%d_%H%M%S')}"

        metadata['task_type'] = formatted_task['task_type']
        metadata['video_urls'] = task_data.get('video_urls', [])
        metadata['audio_urls'] = task_data.get('audio_urls', [])  # 🎯 传递音频链接

        formatted_task['metadata'] = metadata

        # 添加其他可能的字段
        for key in ['priority', 'callback_url', 'options']:
            if key in task_data:
                formatted_task[key] = task_data[key]

        return formatted_task

    def select_best_machine(self) -> Optional[SimpleMachine]:
        """选择最佳机器"""
        # 🔍 调试信息：显示所有机器状态
        print(f"🔍 机器选择调试 - 总共 {len(self.machines)} 台机器:")
        for m in self.machines:
            print(f"   - {m.url} | 优先级:{m.priority} | 在线:{m.is_online} | 忙碌:{m.is_busy} | 任务数:{m.current_tasks}")

        # 只考虑在线的机器
        online_machines = [m for m in self.machines if m.is_online]
        print(f"🔍 在线机器: {len(online_machines)} 台")
        if not online_machines:
            return None

        # 优先选择空闲机器
        idle_machines = [m for m in online_machines if not m.is_busy]
        print(f"🔍 空闲机器: {len(idle_machines)} 台")
        if idle_machines:
            # 在空闲机器中选择优先级最高的
            selected = min(idle_machines, key=lambda m: (m.priority, m.current_tasks))
            print(f"🎯 选择空闲机器: {selected.url} (优先级:{selected.priority})")
            return selected

        # 都在忙，选择任务最少的
        selected = min(online_machines, key=lambda m: (m.current_tasks, m.priority))
        print(f"🎯 选择忙碌机器: {selected.url} (任务数:{selected.current_tasks})")
        return selected
    
    def dispatch_task(self, post_data: Dict):
        """分发任务（带重复检查）"""
        # 提取帖子信息（适应新的简化格式）
        post_id = post_data.get('metadata', {}).get('post_id', '')
        title = post_data.get('title', '未知标题')
        author = post_data.get('metadata', {}).get('author', '未知作者')
        url = post_data.get('source_url', '')  # 统一使用 source_url

        # 使用数据管理器检查是否已处理
        if self.data_manager and self.data_manager.is_post_processed(post_id):
            print(f"⏭️ 跳过已处理帖子: {title}")
            return

        # 添加到数据管理器
        if self.data_manager:
            self.data_manager.add_post(post_id, title, author, url)

        # 🎯 关键修复：格式化任务数据以匹配工作节点期望的格式
        try:
            formatted_task = self._format_task_data(post_data)
        except Exception as e:
            print(f"❌ 格式化任务数据失败: {e}")
            if self.data_manager:
                self.data_manager.mark_post_failed(post_id, f"格式化任务数据失败: {e}")
            return

        # 本地队列模式直接提交
        if self.dispatch_mode == 'local':
            queued_id = self._submit_to_local_queue(post_data, formatted_task)
            if queued_id:
                if self.data_manager:
                    self.data_manager.mark_post_dispatched(post_id, 'local_queue')
                self.add_real_stat('total_tasks_sent', 1)
                self.add_real_stat('successful_tasks', 1)
                self.add_real_stat('local_tasks_queued', 1)
                print(f"✅ 任务已排入本地队列: {title} (任务ID: {queued_id})")
                self.logger.info(f"任务排入本地队列: {post_id}")
            else:
                if self.data_manager:
                    self.data_manager.mark_post_failed(post_id, "本地队列提交失败")
                self.add_real_stat('total_tasks_sent', 1)
                self.add_real_stat('failed_tasks', 1)
                print(f"❌ 提交任务到本地队列失败: {title}")
                self.logger.error(f"提交任务到本地队列失败: {post_id}")
            return

        machine = self.select_best_machine()
        if machine:
            success = self.send_task_to_machine(machine, formatted_task)
            if success:
                if self.data_manager:
                    self.data_manager.mark_post_dispatched(post_id, machine.url)

                self.add_real_stat('total_tasks_sent', 1)
                self.add_real_stat('successful_tasks', 1)
                print(f"✅ 任务已发送到 {machine.url}: {title}")
                self.logger.info(f"任务已发送到 {machine.url}: {post_id}")
                return

            self.logger.error(f"任务发送失败: {machine.url}")
            print(f"❌ 任务发送失败: {machine.url}")

            if self.dispatch_mode == 'hybrid':
                queued_id = self._submit_to_local_queue(post_data, formatted_task)
                if queued_id:
                    if self.data_manager:
                        self.data_manager.mark_post_dispatched(post_id, 'local_queue')
                    self.add_real_stat('total_tasks_sent', 1)
                    self.add_real_stat('successful_tasks', 1)
                    self.add_real_stat('local_tasks_queued', 1)
                    print(f"✅ 失败后切换到本地队列: {title} (任务ID: {queued_id})")
                    self.logger.info(f"任务发送失败后改为本地队列: {post_id}")
                    return

            if self.data_manager:
                self.data_manager.mark_post_failed(post_id, "任务发送失败")
            self.add_real_stat('total_tasks_sent', 1)
            self.add_real_stat('failed_tasks', 1)
            self.logger.error(f"任务发送失败且未能回退: {post_id}")
            return

        # 没有可用机器
        self.logger.warning("没有可用的处理机器")
        print("⚠️ 没有可用的处理机器")

        if self.dispatch_mode == 'hybrid':
            queued_id = self._submit_to_local_queue(post_data, formatted_task)
            if queued_id:
                if self.data_manager:
                    self.data_manager.mark_post_dispatched(post_id, 'local_queue')
                self.add_real_stat('total_tasks_sent', 1)
                self.add_real_stat('successful_tasks', 1)
                self.add_real_stat('local_tasks_queued', 1)
                print(f"✅ 无机器可用，任务排入本地队列: {title} (任务ID: {queued_id})")
                self.logger.info(f"无机器可用，任务排入本地队列: {post_id}")
                return

        if self.data_manager:
            self.data_manager.mark_post_failed(post_id, "没有可用的处理机器")
        self.add_real_stat('total_tasks_sent', 1)
        self.add_real_stat('failed_tasks', 1)
        self.logger.warning(f"没有可用的处理机器且未能回退: {post_id}")

    def _generate_task_key(self, post_data: Dict) -> str:
        """生成任务唯一标识"""
        # 使用帖子ID和视频URL生成唯一标识
        thread_id = post_data.get('metadata', {}).get('thread_id', '')
        source_url = post_data.get('source_url', '')
        return f"{thread_id}_{hash(source_url)}"
    
    def send_task_to_machine(self, machine: SimpleMachine, task_data: Dict) -> bool:
        """发送任务到指定机器"""
        try:
            # 只使用集群工作节点API端点，不再回退到轻量级API
            response = requests.post(
                f"{machine.url}/api/worker/receive-task",
                json=task_data,
                timeout=30
            )

            if response.status_code == 200:
                print(f"✅ 集群API成功: {machine.url}")
                return True
            elif response.status_code == 503:
                print(f"⚠️ 工作节点忙碌: {machine.url}")
                return False
            else:
                print(f"❌ 集群API失败 ({response.status_code}): {machine.url}")
                print(f"💡 请确保工作节点以集群模式启动: python start_lightweight.py --cluster-worker --port {machine.port}")
                return False

        except Exception as e:
            print(f"❌ 发送任务到 {machine.url} 失败: {e}")
            print(f"💡 请检查工作节点是否以集群模式启动并且可访问")
            self.logger.error(f"发送任务到 {machine.url} 失败: {e}")
            return False
    
    def run(self):
        """运行监控器"""
        print(f"🚀 集群监控器启动在 http://localhost:{self.port}")
        print(f"📊 Web界面: http://localhost:{self.port}")
        self.logger.info(f"监控器启动在端口 {self.port}")

        try:
            from werkzeug.serving import run_simple
            import logging
            # 禁用werkzeug的日志警告
            werkzeug_logger = logging.getLogger('werkzeug')
            werkzeug_logger.setLevel(logging.ERROR)

            run_simple('0.0.0.0', self.port, self.app,
                      threaded=True,
                      use_reloader=False,
                      use_debugger=False,
                      use_evalex=False)
        except KeyboardInterrupt:
            print("\n🛑 收到停止信号")
            self.stop_forum_monitoring()
            if self.mock_data_manager:
                self.mock_data_manager.stop_mock_updates()
        except Exception as e:
            print(f"❌ 运行异常: {e}")
            self.logger.error(f"运行异常: {e}")
            if self.mock_data_manager:
                self.mock_data_manager.stop_mock_updates()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='集群监控系统')
    parser.add_argument('--port', type=int, default=8000, help='监听端口')
    
    args = parser.parse_args()
    
    # 创建并运行监控器
    monitor = ForumMonitor(args.port)
    monitor.run()


if __name__ == "__main__":
    main()

