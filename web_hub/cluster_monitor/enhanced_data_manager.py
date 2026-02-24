#!/usr/bin/env python3
"""
SQLite + Redis 双层存储数据管理器
专为cluster_monitor设计的企业级数据存储方案

特点：
1. SQLite持久化存储 - 数据安全保障
2. Redis高速缓存 - 提升访问性能
3. 自动数据同步 - 保证数据一致性
4. 故障恢复机制 - Redis不可用时降级到SQLite
5. 完整的统计和查询功能
"""

import os
import json
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
import logging

# Redis支持检测
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️ Redis不可用，将使用纯SQLite模式")


@dataclass
class ForumPostRecord:
    """论坛帖子记录（与数据库表结构一致）"""
    post_id: str
    thread_id: str
    title: str
    author_name: str
    source_url: str  # 统一使用 source_url（与数据库表和工作节点一致）
    discovered_time: datetime
    processing_status: str = "discovered"  # discovered, dispatched, completed, failed
    dispatch_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    task_id: Optional[str] = None
    machine_url: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    has_video: bool = False
    has_audio: bool = False
    content_length: int = 0
    tags: List[str] = None
    created_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 处理datetime对象
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        # 处理列表
        if data['tags'] is None:
            data['tags'] = []
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ForumPostRecord':
        """从字典创建对象"""
        # 处理datetime字段
        datetime_fields = ['discovered_time', 'dispatch_time', 'completion_time', 'created_at', 'last_updated']
        for field in datetime_fields:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        # 处理tags字段
        if data.get('tags') is None:
            data['tags'] = []

        # 过滤掉不存在的字段，避免意外的关键字参数错误
        valid_fields = {
            'post_id', 'thread_id', 'title', 'author_name', 'source_url',
            'discovered_time', 'processing_status', 'dispatch_time',
            'completion_time', 'task_id', 'machine_url', 'error_message',
            'retry_count', 'has_video', 'has_audio', 'content_length',
            'tags', 'created_at', 'last_updated'
        }

        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        return cls(**filtered_data)


