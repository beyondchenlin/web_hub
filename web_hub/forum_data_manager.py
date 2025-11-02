#!/usr/bin/env python3
"""
混合数据管理器 - SQLite + Redis 混合存储管理
支持论坛帖子数据的持久化存储和高速缓存

主要功能:
1. SQLite持久化存储 - 数据安全保障
2. Redis高速缓存 - 提升访问性能
3. 自动数据同步 - 保证数据一致性
4. 故障恢复机制 - Redis不可用时降级到SQLite
"""

import os
import sys
import json
import sqlite3
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入版本管理配置
from database_version import get_current_version, get_required_columns

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️ Redis不可用，将使用纯SQLite模式")


@dataclass
class ForumPost:
    """论坛帖子数据模型"""
    post_id: str
    thread_id: str
    forum_id: int = 2
    title: str = ""
    content: str = ""
    author_id: str = ""
    author_name: str = ""
    cover_title_up: str = ""
    cover_title_middle: str = ""
    cover_title_down: str = ""
    cover_info_raw: str = ""
    video_urls: List[str] = None
    audio_urls: List[str] = None
    original_filenames: List[str] = None  # 新增：存储原始文件名
    media_count: int = 0
    processing_status: str = "pending"
    task_id: str = ""
    output_path: str = ""
    reply_status: str = "pending"
    reply_content: str = ""
    reply_time: Optional[datetime] = None
    post_time: Optional[datetime] = None
    discovered_time: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    source_url: str = ""
    is_processed: bool = False
    is_replied: bool = False
    priority: int = 1

    def __post_init__(self):
        if self.video_urls is None:
            self.video_urls = []
        if self.audio_urls is None:
            self.audio_urls = []
        if self.original_filenames is None:
            self.original_filenames = []
        if self.metadata is None:
            self.metadata = {}
        if self.discovered_time is None:
            self.discovered_time = datetime.now()
        if self.last_updated is None:
            self.last_updated = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        # 处理datetime对象
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        # 处理列表和字典
        data['video_urls'] = json.dumps(self.video_urls)
        data['audio_urls'] = json.dumps(self.audio_urls)
        data['original_filenames'] = json.dumps(self.original_filenames or [])
        data['metadata'] = json.dumps(self.metadata)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ForumPost':
        """从字典创建实例"""
        # 创建数据副本以避免修改原始数据
        data = dict(data)

        # 确保封面标题字段存在且不为None
        if 'cover_title_up' not in data:
            data['cover_title_up'] = ''
        if 'cover_title_middle' not in data:
            data['cover_title_middle'] = ''
        if 'cover_title_down' not in data:
            data['cover_title_down'] = ''

        # 处理datetime字段
        datetime_fields = ['reply_time', 'post_time', 'discovered_time', 'last_updated']
        for field in datetime_fields:
            if data.get(field) and isinstance(data[field], str):
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except ValueError:
                    data[field] = None

        # 处理JSON字段
        if isinstance(data.get('video_urls'), str):
            data['video_urls'] = json.loads(data['video_urls'])
        if isinstance(data.get('audio_urls'), str):
            data['audio_urls'] = json.loads(data['audio_urls'])
        if isinstance(data.get('original_filenames'), str):
            data['original_filenames'] = json.loads(data['original_filenames'])
        if isinstance(data.get('metadata'), str):
            data['metadata'] = json.loads(data['metadata'])

        return cls(**data)


