#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
轻量级视频处理系统 - 任务处理器

主要功能：
- 视频下载处理
- 视频处理流水线集成
- 视频上传处理
- 任务状态管理
"""

import os
import sys
import time
import shutil
import threading
import subprocess
import re
from typing import Optional, Dict, Any, List
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.task_model import TaskType

from .queue_manager import QueueManager, VideoTask, TaskStatus
from .resource_monitor import LightweightResourceMonitor
from .logger import get_logger
from .performance_tracker import performance_tracker
from .report_generator import report_generator
from .task_router import TaskRouter


class TaskProcessor:
    """任务处理器"""
    
    def __init__(self, config, queue_manager: QueueManager, 
                 resource_monitor: LightweightResourceMonitor):
        self.config = config
        self.queue_manager = queue_manager
        self.resource_monitor = resource_monitor
        self.logger = get_logger("TaskProcessor")
        self.task_router = TaskRouter(config)
        
        # 线程池
        self.download_executor = ThreadPoolExecutor(
            max_workers=config.max_download_workers,
            thread_name_prefix="download"
        )
        self.process_executor = ThreadPoolExecutor(
            max_workers=config.max_concurrent_videos,
            thread_name_prefix="process"
        )
        self.upload_executor = ThreadPoolExecutor(
            max_workers=config.max_upload_workers,
            thread_name_prefix="upload"
        )
        
        # 运行状态
        self.running = False
        self.worker_threads = []
        
        # 导入原有pipeline模块
        self._import_pipeline_modules()

        # 任务心跳跟踪
        self.task_heartbeats = {}
        self.heartbeat_lock = threading.Lock()

        # 日志优化：添加计数器和状态跟踪
        self.download_no_task_count = 0
        self.process_no_task_count = 0
        self.upload_no_task_count = 0
        self.last_status_time = time.time()
        self.status_report_interval = 30  # 每30秒输出一次状态汇总

        # 添加输出锁，防止多线程输出混乱
        self.print_lock = threading.Lock()

    def _safe_print(self, message):
        """线程安全的print函数"""
        with self.print_lock:
            print(message, flush=True)
    
    def _import_pipeline_modules(self):
        """导入原有pipeline模块"""
        try:
            from pre.main.pipeline import init_pipeline, run_step
            from pre.stage.stage0 import step0_clean_json
            from pre.stage.stage1 import step1_transcode
            from pre.stage.stage2 import step2_remove_silence
            from pre.stage.stage3 import step3_fix_video
            from pre.stage.stage4 import step4_recognize
            from pre.stage.stage5 import step5_ai_processing
            from pre.stage.stage6 import step6_clip
            from pre.stage.stage7 import step7_add_subtitle
            from pre.stage.stage8 import step8_add_title
            from pre.stage.stage9 import step9_organize_files
            
            self.pipeline_modules = {
                'init_pipeline': init_pipeline,
                'run_step': run_step,
                'steps': {
                    0: step0_clean_json,
                    1: step1_transcode,
                    2: step2_remove_silence,
                    3: step3_fix_video,
                    4: step4_recognize,
                    5: step5_ai_processing,
                    6: step6_clip,
                    7: step7_add_subtitle,
                    8: step8_add_title,
                    9: step9_organize_files
                }
            }
            self.logger.info("Pipeline模块导入成功")
        except ImportError as e:
            self.logger.error(f"Pipeline模块导入失败: {e}")
            self.pipeline_modules = None
    
    def start(self):
        """启动任务处理器"""
        if self.running:
            return

        self.running = True

        # 强制输出启动信息到控制台
        self._safe_print("🚀 TaskProcessor 正在启动...")

        # 启动工作线程
        self.worker_threads = [
            threading.Thread(target=self._download_worker, daemon=True),
            threading.Thread(target=self._process_worker, daemon=True),
            threading.Thread(target=self._upload_worker, daemon=True)
        ]

        for thread in self.worker_threads:
            thread.start()

        self.logger.info("任务处理器已启动")
        self._safe_print("✅ TaskProcessor 启动完成！")
    
    def stop(self):
        """停止任务处理器"""
        self.running = False
        
        # 关闭线程池
        self.download_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)
        self.upload_executor.shutdown(wait=True)
        
        # 等待工作线程结束
        for thread in self.worker_threads:
            thread.join(timeout=5)
        
        self.logger.info("任务处理器已停止")

    def _log_status_summary(self):
        """输出状态汇总信息"""
        current_time = time.time()
        if current_time - self.last_status_time >= self.status_report_interval:
            # 获取队列状态
            queue_sizes = self.queue_manager.get_queue_sizes()

            # 构建状态信息
            status_parts = []
            if self.download_no_task_count > 0:
                status_parts.append(f"下载队列尝试{self.download_no_task_count}次(无任务)")
            if self.process_no_task_count > 0:
                status_parts.append(f"处理队列尝试{self.process_no_task_count}次(无任务)")
            if self.upload_no_task_count > 0:
                status_parts.append(f"上传队列尝试{self.upload_no_task_count}次(无任务)")

            if status_parts:
                self._safe_print(f"📊 {self.status_report_interval}秒状态汇总: {', '.join(status_parts)}")
                self._safe_print(f"📊 当前队列状态: {queue_sizes}")
                self.logger.info(f"状态汇总: {', '.join(status_parts)}, 队列状态: {queue_sizes}")

            # 重置计数器和时间
            self.download_no_task_count = 0
            self.process_no_task_count = 0
            self.upload_no_task_count = 0
            self.last_status_time = current_time

    def _download_worker(self):
        """下载工作器"""
        self._safe_print("🔽 下载工作器已启动")
        self.logger.info("下载工作器已启动")

        loop_count = 0
        while self.running:
            try:
                loop_count += 1

                # 🎯 降低日志频率：每6次循环输出一次调试信息（约30秒）
                if loop_count % 6 == 0:
                    self._safe_print(f"🔽 下载工作器循环 #{loop_count}")
                    self.logger.info(f"下载工作器循环 #{loop_count}")

                # 检查资源状态
                if not self.resource_monitor.can_start_new_task():
                    self._safe_print("⚠️ 资源不足，等待...")
                    self.logger.info("资源不足，等待...")
                    time.sleep(10)
                    continue

                # 🎯 获取下载任务（5秒超时）
                task = self.queue_manager.get_next_download_task(timeout=5)
                if not task:
                    # 增加无任务计数，不立即输出日志
                    self.download_no_task_count += 1
                    # 检查是否需要输出状态汇总
                    self._log_status_summary()
                    continue

                # 获取到任务时输出信息，包括等待次数
                wait_info = f" (等待了{self.download_no_task_count}次)" if self.download_no_task_count > 0 else ""
                print(f"✅ 获取到下载任务: {task.task_id}{wait_info}")
                self.logger.info(f"获取到下载任务: {task.task_id}{wait_info}")

                # 重置计数器
                self.download_no_task_count = 0

                # 提交到线程池（异步执行，不等待完成）
                print(f"🚀 提交下载任务到线程池: {task.task_id}")
                future = self.download_executor.submit(self._process_download, task)
                self.logger.info(f"下载任务已提交到线程池: {task.task_id}")
                print(f"✅ 下载任务已提交，继续处理下一个任务")

            except Exception as e:
                self.logger.error(f"下载工作器错误: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                time.sleep(5)
    
    def _process_worker(self):
        """处理工作器"""
        self._safe_print("⚙️ 处理工作器已启动")
        self.logger.info("处理工作器已启动")

        loop_count = 0
        while self.running:
            try:
                loop_count += 1

                # 🎯 降低日志频率：每6次循环输出一次调试信息（约30秒）
                if loop_count % 6 == 0:
                    self._safe_print(f"⚙️ 处理工作器循环 #{loop_count}")
                    self.logger.info(f"处理工作器循环 #{loop_count}")

                # 检查资源状态
                if not self.resource_monitor.can_start_new_task():
                    self._safe_print("⚠️ 资源不足，等待...")
                    self.logger.info("资源不足，等待...")
                    time.sleep(10)
                    continue

                # 🎯 获取处理任务（5秒超时）
                task = self.queue_manager.get_next_process_task(timeout=5)
                if not task:
                    # 增加无任务计数，不立即输出日志
                    self.process_no_task_count += 1
                    # 检查是否需要输出状态汇总
                    self._log_status_summary()
                    continue

                # TTS任务直接走适配器处理
                if task.task_type in {TaskType.TTS, TaskType.VOICE_CLONE}:
                    self.process_no_task_count = 0
                    self._process_tts_task(task)
                    continue

                wait_info = (
                    f" (等待了{self.process_no_task_count}次)"
                    if self.process_no_task_count > 0
                    else ""
                )
                print(f"✅ 获取到处理任务: {task.task_id}{wait_info}")
                print(f"📁 源文件路径: {task.source_path}")
                self.logger.info(f"获取到处理任务: {task.task_id}{wait_info}")
                self.logger.info(f"源文件路径: {task.source_path}")

                self.process_no_task_count = 0

                print(f"🚀 提交任务到线程池: {task.task_id}")
                future = self.process_executor.submit(self._process_video, task)
                self.logger.info(f"任务已提交到线程池: {task.task_id}")
                print(f"✅ 任务已提交，继续处理下一个任务")

            except Exception as e:
                self.logger.error(f"处理工作器错误: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                time.sleep(5)
    
    def _upload_worker(self):
        """上传工作器"""
        self._safe_print("⬆️ 上传工作器已启动")
        self.logger.info("上传工作器已启动")

        loop_count = 0
        while self.running:
            try:
                loop_count += 1

                # 🎯 降低日志频率：每6次循环输出一次调试信息（约30秒）
                if loop_count % 6 == 0:
                    self._safe_print(f"⬆️ 上传工作器循环 #{loop_count}")
                    self.logger.info(f"上传工作器循环 #{loop_count}")

                # 🎯 获取上传任务（5秒超时）
                task = self.queue_manager.get_next_upload_task(timeout=5)
                if not task:
                    # 增加无任务计数，不立即输出日志
                    self.upload_no_task_count += 1
                    # 检查是否需要输出状态汇总
                    self._log_status_summary()
                    continue

                # 获取到任务时输出信息，包括等待次数
                wait_info = f" (等待了{self.upload_no_task_count}次)" if self.upload_no_task_count > 0 else ""
                print(f"✅ 获取到上传任务: {task.task_id}{wait_info}")
                self.logger.info(f"获取到上传任务: {task.task_id}{wait_info}")

                # 重置计数器
                self.upload_no_task_count = 0

                # 提交到线程池（异步执行，不等待完成）
                print(f"🚀 提交上传任务到线程池: {task.task_id}")
                future = self.upload_executor.submit(self._process_upload, task)
                self.logger.info(f"上传任务已提交到线程池: {task.task_id}")
                print(f"✅ 上传任务已提交，继续处理下一个任务")

            except Exception as e:
                self.logger.error(f"上传工作器错误: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                time.sleep(5)
    
    def _process_download(self, task: VideoTask):
        """处理下载任务"""
        try:
            self.logger.info(f"开始下载任务: {task.task_id}")

            # 🎯 源头修复：检查是否需要解析帖子URL
            # 情况1：没有source_url但有post_url（旧逻辑）
            if not task.source_url and task.metadata and task.metadata.get('post_url'):
                print(f"🔍 检测到帖子URL，开始解析: {task.metadata.get('post_url')}")
                task.source_url = self._parse_post_url_for_video(task)
                if not task.source_url:
                    raise ValueError("无法从帖子URL中提取视频链接")

            # 🎯 情况2：source_url是帖子URL（集群任务的情况）
            elif task.source_url and self._is_post_url(task.source_url):
                print(f"🔍 检测到source_url是帖子URL，开始解析: {task.source_url}")
                # 将帖子URL保存到metadata
                if not task.metadata:
                    task.metadata = {}
                task.metadata['post_url'] = task.source_url

                # 解析帖子获取真实的媒体URL（视频/音频/文本）
                media_url = self._parse_post_url_for_video(task)
                if not media_url:
                    raise ValueError("无法从帖子URL中提取内容")

                # 🎯 处理纯文本任务
                if media_url == "TEXT_ONLY_TASK":
                    print(f"📝 检测到纯文本任务，跳过下载步骤")
                    # 纯文本任务不需要下载，直接进入处理队列
                    task.source_url = None  # 清空source_url
                    task.status = TaskStatus.DOWNLOADED
                    self.queue_manager.add_to_process_queue(task)
                    return

                # 更新source_url为真实的媒体URL
                task.source_url = media_url
                print(f"✅ 成功解析媒体URL: {media_url}")

            if not task.source_url:
                raise ValueError("缺少源URL")

            # 首先尝试从任务metadata获取原始文件名
            original_filename = None
            if task.metadata and task.metadata.get('original_filename'):
                original_filename = task.metadata.get('original_filename')
                print(f"📝 从任务metadata获取原始文件名: {original_filename}")
                self.logger.info(f"从任务metadata获取原始文件名: {original_filename}")

            # 如果metadata中没有，尝试从数据库获取
            if not original_filename:
                original_filename = self._get_original_filename_from_db(task.task_id, task.source_url)

            # 如果数据库中也没有，从URL中提取
            if not original_filename:
                original_filename = self._extract_filename_from_url(task.source_url)

            # 创建本地文件路径 - 使用原始文件名
            if original_filename:
                filename = original_filename
                print(f"📝 使用原始文件名: {filename}")
            else:
                # 如果无法提取原始文件名，使用UUID作为备用
                filename = f"{task.task_id}.mp4"
                print(f"📝 使用备用文件名: {filename}")

            local_path = os.path.join(self.config.input_dir, filename)

            # 实现真实的下载逻辑
            self._download_video(task.source_url, local_path, task.task_id)

            # 保存原始文件名到任务metadata
            if not task.metadata:
                task.metadata = {}
            task.metadata['original_filename'] = filename

            # 更新任务metadata到队列管理器
            self.queue_manager.update_task_metadata(task.task_id, task.metadata)

            # 完成下载
            self.queue_manager.complete_download(task.task_id, local_path)
            self.logger.info(f"下载完成: {task.task_id}, 原始文件名: {filename}")

        except Exception as e:
            error_msg = f"下载失败: {str(e)}"
            self.logger.error(f"任务 {task.task_id} {error_msg}")
            self.queue_manager.fail_task(task.task_id, error_msg)

    def _process_tts_task(self, task: VideoTask) -> None:
        """Handle TTS/voice clone tasks via the router."""

        self.logger.info(f"开始处理TTS任务: {task.task_id}")
        try:
            route_result = self.task_router.route(task)
            if not route_result.get("success"):
                error_message = route_result.get("error", "TTS任务处理失败")
                self.logger.error(f"TTS任务失败: {task.task_id}, 错误: {error_message}")
                self.queue_manager.fail_task(task.task_id, error_message, retry=False)
                return

            reply_payload = route_result.get("reply")
            if reply_payload:
                from shared.forum_reply_manager import get_forum_reply_manager

                reply_manager = get_forum_reply_manager()
                reply_manager.reply_with_task_result(task, reply_payload)

                attachments = reply_payload.get("attachments") or []
                if attachments:
                    task.output_files = attachments

            self.queue_manager.update_task_status(
                task.task_id,
                TaskStatus.COMPLETED,
                result=route_result.get("result"),
            )
            self.logger.info(f"TTS任务完成: {task.task_id}")

        except Exception as exc:  # pragma: no cover - defensive logging
            error_message = f"TTS任务执行异常: {exc}"
            self.logger.error(error_message)
            self.queue_manager.fail_task(task.task_id, error_message, retry=False)
    
    def _download_video(self, url: str, local_path: str, task_id: str):
        """真实的视频下载逻辑"""
        download_start_time = time.time()
        try:
            self.logger.info(f"开始下载视频: {url}")
            print(f"🔽 开始下载视频: {url}")

            # 确保目录存在
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)

            # 使用requests下载
            import requests

            # 设置请求头，模拟浏览器
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            # 发送HEAD请求获取文件信息
            try:
                head_response = requests.head(url, headers=headers, timeout=30, allow_redirects=True)
                total_size = int(head_response.headers.get('content-length', 0))
                print(f"📊 文件大小: {total_size / (1024*1024):.2f} MB" if total_size > 0 else "📊 文件大小: 未知")
            except:
                total_size = 0

            # 下载文件
            response = requests.get(url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()

            downloaded_size = 0
            last_progress_mb = 0
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        # 每下载0.5MB更新一次进度（减少更新频率，提高兼容性）
                        current_mb = downloaded_size / (1024 * 1024)
                        if current_mb - last_progress_mb >= 0.5 or downloaded_size < 1024 * 1024:
                            if total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                total_mb = total_size / (1024 * 1024)
                                # 创建固定长度的进度条字符串，避免Windows终端显示问题
                                progress_text = f"📥 下载进度: {progress:5.1f}% ({current_mb:6.2f}/{total_mb:6.2f} MB)"
                                # 清空当前行并重新打印
                                print(f"\r{progress_text:<60}", end='', flush=True)
                            else:
                                progress_text = f"📥 已下载: {current_mb:6.2f} MB"
                                print(f"\r{progress_text:<60}", end='', flush=True)
                            last_progress_mb = current_mb

            # 验证下载的文件
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                file_size = os.path.getsize(local_path)
                download_duration = time.time() - download_start_time
                # 换行结束进度条显示
                print()
                print(f"✅ 视频下载完成: {local_path}")
                print(f"📁 文件大小: {file_size / (1024*1024):.2f} MB")
                print(f"⏱️ 下载耗时: {download_duration:.1f}秒")
                self.logger.info(f"视频下载完成: {local_path}, 大小: {file_size} bytes, 耗时: {download_duration:.1f}秒")

                # 记录下载时间到性能追踪器
                performance_tracker.record_download_time(task_id, download_duration)

                return True
            else:
                raise ValueError("下载的文件为空或不存在")

        except Exception as e:
            error_msg = f"视频下载失败: {str(e)}"
            print(f"❌ {error_msg}")
            self.logger.error(error_msg)

            # 清理失败的下载文件
            if os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except:
                    pass

            raise Exception(error_msg)

    def _get_original_filename_from_db(self, task_id: str, source_url: str) -> Optional[str]:
        """从数据库获取原始文件名"""
        try:
            # 导入数据管理器
            from forum_data_manager import get_data_manager

            data_manager = get_data_manager()

            # 通过task_id查找对应的帖子
            posts = data_manager.get_posts_by_status("processing", limit=100)
            posts.extend(data_manager.get_posts_by_status("pending", limit=100))

            for post in posts:
                if post.task_id == task_id and post.video_urls:
                    # 找到匹配的URL索引
                    for i, video_url in enumerate(post.video_urls):
                        if video_url == source_url and post.original_filenames and i < len(post.original_filenames):
                            filename = post.original_filenames[i]
                            print(f"📝 从数据库获取原始文件名: {filename}")
                            self.logger.info(f"从数据库获取原始文件名: {source_url} -> {filename}")
                            return filename

            return None

        except Exception as e:
            print(f"⚠️ 从数据库获取文件名失败: {e}")
            self.logger.warning(f"从数据库获取文件名失败: {e}")
            return None

    def _extract_filename_from_url(self, url: str) -> Optional[str]:
        """从URL中提取原始文件名，保持中文字符"""
        try:
            import urllib.parse
            import re

            # 解析URL
            parsed_url = urllib.parse.urlparse(url)

            # 从路径中提取文件名
            path = parsed_url.path
            if not path:
                return None

            # 获取路径的最后一部分（文件名）
            filename = os.path.basename(path)

            if not filename:
                return None

            # URL解码，处理中文字符
            filename = urllib.parse.unquote(filename, encoding='utf-8')

            # 验证文件名是否为视频文件
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']
            if not any(filename.lower().endswith(ext) for ext in video_extensions):
                # 如果没有视频扩展名，添加.mp4
                if '.' not in filename:
                    filename += '.mp4'
                else:
                    # 替换扩展名为.mp4
                    name_without_ext = os.path.splitext(filename)[0]
                    filename = name_without_ext + '.mp4'

            # 清理文件名中的非法字符（保留中文）
            # 移除Windows文件名中不允许的字符，但保留中文
            illegal_chars = r'[<>:"/\\|?*]'
            filename = re.sub(illegal_chars, '_', filename)

            # 限制文件名长度
            if len(filename) > 200:
                name_part, ext_part = os.path.splitext(filename)
                max_name_length = 200 - len(ext_part)
                filename = name_part[:max_name_length] + ext_part

            print(f"📝 提取的原始文件名: {filename}")
            self.logger.info(f"从URL提取文件名: {url} -> {filename}")

            return filename

        except Exception as e:
            print(f"⚠️ 无法从URL提取文件名: {e}")
            self.logger.warning(f"无法从URL提取文件名: {url}, 错误: {e}")
            return None


    def _process_video(self, task: VideoTask):
        """处理视频任务 - 使用内部pipeline模块"""
        try:
            print(f"🎬 开始处理视频: {task.task_id}")
            print(f"📁 源文件: {task.source_path}")
            self.logger.info(f"开始处理视频: {task.task_id}")

            if not task.source_path or not os.path.exists(task.source_path):
                error_msg = f"源文件不存在: {task.source_path}"
                print(f"❌ {error_msg}")
                raise ValueError(error_msg)

            print(f"✅ 源文件存在，开始处理...")

            # 获取视频信息并开始性能追踪
            file_size_mb = os.path.getsize(task.source_path) / (1024 * 1024)

            # 获取原始文件名
            original_filename = "unknown.mp4"
            if task.metadata and task.metadata.get('original_filename'):
                original_filename = task.metadata.get('original_filename')

            # 获取视频时长（使用ffprobe）
            video_duration = self._get_video_duration(task.source_path)
            if video_duration <= 0:
                video_duration = 180.0  # 如果获取失败，默认3分钟
                print(f"⚠️ 无法获取视频时长，使用默认值: {video_duration}秒")

            # 开始性能追踪
            perf_task_id = performance_tracker.start_video_processing(
                video_filename=task.task_id,
                original_filename=original_filename,
                file_size_mb=file_size_mb,
                video_duration_seconds=video_duration
            )

            # 创建输出目录 - 使用绝对路径
            output_dir = os.path.abspath(os.path.join(self.config.output_dir, task.task_id))
            os.makedirs(output_dir, exist_ok=True)
            print(f"📂 创建输出目录: {output_dir}")

            # 保存论坛帖子信息到输出目录（如果有的话）
            print(f"🔍 [DEBUG] 准备保存论坛信息...")
            print(f"🔍 [DEBUG] 任务ID: {task.task_id}")
            print(f"🔍 [DEBUG] 输出目录: {output_dir}")
            print(f"🔍 [DEBUG] 任务metadata存在: {task.metadata is not None}")
            if task.metadata:
                print(f"🔍 [DEBUG] metadata字段:")
                for key, value in task.metadata.items():
                    print(f"     - {key}: {value}")
            self._save_forum_info_to_output(task, output_dir)

            # 获取pipeline配置，包含GPU设置
            from lightweight.config import get_config_manager
            config_manager = get_config_manager()
            pipeline_config = config_manager.get_pipeline_config()
            pipeline_config['output_dir'] = output_dir

            print(f"🔧 GPU加速状态: {'启用' if pipeline_config.get('use_gpu', False) else '禁用'}")
            self.logger.info(f"GPU加速状态: {'启用' if pipeline_config.get('use_gpu', False) else '禁用'}")

            # 使用内部pipeline模块处理
            print(f"⚙️ 开始执行pipeline...")
            success, output_file = self._run_pipeline_internal(task.source_path, pipeline_config, task.task_id)

            if not success:
                error_msg = "视频处理失败"
                print(f"❌ {error_msg}")
                raise RuntimeError(error_msg)

            print(f"✅ Pipeline执行成功，输出文件: {output_file}")

            # 完成处理
            self.queue_manager.complete_process(task.task_id, output_file)
            print(f"🎉 视频处理完成: {task.task_id}")
            self.logger.info(f"视频处理完成: {task.task_id}")

        except Exception as e:
            error_msg = f"视频处理失败: {str(e)}"
            print(f"❌ 任务 {task.task_id} {error_msg}")
            self.logger.error(f"任务 {task.task_id} {error_msg}")
            self.queue_manager.fail_task(task.task_id, error_msg)

    def _run_pipeline_internal(self, input_video: str, config: Dict[str, Any], task_id: str) -> tuple:
        """使用内部pipeline模块运行处理流水线"""
        try:
            print(f"🔧 开始内部pipeline处理: {task_id}")
            self.logger.info(f"开始内部pipeline处理: {task_id}")

            # 初始化pipeline
            init_pipeline = self.pipeline_modules['init_pipeline']
            run_step = self.pipeline_modules['run_step']
            steps = self.pipeline_modules['steps']

            # 初始化必要的组件
            from pre.main.timing import StepTimer
            import logging

            # 创建logger
            logger = logging.getLogger("FunClip")

            # 创建计时器
            timer = StepTimer()

            # ASR 已禁用：不加载 funasr/VideoClipper，audio_clipper 保持为 None
            audio_clipper = None

            # 初始化pipeline（不需要参数）
            init_pipeline()

            current_video = input_video

            # 执行各个步骤
            for step_num in range(0, 10):  # 步骤0-9
                if not config.get(f'enable_step{step_num}', True):
                    print(f"⏭️ 跳过步骤{step_num}")
                    continue

                step_func = steps.get(step_num)
                if not step_func:
                    print(f"⚠️ 步骤{step_num}函数不存在")
                    continue

                step_name = self._get_step_name(step_num)
                print(f"🔄 执行步骤{step_num}: {step_name}")
                self.logger.info(f"执行步骤{step_num}: {step_name}")

                # 开始阶段计时
                gpu_accelerated = step_num in [2, 3]  # 语音识别和智能分割使用GPU
                performance_tracker.start_stage(task_id, f"Stage{step_num} ({step_name})", gpu_accelerated)

                # 记录资源使用
                self.resource_monitor.record_step_resource(step_num, step_name)

                # 运行步骤
                success, output_file, duration = run_step(
                    step_num, step_name, step_func, current_video,
                    config, timer, audio_clipper, enabled=True
                )

                # 结束阶段计时
                performance_tracker.end_stage(task_id, f"Stage{step_num} ({step_name})", gpu_accelerated)

                if not success:
                    print(f"❌ 步骤{step_num}执行失败")
                    self.logger.error(f"步骤{step_num}执行失败")
                    if config.get('stop_on_error', True):
                        return False, None
                    continue

                if output_file:
                    # 步骤0、4、5不改变视频文件路径，只是执行清理或生成辅助文件
                    if step_num not in [0, 4, 5]:
                        current_video = output_file
                    print(f"✅ 步骤{step_num}完成，输出: {output_file}")
                    self.logger.info(f"步骤{step_num}完成，输出: {output_file}")

            print(f"🎉 Pipeline处理完成: {current_video}")

            # 结束性能追踪并生成报告
            report = performance_tracker.end_video_processing(task_id)
            if report:
                print(f"📊 性能报告生成成功，开始保存各种格式...")
                # 生成所有格式的报告
                report_files = report_generator.save_all_formats(report)
                print(f"📊 报告文件生成完成: {list(report_files.keys())}")

                # 将用户友好报告保存到任务metadata中，用于论坛回复
                if task_id and hasattr(self, 'queue_manager'):
                    task_obj = self.queue_manager.get_task(task_id)
                    if task_obj and task_obj.metadata:
                        user_report_content = report_files.get('user_report', '')
                        if user_report_content:
                            task_obj.metadata['user_report'] = user_report_content
                            task_obj.metadata['technical_report'] = report_files.get('technical_report', '')
                            self.queue_manager.update_task_metadata(task_id, task_obj.metadata)
                            print(f"✅ 用户报告已保存到任务metadata (长度: {len(user_report_content)} 字符)")
                        else:
                            print(f"⚠️ 用户报告内容为空，无法保存到metadata")
                    else:
                        print(f"⚠️ 无法获取任务或任务metadata为空: task_id={task_id}")
                else:
                    print(f"⚠️ 缺少task_id或queue_manager: task_id={task_id}, has_queue_manager={hasattr(self, 'queue_manager')}")
            else:
                print(f"⚠️ 性能跟踪器没有返回报告，任务ID: {task_id}")

            return True, current_video

        except Exception as e:
            print(f"❌ Pipeline内部处理异常: {e}")
            self.logger.error(f"Pipeline内部处理异常: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

            # 记录错误到性能追踪器
            performance_tracker.add_error(task_id, f"Pipeline处理异常: {str(e)}")
            performance_tracker.end_video_processing(task_id)

            return False, None

    def _run_pipeline(self, input_video: str, config: Dict[str, Any],
                     logger, timer, audio_clipper) -> tuple:
        """运行处理流水线"""
        current_video = input_video
        run_step = self.pipeline_modules['run_step']
        steps = self.pipeline_modules['steps']
        
        try:
            # 执行各个步骤
            for step_num in range(1, 10):  # 步骤1-9
                if not config.get(f'enable_step{step_num}', True):
                    continue
                
                step_func = steps.get(step_num)
                if not step_func:
                    continue
                
                step_name = self._get_step_name(step_num)
                
                # 记录资源使用
                self.resource_monitor.record_step_resource(step_num, step_name)
                
                # 运行步骤
                success, output_file, duration = run_step(
                    step_num, step_name, step_func, current_video,
                    config, timer, audio_clipper, enabled=True
                )
                
                if not success:
                    if config.get('stop_on_error', True):
                        return False, None
                    continue
                
                if output_file:
                    # 步骤0、4、5不改变视频文件路径，只是执行清理或生成辅助文件
                    if step_num not in [0, 4, 5]:
                        current_video = output_file
            
            return True, current_video
            
        except Exception as e:
            self.logger.error(f"Pipeline执行错误: {e}")
            return False, None

    def _run_pipeline_subprocess(self, cmd: list, task_id: str) -> tuple:
        """使用subprocess运行pipeline命令"""
        try:
            self.logger.info(f"启动pipeline子进程: {' '.join(cmd)}")

            # 启动子进程，实时显示输出
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 合并stderr到stdout
                text=True,
                cwd=os.getcwd(),
                env=os.environ.copy(),
                bufsize=1,  # 行缓冲
                universal_newlines=True
            )

            print(f"📋 Pipeline详细日志 (任务: {task_id}):")
            print("=" * 80)

            # 实时读取并显示输出
            output_lines = []
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    line = line.rstrip()
                    print(f"📄 {line}")  # 实时显示每一行
                    output_lines.append(line)
                    self.logger.debug(f"Pipeline输出: {line}")

            # 等待进程完成
            process.wait()

            print("=" * 80)
            print(f"📋 Pipeline执行完成 (返回码: {process.returncode})")

            # 检查返回码
            if process.returncode == 0:
                print(f"✅ Pipeline执行成功: {task_id}")
                self.logger.info(f"Pipeline执行成功: {task_id}")

                # 查找输出文件 - 使用绝对路径
                output_dir = os.path.abspath(os.path.join(self.config.output_dir, task_id))
                output_file = self._find_output_file(output_dir)

                return True, output_file
            else:
                print(f"❌ Pipeline执行失败: {task_id} (返回码: {process.returncode})")
                self.logger.error(f"Pipeline执行失败: {task_id}")
                return False, None

        except Exception as e:
            print(f"❌ Pipeline子进程执行异常: {e}")
            self.logger.error(f"Pipeline子进程执行异常: {e}")
            return False, None

    def _find_output_file(self, output_dir: str) -> Optional[str]:
        """查找输出目录中的主要视频文件"""
        if not os.path.exists(output_dir):
            return None

        try:
            # 查找视频文件
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv']
            for file in os.listdir(output_dir):
                if any(file.lower().endswith(ext) for ext in video_extensions):
                    return os.path.join(output_dir, file)

            # 如果没有找到视频文件，返回目录路径
            return output_dir

        except Exception as e:
            self.logger.warning(f"查找输出文件失败: {e}")
            return output_dir

    def _get_step_name(self, step_num: int) -> str:
        """获取步骤名称"""
        step_names = {
            1: "视频转码",
            2: "移除静音",
            3: "视频修复",
            4: "语音识别",
            5: "AI处理",
            6: "视频剪辑",
            7: "添加字幕",
            8: "添加标题",
            9: "文件整理"
        }
        return step_names.get(step_num, f"步骤{step_num}")

    def _get_video_duration(self, video_path: str) -> float:
        """获取视频时长（秒）"""
        try:
            import subprocess
            import json

            # 使用ffprobe获取视频信息
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                video_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = float(data['format']['duration'])
                print(f"📏 视频时长: {duration:.1f}秒 ({duration/60:.1f}分钟)")
                return duration
            else:
                print(f"⚠️ ffprobe执行失败: {result.stderr}")
                return 0.0

        except subprocess.TimeoutExpired:
            print("⚠️ ffprobe执行超时")
            return 0.0
        except Exception as e:
            print(f"⚠️ 获取视频时长失败: {e}")
            return 0.0

    def _save_forum_info_to_output(self, task: VideoTask, output_dir: str):
        """保存论坛帖子信息到输出目录"""
        try:
            if not task.metadata:
                return

            # 检查是否有论坛相关信息 - 使用更宽松的判断
            metadata = task.metadata
            
            # 打印metadata信息用于调试
            print(f"🔍 [DEBUG] 检查是否保存forum_post_info.json:")
            print(f"   - source: {metadata.get('source', 'None')}")
            print(f"   - is_forum_task: {metadata.get('is_forum_task', False)}")
            print(f"   - is_cluster_task: {metadata.get('is_cluster_task', False)}")
            print(f"   - post_id: {metadata.get('post_id', 'None')}")
            print(f"   - post_url: {metadata.get('post_url', 'None')}")
            
            # 只要有post_url或者标记为论坛/集群任务，就保存文件
            should_save = (
                metadata.get('post_url', '') != '' or
                metadata.get('is_forum_task', False) or
                metadata.get('is_cluster_task', False) or
                metadata.get('source') in ['forum', 'forum_manual']
            )
            
            if not should_save:
                print(f"⚠️ 不满足保存条件，跳过保存forum_post_info.json")
                return
            
            print(f"✅ 满足保存条件，开始保存forum_post_info.json")

            # 导入数据模型
            from lightweight.forum_data_model import ForumPostInfo
            
            # 提取论坛信息
            print(f"🔍 [DEBUG] 任务metadata内容: {metadata}")
            print(f"🔍 [DEBUG] metadata中的封面标题字段:")
            print(f"   - cover_title_up: '{metadata.get('cover_title_up', '')}'")
            print(f"   - cover_title_middle: '{metadata.get('cover_title_middle', '')}'")
            print(f"   - cover_title_down: '{metadata.get('cover_title_down', '')}'")

            # 使用数据模型构建论坛信息
            forum_post = ForumPostInfo()
            forum_post.post_id = metadata.get('post_id', '')
            forum_post.title = metadata.get('title', '')
            forum_post.author_id = metadata.get('author_id', '')
            forum_post.original_filename = metadata.get('original_filename', '')
            forum_post.post_url = metadata.get('post_url', '')
            forum_post.source = metadata.get('source', 'forum')
            
            # 添加封面标题（使用语义化结构）
            for position in ['up', 'middle', 'down']:
                key = f'cover_title_{position}'
                if key in metadata and metadata[key]:
                    forum_post.add_cover_title(metadata[key], position)
            
            # 转换为字典（包含新旧格式）
            forum_info = forum_post.to_dict()

            print(f"🔍 [DEBUG] 构建的forum_info:")
            print(f"   - 旧格式 cover_title_up: '{forum_info['cover_title_up']}'")
            print(f"   - 旧格式 cover_title_middle: '{forum_info['cover_title_middle']}'")
            print(f"   - 旧格式 cover_title_down: '{forum_info['cover_title_down']}'")
            print(f"   - 新格式 cover_titles: {forum_info['cover_titles']}")

            # 检查是否有任何封面标题
            has_any_cover_title = bool(forum_info['cover_title_up'] or forum_info['cover_title_middle'] or forum_info['cover_title_down'])
            print(f"🔍 [DEBUG] 是否有封面标题: {has_any_cover_title}")

            # 保存论坛信息文件（无论是否有封面标题）
            forum_info_file = os.path.join(output_dir, "forum_post_info.json")

            # 🎯 集群模式增强：添加完整的帖子内容用于热词提取
            if metadata and (metadata.get('is_cluster_task') or metadata.get('is_forum_task')):
                print(f"🔍 检测到集群/论坛任务，metadata keys: {list(metadata.keys())}")
                # 从集群任务中获取完整的帖子数据
                forum_post_data = metadata.get('forum_post_data', {})
                print(f"🔍 forum_post_data keys: {list(forum_post_data.keys()) if forum_post_data else 'None'}")
                if forum_post_data:
                    # 添加完整的帖子内容和核心文本
                    forum_post.content = forum_post_data.get('content', '')
                    forum_post.core_text = forum_post_data.get('core_text', '')
                    # 重新生成字典以包含新添加的内容
                    forum_info = forum_post.to_dict()
                    print(f"🎯 集群模式：添加完整帖子内容用于热词提取")
                    print(f"📝 帖子内容长度: {len(forum_info.get('content', ''))}")
                    print(f"🎯 核心文本长度: {len(forum_info.get('core_text', ''))}")
                    # 显示内容预览
                    if forum_info.get('content'):
                        content_preview = forum_info['content'][:100] + "..." if len(forum_info['content']) > 100 else forum_info['content']
                        print(f"📄 保存的帖子内容预览: {content_preview}")
                else:
                    print(f"⚠️ 集群任务中未找到forum_post_data")

            with open(forum_info_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(forum_info, f, ensure_ascii=False, indent=2)

            print(f"💾 保存论坛信息到: {forum_info_file}")
            print(f"✅ forum_post_info.json 文件保存成功！")
            print(f"📍 文件路径: {os.path.abspath(forum_info_file)}")

            # 验证文件是否正确保存
            if os.path.exists(forum_info_file):
                with open(forum_info_file, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                print(f"🔍 [DEBUG] 验证保存的文件内容:")
                print(f"   - 旧格式 cover_title_up: '{saved_data.get('cover_title_up', '')}'")
                print(f"   - 旧格式 cover_title_middle: '{saved_data.get('cover_title_middle', '')}'")
                print(f"   - 旧格式 cover_title_down: '{saved_data.get('cover_title_down', '')}'")
                print(f"   - 新格式 cover_titles: {saved_data.get('cover_titles', [])}")
            else:
                print(f"❌ [ERROR] 文件保存失败: {forum_info_file}")

            # 显示封面标题信息（使用新的数据格式）
            if forum_info['cover_titles']:
                print(f"🖼️ 找到 {len(forum_info['cover_titles'])} 个封面标题:")
                for title_data in forum_info['cover_titles']:
                    position_name = {'up': '上', 'middle': '中', 'down': '下'}.get(title_data['position'], title_data['position'])
                    print(f"   - 封面标题{position_name}: {title_data['text']}")
            else:
                print(f"📝 帖子未提供封面标题，将使用AI生成")
            self.logger.info(f"保存论坛信息到: {forum_info_file}")

        except Exception as e:
            print(f"⚠️ 保存论坛信息失败: {e}")
            self.logger.warning(f"保存论坛信息失败: {e}")
            # 打印完整的错误堆栈
            import traceback
            traceback.print_exc()
            self.logger.error(traceback.format_exc())
    
    def _process_upload(self, task: VideoTask):
        """处理上传任务 - 直接回复到论坛"""
        try:
            self.logger.info(f"开始上传任务: {task.task_id}")
            print(f"⬆️ 开始上传任务: {task.task_id}")

            if not task.output_path or not os.path.exists(task.output_path):
                raise ValueError(f"输出文件不存在: {task.output_path}")

            # 实现论坛回复逻辑
            success = self._reply_to_forum(task)

            if success:
                # 完成上传
                self.queue_manager.complete_upload(task.task_id)
                print(f"✅ 论坛回复完成: {task.task_id}")
                self.logger.info(f"论坛回复完成: {task.task_id}")
            else:
                raise Exception("论坛回复失败")

            # 清理临时文件
            self._cleanup_task_files(task)

        except Exception as e:
            error_msg = f"上传失败: {str(e)}"
            print(f"❌ {error_msg}")
            self.logger.error(f"任务 {task.task_id} {error_msg}")
            self.queue_manager.fail_task(task.task_id, error_msg, retry=False)

    def _parse_post_url_for_video(self, task: VideoTask) -> Optional[str]:
        """解析帖子URL获取视频链接"""
        try:
            post_url = task.metadata.get('post_url')
            if not post_url:
                return None

            print(f"🔍 开始解析帖子URL: {post_url}")

            # 获取论坛集成实例
            from .forum_integration import ForumIntegration
            forum_integration = ForumIntegration(self.queue_manager, self.config)

            if not forum_integration.forum_crawler:
                print("❌ 论坛爬虫未初始化，无法解析帖子")
                return None

            print(f"🔍 [DEBUG] 论坛爬虫登录状态: {forum_integration.forum_crawler.logged_in}")
            print(f"🔍 [DEBUG] 论坛爬虫用户名: {forum_integration.forum_crawler.username}")

            # 使用论坛爬虫解析帖子内容
            content_info = forum_integration.forum_crawler.get_thread_content(post_url)

            if not content_info:
                print("❌ 无法获取帖子内容")
                return None

            print(f"🔍 [DEBUG] 获取到的content_info: {content_info}")
            print(f"🔍 [DEBUG] content_info中的cover_info: {content_info.get('cover_info', {})}")

            # 🎯 支持三种类型：视频、音频、纯文本
            video_urls = content_info.get('video_urls', [])
            audio_urls = content_info.get('audio_urls', [])
            core_text = content_info.get('core_text', '').strip()

            # 优先级：视频 > 音频 > 纯文本
            media_url = None
            if video_urls:
                media_url = video_urls[0]
                print(f"✅ 成功提取视频链接: {media_url}")
            elif audio_urls:
                media_url = audio_urls[0]
                print(f"✅ 成功提取音频链接: {media_url}")
            elif core_text:
                # 纯文本任务（TTS合成），不需要media_url
                print(f"✅ 成功提取文本内容: {len(core_text)} 字符")
                print(f"📝 文本预览: {core_text[:100]}...")
                # 对于纯文本任务，返回特殊标记
                media_url = "TEXT_ONLY_TASK"
            else:
                print("❌ 帖子中未找到视频、音频或文本内容")
                return None

            # 🎯 关键修复：立即更新任务metadata中的封面标题信息
            original_filenames = content_info.get('original_filenames', [])
            cover_info = content_info.get('cover_info', {})

            task.metadata.update({
                'video_urls': video_urls,
                'audio_urls': audio_urls,  # 🎯 添加音频链接
                'original_filenames': original_filenames,
                'content': content_info.get('content', ''),
                'core_text': content_info.get('core_text', ''),  # 🎯 添加核心文本（用于TTS）
                'cover_info': cover_info,
                'title': content_info.get('title', ''),
                'author': content_info.get('author', ''),
                'category': content_info.get('category', ''),  # 🎯 添加Discuz分类信息字段
                # 🎯 直接从cover_info提取封面标题到metadata
                'cover_title_up': cover_info.get('cover_title_up', ''),
                'cover_title_middle': cover_info.get('cover_title_middle', ''),
                'cover_title_down': cover_info.get('cover_title_down', '')
            })

            print(f"🎯 [DEBUG] 立即更新任务metadata中的封面标题:")
            print(f"   - cover_title_up: '{task.metadata.get('cover_title_up', '')}'")
            print(f"   - cover_title_middle: '{task.metadata.get('cover_title_middle', '')}'")
            print(f"   - cover_title_down: '{task.metadata.get('cover_title_down', '')}')")

            # 🎯 关键修复：设置第一个视频的原始文件名
            if original_filenames and len(original_filenames) > 0:
                task.metadata['original_filename'] = original_filenames[0]
                print(f"📝 设置原始文件名: {original_filenames[0]}")

            # 🎯 关键修复：将帖子内容保存到数据库
            try:
                from forum_data_manager import HybridForumDataManager, ForumPost
                data_manager = HybridForumDataManager()

                # 从URL提取post_id
                import re
                post_id_match = re.search(r'thread-(\d+)-', post_url)
                if post_id_match:
                    post_id = post_id_match.group(1)

                    # 构建帖子数据
                    cover_info = content_info.get('cover_info', {})

                    # 创建ForumPost对象
                    from datetime import datetime
                    forum_post = ForumPost(
                        post_id=post_id,
                        thread_id=post_id,  # 使用post_id作为thread_id
                        forum_id=2,
                        title=content_info.get('title', ''),
                        content=content_info.get('content', ''),
                        author_id=content_info.get('author_id', ''),
                        author_name=content_info.get('author', ''),
                        cover_title_up=cover_info.get('cover_title_up', ''),
                        cover_title_down=cover_info.get('cover_title_down', ''),
                        cover_info_raw=str(cover_info),
                        video_urls=video_urls if video_urls else [],
                        original_filenames=original_filenames if original_filenames else [],
                        media_count=len(video_urls) if video_urls else 0,
                        processing_status='pending',
                        task_id=task.task_id,
                        output_path='',
                        reply_status='pending',
                        reply_content='',
                        post_time=datetime.now(),  # 添加必需的post_time字段
                        discovered_time=datetime.now(),
                        last_updated=datetime.now()
                    )

                    # 保存到数据库
                    success = data_manager.save_post(forum_post)
                    if success:
                        print(f"✅ 帖子内容已保存到数据库: post_id={post_id}")

                        # 🎯 关键修复：更新任务metadata中的封面标题
                        task.metadata.update({
                            'title': content_info.get('title', ''),
                            'cover_title_up': cover_info.get('cover_title_up', ''),
                            'cover_title_middle': cover_info.get('cover_title_middle', ''),
                            'cover_title_down': cover_info.get('cover_title_down', ''),
                            'content': content_info.get('content', ''),
                            'author': content_info.get('author', '')
                        })
                        print(f"✅ 任务metadata已更新封面标题: 上='{cover_info.get('cover_title_up', '')}', 中='{cover_info.get('cover_title_middle', '')}', 下='{cover_info.get('cover_title_down', '')}'")
                    else:
                        print(f"❌ 保存帖子内容到数据库失败")

            except Exception as e:
                print(f"⚠️ 保存帖子内容到数据库失败: {e}")
                # 不影响主流程，继续执行

            return media_url

        except Exception as e:
            print(f"❌ 解析帖子URL失败: {e}")
            self.logger.error(f"解析帖子URL失败: {e}")
            return None

    def _is_post_url(self, url: str) -> bool:
        """判断URL是否是论坛帖子URL"""
        try:
            if not url:
                return False

            # 检查是否是论坛帖子URL的模式
            post_patterns = [
                r'thread-\d+-\d+-\d+\.html',  # thread-74-1-1.html
                r'forum\.php\?mod=viewthread',  # forum.php?mod=viewthread&tid=74
                r'/viewthread\.php',  # viewthread.php?tid=74
            ]

            for pattern in post_patterns:
                if re.search(pattern, url):
                    print(f"🔍 识别为帖子URL: {url}")
                    return True

            # 检查域名是否是论坛域名
            if any(domain in url for domain in ('tts.lrtcai.com', 'aicut.lrtcai.com')) and ('thread-' in url or 'viewthread' in url):
                print(f"🔍 识别为论坛帖子URL: {url}")
                return True

            return False

        except Exception as e:
            print(f"❌ 判断帖子URL失败: {e}")
            return False

    def _reply_to_forum(self, task: VideoTask) -> bool:
        """回复到论坛帖子，支持上传视频文件"""
        try:
            print(f"📝 准备回复论坛帖子...")

            # 获取任务的元数据，包含帖子信息
            metadata = task.metadata or {}
            post_id = metadata.get('post_id')

            if not post_id:
                print("⚠️ 任务缺少帖子ID，无法回复论坛")
                self.logger.warning(f"任务 {task.task_id} 缺少帖子ID")
                return False

            # 构建回复内容
            reply_content = self._build_reply_content(task)

            # 获取要上传的视频文件
            video_files = self._get_upload_video_files(task)

            # 使用论坛回复机器人（支持文件上传）
            success = self._send_forum_reply_with_files(post_id, reply_content, video_files, task.task_id)

            if success:
                print(f"✅ 成功回复论坛帖子: {post_id}")
                if video_files:
                    print(f"📁 成功上传 {len(video_files)} 个视频文件")
                self.logger.info(f"成功回复论坛帖子: {post_id}")
                return True
            else:
                print(f"❌ 回复论坛帖子失败: {post_id}")
                return False

        except Exception as e:
            print(f"❌ 论坛回复异常: {e}")
            self.logger.error(f"论坛回复异常: {e}")
            return False

    def _build_reply_content(self, task: VideoTask) -> str:
        """构建回复内容"""
        try:
            # 获取原始文件名
            metadata = task.metadata or {}
            original_filename = metadata.get('original_filename', '未知文件')

            # 获取用户友好的性能报告
            user_report = metadata.get('user_report', '')
            print(f"🔍 调试信息 - 任务 {task.task_id}:")
            print(f"   - metadata keys: {list(metadata.keys()) if metadata else 'None'}")
            print(f"   - user_report存在: {'是' if user_report else '否'}")
            if user_report:
                print(f"   - user_report长度: {len(user_report)} 字符")
                print(f"   - user_report前100字符: {user_report[:100]}...")

            # 获取输出文件信息
            output_file = task.output_path
            video_files = []

            if os.path.isdir(output_file):
                # 如果是目录，查找其中的视频文件
                for file in os.listdir(output_file):
                    if file.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                        video_files.append(file)

                # 按文件名排序，优先显示带字幕的版本
                video_files.sort(key=lambda x: (
                    '带字幕' not in x,  # 带字幕的优先
                    '智能剪辑' not in x,  # 智能剪辑的优先
                    x  # 按文件名排序
                ))
            elif os.path.isfile(output_file) and output_file.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                video_files.append(os.path.basename(output_file))

            # 构建文件列表信息
            if video_files:
                file_list = "\n".join([f"  📹 {file}" for file in video_files])
                file_info = f"📁 处理完成的视频文件 ({len(video_files)} 个):\n{file_list}"
            else:
                file_info = "📁 视频处理已完成"

            # 获取处理时间
            from datetime import datetime
            process_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 构建回复内容 - 如果有性能报告就使用，否则使用默认格式
            if user_report:
                # 使用生成的用户友好报告
                reply_content = user_report
            else:
                # 使用默认回复格式
                reply_content = f"""🎬 AI智能剪辑完成！

