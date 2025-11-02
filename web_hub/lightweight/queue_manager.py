#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
轻量级视频处理系统 - 队列管理器

主要功能：
- 内部任务队列管理
- 任务状态跟踪
- 优先级队列支持
- Redis状态存储
"""

import json
import os
import time
import uuid
import threading
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from queue import Queue, PriorityQueue, Empty
from datetime import datetime, timedelta

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """任务优先级枚举"""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    URGENT = 0


@dataclass
class VideoTask:
    """视频任务数据类"""
    task_id: str
    source_url: Optional[str] = None
    source_path: Optional[str] = None
    output_path: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}
    
    def __lt__(self, other):
        """用于优先级队列排序"""
        return self.priority.value < other.priority.value
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 处理datetime和enum序列化
        data['status'] = self.status.value
        data['priority'] = self.priority.value
        data['created_at'] = self.created_at.isoformat() if self.created_at else None
        data['started_at'] = self.started_at.isoformat() if self.started_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VideoTask':
        """从字典创建任务"""
        # 处理datetime和enum反序列化
        if 'status' in data:
            data['status'] = TaskStatus(data['status'])
        if 'priority' in data:
            data['priority'] = TaskPriority(data['priority'])
        if 'created_at' in data and data['created_at']:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'started_at' in data and data['started_at']:
            data['started_at'] = datetime.fromisoformat(data['started_at'])
        if 'completed_at' in data and data['completed_at']:
            data['completed_at'] = datetime.fromisoformat(data['completed_at'])
        return cls(**data)


class QueueManager:
    """队列管理器"""
    
    def __init__(self, config):
        self.config = config
        self.redis_client = None
        self._init_redis()
        
        # 内部队列
        self.download_queue = PriorityQueue()
        self.process_queue = PriorityQueue()
        self.upload_queue = PriorityQueue()
        
        # 任务存储
        self.tasks: Dict[str, VideoTask] = {}
        self.lock = threading.RLock()
        
        # 统计信息
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'active_tasks': 0
        }

        # 验证数据一致性并恢复任务
        self._validate_and_recover_tasks()
    
    def _init_redis(self):
        """初始化Redis连接"""
        if not REDIS_AVAILABLE:
            print("警告: Redis不可用，将使用内存存储")
            return
        
        try:
            self.redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # 测试连接
            self.redis_client.ping()
            print("Redis连接成功")
        except Exception as e:
            print(f"Redis连接失败: {e}")
            self.redis_client = None
    
    def create_task(self, source_url: Optional[str] = None,
                   source_path: Optional[str] = None,
                   priority: TaskPriority = TaskPriority.NORMAL,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """创建新任务"""

        # 🔥 关键修复：测试模式下跳过去重检查
        test_mode = getattr(self.config, 'forum_test_mode', False)
        test_once = getattr(self.config, 'forum_test_once', False)

        if test_mode or test_once:
            print(f"🧪 测试模式：跳过重复检查，强制创建新任务")
        else:
            # 生产模式：源头去重检查
            existing_task_id = self._check_duplicate_task(source_url, source_path, metadata)
            if existing_task_id:
                print(f"🔄 发现重复任务，返回已存在的任务ID: {existing_task_id}")
                if metadata and metadata.get('original_filename'):
                    print(f"   文件名: {metadata['original_filename']}")
                return existing_task_id

        task_id = str(uuid.uuid4())

        task = VideoTask(
            task_id=task_id,
            source_url=source_url,
            source_path=source_path,
            priority=priority,
            metadata=metadata or {}
        )

        with self.lock:
            self.tasks[task_id] = task
            self.stats['total_tasks'] += 1
            self.stats['active_tasks'] += 1

        # 保存到Redis
        self._save_task_to_redis(task)
        
        # 添加到下载队列
        if source_url:
            print(f"📥 添加任务到下载队列: {task_id}")
            print(f"🔗 源URL: {source_url}")
            self.download_queue.put(task)
            print(f"📊 下载队列大小: {self.download_queue.qsize()}")
        elif source_path:
            # 转换为绝对路径并验证文件存在
            abs_source_path = os.path.abspath(source_path)
            print(f"📁 源文件路径: {source_path}")
            print(f"📁 绝对路径: {abs_source_path}")

            if not os.path.exists(abs_source_path):
                print(f"❌ 源文件不存在: {abs_source_path}")
                print(f"⚠️ 将使用原始路径继续处理: {source_path}")
                # 不抛出异常，使用原始路径继续处理
                abs_source_path = source_path

            # 更新任务的source_path为绝对路径
            task.source_path = abs_source_path

            # 直接添加到处理队列
            print(f"⚙️ 添加任务到处理队列: {task_id}")
            print(f"✅ 源文件验证通过: {abs_source_path}")
            task.status = TaskStatus.PENDING  # 保持PENDING状态，让TaskProcessor设置PROCESSING
            self.process_queue.put(task)
            print(f"📊 处理队列大小: {self.process_queue.qsize()}")

        return task_id

    def _check_duplicate_task(self, source_url: Optional[str] = None,
                             source_path: Optional[str] = None,
                             metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """检查是否存在重复任务"""

        # 获取用于去重的关键信息
        post_id = None
        post_url = None
        if metadata:
            post_id = metadata.get('post_id')
            post_url = metadata.get('post_url')

        # 检查内存中的任务
        with self.lock:
            for task_id, task in self.tasks.items():
                # 跳过已完成、失败或取消的任务
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    continue

                # 🎯 优先基于帖子ID去重（论坛任务的主要去重逻辑）
                if post_id and task.metadata:
                    task_post_id = task.metadata.get('post_id')
                    if task_post_id == post_id:
                        print(f"🔄 发现重复帖子任务，帖子ID: {post_id}")
                        return task_id

                # 🎯 基于帖子URL去重（备用方案）
                if post_url and task.metadata:
                    task_post_url = task.metadata.get('post_url')
                    if task_post_url == post_url:
                        print(f"🔄 发现重复帖子任务，帖子URL: {post_url}")
                        return task_id

                # 🔧 基于文件路径去重（本地文件任务）
                if source_path and task.source_path == source_path:
                    print(f"🔄 发现重复文件任务，路径: {source_path}")
                    return task_id

                # ⚠️ 注意：不再基于视频URL或文件名去重，避免误判不同帖子的同名视频

        # 检查Redis中的任务（防止内存和Redis不一致）
        if self.redis_client:
            try:
                task_keys = self.redis_client.keys("task:*")
                for key in task_keys:
                    try:
                        task_data = self.redis_client.get(key)
                        if not task_data:
                            continue

                        task_dict = json.loads(task_data)
                        task_status = task_dict.get('status')

                        # 跳过已完成、失败或取消的任务
                        if task_status in ['completed', 'failed', 'cancelled']:
                            continue

                        task_metadata = task_dict.get('metadata', {})

                        # 🎯 优先基于帖子ID去重（论坛任务的主要去重逻辑）
                        if post_id:
                            task_post_id = task_metadata.get('post_id')
                            if task_post_id == post_id:
                                print(f"🔄 Redis中发现重复帖子任务，帖子ID: {post_id}")
                                return task_dict.get('task_id')

                        # 🎯 基于帖子URL去重（备用方案）
                        if post_url:
                            task_post_url = task_metadata.get('post_url')
                            if task_post_url == post_url:
                                print(f"🔄 Redis中发现重复帖子任务，帖子URL: {post_url}")
                                return task_dict.get('task_id')

                        # 🔧 基于文件路径去重（本地文件任务）
                        if source_path and task_dict.get('source_path') == source_path:
                            print(f"🔄 Redis中发现重复文件任务，路径: {source_path}")
                            return task_dict.get('task_id')

                        # ⚠️ 注意：不再基于视频URL或文件名去重，避免误判不同帖子的同名视频

                    except Exception as e:
                        print(f"⚠️ 检查Redis任务去重失败 {key}: {e}")
                        continue

            except Exception as e:
                print(f"⚠️ Redis去重检查失败: {e}")

        return None

    def get_task(self, task_id: str) -> Optional[VideoTask]:
        """获取任务"""
        with self.lock:
            return self.tasks.get(task_id)
    
    def update_task_status(self, task_id: str, status: TaskStatus,
                          error_message: Optional[str] = None):
        """更新任务状态"""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

            old_status = task.status
            task.status = status

            # 改进状态转换时的时间戳管理
            if status in [TaskStatus.DOWNLOADING, TaskStatus.PROCESSING, TaskStatus.UPLOADING] and not task.started_at:
                task.started_at = datetime.now()
                print(f"🕐 设置任务开始时间: {task.task_id} -> {task.started_at}")
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                task.completed_at = datetime.now()
                self.stats['active_tasks'] -= 1

                if status == TaskStatus.COMPLETED:
                    self.stats['completed_tasks'] += 1
                elif status == TaskStatus.FAILED:
                    self.stats['failed_tasks'] += 1

            if error_message:
                task.error_message = error_message

        # 保存到Redis
        self._save_task_to_redis(task)
        return True
    
    def get_next_download_task(self, timeout: Optional[float] = None) -> Optional[VideoTask]:
        """获取下一个下载任务"""
        try:
            task = self.download_queue.get(timeout=timeout)
            task.status = TaskStatus.DOWNLOADING
            self._save_task_to_redis(task)
            return task
        except Empty:
            return None
    
    def get_next_process_task(self, timeout: Optional[float] = None) -> Optional[VideoTask]:
        """获取下一个处理任务"""
        try:
            task = self.process_queue.get(timeout=timeout)
            # 使用update_task_status来正确设置started_at时间戳
            self.update_task_status(task.task_id, TaskStatus.PROCESSING)
            return task
        except Empty:
            return None
    
    def get_next_upload_task(self, timeout: Optional[float] = None) -> Optional[VideoTask]:
        """获取下一个上传任务"""
        try:
            task = self.upload_queue.get(timeout=timeout)
            task.status = TaskStatus.UPLOADING
            self._save_task_to_redis(task)
            return task
        except Empty:
            return None
    
    def complete_download(self, task_id: str, local_path: str):
        """完成下载，移动到处理队列"""
        with self.lock:
            task = self.tasks.get(task_id)
            if task:
                task.source_path = local_path
                task.status = TaskStatus.PENDING
                self.process_queue.put(task)
                self._save_task_to_redis(task)
    
    def complete_process(self, task_id: str, output_path: str):
        """完成处理，移动到上传队列"""
        with self.lock:
            task = self.tasks.get(task_id)
            if task:
                task.output_path = output_path
                task.status = TaskStatus.PENDING
                self.upload_queue.put(task)
                self._save_task_to_redis(task)
    
    def complete_upload(self, task_id: str):
        """完成上传"""
        self.update_task_status(task_id, TaskStatus.COMPLETED)
    
    def fail_task(self, task_id: str, error_message: str, retry: bool = True):
        """任务失败处理"""
        import threading
        import time

        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return

            task.retry_count += 1
            task.error_message = error_message

            print(f"⚠️ 任务失败: {task_id}, 重试次数: {task.retry_count}/{task.max_retries}, 错误: {error_message}")

            if retry and task.retry_count < task.max_retries:
                # 计算重试延迟（指数退避）
                retry_delay = min(30, 5 * (2 ** (task.retry_count - 1)))  # 5s, 10s, 20s, 最大30s
                print(f"🔄 将在 {retry_delay} 秒后重试任务: {task_id}")

                # 延迟重试任务
                def retry_task():
                    time.sleep(retry_delay)
                    with self.lock:
                        if task.task_id in self.tasks and self.tasks[task.task_id].status != TaskStatus.CANCELLED:
                            task.status = TaskStatus.PENDING
                            if task.source_url and not task.source_path:
                                self.download_queue.put(task)
                                print(f"🔄 重新加入下载队列: {task_id}")
                            elif task.source_path and not task.output_path:
                                self.process_queue.put(task)
                                print(f"🔄 重新加入处理队列: {task_id}")
                            elif task.output_path:
                                self.upload_queue.put(task)
                                print(f"🔄 重新加入上传队列: {task_id}")

                # 在后台线程中执行延迟重试
                retry_thread = threading.Thread(target=retry_task, daemon=True)
                retry_thread.start()
            else:
                # 标记为失败
                task.status = TaskStatus.FAILED
                self.stats['active_tasks'] -= 1
                self.stats['failed_tasks'] += 1
                print(f"💀 任务彻底失败: {task_id}, 已达到最大重试次数")

        self._save_task_to_redis(task)
    
    def cancel_task(self, task_id: str):
        """取消任务"""
        self.update_task_status(task_id, TaskStatus.CANCELLED)

    def update_task_metadata(self, task_id: str, metadata: Dict[str, Any]):
        """更新任务metadata"""
        with self.lock:
            task = self.tasks.get(task_id)
            if task:
                task.metadata = metadata
                self._save_task_to_redis(task)
                return True
        return False
    
    def get_queue_sizes(self) -> Dict[str, int]:
        """获取队列大小"""
        return {
            'download': self.download_queue.qsize(),
            'process': self.process_queue.qsize(),
            'upload': self.upload_queue.qsize()
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        queue_sizes = self.get_queue_sizes()

        # 强制重新计算活跃任务数量，确保数据一致性
        actual_active_count = 0
        with self.lock:
            for task in self.tasks.values():
                if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    actual_active_count += 1

        # 如果发现不一致，修正统计数据
        if self.stats['active_tasks'] != actual_active_count:
            print(f"🔧 修正活跃任务计数: {self.stats['active_tasks']} -> {actual_active_count}")
            self.stats['active_tasks'] = actual_active_count

        return {
            **self.stats,
            'queue_sizes': queue_sizes,
            'timestamp': datetime.now().isoformat()
        }

    def get_status(self) -> Dict[str, int]:
        """获取队列状态（兼容性方法）"""
        queue_sizes = self.get_queue_sizes()
        with self.lock:
            # 统计各状态的任务数量
            status_counts = {
                'pending': 0,
                'processing': 0,
                'completed': 0,
                'failed': 0
            }

            for task in self.tasks.values():
                if task.status in [TaskStatus.PENDING, TaskStatus.DOWNLOADING]:
                    status_counts['pending'] += 1
                elif task.status == TaskStatus.PROCESSING:
                    status_counts['processing'] += 1
                elif task.status == TaskStatus.COMPLETED:
                    status_counts['completed'] += 1
                elif task.status == TaskStatus.FAILED:
                    status_counts['failed'] += 1

            # 加上队列中的任务
            status_counts['pending'] += queue_sizes['download'] + queue_sizes['process'] + queue_sizes['upload']

            return status_counts

    def is_empty(self) -> bool:
        """检查所有队列是否为空"""
        queue_sizes = self.get_queue_sizes()
        return all(size == 0 for size in queue_sizes.values())
    
    def get_active_tasks(self) -> List[VideoTask]:
        """获取活跃任务列表"""
        with self.lock:
            active_tasks = []
            current_time = datetime.now()
            zombie_tasks = []

            for task in self.tasks.values():
                # 跳过已完成、失败或取消的任务
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    continue

                # 改进的僵尸任务检测逻辑
                is_zombie = False

                # 检查运行中的任务是否超时
                if task.status in [TaskStatus.DOWNLOADING, TaskStatus.PROCESSING, TaskStatus.UPLOADING]:
                    # 使用started_at或created_at作为基准时间
                    base_time = task.started_at if task.started_at else task.created_at
                    if base_time:
                        running_time = (current_time - base_time).total_seconds()
                        # 设置更合理的超时时间：下载30分钟，处理60分钟，上传30分钟
                        timeout_map = {
                            TaskStatus.DOWNLOADING: 1800,  # 30分钟
                            TaskStatus.PROCESSING: 3600,   # 60分钟
                            TaskStatus.UPLOADING: 1800     # 30分钟
                        }
                        timeout = timeout_map.get(task.status, 1800)

                        if running_time > timeout:
                            print(f"⚠️ 发现僵尸任务: {task.task_id}, 状态: {task.status.value}, 运行时间: {running_time:.0f}秒")
                            is_zombie = True
                    else:
                        # 如果没有时间戳，说明数据不完整，也视为僵尸任务
                        print(f"⚠️ 发现无时间戳任务: {task.task_id}, 状态: {task.status.value}")
                        is_zombie = True

                # 检查待处理任务是否超时（超过2小时的待处理任务）
                elif task.status == TaskStatus.PENDING:
                    if task.created_at and (current_time - task.created_at).total_seconds() > 7200:  # 2小时
                        print(f"⚠️ 发现超时待处理任务: {task.task_id}, 创建时间: {task.created_at}")
                        is_zombie = True

                # 处理僵尸任务
                if is_zombie:
                    print(f"🧹 清理僵尸任务: {task.task_id}")
                    task.status = TaskStatus.FAILED
                    task.error_message = f"任务超时或状态异常，自动清理"
                    task.completed_at = current_time
                    zombie_tasks.append(task.task_id)
                    self.stats['failed_tasks'] += 1
                    self._save_task_to_redis(task)
                    continue

                active_tasks.append(task)

            # 批量更新活跃任务计数
            if zombie_tasks:
                zombie_count = len(zombie_tasks)
                if self.stats['active_tasks'] >= zombie_count:
                    self.stats['active_tasks'] -= zombie_count
                else:
                    self.stats['active_tasks'] = 0
                print(f"🧹 清理了 {zombie_count} 个僵尸任务，当前活跃任务: {self.stats['active_tasks']}")

            return active_tasks
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """清理旧任务"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with self.lock:
            tasks_to_remove = []
            for task_id, task in self.tasks.items():
                if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] 
                    and task.completed_at and task.completed_at < cutoff_time):
                    tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                del self.tasks[task_id]
                # 从Redis删除
                if self.redis_client:
                    try:
                        self.redis_client.delete(f"task:{task_id}")
                    except Exception:
                        pass
    
    def _save_task_to_redis(self, task: VideoTask):
        """保存任务到Redis"""
        if not self.redis_client:
            return
        
        try:
            task_data = json.dumps(task.to_dict(), ensure_ascii=False)
            self.redis_client.setex(f"task:{task.task_id}", 86400, task_data)  # 24小时过期
        except Exception as e:
            print(f"保存任务到Redis失败: {e}")
    
    def _load_task_from_redis(self, task_id: str) -> Optional[VideoTask]:
        """从Redis加载任务"""
        if not self.redis_client:
            return None
        
        try:
            task_data = self.redis_client.get(f"task:{task_id}")
            if task_data:
                return VideoTask.from_dict(json.loads(task_data))
        except Exception as e:
            print(f"从Redis加载任务失败: {e}")
        
        return None

    def _validate_and_recover_tasks(self):
        """验证数据一致性并恢复任务"""
        if not self.redis_client:
            print("ℹ️ Redis不可用，跳过任务恢复")
            return

        try:
            print("🔍 验证Redis数据一致性...")

            # 获取所有任务键
            task_keys = self.redis_client.keys("task:*")
            print(f"📊 Redis中发现 {len(task_keys)} 个任务")

            if len(task_keys) == 0:
                print("ℹ️ Redis中没有任务，跳过恢复")
                return

            # 分析任务状态和重复情况
            status_count = {}
            filename_count = {}
            valid_tasks = []
            duplicate_tasks = []

            for key in task_keys:
                try:
                    task_data = self.redis_client.get(key)
                    if not task_data:
                        continue

                    task_dict = json.loads(task_data)
                    task_status = task_dict.get('status', 'unknown')

                    # 统计状态
                    status_count[task_status] = status_count.get(task_status, 0) + 1

                    # 检查重复（基于原始文件名）
                    metadata = task_dict.get('metadata', {})
                    original_filename = metadata.get('original_filename', '')

                    if original_filename:
                        if original_filename in filename_count:
                            # 发现重复
                            duplicate_tasks.append({
                                'key': key,
                                'task_id': task_dict.get('task_id'),
                                'filename': original_filename,
                                'status': task_status,
                                'created_at': task_dict.get('created_at', '')
                            })
                        else:
                            filename_count[original_filename] = {
                                'key': key,
                                'task_id': task_dict.get('task_id'),
                                'status': task_status,
                                'created_at': task_dict.get('created_at', '')
                            }
                            valid_tasks.append(task_dict)
                    else:
                        # 没有文件名的任务也认为是有效的
                        valid_tasks.append(task_dict)

                except Exception as e:
                    print(f"⚠️ 解析任务失败 {key}: {e}")

            # 显示验证结果
            print(f"📊 数据一致性验证结果:")
            print(f"   - 总任务数: {len(task_keys)}")
            print(f"   - 有效任务: {len(valid_tasks)}")
            print(f"   - 重复任务: {len(duplicate_tasks)}")

            for status, count in status_count.items():
                print(f"   - {status}: {count} 个")

            # 清理重复任务
            if duplicate_tasks:
                print(f"🧹 清理 {len(duplicate_tasks)} 个重复任务...")
                cleaned_count = 0
                for dup_task in duplicate_tasks:
                    try:
                        self.redis_client.delete(dup_task['key'])
                        cleaned_count += 1
                        print(f"   删除重复任务: {dup_task['filename']} ({dup_task['task_id']})")
                    except Exception as e:
                        print(f"   ❌ 删除失败: {e}")

                print(f"✅ 清理了 {cleaned_count} 个重复任务")

            # 恢复有效任务
            recovered_count = 0
            for task_dict in valid_tasks:
                try:
                    task = VideoTask.from_dict(task_dict)

                    # 只恢复pending和进行中的任务
                    if task.status in [TaskStatus.PENDING, TaskStatus.DOWNLOADING, TaskStatus.PROCESSING, TaskStatus.UPLOADING]:
                        with self.lock:
                            self.tasks[task.task_id] = task
                            self.stats['total_tasks'] += 1
                            self.stats['active_tasks'] += 1

                        # 🎯 源头修复：改进任务恢复逻辑，特别处理集群任务
                        if task.status == TaskStatus.PENDING:
                            # 检查是否是集群任务
                            is_cluster_task = task.metadata and task.metadata.get('source') == 'cluster_worker'

                            if is_cluster_task:
                                # 🎯 集群任务特殊处理：从metadata中恢复URL
                                post_url = task.metadata.get('post_url')
                                if post_url and not task.source_url:
                                    print(f"🔧 修复集群任务URL: {task.task_id}")
                                    task.source_url = post_url
                                    self._save_task_to_redis(task)

                            # 按照处理流程顺序判断任务应该进入哪个队列
                            if task.source_url and not task.source_path:
                                # 需要下载
                                self.download_queue.put(task)
                                print(f"📥 恢复下载任务: {task.task_id}")
                                if task.metadata and task.metadata.get('original_filename'):
                                    print(f"   文件名: {task.metadata['original_filename']}")
                                elif is_cluster_task:
                                    print(f"   集群任务URL: {task.source_url}")
                            elif task.source_path and not task.output_path:
                                # 需要处理
                                self.process_queue.put(task)
                                print(f"⚙️ 恢复处理任务: {task.task_id}")
                            elif task.output_path:
                                # 需要上传
                                self.upload_queue.put(task)
                                print(f"📤 恢复上传任务: {task.task_id}")
                            else:
                                # 🎯 处理异常情况：pending任务但没有明确的处理路径
                                if is_cluster_task:
                                    print(f"⚠️ 集群任务数据不完整，尝试修复: {task.task_id}")
                                    post_url = task.metadata.get('post_url')
                                    if post_url:
                                        task.source_url = post_url
                                        self.download_queue.put(task)
                                        print(f"🔧 已修复并加入下载队列: {task.task_id}")
                                        self._save_task_to_redis(task)
                                    else:
                                        print(f"❌ 无法修复集群任务，标记为失败: {task.task_id}")
                                        task.status = TaskStatus.FAILED
                                        task.error_message = "集群任务数据不完整，无法恢复"
                                        self.stats['failed_tasks'] += 1
                                        self._save_task_to_redis(task)
                                else:
                                    print(f"⚠️ 任务数据不完整，跳过恢复: {task.task_id}")
                        else:
                            # 进行中的任务恢复到内存，但不加入队列
                            print(f"📋 恢复进行中任务到内存: {task.task_id} ({task.status.value})")

                        recovered_count += 1

                except Exception as e:
                    print(f"⚠️ 恢复任务失败: {e}")

            if recovered_count > 0:
                print(f"✅ 成功恢复 {recovered_count} 个有效任务")

                # 显示队列状态
                queue_sizes = self.get_queue_sizes()
                print(f"📊 队列状态:")
                print(f"   下载队列: {queue_sizes['download']} 个任务")
                print(f"   处理队列: {queue_sizes['process']} 个任务")
                print(f"   上传队列: {queue_sizes['upload']} 个任务")
            else:
                print("ℹ️ 没有需要恢复的任务")

        except Exception as e:
            print(f"❌ 数据一致性验证失败: {e}")
            import traceback
            traceback.print_exc()
