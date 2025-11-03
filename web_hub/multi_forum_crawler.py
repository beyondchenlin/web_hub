#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多论坛爬虫管理器
支持同时监控多个论坛网站

功能：
1. 从环境变量读取多个论坛配置
2. 并行监控多个论坛
3. 统一的任务提交接口
4. 配置验证和状态监控

使用方法：
from multi_forum_crawler import MultiForumCrawler
crawler = MultiForumCrawler()
crawler.start_monitoring()
"""

import os
import time
import threading
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from forum_config_manager import ForumConfigManager, ForumConfig
from aicut_forum_crawler import AicutForumCrawler

class MultiForumCrawler:
    """多论坛爬虫管理器"""
    
    def __init__(self, config_file: str = ".env"):
        self.config_manager = ForumConfigManager(config_file)
        # 从配置文件加载所有论坛
        self.config_manager.load_all_forums_from_settings()
        self.crawlers: Dict[str, AicutForumCrawler] = {}
        self.running = False
        self.threads: Dict[str, threading.Thread] = {}
        self.stop_event = threading.Event()

        # 初始化爬虫实例
        self._initialize_crawlers()
    
    def _initialize_crawlers(self):
        """初始化所有论坛爬虫"""
        forum_configs = self.config_manager.get_enabled_forum_configs()
        
        if not forum_configs:
            print("⚠️ 没有找到启用的论坛配置")
            return
        
        print(f"🚀 初始化 {len(forum_configs)} 个论坛爬虫...")
        
        for name, config in forum_configs.items():
            try:
                crawler = AicutForumCrawler(
                    username=config.username,
                    password=config.password,
                    test_mode=config.test_mode,
                    test_once=config.test_once,
                    base_url=config.base_url,
                    forum_url=config.target_url
                )
                
                # 尝试登录
                if crawler.login():
                    self.crawlers[name] = crawler
                    print(f"✅ 论坛 {config.name} 初始化成功")
                else:
                    print(f"❌ 论坛 {config.name} 登录失败")
                    
            except Exception as e:
                print(f"❌ 论坛 {config.name} 初始化失败: {e}")
    
    def start_monitoring(self):
        """开始监控所有论坛"""
        if not self.crawlers:
            print("❌ 没有可用的论坛爬虫")
            return False
        
        print(f"🔍 开始监控 {len(self.crawlers)} 个论坛...")
        self.running = True
        self.stop_event.clear()
        
        # 为每个论坛创建监控线程
        for name, crawler in self.crawlers.items():
            config = self.config_manager.get_forum_config(name)
            thread = threading.Thread(
                target=self._monitor_forum,
                args=(name, crawler, config),
                daemon=True
            )
            thread.start()
            self.threads[name] = thread
            print(f"🎯 论坛 {config.name} 监控线程已启动")
        
        return True
    
    def _monitor_forum(self, name: str, crawler: AicutForumCrawler, config: ForumConfig):
        """监控单个论坛"""
        print(f"📡 开始监控论坛: {config.name}")
        
        while self.running and not self.stop_event.is_set():
            try:
                # 获取论坛帖子
                threads = crawler.get_forum_threads()
                
                if threads:
                    print(f"📋 论坛 {config.name} 发现 {len(threads)} 个帖子")
                    
                    # 处理每个帖子
                    for thread_info in threads:
                        if self.stop_event.is_set():
                            break
                        
                        # 检查是否已处理
                        thread_id = thread_info['thread_id']
                        if thread_id in crawler.processed_threads:
                            continue
                        
                        # 获取帖子详细内容
                        content_info = crawler.get_thread_content(thread_info['thread_url'])
                        
                        # 检查是否有视频内容
                        if content_info.get('has_video', False):
                            # 提交处理任务
                            self._submit_processing_task(name, thread_info, content_info)
                        
                        # 标记为已处理
                        crawler.mark_post_processed(thread_id)
                
                # 如果是单次运行模式，退出循环
                if config.test_once:
                    print(f"🧪 论坛 {config.name} 单次运行完成")
                    break
                
                # 等待下次检查
                if not self.stop_event.wait(config.check_interval):
                    continue
                else:
                    break
                    
            except Exception as e:
                print(f"❌ 监控论坛 {config.name} 时出错: {e}")
                # 出错时等待一段时间再重试
                if not self.stop_event.wait(60):
                    continue
                else:
                    break
        
        print(f"🛑 论坛 {config.name} 监控已停止")
    
    def _submit_processing_task(self, forum_name: str, thread_info: Dict[str, Any], content_info: Dict[str, Any]):
        """提交视频处理任务"""
        try:
            # 导入任务提交模块
            from lightweight.queue_manager import QueueManager
            
            # 创建任务数据
            task_data = {
                'forum_name': forum_name,
                'thread_id': thread_info['thread_id'],
                'title': thread_info['title'],
                'author': thread_info['author'],
                'thread_url': thread_info['thread_url'],
                'video_urls': content_info['video_urls'],
                'original_filenames': content_info.get('original_filenames', []),
                'audio_urls': content_info.get('audio_urls', []),
                'content': content_info['content'],
                'cover_info': content_info.get('cover_info', {}),
                'forum_id': thread_info.get('forum_id', 1),
                'forum_name_display': thread_info.get('forum_name', '未知板块')
            }
            
            # 提交到队列
            queue_manager = QueueManager()
            task_id = queue_manager.submit_task(task_data)
            
            print(f"✅ 已提交处理任务: {thread_info['title']} (任务ID: {task_id})")
            
        except Exception as e:
            print(f"❌ 提交处理任务失败: {e}")
    
    def stop_monitoring(self):
        """停止监控所有论坛"""
        print("🛑 停止论坛监控...")
        self.running = False
        self.stop_event.set()
        
        # 等待所有线程结束
        for name, thread in self.threads.items():
            if thread.is_alive():
                print(f"⏳ 等待论坛 {name} 监控线程结束...")
                thread.join(timeout=10)
        
        self.threads.clear()
        print("✅ 所有论坛监控已停止")
    
    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        status = {
            'running': self.running,
            'total_forums': len(self.crawlers),
            'active_threads': len([t for t in self.threads.values() if t.is_alive()]),
            'forums': {}
        }
        
        for name, crawler in self.crawlers.items():
            config = self.config_manager.get_forum_config(name)
            thread = self.threads.get(name)
            
            status['forums'][name] = {
                'name': config.name if config else name,
                'base_url': config.base_url if config else 'Unknown',
                'enabled': config.enabled if config else False,
                'thread_alive': thread.is_alive() if thread else False,
                'processed_posts': len(crawler.processed_threads),
                'test_mode': config.test_mode if config else False
            }
        
        return status
    
    def print_status(self):
        """打印监控状态"""
        status = self.get_status()
        
        print("\n📊 多论坛监控状态")
        print("=" * 50)
        print(f"运行状态: {'🟢 运行中' if status['running'] else '🔴 已停止'}")
        print(f"论坛总数: {status['total_forums']}")
        print(f"活跃线程: {status['active_threads']}")
        print()
        
        for name, forum_status in status['forums'].items():
            thread_status = "🟢 活跃" if forum_status['thread_alive'] else "🔴 停止"
            mode = "🧪 测试" if forum_status['test_mode'] else "🚀 生产"
            
            print(f"📍 {forum_status['name']} ({name})")
            print(f"   状态: {thread_status}")
            print(f"   模式: {mode}")
            print(f"   网站: {forum_status['base_url']}")
            print(f"   已处理: {forum_status['processed_posts']} 个帖子")
            print()


def main():
    """主函数 - 用于测试和独立运行"""
    import argparse
    import signal
    
    parser = argparse.ArgumentParser(description="多论坛爬虫管理器")
    parser.add_argument("--config", default=".env", help="配置文件路径")
    parser.add_argument("--status", action="store_true", help="显示状态信息")
    parser.add_argument("--test-once", action="store_true", help="测试模式（单次运行）")
    
    args = parser.parse_args()
    
    # 创建爬虫管理器
    crawler_manager = MultiForumCrawler(args.config)
    
    if args.status:
        crawler_manager.print_status()
        return
    
    # 设置信号处理
    def signal_handler(signum, frame):
        print("\n🛑 收到停止信号，正在关闭...")
        crawler_manager.stop_monitoring()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 验证配置
    is_valid, errors = crawler_manager.config_manager.validate_configs()
    if not is_valid:
        print("❌ 配置验证失败:")
        for error in errors:
            print(f"   - {error}")
        return
    
    # 显示配置摘要
    crawler_manager.config_manager.print_config_summary()
    
    # 开始监控
    if crawler_manager.start_monitoring():
        print("\n🎯 多论坛监控已启动")
        print("按 Ctrl+C 停止监控")
        
        try:
            # 主循环 - 定期显示状态
            while crawler_manager.running:
                time.sleep(60)  # 每分钟显示一次状态
                if not args.test_once:
                    crawler_manager.print_status()
        except KeyboardInterrupt:
            pass
        finally:
            crawler_manager.stop_monitoring()
    else:
        print("❌ 启动多论坛监控失败")


if __name__ == "__main__":
    main()