class SQLiteRedisDataManager:
    """SQLite + Redis 双层存储数据管理器"""

    def __init__(
        self,
        db_path: str = "data/forum_posts.db",
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 1,
        redis_prefix: str = "clonetts_monitor:",
    ):
        self.db_path = db_path
        self.redis_client = None
        self.redis_prefix = (redis_prefix.rstrip(":") + ":") if redis_prefix else "clonetts_monitor:"
        self._lock = threading.RLock()
        self.logger = logging.getLogger(__name__)

        # Redis配置
        self.redis_config = {
            'host': redis_host,
            'port': redis_port,
            'db': redis_db,
            'decode_responses': True,
            'socket_timeout': 5,
            'socket_connect_timeout': 5
        }

        # 确保数据目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # 初始化SQLite数据库
        self._init_database()

        # 初始化Redis连接
        self._init_redis()

        # 统计信息缓存
        self._stats_cache = {}
        self._stats_cache_time = None

        print(f"📊 SQLite + Redis 数据管理器已初始化")
        print(f"   SQLite: {self.db_path}")
        print(f"   Redis: {'✅ 可用' if self.redis_client else '❌ 不可用，使用SQLite模式'}")
        
    def _init_database(self):
        """初始化SQLite数据库 - 使用统一的SQL脚本"""
        try:
            # 尝试使用统一的 forum_posts.sql 脚本（与工作节点相同）
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            candidate_paths = [
                os.path.join(base_dir, "forum_posts.sql"),                # web_hub/forum_posts.sql
                os.path.join(os.getcwd(), "web_hub", "forum_posts.sql"), # 从仓库根目录运行
                os.path.join(os.getcwd(), "forum_posts.sql"),             # 当前目录
            ]

            sql_script_path = next((p for p in candidate_paths if os.path.exists(p)), None)

            if sql_script_path:
                # 使用统一的SQL脚本创建表
                self.logger.info(f"使用统一SQL脚本初始化数据库: {sql_script_path}")
                with open(sql_script_path, 'r', encoding='utf-8') as f:
                    sql_script = f.read()

                with sqlite3.connect(self.db_path) as conn:
                    conn.executescript(sql_script)
                    conn.commit()

                self.logger.info("SQLite数据库初始化成功（使用统一脚本）")
            else:
                # 降级方案：手动创建表（与forum_posts.sql保持一致）
                self.logger.warning("未找到forum_posts.sql，使用内置表结构")
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                    CREATE TABLE IF NOT EXISTS forum_posts (
                        post_id TEXT PRIMARY KEY,
                        thread_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        author_name TEXT NOT NULL,
                        source_url TEXT NOT NULL,
                        discovered_time TEXT NOT NULL,
                        processing_status TEXT DEFAULT 'discovered',
                        dispatch_time TEXT,
                        completion_time TEXT,
                        task_id TEXT,
                        machine_url TEXT,
                        error_message TEXT,
                        retry_count INTEGER DEFAULT 0,
                        has_video BOOLEAN DEFAULT FALSE,
                        has_audio BOOLEAN DEFAULT FALSE,
                        content_length INTEGER DEFAULT 0,
                        tags TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        last_updated TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """)
                    conn.commit()

            # 兼容性检查：如果是旧数据库，添加缺失的监控字段
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("PRAGMA table_info(forum_posts)")
                existing_columns = {row[1] for row in cursor.fetchall()}

                # 监控节点必需的字段
                required_fields = {
                    'machine_url': 'TEXT',
                    'dispatch_time': 'TEXT',
                    'completion_time': 'TEXT',
                    'error_message': 'TEXT',
                    'retry_count': 'INTEGER DEFAULT 0',
                    'has_video': 'BOOLEAN DEFAULT FALSE',
                    'has_audio': 'BOOLEAN DEFAULT FALSE',
                    'content_length': 'INTEGER DEFAULT 0',
                    'tags': 'TEXT',
                    'created_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
                }

                # 添加缺失的字段（兼容旧数据库）
                for field_name, field_type in required_fields.items():
                    if field_name not in existing_columns:
                        try:
                            conn.execute(f"ALTER TABLE forum_posts ADD COLUMN {field_name} {field_type}")
                            self.logger.info(f"添加监控字段: {field_name}")
                        except Exception as e:
                            self.logger.warning(f"添加字段 {field_name} 失败（可能已存在）: {e}")

                conn.commit()

                # 创建索引
                conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON forum_posts(processing_status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_discovered_time ON forum_posts(discovered_time)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_author ON forum_posts(author_name)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_machine ON forum_posts(machine_url)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_retry ON forum_posts(retry_count)")

                conn.commit()
                self.logger.info("SQLite数据库初始化成功")

        except Exception as e:
            self.logger.error(f"SQLite数据库初始化失败: {e}")
            raise

    def _init_redis(self):
        """初始化Redis连接"""
        if not REDIS_AVAILABLE:
            self.logger.warning("Redis模块不可用")
            return

        try:
            self.redis_client = redis.Redis(**self.redis_config)
            self.redis_client.ping()
            self.logger.info("Redis连接成功")

        except Exception as e:
            self.logger.warning(f"Redis连接失败: {e}，将只使用SQLite存储")
            self.redis_client = None
    
    def save_post(self, post: ForumPostRecord) -> bool:
        """保存帖子记录"""
        try:
            with self._lock:
                # 保存到SQLite（主存储）
                success = self._save_to_sqlite(post)
                if success:
                    # 更新Redis缓存
                    self._update_redis_cache(post)
                    # 更新Redis状态集合
                    self._update_redis_status_sets(post)
                    # 清除统计缓存
                    self._clear_stats_cache()

                return success
        except Exception as e:
            self.logger.error(f"保存帖子记录失败: {e}")
            return False
    
    def _save_to_sqlite(self, post: ForumPostRecord) -> bool:
        """保存到SQLite"""
        try:
            data = post.to_dict()
            data['tags'] = json.dumps(data['tags'], ensure_ascii=False)
            data['last_updated'] = datetime.now().isoformat()

            # 移除不存在的字段（统一使用 source_url）
            valid_columns = [
                'post_id', 'thread_id', 'title', 'author_name', 'source_url',
                'discovered_time', 'processing_status', 'dispatch_time',
                'completion_time', 'task_id', 'machine_url', 'error_message',
                'retry_count', 'has_video', 'has_audio', 'content_length',
                'tags', 'created_at', 'last_updated'
            ]

            filtered_data = {k: v for k, v in data.items() if k in valid_columns}
            columns = list(filtered_data.keys())
            placeholders = ['?' for _ in columns]
            values = list(filtered_data.values())

            sql = f"""
            INSERT OR REPLACE INTO forum_posts ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            """

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(sql, values)
                conn.commit()

            return True
        except Exception as e:
            self.logger.error(f"SQLite保存失败: {e}")
            return False

    def _update_redis_cache(self, post: ForumPostRecord):
        """更新Redis缓存"""
        try:
            if not self.redis_client:
                return

            cache_key = f"{self.redis_prefix}post:{post.post_id}"
            post_json = json.dumps(post.to_dict(), ensure_ascii=False)

            # 设置缓存，过期时间24小时
            self.redis_client.setex(cache_key, 86400, post_json)

        except Exception as e:
            self.logger.warning(f"Redis缓存更新失败: {e}")

    def _update_redis_status_sets(self, post: ForumPostRecord):
        """更新Redis状态集合"""
        try:
            if not self.redis_client:
                return

            # 从所有状态集合中移除
            for status in ['discovered', 'dispatched', 'completed', 'failed']:
                status_key = f"{self.redis_prefix}status:{status}"
                self.redis_client.srem(status_key, post.post_id)

            # 添加到当前状态集合
            current_status_key = f"{self.redis_prefix}status:{post.processing_status}"
            self.redis_client.sadd(current_status_key, post.post_id)

            # 设置过期时间（7天）
            self.redis_client.expire(current_status_key, 604800)

        except Exception as e:
            self.logger.warning(f"Redis状态集合更新失败: {e}")
    
    def get_post(self, post_id: str) -> Optional[ForumPostRecord]:
        """获取帖子记录"""
        try:
            # 先尝试从Redis获取
            if self.redis_client:
                cached_data = self._get_from_redis(post_id)
                if cached_data:
                    return cached_data

            # 从SQLite获取
            post = self._get_from_sqlite(post_id)

            # 如果从SQLite获取成功，更新Redis缓存
            if post and self.redis_client:
                self._update_redis_cache(post)

            return post

        except Exception as e:
            self.logger.error(f"获取帖子记录失败: {e}")
            return None

    def _get_from_redis(self, post_id: str) -> Optional[ForumPostRecord]:
        """从Redis获取"""
        try:
            cache_key = f"{self.redis_prefix}post:{post_id}"
            cached_json = self.redis_client.get(cache_key)
            if cached_json:
                post_data = json.loads(cached_json)
                return ForumPostRecord.from_dict(post_data)
        except Exception as e:
            self.logger.warning(f"Redis读取失败: {e}")
        return None

    def _get_from_sqlite(self, post_id: str) -> Optional[ForumPostRecord]:
        """从SQLite获取"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM forum_posts WHERE post_id = ?", (post_id,))
                row = cursor.fetchone()

                if row:
                    data = dict(row)
                    # 处理tags字段
                    if data['tags']:
                        data['tags'] = json.loads(data['tags'])
                    else:
                        data['tags'] = []

                    return ForumPostRecord.from_dict(data)
        except Exception as e:
            self.logger.error(f"SQLite读取失败: {e}")
        return None
    
    def is_post_processed(self, post_id: str) -> bool:
        """检查帖子是否已被处理"""
        try:
            # 先检查Redis状态集合（快速查询）
            if self.redis_client:
                for status in ['dispatched', 'completed']:
                    status_key = f"{self.redis_prefix}status:{status}"
                    if self.redis_client.sismember(status_key, post_id):
                        return True

            # 从SQLite检查
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM forum_posts WHERE post_id = ? AND processing_status IN ('dispatched', 'completed')",
                    (post_id,)
                )
                return cursor.fetchone() is not None

        except Exception as e:
            self.logger.error(f"检查帖子处理状态失败: {e}")
            return False

    def add_post(self, post_id: str, title: str, author: str, url: str) -> bool:
        """添加新帖子"""
        try:
            # 检查是否已存在
            if self.get_post(post_id):
                return False

            post = ForumPostRecord(
                post_id=post_id,
                thread_id=post_id,  # 使用post_id作为thread_id
                title=title,
                author_name=author,
                source_url=url,  # 统一使用 source_url
                discovered_time=datetime.now()
            )

            return self.save_post(post)

        except Exception as e:
            self.logger.error(f"添加帖子失败: {e}")
            return False
    
    def mark_post_dispatched(self, post_id: str, machine_url: str) -> bool:
        """标记帖子已分发"""
        return self.update_post_status(
            post_id,
            'dispatched',
            machine_url=machine_url,
            dispatch_time=datetime.now()
        )

    def mark_post_completed(self, post_id: str) -> bool:
        """标记帖子完成"""
        return self.update_post_status(
            post_id,
            'completed',
            completion_time=datetime.now()
        )

    def mark_post_failed(self, post_id: str, error_message: str) -> bool:
        """标记帖子失败"""
        post = self.get_post(post_id)
        retry_count = post.retry_count + 1 if post else 1

        return self.update_post_status(
            post_id,
            'failed',
            error_message=error_message,
            retry_count=retry_count
        )

    def get_posts_by_status(self, status: str, limit: int = 100) -> List[ForumPostRecord]:
        """按状态获取帖子列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """SELECT * FROM forum_posts
                       WHERE processing_status = ?
                       ORDER BY discovered_time DESC
                       LIMIT ?""",
                    (status, limit)
                )

                posts = []
                for row in cursor.fetchall():
                    data = dict(row)
                    if data['tags']:
                        data['tags'] = json.loads(data['tags'])
                    else:
                        data['tags'] = []
                    posts.append(ForumPostRecord.from_dict(data))

                return posts
        except Exception as e:
            self.logger.error(f"按状态查询帖子失败: {e}")
            return []
    
    def update_post_status(self, post_id: str, status: str, **kwargs) -> bool:
        """更新帖子状态"""
        try:
            with self._lock:
                # 构建更新字段
                update_fields = ["processing_status = ?", "last_updated = ?"]
                values = [status, datetime.now().isoformat()]

                # 添加其他字段
                for key, value in kwargs.items():
                    if key in ['dispatch_time', 'completion_time'] and isinstance(value, datetime):
                        value = value.isoformat()
                    update_fields.append(f"{key} = ?")
                    values.append(value)

                values.append(post_id)

                sql = f"""
                UPDATE forum_posts
                SET {', '.join(update_fields)}
                WHERE post_id = ?
                """

                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(sql, values)
                    success = cursor.rowcount > 0
                    conn.commit()

                if success:
                    # 获取更新后的帖子信息
                    updated_post = self._get_from_sqlite(post_id)
                    if updated_post:
                        # 更新Redis缓存
                        self._update_redis_cache(updated_post)
                        # 更新Redis状态集合
                        self._update_redis_status_sets(updated_post)

                    # 清除统计缓存
                    self._clear_stats_cache()

                return success
        except Exception as e:
            self.logger.error(f"更新帖子状态失败: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            # 检查缓存
            if (self._stats_cache_time and
                datetime.now() - self._stats_cache_time < timedelta(minutes=5)):
                return self._stats_cache

            with sqlite3.connect(self.db_path) as conn:
                # 状态统计
                cursor = conn.execute("""
                    SELECT processing_status, COUNT(*) as count
                    FROM forum_posts
                    GROUP BY processing_status
                """)
                status_counts = dict(cursor.fetchall())

                # 总数统计
                cursor = conn.execute("SELECT COUNT(*) FROM forum_posts")
                total_posts = cursor.fetchone()[0]

                # 今日统计
                today = datetime.now().date().isoformat()
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM forum_posts
                    WHERE DATE(discovered_time) = ?
                """, (today,))
                today_posts = cursor.fetchone()[0]

                # 机器统计
                cursor = conn.execute("""
                    SELECT machine_url, COUNT(*) as count
                    FROM forum_posts
                    WHERE machine_url IS NOT NULL
                    GROUP BY machine_url
                """)
                machine_stats = dict(cursor.fetchall())

                stats = {
                    'total_posts': total_posts,
                    'today_posts': today_posts,
                    'status_counts': status_counts,
                    'machine_stats': machine_stats,
                    'processed_posts': status_counts.get('dispatched', 0) + status_counts.get('completed', 0),
                    'redis_available': self.redis_client is not None,
                    'last_updated': datetime.now().isoformat()
                }

                # 缓存结果
                self._stats_cache = stats
                self._stats_cache_time = datetime.now()

                return stats

        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {}

    def _clear_stats_cache(self):
        """清除统计缓存"""
        self._stats_cache = {}
        self._stats_cache_time = None

    def close(self):
        """关闭数据管理器"""
        try:
            if self.redis_client:
                self.redis_client.close()
            print("💾 SQLite + Redis 数据管理器已关闭")
        except Exception as e:
            self.logger.error(f"关闭数据管理器失败: {e}")


# 全局实例
_data_manager = None


def get_sqlite_redis_data_manager() -> SQLiteRedisDataManager:
    """获取SQLite + Redis数据管理器单例"""
    global _data_manager
    if _data_manager is None:
        db_path = os.getenv("FORUM_DB_PATH", "data/forum_posts.db")
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_prefix = os.getenv("REDIS_PREFIX", "clonetts_monitor:")
        try:
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
        except ValueError:
            redis_port = 6379
        # 监控端默认使用独立DB=1，避免误用工作节点的 REDIS_DB=0
        monitor_redis_db = os.getenv("MONITOR_REDIS_DB", os.getenv("REDIS_MONITOR_DB", "1"))
        try:
            redis_db = int(monitor_redis_db)
        except ValueError:
            redis_db = 1

        _data_manager = SQLiteRedisDataManager(
            db_path=db_path,
            redis_host=redis_host,
            redis_port=redis_port,
            redis_db=redis_db,
            redis_prefix=redis_prefix,
        )
    return _data_manager
