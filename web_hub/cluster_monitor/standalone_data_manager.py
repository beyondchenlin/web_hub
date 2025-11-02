#!/usr/bin/env python3
"""
独立监控系统数据管理器
专为cluster_monitor设计的轻量级、无外部依赖的数据存储方案

特点：
1. 纯Python标准库实现，无需Redis/SQLite
2. 高性能内存存储 + 定期持久化
3. 自动数据清理和统计功能
4. 支持并发访问和故障恢复
"""

import os
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import logging


@dataclass
class PostRecord:
    """帖子记录"""
    post_id: str
    title: str
    author: str
    url: str
    discovered_time: datetime
    status: str = "discovered"  # discovered, dispatched, completed, failed
    machine_url: Optional[str] = None
    dispatch_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 处理datetime对象
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PostRecord':
        """从字典创建对象"""
        # 处理datetime字段
        datetime_fields = ['discovered_time', 'dispatch_time', 'completion_time']
        for field in datetime_fields:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])
        return cls(**data)


class StandaloneDataManager:
    """独立数据管理器"""
    
    def __init__(self, data_dir: str = "data", max_records: int = 10000):
        self.data_dir = data_dir
        self.max_records = max_records
        self.data_file = os.path.join(data_dir, "posts_data.json")
        self.stats_file = os.path.join(data_dir, "stats.json")
        
        # 确保数据目录存在
        os.makedirs(data_dir, exist_ok=True)
        
        # 内存存储
        self._posts: Dict[str, PostRecord] = {}
        self._processed_ids: set = set()  # 快速查找已处理的帖子ID
        self._stats = {
            'total_discovered': 0,
            'total_dispatched': 0,
            'total_completed': 0,
            'total_failed': 0,
            'start_time': datetime.now().isoformat(),
            'last_cleanup': datetime.now().isoformat()
        }
        
        # 线程锁
        self._lock = threading.RLock()
        
        # 自动保存配置
        self._auto_save_interval = 60  # 60秒自动保存一次
        self._last_save_time = time.time()
        
        # 日志
        self.logger = logging.getLogger(__name__)
        
        # 加载数据
        self._load_data()
        
        # 启动后台任务
        self._start_background_tasks()
        
        print(f"📊 独立数据管理器已初始化")
        print(f"   数据目录: {self.data_dir}")
        print(f"   已加载记录: {len(self._posts)}")
        print(f"   已处理帖子: {len(self._processed_ids)}")
    
    def _load_data(self):
        """加载数据"""
        try:
            # 加载帖子数据
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for post_data in data.get('posts', []):
                        post = PostRecord.from_dict(post_data)
                        self._posts[post.post_id] = post
                        if post.status in ['dispatched', 'completed']:
                            self._processed_ids.add(post.post_id)
                
                print(f"💾 加载了 {len(self._posts)} 个帖子记录")
            
            # 加载统计数据
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    saved_stats = json.load(f)
                    self._stats.update(saved_stats)
                
        except Exception as e:
            self.logger.error(f"加载数据失败: {e}")
    
    def _save_data(self):
        """保存数据"""
        try:
            with self._lock:
                # 保存帖子数据
                posts_data = {
                    'posts': [post.to_dict() for post in self._posts.values()],
                    'saved_at': datetime.now().isoformat()
                }
                
                with open(self.data_file, 'w', encoding='utf-8') as f:
                    json.dump(posts_data, f, ensure_ascii=False, indent=2)
                
                # 保存统计数据
                self._stats['last_save'] = datetime.now().isoformat()
                with open(self.stats_file, 'w', encoding='utf-8') as f:
                    json.dump(self._stats, f, ensure_ascii=False, indent=2)
                
                self._last_save_time = time.time()
                
        except Exception as e:
            self.logger.error(f"保存数据失败: {e}")
    
    def is_post_processed(self, post_id: str) -> bool:
        """检查帖子是否已被处理"""
        return post_id in self._processed_ids
    
    def add_post(self, post_id: str, title: str, author: str, url: str) -> bool:
        """添加新帖子"""
        try:
            with self._lock:
                if post_id in self._posts:
                    return False  # 已存在
                
                post = PostRecord(
                    post_id=post_id,
                    title=title,
                    author=author,
                    url=url,
                    discovered_time=datetime.now()
                )
                
                self._posts[post_id] = post
                self._stats['total_discovered'] += 1
                
                # 自动保存检查
                self._check_auto_save()
                
                return True
        except Exception as e:
            self.logger.error(f"添加帖子失败: {e}")
            return False
    
    def mark_post_dispatched(self, post_id: str, machine_url: str) -> bool:
        """标记帖子已分发"""
        try:
            with self._lock:
                if post_id not in self._posts:
                    return False
                
                post = self._posts[post_id]
                post.status = "dispatched"
                post.machine_url = machine_url
                post.dispatch_time = datetime.now()
                
                self._processed_ids.add(post_id)
                self._stats['total_dispatched'] += 1
                
                return True
        except Exception as e:
            self.logger.error(f"标记帖子分发失败: {e}")
            return False
    
    def mark_post_completed(self, post_id: str) -> bool:
        """标记帖子完成"""
        try:
            with self._lock:
                if post_id not in self._posts:
                    return False
                
                post = self._posts[post_id]
                post.status = "completed"
                post.completion_time = datetime.now()
                
                self._stats['total_completed'] += 1
                
                return True
        except Exception as e:
            self.logger.error(f"标记帖子完成失败: {e}")
            return False
    
    def mark_post_failed(self, post_id: str, error_message: str) -> bool:
        """标记帖子失败"""
        try:
            with self._lock:
                if post_id not in self._posts:
                    return False
                
                post = self._posts[post_id]
                post.status = "failed"
                post.error_message = error_message
                post.retry_count += 1
                
                self._stats['total_failed'] += 1
                
                return True
        except Exception as e:
            self.logger.error(f"标记帖子失败: {e}")
            return False
    
    def get_posts_by_status(self, status: str, limit: int = 100) -> List[PostRecord]:
        """按状态获取帖子"""
        try:
            with self._lock:
                posts = [post for post in self._posts.values() if post.status == status]
                # 按发现时间排序
                posts.sort(key=lambda x: x.discovered_time, reverse=True)
                return posts[:limit]
        except Exception as e:
            self.logger.error(f"查询帖子失败: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            with self._lock:
                # 计算实时统计
                status_counts = defaultdict(int)
                for post in self._posts.values():
                    status_counts[post.status] += 1
                
                # 计算运行时间
                start_time = datetime.fromisoformat(self._stats['start_time'])
                uptime_seconds = (datetime.now() - start_time).total_seconds()
                
                return {
                    'total_posts': len(self._posts),
                    'processed_posts': len(self._processed_ids),
                    'status_counts': dict(status_counts),
                    'uptime_seconds': int(uptime_seconds),
                    'memory_usage_mb': self._estimate_memory_usage(),
                    'last_save': self._stats.get('last_save', 'Never'),
                    **self._stats
                }
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def _estimate_memory_usage(self) -> float:
        """估算内存使用量（MB）"""
        try:
            import sys
            total_size = 0
            total_size += sys.getsizeof(self._posts)
            total_size += sys.getsizeof(self._processed_ids)
            for post in self._posts.values():
                total_size += sys.getsizeof(post)
            return round(total_size / 1024 / 1024, 2)
        except:
            return 0.0
    
    def _check_auto_save(self):
        """检查是否需要自动保存"""
        if time.time() - self._last_save_time > self._auto_save_interval:
            self._save_data()
    
    def _start_background_tasks(self):
        """启动后台任务"""
        def background_worker():
            while True:
                try:
                    time.sleep(300)  # 5分钟执行一次
                    self._cleanup_old_records()
                    self._save_data()
                except Exception as e:
                    self.logger.error(f"后台任务异常: {e}")
        
        thread = threading.Thread(target=background_worker, daemon=True)
        thread.start()
    
    def _cleanup_old_records(self):
        """清理旧记录"""
        try:
            with self._lock:
                if len(self._posts) <= self.max_records:
                    return
                
                # 按时间排序，保留最新的记录
                posts_by_time = sorted(
                    self._posts.values(),
                    key=lambda x: x.discovered_time,
                    reverse=True
                )
                
                # 保留最新的记录
                posts_to_keep = posts_by_time[:self.max_records]
                new_posts = {post.post_id: post for post in posts_to_keep}
                
                # 更新内存数据
                removed_count = len(self._posts) - len(new_posts)
                self._posts = new_posts
                
                # 重建已处理ID集合
                self._processed_ids = {
                    post.post_id for post in new_posts.values()
                    if post.status in ['dispatched', 'completed']
                }
                
                self._stats['last_cleanup'] = datetime.now().isoformat()
                
                if removed_count > 0:
                    print(f"🧹 清理了 {removed_count} 个旧记录")
                
        except Exception as e:
            self.logger.error(f"清理旧记录失败: {e}")
    
    def force_save(self):
        """强制保存数据"""
        self._save_data()
    
    def close(self):
        """关闭数据管理器"""
        self._save_data()
        print("💾 数据已保存，管理器已关闭")


# 全局实例
_data_manager = None


def get_standalone_data_manager() -> StandaloneDataManager:
    """获取独立数据管理器单例"""
    global _data_manager
    if _data_manager is None:
        _data_manager = StandaloneDataManager()
    return _data_manager


if __name__ == "__main__":
    # 测试代码
    print("🧪 测试独立数据管理器...")
    
    manager = StandaloneDataManager("test_data")
    
    # 测试添加帖子
    manager.add_post("test_001", "测试帖子1", "用户1", "http://example.com/1")
    manager.add_post("test_002", "测试帖子2", "用户2", "http://example.com/2")
    
    # 测试标记状态
    manager.mark_post_dispatched("test_001", "http://localhost:8003")
    manager.mark_post_completed("test_001")
    
    # 测试查询
    print(f"已处理: {manager.is_post_processed('test_001')}")
    print(f"未处理: {manager.is_post_processed('test_002')}")
    
    # 测试统计
    stats = manager.get_statistics()
    print(f"统计信息: {stats}")
    
    manager.close()
    print("🎉 测试完成")
