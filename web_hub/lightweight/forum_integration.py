#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
轻量级视频处理系统 - 论坛集成模块

主要功能：
- 集成论坛爬虫监控新帖
- 自动创建下载任务
- 处理完成后自动回复论坛
"""

import os
import sys
import time
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .queue_manager import QueueManager, TaskPriority
from .logger import get_logger

# 导入数据管理器和论坛爬虫
try:
    from forum_data_manager import get_data_manager, ForumPost
    DATA_MANAGER_AVAILABLE = True
except ImportError:
    DATA_MANAGER_AVAILABLE = False
    print("⚠️ 数据管理器不可用")

try:
    from aicut_forum_crawler import AicutForumCrawler
    from aicut_lrtcai_config import create_aicut_config
    FORUM_CRAWLER_AVAILABLE = True
except ImportError:
    FORUM_CRAWLER_AVAILABLE = False
    print("⚠️ 论坛爬虫不可用")


class ForumIntegration:
    """论坛集成管理器"""

    def __init__(self, queue_manager: QueueManager, config):
        self.queue_manager = queue_manager
        self.config = config
        self.logger = get_logger("ForumIntegration")

        # 论坛监控状态
        self.running = False
        self.monitor_thread = None

        # 论坛配置
        self.forum_enabled = getattr(config, 'forum_enabled', True)
        self.check_interval = getattr(config, 'forum_check_interval', 180)  # 3分钟

        # 初始化数据管理器
        self.data_manager = None
        if DATA_MANAGER_AVAILABLE:
            try:
                self.data_manager = get_data_manager()
                self.logger.info("数据管理器初始化成功")
            except Exception as e:
                self.logger.error(f"数据管理器初始化失败: {e}")

        # 初始化论坛爬虫 - 支持集群工作节点模式
        self.forum_crawler = None
        forum_parsing_enabled = getattr(config, 'forum_parsing_enabled', False)
        if FORUM_CRAWLER_AVAILABLE and (self.forum_enabled or forum_parsing_enabled):
            try:
                # 从环境变量获取论坛账号信息 - 支持多种环境变量名
                username = (os.getenv('FORUM_USERNAME') or
                           os.getenv('AICUT_ADMIN_USERNAME') or
                           'AI剪辑助手')
                password = (os.getenv('FORUM_PASSWORD') or
                           os.getenv('AICUT_ADMIN_PASSWORD') or
                           '594188@lrtcai')

                print(f"🔐 论坛登录信息: 用户名={username}, 密码={'*' * len(password) if password else '未设置'}")

                # 获取测试模式配置
                test_mode = getattr(config, 'forum_test_mode', True)
                test_once = getattr(config, 'forum_test_once', False)

                print(f"🔍 [DEBUG] 论坛模式配置: test_mode={test_mode}, test_once={test_once}")
                print(f"🔍 [DEBUG] 环境变量FORUM_TEST_MODE: {os.getenv('FORUM_TEST_MODE', '未设置')}")

                # 获取论坛URL配置
                base_url = os.getenv('FORUM_BASE_URL', 'https://aicut.lrtcai.com')
                forum_url = os.getenv('FORUM_TARGET_URL', 'https://aicut.lrtcai.com/forum-2-1.html')

                print(f"🌐 论坛配置: 基础URL={base_url}, 目标URL={forum_url}")

                self.forum_crawler = AicutForumCrawler(username, password, test_mode, test_once, base_url, forum_url)

                # 立即登录并验证
                if self.forum_crawler:
                    print(f"🔍 尝试登录论坛...")
                    login_success = self.forum_crawler.login()
                    if login_success:
                        print(f"✅ 论坛登录成功: {username}")
                        self.logger.info(f"论坛爬虫初始化成功 - 模式: {'测试' if test_mode else '生产'} - 登录成功: {username}")

                        # 测试获取帖子列表
                        print(f"🧪 测试获取帖子列表...")
                        test_threads = self.forum_crawler.get_forum_threads()
                        print(f"📊 测试结果: 发现 {len(test_threads)} 个帖子")

                    else:
                        print(f"❌ 论坛登录失败: {username}")
                        self.logger.error(f"论坛爬虫初始化成功但登录失败: {username}")
                else:
                    self.logger.info(f"论坛爬虫初始化成功 - 模式: {'测试' if test_mode else '生产'}")
            except Exception as e:
                print(f"❌ 论坛爬虫初始化异常: {e}")
                self.logger.error(f"论坛爬虫初始化失败: {e}")
                import traceback
                traceback.print_exc()
        elif not self.forum_enabled and not forum_parsing_enabled:
            print("🖥️ 论坛功能已禁用，跳过论坛爬虫初始化")
            self.logger.info("论坛功能已禁用，跳过论坛爬虫初始化")
        elif forum_parsing_enabled:
            print("🖥️ 集群工作节点模式：论坛爬虫已初始化，仅用于解析任务")
            self.logger.info("集群工作节点模式：论坛爬虫已初始化，仅用于解析任务")

        # 已处理的帖子记录（从数据库加载）
        self.processed_posts = set()
        # 检查是否为测试模式
        self.test_mode = getattr(config, 'forum_test_mode', False)  # 默认为生产模式
        self.test_once = getattr(config, 'forum_test_once', False)  # 单次运行模式
        if not self.test_mode:
            # 只在生产模式下加载已处理的帖子记录
            self._load_processed_posts()
            print("🚀 生产模式：已加载历史处理记录")
        elif self.test_once:
            print("🧪 测试模式（单次运行）：不加载历史处理记录")
        else:
            print("🧪 测试模式（持续运行）：不加载历史处理记录")

        self.logger.info("论坛集成模块初始化完成")

    def _load_processed_posts(self):
        """从数据库加载已处理的帖子ID"""
        if not self.data_manager:
            return

        try:
            # 获取所有已处理的帖子
            processed_posts = self.data_manager.get_posts_by_status("completed", limit=1000)
            for post in processed_posts:
                self.processed_posts.add(post.post_id)

            # 也加载正在处理的帖子
            processing_posts = self.data_manager.get_posts_by_status("processing", limit=100)
            for post in processing_posts:
                self.processed_posts.add(post.post_id)

            self.logger.info(f"加载了 {len(self.processed_posts)} 个已处理帖子记录")
        except Exception as e:
            self.logger.error(f"加载已处理帖子记录失败: {e}")

    def start(self):
        """启动论坛监控"""
        if not self.forum_enabled:
            self.logger.info("论坛监控已禁用")
            return
        
        if self.running:
            self.logger.warning("论坛监控已在运行")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_forum, daemon=True)
        self.monitor_thread.start()
        
        print("🔍 论坛监控已启动")
        self.logger.info("论坛监控已启动")
    
    def stop(self):
        """停止论坛监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        print("🛑 论坛监控已停止")
        self.logger.info("论坛监控已停止")
    
    def _monitor_forum(self):
        """论坛监控主循环"""
        self.logger.info("开始论坛监控循环")

        if self.test_once:
            # 单次运行模式：只检查一次后停止
            try:
                print("🧪 测试模式（单次运行）：开始检查论坛...")
                self._check_new_posts()
                print("🧪 测试模式（单次运行）：检查完成，系统将停止")
                self.running = False
                return
            except Exception as e:
                self.logger.error(f"单次运行模式检查失败: {e}")
                self.running = False
                return

        # 持续运行模式
        while self.running:
            try:
                # 检查论坛新帖
                self._check_new_posts()

                # 等待下次检查
                for _ in range(self.check_interval):
                    if not self.running:
                        break
                    time.sleep(1)

            except Exception as e:
                self.logger.error(f"论坛监控异常: {e}")
                time.sleep(30)  # 出错后等待30秒
    
    def _check_new_posts(self):
        """检查论坛新帖"""
        try:
            print("🔍 开始检查论坛新帖...")
            self.logger.info("检查论坛新帖...")

            # 检查论坛爬虫是否可用
            if not self.forum_crawler:
                print("❌ 论坛爬虫未初始化")
                self.logger.error("论坛爬虫未初始化")
                return

            # 这里集成论坛爬虫逻辑
            print("📋 调用论坛爬虫获取新帖...")
            new_posts = self._get_new_posts_from_forum()
            print(f"📊 论坛爬虫返回 {len(new_posts)} 个帖子")

            if not new_posts:
                print("ℹ️ 未发现新帖子")
                self.logger.info("未发现新帖子")
                return

            processed_count = 0
            for post in new_posts:
                post_id = post['post_id']

                # 检查是否已处理（测试模式和生产模式都要去重）
                if post_id not in self.processed_posts:
                    print(f"🆕 发现新帖子: {post_id} - {post.get('title', '无标题')}")
                    self._process_new_post(post)
                    self.processed_posts.add(post_id)
                    processed_count += 1

                    if self.test_mode:
                        print(f"🧪 测试模式：处理帖子 {post_id}")
                    else:
                        print(f"🚀 生产模式：处理新帖子 {post_id}")
                else:
                    if self.test_mode:
                        print(f"⏭️ 测试模式：跳过本次已处理帖子 {post_id}")
                    else:
                        print(f"⏭️ 生产模式：跳过已处理帖子 {post_id}")

            if new_posts:
                if self.test_mode:
                    print(f"🧪 测试模式：处理了 {processed_count}/{len(new_posts)} 个帖子")
                    self.logger.info(f"测试模式：处理了 {processed_count}/{len(new_posts)} 个帖子")
                    # 单次运行模式：处理完所有帖子后停止
                    if self.test_once:
                        print(f"🧪 测试模式（单次运行）：已处理 {processed_count} 个帖子，系统将停止")
                        self.running = False
                        return
                else:
                    print(f"🚀 生产模式：处理了 {processed_count} 个新帖子")
                    self.logger.info(f"生产模式：处理了 {processed_count} 个新帖子")

        except Exception as e:
            print(f"❌ 检查论坛新帖异常: {e}")
            self.logger.error(f"检查论坛新帖失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_new_posts_from_forum(self) -> List[Dict[str, Any]]:
        """从论坛获取新帖子"""
        if not self.forum_crawler:
            print("❌ 论坛爬虫未初始化")
            self.logger.warning("论坛爬虫未初始化")
            return []

        try:
            print("🕷️ 调用论坛爬虫监控新帖...")
            # 使用论坛爬虫监控新帖
            new_posts = self.forum_crawler.monitor_new_posts()
            print(f"🕷️ 论坛爬虫返回 {len(new_posts)} 个原始帖子")

            if not new_posts:
                print("ℹ️ 论坛爬虫未返回任何帖子")
                return []

            # 转换为标准格式
            formatted_posts = []
            for i, post in enumerate(new_posts):
                print(f"📝 处理第 {i+1} 个帖子: {post.get('title', '无标题')}")

                # 获取主要视频链接
                video_urls = post.get('video_urls', [])
                primary_video_url = video_urls[0] if video_urls else None

                print(f"🎬 视频链接数量: {len(video_urls)}")
                if video_urls:
                    print(f"🔗 主要视频链接: {primary_video_url}")

                # 获取原始文件名（爬虫已经提取好了）
                original_filenames = post.get('original_filenames', [])
                print(f"📁 原始文件名数量: {len(original_filenames)}")

                formatted_post = {
                    'post_id': post['thread_id'],
                    'thread_id': post['thread_id'],
                    'title': post.get('title', ''),
                    'content': post.get('content', ''),  # 🔥 关键修复：添加内容字段
                    'author_id': post.get('author', ''),  # 修复：使用author而不是author_id
                    'author_name': post.get('author', ''),  # 修复：使用author而不是author_name
                    'video_url': primary_video_url,
                    'post_url': post.get('thread_url', ''),
                    'post_time': post.get('post_time'),
                    # 🎯 使用统一的up/middle/down封面标题字段
                    'cover_title_up': post.get('cover_info', {}).get('cover_title_up', ''),
                    'cover_title_middle': post.get('cover_info', {}).get('cover_title_middle', ''),
                    'cover_title_down': post.get('cover_info', {}).get('cover_title_down', ''),
                    'video_urls': video_urls,
                    'audio_urls': post.get('audio_urls', []),
                    'original_filenames': original_filenames
                }

                # 只添加有视频链接的帖子
                if video_urls or primary_video_url:
                    formatted_posts.append(formatted_post)
                    print(f"✅ 添加帖子到处理队列: {post['thread_id']}")
                else:
                    print(f"⏭️ 跳过无视频链接的帖子: {post['thread_id']}")

            print(f"📊 最终格式化帖子数量: {len(formatted_posts)}")
            return formatted_posts

        except Exception as e:
            print(f"❌ 获取论坛新帖异常: {e}")
            self.logger.error(f"获取论坛新帖失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _process_new_post(self, post: Dict[str, Any]):
        """处理新帖子"""
        try:
            post_id = post['post_id']
            video_urls = post.get('video_urls', [])
            video_url = post.get('video_url')

            # 确保有视频链接
            if not video_urls and not video_url:
                self.logger.warning(f"帖子 {post_id} 没有视频链接")
                return

            # 使用第一个视频链接作为主要处理对象
            primary_video_url = video_url or (video_urls[0] if video_urls else None)

            self.logger.info(f"处理新帖子: {post_id}, 视频链接: {primary_video_url}")
            print(f"📝 发现新帖子: {post_id}")
            print(f"🔗 视频链接: {primary_video_url}")

            # 保存帖子到数据库
            if self.data_manager:
                forum_post = ForumPost(
                    post_id=post_id,
                    thread_id=post.get('thread_id', post_id),
                    title=post.get('title', ''),
                    content=post.get('content', ''),  # 添加内容字段
                    author_id=post.get('author_id', ''),
                    author_name=post.get('author_name', ''),
                    cover_title_up=post.get('cover_title_up', ''),
                    cover_title_middle=post.get('cover_title_middle', ''),
                    cover_title_down=post.get('cover_title_down', ''),
                    video_urls=video_urls,
                    audio_urls=post.get('audio_urls', []),
                    original_filenames=post.get('original_filenames', []),
                    media_count=len(video_urls) + len(post.get('audio_urls', [])),
                    source_url=post.get('post_url', ''),
                    post_time=post.get('post_time'),
                    processing_status='pending'
                )

                if self.data_manager.save_post(forum_post):
                    self.logger.info(f"帖子数据保存成功: {post_id}")
                else:
                    self.logger.error(f"帖子数据保存失败: {post_id}")

            # 创建下载任务
            # 获取对应的原始文件名
            original_filenames = post.get('original_filenames', [])
            original_filename = original_filenames[0] if original_filenames else None

            task_metadata = {
                'post_id': post_id,
                'author_id': post.get('author_id'),
                'title': post.get('title'),
                'post_url': post.get('post_url'),
                'source': 'forum',
                'cover_title_up': post.get('cover_title_up', ''),
                'cover_title_middle': post.get('cover_title_middle', ''),
                'cover_title_down': post.get('cover_title_down', ''),
                'original_filename': original_filename,  # 添加原始文件名
                'all_original_filenames': original_filenames  # 保存所有文件名
            }

            print(f"🔧 调用队列管理器创建任务...")
            print(f"🔗 源URL: {primary_video_url}")
            print(f"📋 元数据: {task_metadata}")

            task_id = self.queue_manager.create_task(
                source_url=primary_video_url,
                priority=TaskPriority.NORMAL,
                metadata=task_metadata
            )

            print(f"✅ 队列管理器返回任务ID: {task_id}")

            # 更新数据库中的任务ID
            if self.data_manager:
                self.data_manager.update_post_status(
                    post_id,
                    'processing',
                    task_id=task_id
                )

            print(f"✅ 已创建处理任务: {task_id}")
            self.logger.info(f"为帖子 {post_id} 创建任务: {task_id}")

        except Exception as e:
            self.logger.error(f"处理新帖子失败: {e}")
    
    def create_forum_task(self, post_id: str, video_url: str,
                         author_id: str = None, title: str = None,
                         original_filename: str = None) -> str:
        """手动创建论坛任务"""
        try:
            task_metadata = {
                'post_id': post_id,
                'author_id': author_id,
                'title': title,
                'source': 'forum_manual',
                'original_filename': original_filename
            }
            
            task_id = self.queue_manager.create_task(
                source_url=video_url,
                priority=TaskPriority.HIGH,  # 手动任务使用高优先级
                metadata=task_metadata
            )
            
            self.logger.info(f"手动创建论坛任务: {task_id} for post {post_id}")
            return task_id
            
        except Exception as e:
            self.logger.error(f"创建论坛任务失败: {e}")
            raise

    def get_new_posts(self) -> List[Dict[str, Any]]:
        """获取新帖子（供外部调用）"""
        return self._get_new_posts_from_forum()

    def process_single_forum_url(self, url: str):
        """处理单个论坛URL - 完整的单机模式流程（供集群工作节点调用）"""
        try:
            print(f"🔗 集群工作节点：按单机模式处理论坛URL: {url}")

            # 检查论坛爬虫是否可用
            if not self.forum_crawler:
                print("❌ 论坛爬虫未初始化")
                return False

            # 🎯 第1步：爬取帖子内容（与单机模式相同）
            print(f"🕷️ 爬取论坛帖子内容: {url}")
            post_content = self.forum_crawler.get_thread_content(url)

            if not post_content:
                print("❌ 爬取帖子内容失败")
                return False

            if not post_content.get('has_video'):
                print("❌ 帖子无视频内容")
                return False

            # 🎯 第2步：数据格式化（与单机模式的_get_new_posts_from_forum相同）
            print("🔧 按单机模式格式化帖子数据")

            # 从URL提取post_id
            import re
            post_id_match = re.search(r'thread-(\d+)-', url)
            if not post_id_match:
                print("❌ 无法从URL提取帖子ID")
                return False

            post_id = post_id_match.group(1)

            # 获取视频信息
            video_urls = post_content.get('video_urls', [])
            primary_video_url = video_urls[0] if video_urls else None
            original_filenames = post_content.get('original_filenames', [])

            print(f"📝 帖子ID: {post_id}")
            print(f"🎬 视频链接数量: {len(video_urls)}")
            print(f"📁 原始文件名数量: {len(original_filenames)}")
            print(f"📝 封面标题: {post_content.get('cover_info', {})}")

            # 🎯 关键：按照单机模式格式化数据结构（与_get_new_posts_from_forum中的逻辑相同）
            formatted_post = {
                'post_id': post_id,
                'thread_id': post_id,
                'title': post_content.get('title', ''),
                'content': post_content.get('content', ''),
                'author_id': post_content.get('author', ''),
                'author_name': post_content.get('author', ''),
                'video_url': primary_video_url,
                'post_url': url,
                'post_time': post_content.get('post_time'),
                # 🎯 关键：从cover_info中提取封面标题到顶层（单机模式的格式化逻辑）
                'cover_title_up': post_content.get('cover_info', {}).get('cover_title_up', ''),
                'cover_title_down': post_content.get('cover_info', {}).get('cover_title_down', ''),
                'video_urls': video_urls,
                'audio_urls': post_content.get('audio_urls', []),
                'original_filenames': original_filenames
            }

            print(f"🖼️ 格式化后封面标题上: '{formatted_post['cover_title_up']}'")
            print(f"🖼️ 格式化后封面标题下: '{formatted_post['cover_title_down']}'")

            # 🎯 第3步：处理格式化后的帖子（与单机模式相同）
            print("🔧 调用单机模式的帖子处理逻辑")
            self._process_new_post(formatted_post)

            print("✅ 集群工作节点：单机模式处理完成")
            return True

        except Exception as e:
            print(f"❌ 集群工作节点处理失败: {e}")
            self.logger.error(f"集群工作节点处理失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_post_statistics(self) -> Dict[str, Any]:
        """获取帖子统计信息"""
        if not self.data_manager:
            return {}

        return self.data_manager.get_statistics()

    def mark_post_completed(self, post_id: str, output_path: str = None) -> bool:
        """标记帖子处理完成"""
        if not self.data_manager:
            return False

        try:
            success = self.data_manager.update_post_status(
                post_id,
                'completed',
                output_path=output_path
            )

            if success:
                self.logger.info(f"帖子标记为已完成: {post_id}")
                # 触发自动回复
                self._trigger_auto_reply(post_id, output_path)

            return success
        except Exception as e:
            self.logger.error(f"标记帖子完成失败: {e}")
            return False

    def _trigger_auto_reply(self, post_id: str, output_path: str = None):
        """触发自动回复"""
        try:
            if not self.forum_crawler:
                self.logger.warning("论坛爬虫未初始化，无法自动回复")
                return

            # 获取帖子信息
            post = None
            if self.data_manager:
                post = self.data_manager.get_post(post_id)

            # 生成回复内容
            reply_content = self._generate_reply_content(post, output_path)

            # 发送回复
            success = self.forum_crawler.reply_to_thread(post_id, reply_content)

            if success and self.data_manager:
                # 更新回复状态
                self.data_manager.update_post_status(
                    post_id,
                    'completed',
                    reply_status='sent',
                    reply_content=reply_content
                )
                self.logger.info(f"自动回复发送成功: {post_id}")
            else:
                self.logger.error(f"自动回复发送失败: {post_id}")

        except Exception as e:
            self.logger.error(f"触发自动回复失败: {e}")

    def _generate_reply_content(self, post: ForumPost = None, output_path: str = None) -> str:
        """生成回复内容"""
        reply_template = """🎬 您的视频已处理完成！

📁 处理完成的文件已保存到输出目录

✨ 处理内容包括:
- 移除静音片段
- 语音识别和字幕生成
- AI智能剪辑
- 添加标题和字幕

请查看输出目录获取处理后的视频文件。

---
🤖 AI剪辑助手自动回复"""

        # 如果有封面信息，添加到回复中
        if post and (post.cover_title_up or post.cover_title_down):
            cover_info = ""
            if post.cover_title_up:
                cover_info += f"封面标题上: {post.cover_title_up}\n"
            if post.cover_title_down:
                cover_info += f"封面标题下: {post.cover_title_down}\n"

            reply_template = f"🖼️ 封面信息:\n{cover_info}\n" + reply_template

        return reply_template
    
    def get_forum_stats(self) -> Dict[str, Any]:
        """获取论坛集成统计信息"""
        return {
            'forum_enabled': self.forum_enabled,
            'monitor_running': self.running,
            'check_interval': self.check_interval,
            'processed_posts_count': len(self.processed_posts),
            'last_check': datetime.now().isoformat()
        }


class ForumReplyBot:
    """论坛回复机器人"""
    
    def __init__(self, config):
        self.config = config
        self.logger = get_logger("ForumReplyBot")

        # 回复配置
        self.reply_enabled = getattr(config, 'auto_reply_enabled', True)

        # 初始化数据管理器
        self.data_manager = None
        if DATA_MANAGER_AVAILABLE:
            try:
                self.data_manager = get_data_manager()
            except Exception as e:
                self.logger.error(f"数据管理器初始化失败: {e}")

        # 初始化论坛爬虫
        self.forum_crawler = None
        if FORUM_CRAWLER_AVAILABLE:
            try:
                # 统一从环境变量读取论坛账号信息
                username = os.getenv('FORUM_USERNAME') or os.getenv('AICUT_ADMIN_USERNAME', '')
                password = os.getenv('FORUM_PASSWORD') or os.getenv('AICUT_ADMIN_PASSWORD', '')
                # 获取测试模式配置
                test_mode = getattr(config, 'forum_test_mode', True)
                test_once = getattr(config, 'forum_test_once', False)
                self.forum_crawler = AicutForumCrawler(username, password, test_mode, test_once)
                # 立即登录
                if self.forum_crawler:
                    login_success = self.forum_crawler.login()
                    if login_success:
                        self.logger.info(f"论坛登录成功: {username} - 模式: {'测试' if test_mode else '生产'}")
                    else:
                        self.logger.error(f"论坛登录失败: {username}")
            except Exception as e:
                self.logger.error(f"论坛爬虫初始化失败: {e}")

        self.reply_template = """🎬 视频AI剪辑已完成！

📁 处理完成的文件已保存到输出目录

✨ 处理内容包括:
- 移除静音片段
- 语音识别和字幕生成
- AI智能剪辑
- 添加标题和字幕

请查看输出目录获取处理后的视频文件。

---
🤖 AI剪辑助手自动回复"""

        self.logger.info("论坛回复机器人初始化完成")
    
    def send_reply(self, post_id: str, content: str = None) -> bool:
        """发送论坛回复"""
        try:
            if not self.reply_enabled:
                self.logger.info("论坛回复功能已禁用")
                return False

            if not self.forum_crawler:
                self.logger.warning("论坛爬虫未初始化，无法发送回复")
                return False

            reply_content = content or self.reply_template

            self.logger.info(f"发送论坛回复到帖子: {post_id}")
            print(f"📤 发送论坛回复到帖子: {post_id}")
            print(f"📝 回复内容: {reply_content[:100]}...")

            # 使用论坛爬虫发送回复
            success = self.forum_crawler.reply_to_thread(post_id, reply_content)

            if success:
                # 更新数据库中的回复状态
                if self.data_manager:
                    self.data_manager.update_post_status(
                        post_id,
                        'completed',
                        reply_status='sent',
                        reply_content=reply_content
                    )

                self.logger.info(f"论坛回复发送成功: {post_id}")
                print(f"✅ 论坛回复发送成功: {post_id}")
                return True
            else:
                self.logger.error(f"论坛回复发送失败: {post_id}")
                print(f"❌ 论坛回复发送失败: {post_id}")
                return False

        except Exception as e:
            self.logger.error(f"发送论坛回复失败: {e}")
            print(f"❌ 发送论坛回复异常: {e}")
            return False


# 全局论坛集成实例
_forum_integration = None
_forum_reply_bot = None


def get_forum_integration(queue_manager: QueueManager, config) -> ForumIntegration:
    """获取论坛集成实例"""
    global _forum_integration
    # 总是创建新实例，确保使用正确的队列管理器
    _forum_integration = ForumIntegration(queue_manager, config)
    return _forum_integration


def get_forum_reply_bot(config) -> ForumReplyBot:
    """获取论坛回复机器人实例"""
    global _forum_reply_bot
    if _forum_reply_bot is None:
        _forum_reply_bot = ForumReplyBot(config)
    return _forum_reply_bot
