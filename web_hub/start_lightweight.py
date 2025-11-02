#!/usr/bin/env python3
"""
轻量级视频处理系统启动脚本
"""

import os
import sys
import time
import argparse

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_system(test_mode=False, role="worker"):
    """测试系统组件"""
    print("🔍 测试系统组件...")

    try:
        # 🔧 关键修复：在配置加载前设置环境变量
        is_monitor = (role == "monitor")
        # 工作节点也需要FORUM_ENABLED=true来支持封面标题和热词功能
        os.environ['FORUM_ENABLED'] = 'true'  # 监控节点和工作节点都需要论坛功能
        os.environ['FORUM_PARSING_ENABLED'] = 'true'  # 工作节点需要解析论坛URL

        # 测试配置
        from lightweight.config import get_config_manager
        config_manager = get_config_manager()
        config = config_manager.get_config()

        # 测试阶段只设置测试模式，集群角色配置在启动时统一设置
        if test_mode:
            config.forum_test_mode = test_mode

        if is_monitor:
            mode_name = "🧪 测试模式" if test_mode else "🎯 集群监控节点"
            print(f"✅ 配置系统正常 - 运行模式: {config.mode}")
            print(f"✅ 集群角色: {mode_name}")
            print(f"✅ 监控频率: {config.forum_check_interval}秒")
        else:
            print(f"✅ 配置系统正常 - 运行模式: {config.mode}")
            print(f"✅ 集群角色: 🔗 集群工作节点")
            print(f"✅ 处理能力: 完整视频处理流程")

        # 测试队列管理器
        from lightweight.queue_manager import QueueManager
        queue_manager = QueueManager(config)
        print("✅ 队列管理器正常")

        # 测试资源监控
        from lightweight.resource_monitor import LightweightResourceMonitor
        resource_monitor = LightweightResourceMonitor(config)
        print("✅ 资源监控器正常")

        # 测试日志系统
        from lightweight.logger import init_logger, get_logger
        logger_manager = init_logger(config)
        logger = get_logger("TestLogger")
        # 日志系统初始化完成

        # 测试任务处理器
        from lightweight.task_processor import TaskProcessor
        task_processor = TaskProcessor(config, queue_manager, resource_monitor)
        # 任务处理器初始化完成

        # 测试Web服务器
        from lightweight.web_server import WebServer
        web_server = WebServer(config, queue_manager, resource_monitor, task_processor)
        # Web服务器初始化完成

        return True

    except Exception as e:
        print(f"❌ 系统测试失败: {e}")
        return False

