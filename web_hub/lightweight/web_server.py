#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
轻量级视频处理系统 - Web监控界面

主要功能：
- 系统状态监控
- 任务管理界面
- 资源使用情况展示
- RESTful API接口
"""

import json
import os
import threading
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from flask import Flask, render_template_string, jsonify, request, Response
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

from .queue_manager import QueueManager, TaskPriority
from .resource_monitor import LightweightResourceMonitor
from .task_processor import TaskProcessor
from .logger import get_logger
from shared.task_model import TaskType

# 导入论坛集成模块
try:
    from .forum_integration import get_forum_integration
    FORUM_INTEGRATION_AVAILABLE = True
except ImportError:
    FORUM_INTEGRATION_AVAILABLE = False

try:
    from forum_data_manager import get_data_manager
    DATA_MANAGER_AVAILABLE = True
except ImportError:
    DATA_MANAGER_AVAILABLE = False


class WebServer:
    """Web监控服务器"""
    
    def __init__(self, config, queue_manager: QueueManager,
                 resource_monitor: LightweightResourceMonitor,
                 task_processor: Optional[TaskProcessor] = None):
        self.config = config
        self.queue_manager = queue_manager
        self.resource_monitor = resource_monitor
        self.task_processor = task_processor
        self.logger = get_logger("WebServer")

        if not FLASK_AVAILABLE:
            raise RuntimeError("Flask未安装，无法启动Web服务器")

        # 初始化论坛集成
        self.forum_integration = None
        self.data_manager = None

        # 🔧 修复：检查论坛功能是否启用
        forum_enabled = getattr(config, 'forum_enabled', False)
        forum_parsing_enabled = getattr(config, 'forum_parsing_enabled', False)

        if FORUM_INTEGRATION_AVAILABLE and (forum_enabled or forum_parsing_enabled):
            try:
                self.forum_integration = get_forum_integration(queue_manager, config)
                self.logger.info("论坛集成模块已加载")
            except Exception as e:
                self.logger.error(f"论坛集成模块加载失败: {e}")
        else:
            self.logger.info("论坛功能已禁用，跳过论坛集成模块加载")

        if DATA_MANAGER_AVAILABLE:
            try:
                self.data_manager = get_data_manager()
                self.logger.info("数据管理器已加载")
            except Exception as e:
                self.logger.error(f"数据管理器加载失败: {e}")

        self.app = Flask(__name__)
        self.app.config['JSON_AS_ASCII'] = False
        self._setup_routes()

        self.server_thread = None
        self.running = False
    
    def _setup_routes(self):
        """设置路由"""
        
        @self.app.route('/')
        def index():
            """主页"""
            return render_template_string(self._get_dashboard_template())
        
        @self.app.route('/health')
        def health_check():
            """健康检查端点"""
            return jsonify({
                "status": "healthy",
                "service": "funclip-lightweight",
                "timestamp": datetime.now().isoformat()
            })

        @self.app.route('/api/status')
        def api_status():
            """系统状态API"""
            return jsonify(self._get_system_status())
        
        @self.app.route('/api/tasks')
        def api_tasks():
            """任务列表API"""
            return jsonify(self._get_tasks_info())
        
        @self.app.route('/api/tasks', methods=['POST'])
        def api_create_task():
            """创建任务API"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': '缺少请求数据'}), 400
                
                source_url = data.get('source_url')
                source_path = data.get('source_path')
                post_url = data.get('post_url')  # 新增：支持帖子URL
                priority = data.get('priority', 'normal')
                task_type_raw = data.get('task_type', TaskType.VIDEO.value)

                # 支持三种任务类型：直接视频URL、本地文件路径、帖子URL
                if not source_url and not source_path and not post_url:
                    return jsonify({'error': '必须提供source_url、source_path或post_url之一'}), 400

                # 如果提供了帖子URL，将其添加到metadata中
                metadata = data.get('metadata', {})
                if post_url:
                    metadata['post_url'] = post_url
                    print(f"🔍 接收到帖子URL任务: {post_url}")
                
                # 转换优先级
                priority_map = {
                    'low': TaskPriority.LOW,
                    'normal': TaskPriority.NORMAL,
                    'high': TaskPriority.HIGH,
                    'urgent': TaskPriority.URGENT
                }
                task_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)
                task_type = self._parse_task_type(task_type_raw)

                # 创建任务
                task_id = self.queue_manager.create_task(
                    source_url=source_url,
                    source_path=source_path,
                    priority=task_priority,
                    metadata=metadata,
                    payload=data.get('payload'),
                    task_type=task_type,
                )
                
                return jsonify({
                    'task_id': task_id,
                    'message': '任务创建成功'
                })
                
            except Exception as e:
                self.logger.error(f"创建任务失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/tasks/<task_id>')
        def api_get_task(task_id):
            """获取任务详情API"""
            task = self.queue_manager.get_task(task_id)
            if not task:
                return jsonify({'error': '任务不存在'}), 404
            
            return jsonify(task.to_dict())
        
        @self.app.route('/api/tasks/<task_id>/cancel', methods=['POST'])
        def api_cancel_task(task_id):
            """取消任务API"""
            task = self.queue_manager.get_task(task_id)
            if not task:
                return jsonify({'error': '任务不存在'}), 404
            
            self.queue_manager.cancel_task(task_id)
            return jsonify({'message': '任务已取消'})
        
        @self.app.route('/api/resources')
        def api_resources():
            """资源使用情况API"""
            return jsonify(self._get_resource_info())
        
        @self.app.route('/api/resources/history')
        def api_resource_history():
            """资源使用历史API"""
            hours = request.args.get('hours', 1, type=int)
            history = self.resource_monitor.get_history(hours)

            return jsonify([snapshot.to_dict() for snapshot in history])

        # 日志管理API
        @self.app.route('/api/system/log-mode', methods=['POST'])
        def api_set_log_mode():
            """设置日志模式API"""
            try:
                data = request.get_json()
                mode = data.get('mode', 'development')

                if mode not in ['development', 'production', 'silent']:
                    return jsonify({'error': '无效的日志模式'}), 400

                # 设置环境变量
                import os
                os.environ['LOG_MODE'] = mode

                # 重新配置日志系统
                try:
                    from lightweight.log_performance_config import set_log_mode
                    config = set_log_mode(mode)

                    self.logger.info(f"日志模式已切换到: {mode}")

                    return jsonify({
                        'success': True,
                        'mode': mode,
                        'config': {
                            'console_enabled': config.console_enabled,
                            'verbose_logging': config.verbose_logging,
                            'production_mode': config.mode == 'production'
                        }
                    })
                except Exception as e:
                    return jsonify({'error': f'设置日志模式失败: {str(e)}'}), 500

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/system/log-status')
        def api_log_status():
            """获取日志状态API"""
            try:
                import os
                from lightweight.log_performance_config import LogPerformanceConfig

                config = LogPerformanceConfig()

                return jsonify({
                    'mode': config.mode,
                    'console_enabled': config.console_enabled,
                    'file_enabled': config.file_logging_enabled,
                    'verbose': config.verbose_logging,
                    'performance_optimized': config.mode in ['production', 'silent'],
                    'log_levels': config.get_log_levels(),
                    'performance_settings': config.get_performance_settings()
                })

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/system/console-logging', methods=['POST'])
        def api_toggle_console_logging():
            """切换控制台日志输出API"""
            try:
                data = request.get_json()
                enabled = data.get('enabled', True)

                # 动态调整日志处理器
                import logging
                root_logger = logging.getLogger()

                # 移除现有控制台处理器
                for handler in root_logger.handlers[:]:
                    if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                        root_logger.removeHandler(handler)

                if enabled:
                    # 重新添加控制台处理器
                    from lightweight.logger import ColoredFormatter
                    handler = logging.StreamHandler()
                    formatter = ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                    handler.setFormatter(formatter)
                    handler.setLevel(logging.INFO)
                    root_logger.addHandler(handler)

                self.logger.info(f"控制台日志已{'启用' if enabled else '禁用'}")

                return jsonify({
                    'success': True,
                    'console_enabled': enabled,
                    'message': f"控制台日志已{'启用' if enabled else '禁用'}"
                })

            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/stats')
        def api_stats():
            """统计信息API"""
            return jsonify(self._get_stats())
        
        @self.app.route('/api/logs')
        def api_logs():
            """日志API"""
            lines = request.args.get('lines', 100, type=int)
            level = request.args.get('level', 'INFO')

            # 这里可以实现日志读取逻辑
            return jsonify({
                'logs': [],
                'message': '日志功能待实现'
            })

        @self.app.route('/api/forum/tasks', methods=['POST'])
        def api_create_forum_task():
            """创建论坛任务API"""
            try:
                data = request.get_json()

                # 验证必需字段
                required_fields = ['post_id', 'video_url']
                for field in required_fields:
                    if field not in data:
                        return jsonify({
                            'success': False,
                            'error': f'缺少必需字段: {field}'
                        }), 400

                # 创建任务元数据
                metadata = {
                    'post_id': data['post_id'],
                    'author_id': data.get('author_id'),
                    'title': data.get('title'),
                    'source': 'forum_api'
                }

                # 创建任务
                task_id = self.queue_manager.create_task(
                    source_url=data['video_url'],
                    priority=TaskPriority.HIGH,  # 论坛任务使用高优先级
                    metadata=metadata
                )

                return jsonify({
                    'success': True,
                    'task_id': task_id,
                    'message': f'论坛任务创建成功'
                })

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/forum/posts')
        def api_forum_posts():
            """获取论坛帖子列表API"""
            try:
                if not self.data_manager:
                    return jsonify({
                        'success': False,
                        'error': '数据管理器未初始化'
                    }), 503

                # 获取查询参数
                status = request.args.get('status', 'all')
                limit = request.args.get('limit', 50, type=int)

                if status == 'all':
                    # 获取所有帖子的统计信息
                    stats = self.data_manager.get_statistics()
                    return jsonify({
                        'success': True,
                        'data': {
                            'statistics': stats,
                            'posts': []
                        }
                    })
                else:
                    # 获取特定状态的帖子
                    posts = self.data_manager.get_posts_by_status(status, limit)
                    posts_data = [post.to_dict() for post in posts]

                    return jsonify({
                        'success': True,
                        'data': {
                            'posts': posts_data,
                            'count': len(posts_data),
                            'status': status
                        }
                    })

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/forum/posts/<post_id>')
        def api_forum_post_detail(post_id):
            """获取论坛帖子详情API"""
            try:
                if not self.data_manager:
                    return jsonify({
                        'success': False,
                        'error': '数据管理器未初始化'
                    }), 503

                post = self.data_manager.get_post(post_id)
                if not post:
                    return jsonify({
                        'success': False,
                        'error': '帖子不存在'
                    }), 404

                return jsonify({
                    'success': True,
                    'data': post.to_dict()
                })

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/forum/stats')
        def api_forum_stats():
            """获取论坛统计信息API"""
            try:
                stats = {}

                # 数据管理器统计
                if self.data_manager:
                    stats['database'] = self.data_manager.get_statistics()

                # 论坛集成统计
                if self.forum_integration:
                    forum_stats = self.forum_integration.get_forum_stats()
                    stats['forum_integration'] = forum_stats

                    # 获取帖子统计
                    post_stats = self.forum_integration.get_post_statistics()
                    stats['posts'] = post_stats

                return jsonify({
                    'success': True,
                    'data': stats
                })

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/forum/monitor', methods=['POST'])
        def api_forum_monitor_control():
            """论坛监控控制API"""
            try:
                if not self.forum_integration:
                    return jsonify({
                        'success': False,
                        'error': '论坛集成未初始化'
                    }), 503

                data = request.get_json()
                action = data.get('action')

                if action == 'start':
                    self.forum_integration.start()
                    return jsonify({
                        'success': True,
                        'message': '论坛监控已启动'
                    })
                elif action == 'stop':
                    self.forum_integration.stop()
                    return jsonify({
                        'success': True,
                        'message': '论坛监控已停止'
                    })
                elif action == 'check':
                    # 手动检查新帖
                    new_posts = self.forum_integration.get_new_posts()
                    return jsonify({
                        'success': True,
                        'data': {
                            'new_posts_count': len(new_posts),
                            'new_posts': new_posts[:5]  # 只返回前5个
                        }
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': '无效的操作'
                    }), 400

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/forum/reply', methods=['POST'])
        def api_forum_reply():
            """发送论坛回复API"""
            try:
                if not self.forum_integration:
                    return jsonify({
                        'success': False,
                        'error': '论坛集成未初始化'
                    }), 503

                data = request.get_json()
                post_id = data.get('post_id')
                content = data.get('content')

                if not post_id:
                    return jsonify({
                        'success': False,
                        'error': '缺少帖子ID'
                    }), 400

                # 使用论坛回复机器人发送回复
                from .forum_integration import ForumReplyBot
                reply_bot = ForumReplyBot(self.config)

                success = reply_bot.send_reply(post_id, content)

                if success:
                    return jsonify({
                        'success': True,
                        'message': '回复发送成功'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': '回复发送失败'
                    }), 500

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/upload/task', methods=['POST'])
        def api_upload_task():
            """创建上传任务"""
            try:
                data = request.get_json()
                post_id = data.get('post_id')
                output_dir = data.get('output_dir')
                original_filename = data.get('original_filename', 'video.mp4')

                if not post_id or not output_dir:
                    return jsonify({'error': '缺少必要参数'}), 400

                if not os.path.exists(output_dir):
                    return jsonify({'error': f'输出目录不存在: {output_dir}'}), 400

                # 创建上传任务
                task_metadata = {
                    'post_id': post_id,
                    'output_dir': output_dir,
                    'original_filename': original_filename,
                    'source': 'manual_upload'
                }

                # 使用队列管理器创建上传任务
                import uuid
                task_id = str(uuid.uuid4())

                # 直接添加到上传队列
                upload_task = {
                    'task_id': task_id,
                    'type': 'upload',
                    'post_id': post_id,
                    'output_dir': output_dir,
                    'original_filename': original_filename,
                    'created_at': datetime.now().isoformat(),
                    'status': 'pending'
                }

                # 添加到Redis上传队列
                import redis
                import json
                r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
                r.lpush('upload_queue', json.dumps(upload_task))

                return jsonify({
                    'success': True,
                    'message': '上传任务创建成功',
                    'task_id': task_id
                })

            except Exception as e:
                self.logger.error(f"上传任务API错误: {e}")
                return jsonify({'error': str(e)}), 500

    def _get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        resource_snapshot = self.resource_monitor.get_current_usage()
        queue_sizes = self.queue_manager.get_queue_sizes()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'status': 'running' if self.running else 'stopped',
            'mode': self.config.mode,
            'resources': {
                'cpu_percent': resource_snapshot.cpu_percent if resource_snapshot else 0,
                'memory_percent': resource_snapshot.memory_percent if resource_snapshot else 0,
                'disk_percent': resource_snapshot.disk_percent if resource_snapshot else 0,
                'gpu_percent': resource_snapshot.gpu_percent if resource_snapshot else 0,
            },
            'queues': queue_sizes,
            'config': {
                'max_concurrent_videos': self.config.max_concurrent_videos,
                'max_download_workers': self.config.max_download_workers,
                'max_upload_workers': self.config.max_upload_workers
            }
        }
    
    def _get_tasks_info(self) -> Dict[str, Any]:
        """获取任务信息"""
        active_tasks = self.queue_manager.get_active_tasks()
        stats = self.queue_manager.get_stats()
        
        return {
            'active_tasks': [task.to_dict() for task in active_tasks],
            'stats': stats
        }
    
    def _get_resource_info(self) -> Dict[str, Any]:
        """获取资源信息"""
        return self.resource_monitor.get_stats()
    
    def _get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            'queue_manager': self.queue_manager.get_stats(),
            'resource_monitor': self.resource_monitor.get_stats()
        }
        
        if self.task_processor:
            stats['task_processor'] = self.task_processor.get_stats()
        
        return stats
    
    def _get_dashboard_template(self) -> str:
        """获取仪表板模板"""
        return '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>轻量级视频处理系统 - 监控面板</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .metric { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #eee; }
        .metric:last-child { border-bottom: none; }
        .metric-value { font-weight: bold; color: #27ae60; }
        .status-running { color: #27ae60; }
        .status-stopped { color: #e74c3c; }
        .btn { background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: #2980b9; }
        .btn-danger { background: #e74c3c; }
        .btn-danger:hover { background: #c0392b; }
        .progress-bar { width: 100%; height: 20px; background: #ecf0f1; border-radius: 10px; overflow: hidden; }
        .progress-fill { height: 100%; background: #3498db; transition: width 0.3s; }
        .task-list { max-height: 400px; overflow-y: auto; }
        .task-item { padding: 10px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 10px; }
        .task-status { padding: 2px 8px; border-radius: 12px; font-size: 12px; color: white; }
        .status-pending { background: #f39c12; }
        .status-processing { background: #3498db; }
        .status-completed { background: #27ae60; }
        .status-failed { background: #e74c3c; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎬 轻量级视频处理系统</h1>
            <p>实时监控和管理界面</p>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>系统状态</h3>
                <div id="system-status">
                    <div class="metric">
                        <span>运行状态</span>
                        <span id="status" class="metric-value">加载中...</span>
                    </div>
                    <div class="metric">
                        <span>运行模式</span>
                        <span id="mode" class="metric-value">-</span>
                    </div>
                    <div class="metric">
                        <span>最大并发</span>
                        <span id="max-concurrent" class="metric-value">-</span>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3>资源使用情况</h3>
                <div id="resource-usage">
                    <div class="metric">
                        <span>CPU使用率</span>
                        <div style="flex: 1; margin-left: 20px;">
                            <div class="progress-bar">
                                <div id="cpu-progress" class="progress-fill" style="width: 0%"></div>
                            </div>
                            <span id="cpu-value">0%</span>
                        </div>
                    </div>
                    <div class="metric">
                        <span>内存使用率</span>
                        <div style="flex: 1; margin-left: 20px;">
                            <div class="progress-bar">
                                <div id="memory-progress" class="progress-fill" style="width: 0%"></div>
                            </div>
                            <span id="memory-value">0%</span>
                        </div>
                    </div>
                    <div class="metric">
                        <span>GPU使用率</span>
                        <div style="flex: 1; margin-left: 20px;">
                            <div class="progress-bar">
                                <div id="gpu-progress" class="progress-fill" style="width: 0%"></div>
                            </div>
                            <span id="gpu-value">0%</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>队列状态</h3>
                <div id="queue-status">
                    <div class="metric">
                        <span>下载队列</span>
                        <span id="download-queue" class="metric-value">0</span>
                    </div>
                    <div class="metric">
                        <span>处理队列</span>
                        <span id="process-queue" class="metric-value">0</span>
                    </div>
                    <div class="metric">
                        <span>上传队列</span>
                        <span id="upload-queue" class="metric-value">0</span>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3>任务统计</h3>
                <div id="task-stats">
                    <div class="metric">
                        <span>总任务数</span>
                        <span id="total-tasks" class="metric-value">0</span>
                    </div>
                    <div class="metric">
                        <span>已完成</span>
                        <span id="completed-tasks" class="metric-value">0</span>
                    </div>
                    <div class="metric">
                        <span>失败任务</span>
                        <span id="failed-tasks" class="metric-value">0</span>
                    </div>
                    <div class="metric">
                        <span>活跃任务</span>
                        <span id="active-tasks" class="metric-value">0</span>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h3>活跃任务</h3>
            <div id="active-tasks-list" class="task-list">
                <p>加载中...</p>
            </div>
        </div>
        
        <div class="card">
            <h3>创建新任务</h3>
            <form id="create-task-form">
                <div style="margin-bottom: 10px;">
                    <label>源URL:</label>
                    <input type="url" id="source-url" style="width: 100%; padding: 8px; margin-top: 5px;">
                </div>
                <div style="margin-bottom: 10px;">
                    <label>优先级:</label>
                    <select id="priority" style="width: 100%; padding: 8px; margin-top: 5px;">
                        <option value="normal">普通</option>
                        <option value="high">高</option>
                        <option value="urgent">紧急</option>
                        <option value="low">低</option>
                    </select>
                </div>
                <button type="submit" class="btn">创建任务</button>
            </form>
        </div>
    </div>
    
    <script>
        // 更新系统状态
        function updateStatus() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('status').textContent = data.status;
                    document.getElementById('status').className = 'metric-value ' + (data.status === 'running' ? 'status-running' : 'status-stopped');
                    document.getElementById('mode').textContent = data.mode;
                    document.getElementById('max-concurrent').textContent = data.config.max_concurrent_videos;
                    
                    // 更新资源使用情况
                    const resources = data.resources;
                    updateProgress('cpu', resources.cpu_percent);
                    updateProgress('memory', resources.memory_percent);
                    updateProgress('gpu', resources.gpu_percent);
                    
                    // 更新队列状态
                    document.getElementById('download-queue').textContent = data.queues.download;
                    document.getElementById('process-queue').textContent = data.queues.process;
                    document.getElementById('upload-queue').textContent = data.queues.upload;
                })
                .catch(error => console.error('Error:', error));
        }
        
        // 更新任务信息
        function updateTasks() {
            fetch('/api/tasks')
                .then(response => response.json())
                .then(data => {
                    // 更新统计
                    document.getElementById('total-tasks').textContent = data.stats.total_tasks;
                    document.getElementById('completed-tasks').textContent = data.stats.completed_tasks;
                    document.getElementById('failed-tasks').textContent = data.stats.failed_tasks;
                    document.getElementById('active-tasks').textContent = data.stats.active_tasks;
                    
                    // 更新活跃任务列表
                    const tasksList = document.getElementById('active-tasks-list');
                    if (data.active_tasks.length === 0) {
                        tasksList.innerHTML = '<p>暂无活跃任务</p>';
                    } else {
                        tasksList.innerHTML = data.active_tasks.map(task => `
                            <div class="task-item">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <div>
                                        <strong>${task.task_id.substring(0, 8)}...</strong>
                                        <span class="task-status status-${task.status}">${task.status}</span>
                                    </div>
                                    <div>
                                        <small>${new Date(task.created_at).toLocaleString()}</small>
                                    </div>
                                </div>
                                ${task.source_url ? `<div><small>URL: ${task.source_url}</small></div>` : ''}
                                ${task.error_message ? `<div style="color: red;"><small>错误: ${task.error_message}</small></div>` : ''}
                            </div>
                        `).join('');
                    }
                })
                .catch(error => console.error('Error:', error));
        }
        
        // 更新进度条
        function updateProgress(type, value) {
            const progressBar = document.getElementById(type + '-progress');
            const valueSpan = document.getElementById(type + '-value');
            
            progressBar.style.width = value + '%';
            valueSpan.textContent = value.toFixed(1) + '%';
            
            // 根据使用率设置颜色
            if (value > 90) {
                progressBar.style.background = '#e74c3c';
            } else if (value > 70) {
                progressBar.style.background = '#f39c12';
            } else {
                progressBar.style.background = '#27ae60';
            }
        }
        
        // 创建任务
        document.getElementById('create-task-form').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const sourceUrl = document.getElementById('source-url').value;
            const priority = document.getElementById('priority').value;
            
            if (!sourceUrl) {
                alert('请输入源URL');
                return;
            }
            
            fetch('/api/tasks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    source_url: sourceUrl,
                    priority: priority
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert('创建任务失败: ' + data.error);
                } else {
                    alert('任务创建成功: ' + data.task_id);
                    document.getElementById('source-url').value = '';
                    updateTasks();
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('创建任务失败');
            });
        });
        
        // 定期更新
        updateStatus();
        updateTasks();
        setInterval(updateStatus, 5000);
        setInterval(updateTasks, 10000);
    </script>
</body>
</html>
        '''
    
    def start(self):
        """启动Web服务器"""
        if self.running:
            return
        
        self.running = True
        self.server_thread = threading.Thread(
            target=self._run_server,
            daemon=True
        )
        self.server_thread.start()
        self.logger.info(f"Web服务器已启动: http://{self.config.web_host}:{self.config.web_port}")
    
    def stop(self):
        """停止Web服务器"""
        self.running = False
        self.logger.info("Web服务器已停止")
    
    def _run_server(self):
        """运行服务器"""
        try:
            self.app.run(
                host=self.config.web_host,
                port=self.config.web_port,
                debug=self.config.web_debug,
                use_reloader=False,
                threaded=True
            )
        except Exception as e:
            self.logger.error(f"Web服务器运行错误: {e}")
            self.running = False

    def _parse_task_type(self, value: Any) -> TaskType:
        if isinstance(value, TaskType):
            return value
        if isinstance(value, str):
            try:
                return TaskType(value.lower())
            except ValueError:
                try:
                    return TaskType[value.upper()]
                except KeyError:
                    return TaskType.VIDEO
        return TaskType.VIDEO