class HybridForumDataManager:
    """混合论坛数据管理器"""

    # 数据库版本 - 从统一配置获取
    DATABASE_VERSION = get_current_version()

    def __init__(self, db_path: str = "data/forum_posts.db",
                 redis_host: str = "localhost", redis_port: int = 6379, redis_db: int = 1):
        self.db_path = db_path
        self.redis_config = {
            'host': redis_host,
            'port': redis_port,
            'db': redis_db,
            'decode_responses': True
        }
        
        # 初始化日志
        self.logger = logging.getLogger(__name__)
        
        # 线程锁
        self._lock = threading.RLock()
        
        # 初始化存储
        self._init_sqlite()
        self._init_redis()
        
        print(f"📊 混合数据管理器已初始化")
        print(f"   SQLite: {self.db_path}")
        print(f"   Redis: {'可用' if self.redis_client else '不可用'}")

    def _init_sqlite(self):
        """初始化SQLite数据库 - 工业级简洁方案"""
        try:
            # 确保数据目录存在
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

            # 检查是否缺少关键字段
            if self._missing_required_columns():
                self.logger.info("检测到数据库结构不完整，重新初始化")
                # 简单粗暴：删除旧数据库，重新创建
                if os.path.exists(self.db_path):
                    backup_path = f"{self.db_path}.backup"
                    os.rename(self.db_path, backup_path)
                    self.logger.info(f"已备份旧数据库到: {backup_path}")

            # 执行SQL脚本创建表结构
            sql_script_path = "forum_posts.sql"
            if os.path.exists(sql_script_path):
                with open(sql_script_path, 'r', encoding='utf-8') as f:
                    sql_script = f.read()

                with self._get_db_connection() as conn:
                    conn.executescript(sql_script)
                    conn.commit()

                self.logger.info("SQLite数据库初始化成功")
            else:
                self.logger.warning(f"SQL脚本文件不存在: {sql_script_path}")

        except Exception as e:
            self.logger.error(f"SQLite初始化失败: {e}")
            raise

    def _missing_required_columns(self):
        """检查是否缺少必需的列或版本不匹配"""
        if not os.path.exists(self.db_path):
            return False

        try:
            with self._get_db_connection() as conn:
                # 检查关键字段
                cursor = conn.execute('PRAGMA table_info(forum_posts)')
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]

                if 'cover_title_middle' not in column_names:
                    self.logger.info("缺少cover_title_middle字段")
                    return True

                # 检查版本
                try:
                    cursor = conn.execute(
                        "SELECT config_value FROM system_config WHERE config_key = 'database_version'"
                    )
                    result = cursor.fetchone()
                    current_version = result[0] if result else "1.0"

                    if current_version != self.DATABASE_VERSION:
                        self.logger.info(f"数据库版本不匹配: {current_version} != {self.DATABASE_VERSION}")
                        return True

                except:
                    # system_config表不存在或查询失败
                    self.logger.info("无法检查数据库版本，需要重建")
                    return True

                return False

        except:
            return True  # 如果检查失败，假设需要重建



    def _init_redis(self):
        """初始化Redis连接"""
        self.redis_client = None
        if not REDIS_AVAILABLE:
            return
        
        try:
            self.redis_client = redis.Redis(**self.redis_config)
            # 测试连接
            self.redis_client.ping()
            self.logger.info("Redis连接成功")
        except Exception as e:
            self.logger.warning(f"Redis连接失败，将使用纯SQLite模式: {e}")
            self.redis_client = None

    @contextmanager
    def _get_db_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
        try:
            yield conn
        finally:
            conn.close()

    def _get_cache_key(self, post_id: str) -> str:
        """生成Redis缓存键"""
        return f"forum_post:{post_id}"

    def save_post(self, post: ForumPost) -> bool:
        """保存论坛帖子"""
        try:
            with self._lock:
                # 保存到SQLite
                success = self._save_to_sqlite(post)
                if success:
                    # 更新Redis缓存
                    self._update_cache(post)
                    self.logger.info(f"帖子保存成功: {post.post_id}")
                    return True
                return False
        except Exception as e:
            self.logger.error(f"保存帖子失败: {e}")
            return False

    def _save_to_sqlite(self, post: ForumPost) -> bool:
        """保存到SQLite数据库"""
        try:
            post_data = post.to_dict()
            
            # 构建SQL语句
            columns = list(post_data.keys())
            placeholders = ['?' for _ in columns]
            values = list(post_data.values())
            
            sql = f"""
            INSERT OR REPLACE INTO forum_posts ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            """
            
            with self._get_db_connection() as conn:
                conn.execute(sql, values)
                conn.commit()
            
            return True
        except Exception as e:
            self.logger.error(f"SQLite保存失败: {e}")
            return False

    def _update_cache(self, post: ForumPost):
        """更新Redis缓存"""
        if not self.redis_client:
            return
        
        try:
            cache_key = self._get_cache_key(post.post_id)
            post_json = json.dumps(post.to_dict(), ensure_ascii=False)
            
            # 设置缓存，过期时间1小时
            self.redis_client.setex(cache_key, 3600, post_json)
            
            # 更新索引
            self._update_cache_indexes(post)
            
        except Exception as e:
            self.logger.warning(f"Redis缓存更新失败: {e}")

    def _update_cache_indexes(self, post: ForumPost):
        """更新Redis索引"""
        if not self.redis_client:
            return
        
        try:
            # 按状态索引
            status_key = f"posts_by_status:{post.processing_status}"
            self.redis_client.sadd(status_key, post.post_id)
            self.redis_client.expire(status_key, 3600)
            
            # 按优先级索引
            priority_key = f"posts_by_priority:{post.priority}"
            self.redis_client.sadd(priority_key, post.post_id)
            self.redis_client.expire(priority_key, 3600)
            
        except Exception as e:
            self.logger.warning(f"Redis索引更新失败: {e}")

    def get_post(self, post_id: str) -> Optional[ForumPost]:
        """获取论坛帖子"""
        try:
            # 先尝试从Redis缓存获取
            if self.redis_client:
                cached_data = self._get_from_cache(post_id)
                if cached_data:
                    return cached_data

            # 从SQLite获取
            return self._get_from_sqlite(post_id)

        except Exception as e:
            self.logger.error(f"获取帖子失败: {e}")
            return None

    def _get_from_cache(self, post_id: str) -> Optional[ForumPost]:
        """从Redis缓存获取"""
        try:
            cache_key = self._get_cache_key(post_id)
            cached_json = self.redis_client.get(cache_key)
            if cached_json:
                post_data = json.loads(cached_json)
                return ForumPost.from_dict(post_data)
        except Exception as e:
            self.logger.warning(f"Redis缓存读取失败: {e}")
        return None

    def _get_from_sqlite(self, post_id: str) -> Optional[ForumPost]:
        """从SQLite获取"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM forum_posts WHERE post_id = ?",
                    (post_id,)
                )
                row = cursor.fetchone()
                if row:
                    post_data = dict(row)
                    # 移除数据库的id字段，因为ForumPost类不需要它
                    if 'id' in post_data:
                        del post_data['id']
                    post = ForumPost.from_dict(post_data)
                    # 更新缓存
                    self._update_cache(post)
                    return post
        except Exception as e:
            self.logger.error(f"SQLite查询失败: {e}")
        return None

    def get_posts_by_status(self, status: str, limit: int = 100) -> List[ForumPost]:
        """按状态获取帖子列表"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute(
                    """SELECT * FROM forum_posts
                       WHERE processing_status = ?
                       ORDER BY priority DESC, discovered_time ASC
                       LIMIT ?""",
                    (status, limit)
                )
                posts = []
                for row in cursor.fetchall():
                    post_data = dict(row)
                    # 移除数据库的id字段，因为ForumPost类不需要它
                    if 'id' in post_data:
                        del post_data['id']
                    posts.append(ForumPost.from_dict(post_data))
                return posts
        except Exception as e:
            self.logger.error(f"按状态查询帖子失败: {e}")
            return []

    def get_pending_posts(self, limit: int = 50) -> List[ForumPost]:
        """获取待处理的帖子"""
        return self.get_posts_by_status("pending", limit)

    def update_post_status(self, post_id: str, status: str, **kwargs) -> bool:
        """更新帖子状态"""
        try:
            with self._lock:
                # 构建更新字段
                update_fields = ["processing_status = ?"]
                values = [status]

                # 添加其他更新字段
                for key, value in kwargs.items():
                    if key in ['task_id', 'output_path', 'reply_status', 'reply_content']:
                        update_fields.append(f"{key} = ?")
                        values.append(value)

                # 添加更新时间
                update_fields.append("last_updated = ?")
                values.append(datetime.now().isoformat())
                values.append(post_id)

                sql = f"""
                UPDATE forum_posts
                SET {', '.join(update_fields)}
                WHERE post_id = ?
                """

                with self._get_db_connection() as conn:
                    cursor = conn.execute(sql, values)
                    if cursor.rowcount > 0:
                        conn.commit()
                        # 清除缓存，强制下次从数据库重新加载
                        self._clear_cache(post_id)
                        self.logger.info(f"帖子状态更新成功: {post_id} -> {status}")
                        return True

                return False
        except Exception as e:
            self.logger.error(f"更新帖子状态失败: {e}")
            return False

    def _clear_cache(self, post_id: str):
        """清除指定帖子的缓存"""
        if not self.redis_client:
            return

        try:
            cache_key = self._get_cache_key(post_id)
            self.redis_client.delete(cache_key)
        except Exception as e:
            self.logger.warning(f"清除缓存失败: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            with self._get_db_connection() as conn:
                # 基本统计
                cursor = conn.execute("""
                    SELECT
                        processing_status,
                        COUNT(*) as count
                    FROM forum_posts
                    GROUP BY processing_status
                """)
                status_stats = {row[0]: row[1] for row in cursor.fetchall()}

                # 总数统计
                cursor = conn.execute("SELECT COUNT(*) FROM forum_posts")
                total_posts = cursor.fetchone()[0]

                # 今日统计
                today = datetime.now().date().isoformat()
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM forum_posts WHERE DATE(discovered_time) = ?",
                    (today,)
                )
                today_posts = cursor.fetchone()[0]

                return {
                    'total_posts': total_posts,
                    'today_posts': today_posts,
                    'status_breakdown': status_stats,
                    'cache_enabled': self.redis_client is not None,
                    'last_updated': datetime.now().isoformat()
                }
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {}

    def cleanup_old_data(self, days: int = 30) -> int:
        """清理旧数据"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            with self._get_db_connection() as conn:
                # 清理已完成的旧帖子
                cursor = conn.execute("""
                    DELETE FROM forum_posts
                    WHERE processing_status = 'completed'
                    AND last_updated < ?
                """, (cutoff_date,))

                deleted_count = cursor.rowcount
                conn.commit()

                self.logger.info(f"清理了 {deleted_count} 条旧数据")
                return deleted_count

        except Exception as e:
            self.logger.error(f"清理旧数据失败: {e}")
            return 0

    def export_data(self, output_path: str, format: str = 'json') -> bool:
        """导出数据"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("SELECT * FROM forum_posts ORDER BY discovered_time DESC")
                posts_data = []

                for row in cursor.fetchall():
                    post_data = dict(row)
                    # 移除数据库的id字段以保持一致性
                    if 'id' in post_data:
                        del post_data['id']
                    posts_data.append(post_data)

                # 确保输出目录存在
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                if format.lower() == 'json':
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(posts_data, f, ensure_ascii=False, indent=2, default=str)
                elif format.lower() == 'csv':
                    import csv
                    if posts_data:
                        with open(output_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.DictWriter(f, fieldnames=posts_data[0].keys())
                            writer.writeheader()
                            writer.writerows(posts_data)

                self.logger.info(f"数据导出成功: {output_path}")
                return True

        except Exception as e:
            self.logger.error(f"数据导出失败: {e}")
            return False

    def close(self):
        """关闭连接"""
        if self.redis_client:
            try:
                self.redis_client.close()
            except:
                pass
        self.logger.info("数据管理器已关闭")


# 全局实例
_data_manager = None


def get_data_manager(db_path: str = "data/forum_posts.db") -> HybridForumDataManager:
    """获取数据管理器单例"""
    global _data_manager
    if _data_manager is None:
        _data_manager = HybridForumDataManager(db_path)
    return _data_manager


if __name__ == "__main__":
    # 测试代码
    print("🧪 测试混合数据管理器...")

    # 创建测试实例
    manager = HybridForumDataManager("data/test_forum_posts.db")

    # 创建测试帖子
    test_post = ForumPost(
        post_id="test_001",
        thread_id="thread_001",
        title="测试帖子",
        author_id="user_001",
        author_name="测试用户",
        video_urls=["http://example.com/video1.mp4"],
        priority=2,
        post_time=datetime.now()  # 添加必需的post_time字段
    )

    # 测试保存
    if manager.save_post(test_post):
        print("✅ 帖子保存成功")

    # 测试获取
    retrieved_post = manager.get_post("test_001")
    if retrieved_post:
        print(f"✅ 帖子获取成功: {retrieved_post.title}")

    # 测试统计
    stats = manager.get_statistics()
    print(f"📊 统计信息: {stats}")

    # 清理
    manager.close()
    print("🎉 测试完成")