def start_system(test_mode=False, test_once=False, role="worker", port=8005):
    """启动集群系统"""
    if test_once:
        mode_name = "🧪 测试模式（单次运行）"
    elif test_mode:
        mode_name = "🧪 测试模式（持续运行）"
    elif role == "monitor":
        mode_name = "🎯 集群监控节点"
    else:
        mode_name = "🔗 集群工作节点"
    print(f"🚀 启动集群视频处理系统 - {mode_name}...")

    try:
        from main_lightweight import LightweightVideoProcessor

        # 重新定义 is_monitor 变量
        is_monitor = (role == "monitor")
        if is_monitor:
            print(f"🎯 监控节点：启用论坛监控，端口: {port}")
        else:
            print(f"🔗 工作节点：启用论坛解析，等待任务分配，端口: {port}")

        # 创建处理器
        processor = LightweightVideoProcessor()

        # 设置集群角色
        processor.config.forum_test_mode = test_mode
        processor.config.forum_test_once = test_once
        processor.config.forum_enabled = is_monitor  # 只有监控节点启用论坛监控
        processor.config.forum_parsing_enabled = True  # 监控节点和工作节点都需要论坛解析功能
        processor.config.web_port = port

        print(f"📋 系统配置:")
        print(f"   - 运行模式: {processor.config.mode}")
        if is_monitor:
            print(f"   - 集群角色: 🎯 监控节点")
            print(f"   - 论坛监控: ✅ 启用")
        else:
            print(f"   - 集群角色: 🔗 工作节点")
            print(f"   - 论坛集成: ✅ 自动启用（处理任务）")
        print(f"   - 监控频率: {processor.config.forum_check_interval}秒")
        print(f"   - 最大并发: {processor.config.max_concurrent_videos}")
        print(f"   - Redis主机: {processor.config.redis_host}:{processor.config.redis_port}")
        print(f"   - Web端口: {processor.config.web_port}")
        print(f"   - 日志级别: {processor.config.log_level}")

        # 始终添加任务接收API
        add_cluster_api(processor)

        # 启动处理器
        processor.start()

        print("✅ 系统启动成功！")

        if processor.web_server:
            print(f"🌐 Web监控界面: http://{processor.config.web_host}:{processor.config.web_port}")

        print(f"🔗 任务接收端点: http://localhost:{port}/api/worker/receive-task")

        print("\n📝 使用说明:")
        if is_monitor:
            print("   - 监控节点：自动监控论坛，发现新帖后分发给工作节点")
        else:
            print("   - 工作节点：等待接收URL，执行完整处理流程")
            print("   - 接收到URL后完整处理")
        print("   - 访问Web界面查看系统状态")
        print("   - 在Web界面中创建视频处理任务")
        print("   - 按 Ctrl+C 停止系统")
        
        # 保持运行
        try:
            print("\n⏳ 系统运行中，按 Ctrl+C 停止...")
            while processor.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 接收到停止信号...")
        
        # 关闭系统
        processor.shutdown()
        print("✅ 系统已安全关闭")
        
        return True
        
    except Exception as e:
        print(f"❌ 系统启动失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def add_cluster_api(processor):
    """为工作节点添加任务接收API"""
    from flask import request, jsonify

    @processor.web_server.app.route('/api/worker/receive-task', methods=['POST'])
    def receive_task():
        """接收任务 - 接收论坛URL并完整处理"""
        print("🚨 DEBUG: 进入 receive_task API 函数")
        print(f"🚨 DEBUG: 请求方法: {request.method}")
        print(f"🚨 DEBUG: 请求路径: {request.path}")

        try:
            task_data = request.get_json()
            print(f"🚨 DEBUG: 接收到的原始数据: {task_data}")

            if not task_data:
                print("🚨 DEBUG: 任务数据为空")
                return jsonify({"error": "缺少任务数据"}), 400

            print(f"🔍 集群工作节点接收到任务: {task_data}")

            # 🎯 只提取URL
            url = task_data.get('url') or task_data.get('source_url') or task_data.get('post_url')
            print(f"🚨 DEBUG: 提取的URL: {url}")

            if not url:
                print("❌ 缺少论坛URL")
                return jsonify({"error": "缺少论坛URL"}), 400

            print(f"🎯 集群工作节点：接收到论坛URL: {url}")

            # 检查是否是论坛URL
            if not ('aicut.cn' in url or 'forum' in url.lower() or 'thread-' in url):
                print("❌ 只支持论坛URL")
                return jsonify({"error": "只支持论坛URL"}), 400

            # 🎯 工作节点：先获取论坛信息，再添加到下载队列
            print(f"🚀 集群工作节点：获取论坛信息并添加到下载队列")

            # 从URL提取post_id
            import re
            post_id_match = re.search(r'thread-(\d+)-', url)
            post_id = post_id_match.group(1) if post_id_match else f"url_{hash(url) % 10000}"
            print(f"🚨 DEBUG: 提取的post_id: {post_id}")

            # 🎯 关键修复：直接使用集群监控系统发送的metadata信息
            received_metadata = task_data.get('metadata', {})
            print(f"🔍 [DEBUG] 接收到的metadata: {received_metadata}")

            # 提取封面标题信息
            cover_title_up = received_metadata.get('cover_title_up', '')
            cover_title_middle = received_metadata.get('cover_title_middle', '')
            cover_title_down = received_metadata.get('cover_title_down', '')
            forum_post_data = received_metadata.get('forum_post_data', {})

            print(f"🔍 [DEBUG] 提取的封面标题信息:")
            print(f"   - cover_title_up: '{cover_title_up}'")
            print(f"   - cover_title_middle: '{cover_title_middle}'")
            print(f"   - cover_title_down: '{cover_title_down}'")
            print(f"   - forum_post_data: {forum_post_data}")

            # 创建任务元数据 - 直接使用集群监控系统发送的信息
            task_metadata = {
                'source': 'forum',
                'post_id': post_id,
                'post_url': url,
                'title': received_metadata.get('title', f"论坛帖子_{post_id}"),
                'is_cluster_task': True,
                'is_forum_task': True,
                # 🎯 关键修复：直接使用接收到的封面标题信息
                'cover_title_up': cover_title_up,
                'cover_title_middle': cover_title_middle,
                'cover_title_down': cover_title_down,
                'original_filename': received_metadata.get('original_filename', ''),
                'cover_info_raw': received_metadata.get('cover_info_raw', ''),
                'forum_source': received_metadata.get('forum_source', 'aicut_forum'),
                'forum_post_data': forum_post_data
            }

            print(f"🔍 [DEBUG] 创建的task_metadata封面标题:")
            print(f"   - cover_title_up: '{task_metadata['cover_title_up']}'")
            print(f"   - cover_title_middle: '{task_metadata['cover_title_middle']}'")
            print(f"   - cover_title_down: '{task_metadata['cover_title_down']}'")
            print(f"   - forum_post_data: {task_metadata['forum_post_data']}")

            # 创建任务数据
            task_data_for_queue = {
                'task_id': f"forum_{post_id}",
                'source_url': url,
                'post_id': post_id,
                'title': task_metadata['title'],
                'type': 'forum_url',
                'metadata': task_metadata
            }
            print(f"🚨 DEBUG: 创建的队列任务数据: {task_data_for_queue}")

            # 创建任务
            print(f"🚨 DEBUG: 准备创建任务...")
            from lightweight.queue_manager import TaskPriority
            task_id = processor.queue_manager.create_task(
                source_url=url,
                priority=TaskPriority.NORMAL,
                metadata=task_metadata
            )
            print(f"🚨 DEBUG: 创建任务结果: {task_id}")

            if not task_id:
                print("❌ 创建任务失败")
                return jsonify({"error": "创建任务失败"}), 500

            print("🚨 DEBUG: 准备返回成功响应")
            return jsonify({
                "status": "success",
                "post_id": post_id,
                "message": "论坛URL已添加到处理队列"
            }), 200

        except Exception as e:
            print(f"❌ 集群任务处理失败: {e}")
            print(f"🚨 DEBUG: 异常类型: {type(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": f"处理失败: {str(e)}"}), 500

    @processor.web_server.app.route('/api/worker/status', methods=['GET'])
    def worker_status():
        """获取工作节点状态"""
        try:
            queue_status = processor.queue_manager.get_status()
            queue_sizes = processor.queue_manager.get_queue_sizes()

            # 计算总队列大小
            total_queue_size = sum(queue_sizes.values())

            # 判断是否忙碌（有任务在处理或队列中有任务）
            is_busy = total_queue_size > 0 or queue_status.get('processing', 0) > 0

            # 返回监控系统期望的格式
            return jsonify({
                "status": "online",
                "is_busy": is_busy,
                "total_queue_size": total_queue_size,
                "queue_sizes": queue_sizes,
                "queues": queue_status,
                "timestamp": time.time()
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    print("✅ 集群API端点已添加到Web服务器")

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="并行流水线视频处理系统")
    parser.add_argument("--test", action="store_true", help="启动测试模式（重启后处理所有帖子）")
    parser.add_argument("--test-once", action="store_true", help="测试模式单次运行（处理一轮后停止）")
    # 集群角色：monitor=监控节点，worker=工作节点（默认）
    parser.add_argument("--role", type=str, choices=['monitor', 'worker'], default='worker',
                       help="集群角色：monitor=监控节点（监控论坛），worker=工作节点（处理视频，默认）")
    parser.add_argument("--port", type=int, default=8005, help="Web服务器端口")
    parser.add_argument("--log-mode", choices=['development', 'production', 'silent'],
                       default='development', help="日志模式")
    parser.add_argument("--quiet", action="store_true", help="静默模式（最小日志输出）")
    parser.add_argument("--verbose", action="store_true", help="详细模式（最大日志输出）")
    args = parser.parse_args()

    # 确定集群角色
    test_mode = args.test or args.test_once
    test_once = args.test_once
    role = args.role  # monitor=监控节点，worker=工作节点
    port = args.port

    if test_once:
        mode_name = "🧪 测试模式（单次运行）"
    elif test_mode:
        mode_name = "🧪 测试模式（持续运行）"
    elif role == "monitor":
        mode_name = "🎯 集群监控节点"
    else:
        mode_name = "🔗 集群工作节点"

    # 设置日志模式
    if args.quiet:
        log_mode = 'silent'
    elif args.verbose:
        log_mode = 'development'
    else:
        log_mode = args.log_mode

    # 生产模式下默认使用生产日志模式
    if not test_mode and log_mode == 'development':
        log_mode = 'production'

    # 设置环境变量 - 命令行参数优先级最高
    os.environ['LOG_MODE'] = log_mode

    # 🔥 关键修复：命令行参数覆盖环境变量中的论坛模式设置
    if test_mode:
        os.environ['FORUM_TEST_MODE'] = 'true'
        print(f"🔧 命令行覆盖: FORUM_TEST_MODE = true")

    if test_once:
        os.environ['FORUM_TEST_ONCE'] = 'true'
        print(f"🔧 命令行覆盖: FORUM_TEST_ONCE = true")

    # 🔧 源头修复：确保生产模式有正确的默认值
    if not test_mode and not test_once:
        # 生产模式：确保环境变量有明确的值
        if 'FORUM_TEST_MODE' not in os.environ:
            os.environ['FORUM_TEST_MODE'] = 'false'
        if 'FORUM_TEST_ONCE' not in os.environ:
            os.environ['FORUM_TEST_ONCE'] = 'false'
        print(f"🚀 生产模式：使用默认论坛设置")

    print(f"🔍 最终论坛模式设置:")
    print(f"   - FORUM_TEST_MODE: {os.environ.get('FORUM_TEST_MODE', 'false')}")
    print(f"   - FORUM_TEST_ONCE: {os.environ.get('FORUM_TEST_ONCE', 'false')}")

    print(f"🔧 集群角色: {role} ({'🎯 监控节点' if role == 'monitor' else '🔗 工作节点'})")

    print("=" * 60)
    print("🎬 并行流水线视频处理系统")
    print("=" * 60)
    print(f"📋 启动模式: {mode_name}")
    print(f"📊 日志模式: {log_mode}")

    # 初始化日志性能优化
    try:
        from lightweight.log_performance_config import setup_performance_logging
        log_config = setup_performance_logging()

        if log_mode == 'production':
            print("🚀 生产模式日志优化:")
            print("   - 控制台输出: 最小化")
            print("   - 文件日志: 优化写入")
            print("   - 性能影响: 最小")
        elif log_mode == 'silent':
            print("🤫 静默模式: 仅记录关键错误")
        else:
            print("🔧 开发模式: 详细日志输出")

    except Exception as e:
        print(f"⚠️ 日志优化初始化失败: {e}")
        print("📝 使用默认日志配置")

    if test_once:
        print("🧪 测试模式（单次运行）特点:")
        print("   - 处理所有帖子一轮后自动停止")
        print("   - 不保存已处理记录到文件")
        print("   - 适合快速功能验证")
    elif test_mode:
        print("🧪 测试模式（持续运行）特点:")
        print("   - 重启后处理所有帖子（包括已处理过的）")
        print("   - 不保存已处理记录到文件")
        print("   - 适合开发调试和功能测试")
    else:
        print("🚀 生产模式特点:")
        print("   - 重启后只处理新发布的帖子")
        print("   - 持久化保存已处理记录")
        print("   - 每处理完一个帖子立即保存")
        print("   - 适合正式运营环境")

    print(f"⚡ 监控频率: 每10秒检查一次论坛")
    print()

    # 测试系统
    if not test_system(test_mode, role):
        print("❌ 系统测试失败，请检查配置")
        return False

    print("\n" + "=" * 60)

    # 启动系统
    return start_system(test_mode, test_once, role, port)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