📝 原始视频: {original_filename}
🎯 处理结果: {len(video_files)} 个版本
⚡ 处理方式: AI智能剪辑 + 去气口 + 字幕生成

{file_info}

✨ 处理内容包括:
- 🔇 移除静音片段和气口声
- 🎤 语音识别和字幕生成
- 🎬 AI智能剪辑优化
- 📝 添加标题和字幕
- 🎨 视频质量优化

🕒 处理时间: {process_time}

---
🤖 AI剪辑助手 - 智能视频处理完成"""

            return reply_content

        except Exception as e:
            self.logger.error(f"构建回复内容失败: {e}")
            return f"""🎬 视频处理完成！

⚠️ 处理结果详情获取失败，但视频已成功处理。

---
🤖 AI剪辑助手"""

    def _get_upload_video_files(self, task: VideoTask) -> List[str]:
        """获取要上传的视频文件列表"""
        video_files = []

        try:
            output_path = task.output_path

            if os.path.isfile(output_path) and output_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                # 单个视频文件
                video_files.append(output_path)
            elif os.path.isdir(output_path):
                # 目录，递归查找其中的视频文件
                print(f"🔍 在输出目录中查找视频文件: {output_path}")

                # 递归遍历所有子目录
                for root, dirs, files in os.walk(output_path):
                    for file in files:
                        if file.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                            full_path = os.path.join(root, file)
                            video_files.append(full_path)
                            print(f"📹 找到视频文件: {os.path.relpath(full_path, output_path)}")

                # 按文件名排序，优先上传带字幕的版本
                video_files.sort(key=lambda x: (
                    '带字幕' not in os.path.basename(x),  # 带字幕的优先
                    '智能剪辑' not in os.path.basename(x),  # 智能剪辑的优先
                    os.path.basename(x)  # 按文件名排序
                ))

                # 限制上传文件数量（避免上传过多文件）
                video_files = video_files[:3]  # 最多上传3个文件

            # 准备所有找到的视频文件进行上传（不限制文件大小）
            filtered_files = []
            for video_file in video_files:
                if os.path.exists(video_file):
                    file_size = os.path.getsize(video_file) / (1024 * 1024)  # MB
                    filtered_files.append(video_file)
                    print(f"📁 准备上传: {os.path.basename(video_file)} ({file_size:.1f} MB)")

            if not filtered_files:
                print(f"⚠️ 在输出目录中未找到可上传的视频文件: {output_path}")
                # 列出目录内容以便调试
                if os.path.isdir(output_path):
                    print(f"📂 输出目录内容:")
                    for root, dirs, files in os.walk(output_path):
                        level = root.replace(output_path, '').count(os.sep)
                        indent = ' ' * 2 * level
                        print(f"{indent}{os.path.basename(root)}/")
                        subindent = ' ' * 2 * (level + 1)
                        for file in files:
                            print(f"{subindent}{file}")

            return filtered_files

        except Exception as e:
            print(f"❌ 获取上传文件失败: {e}")
            self.logger.error(f"获取上传文件失败: {e}")
            return []

    def _send_forum_reply_with_files(self, post_id: str, content: str, video_files: List[str] = None, task_id: str = None) -> bool:
        """发送带文件的论坛回复"""
        upload_start_time = time.time()
        try:
            # 导入论坛爬虫
            from aicut_forum_crawler import AicutForumCrawler

            # 创建论坛爬虫实例
            crawler = AicutForumCrawler()

            # 登录
            if not crawler.login():
                print("❌ 论坛登录失败")
                return False

            # 发送回复（支持文件上传）
            success = crawler.reply_to_thread(post_id, content, video_files)

            if success:
                upload_duration = time.time() - upload_start_time
                print(f"✅ 论坛回复发送成功: {post_id}")
                print(f"⏱️ 上传耗时: {upload_duration:.1f}秒")
                if video_files:
                    print(f"📁 成功上传 {len(video_files)} 个视频文件")
                    if task_id:
                        performance_tracker.record_upload_time(task_id, upload_duration)

                # 记录论坛回复时间
                if task_id:
                    performance_tracker.record_forum_reply_time(task_id, upload_duration)
                return True
            else:
                print(f"❌ 论坛回复发送失败: {post_id}")
                return False

        except Exception as e:
            print(f"❌ 发送论坛回复异常: {e}")
            self.logger.error(f"发送论坛回复失败: {e}")
            return False

    def _send_forum_reply(self, post_id: str, content: str) -> bool:
        """发送论坛回复"""
        try:
            # 集成论坛回复功能
            from .forum_integration import get_forum_reply_bot

            reply_bot = get_forum_reply_bot(self.config)
            success = reply_bot.send_reply(post_id, content)

            if success:
                print(f"✅ 论坛回复发送成功: {post_id}")
                return True
            else:
                print(f"❌ 论坛回复发送失败: {post_id}")
                return False

        except Exception as e:
            print(f"❌ 发送论坛回复异常: {e}")
            self.logger.error(f"发送论坛回复失败: {e}")
            return False
    
    def _cleanup_task_files(self, task: VideoTask):
        """清理任务文件"""
        try:
            # ⚠️ 重要：不删除源文件！源文件应该保留在input目录中
            # 只清理临时文件和失败的输出文件

            # 清理失败任务的输出目录（成功的任务保留输出）
            if task.status == TaskStatus.FAILED:
                output_dir = os.path.abspath(os.path.join(self.config.output_dir, task.task_id))
                if os.path.exists(output_dir):
                    self.logger.info(f"🗑️ 清理失败任务的输出目录: {output_dir}")
                    shutil.rmtree(output_dir)

            # 清理临时文件（如果有的话）
            temp_dir = os.path.join(self.config.temp_dir, task.task_id)
            if os.path.exists(temp_dir):
                self.logger.info(f"🗑️ 清理临时文件: {temp_dir}")
                shutil.rmtree(temp_dir)

            self.logger.info(f"✅ 任务文件清理完成: {task.task_id} (源文件已保留)")

        except Exception as e:
            self.logger.warning(f"清理任务文件失败 {task.task_id}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取处理器统计信息"""
        return {
            'download_active': self.download_executor._threads.__len__() if hasattr(self.download_executor, '_threads') else 0,
            'process_active': self.process_executor._threads.__len__() if hasattr(self.process_executor, '_threads') else 0,
            'upload_active': self.upload_executor._threads.__len__() if hasattr(self.upload_executor, '_threads') else 0,
            'running': self.running
        }
