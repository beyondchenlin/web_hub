"""
TTS论坛用户同步模块

功能：
1. 从论坛爬虫获取用户信息
2. 同步用户到TTS系统数据库
3. 管理用户权限和配额
"""

import sqlite3
import json
from typing import Dict, Tuple, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TTSForumUserSync:
    """TTS论坛用户同步管理器"""
    
    def __init__(self, db_path: str = "database/tts_voice_system.db"):
        """
        初始化用户同步管理器
        
        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库连接"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.close()
            logger.info(f"✅ 数据库连接成功: {self.db_path}")
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            raise
    
    def sync_forum_user(self, forum_user_id: str, forum_username: str,
                       email: str = "") -> Tuple[bool, str]:
        """
        同步论坛用户到TTS系统

        Args:
            forum_user_id: 论坛用户ID
            forum_username: 论坛用户名
            email: 用户邮箱

        Returns:
            (是否成功, 消息)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 生成TTS系统用户ID
            tts_user_id = f"forum_{forum_user_id}"

            # 检查用户是否已存在
            cursor.execute(
                "SELECT user_id FROM users WHERE user_id = ?",
                (tts_user_id,)
            )
            existing_user = cursor.fetchone()

            if existing_user:
                # 更新现有用户
                cursor.execute("""
                    UPDATE users
                    SET forum_username = ?,
                        forum_sync_time = ?,
                        email = ?
                    WHERE user_id = ?
                """, (forum_username, datetime.now().isoformat(), email, tts_user_id))

                logger.info(f"✅ 更新用户: {forum_username} (ID: {tts_user_id})")
                message = f"用户已更新: {forum_username}"
            else:
                # 创建新用户
                import hashlib
                # 生成一个随机密码哈希（论坛用户不需要本地密码）
                password_hash = hashlib.sha256(f"forum_{forum_user_id}".encode()).hexdigest()

                cursor.execute("""
                    INSERT INTO users
                    (user_id, username, email, password_hash, forum_user_id, forum_username, forum_sync_time, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tts_user_id,
                    forum_username,
                    email,
                    password_hash,
                    forum_user_id,
                    forum_username,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))

                logger.info(f"✅ 创建新用户: {forum_username} (ID: {tts_user_id})")
                message = f"用户已创建: {forum_username}"

            conn.commit()
            conn.close()

            return True, message

        except Exception as e:
            logger.error(f"❌ 同步用户失败: {e}")
            return False, f"同步失败: {str(e)}"
    
    def get_user_by_forum_id(self, forum_user_id: str) -> Optional[Dict]:
        """
        根据论坛用户ID获取TTS用户信息
        
        Args:
            forum_user_id: 论坛用户ID
        
        Returns:
            用户信息字典或None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM users WHERE forum_user_id = ?",
                (forum_user_id,)
            )
            user = cursor.fetchone()
            conn.close()
            
            if user:
                return dict(user)
            return None
        
        except Exception as e:
            logger.error(f"❌ 查询用户失败: {e}")
            return None
    
    def get_user_by_tts_id(self, tts_user_id: str) -> Optional[Dict]:
        """
        根据TTS用户ID获取用户信息
        
        Args:
            tts_user_id: TTS系统用户ID
        
        Returns:
            用户信息字典或None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (tts_user_id,)
            )
            user = cursor.fetchone()
            conn.close()
            
            if user:
                return dict(user)
            return None
        
        except Exception as e:
            logger.error(f"❌ 查询用户失败: {e}")
            return None
    
    def get_user_voice_quota(self, tts_user_id: str) -> Tuple[int, int]:
        """
        获取用户的音色配额
        
        Args:
            tts_user_id: TTS系统用户ID
        
        Returns:
            (已使用数量, 配额限制)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取用户创建的音色数量
            cursor.execute(
                "SELECT COUNT(*) as count FROM voices WHERE owner_id = ?",
                (tts_user_id,)
            )
            used = cursor.fetchone()[0]
            
            # 获取配额限制（默认20）
            cursor.execute(
                "SELECT voice_quota FROM users WHERE user_id = ?",
                (tts_user_id,)
            )
            result = cursor.fetchone()
            quota = result[0] if result else 20
            
            conn.close()
            
            return used, quota
        
        except Exception as e:
            logger.error(f"❌ 获取音色配额失败: {e}")
            return 0, 20
    
    def get_user_storage_quota(self, tts_user_id: str) -> Tuple[float, float]:
        """
        获取用户的存储配额
        
        Args:
            tts_user_id: TTS系统用户ID
        
        Returns:
            (已使用MB, 配额限制MB)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取用户的总存储使用量
            cursor.execute("""
                SELECT COALESCE(SUM(file_size_mb), 0) as total_size 
                FROM voices 
                WHERE owner_id = ?
            """, (tts_user_id,))
            used = cursor.fetchone()[0]
            
            # 获取配额限制（默认500MB）
            cursor.execute(
                "SELECT storage_quota_mb FROM users WHERE user_id = ?",
                (tts_user_id,)
            )
            result = cursor.fetchone()
            quota = result[0] if result else 500
            
            conn.close()
            
            return used, quota
        
        except Exception as e:
            logger.error(f"❌ 获取存储配额失败: {e}")
            return 0, 500


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("TTS论坛用户同步测试")
    print("=" * 60)

    sync = TTSForumUserSync()

    # 测试1：同步新用户
    print("\n测试1：同步新用户")
    import time
    unique_id = str(int(time.time()))
    success, msg = sync.sync_forum_user(unique_id, f"forumuser_{unique_id}", f"user{unique_id}@example.com")
    print(f"  结果: {msg}")

    # 测试2：获取用户信息
    print("\n测试2：获取用户信息")
    user = sync.get_user_by_forum_id(unique_id)
    if user:
        print(f"  用户ID: {user['user_id']}")
        print(f"  用户名: {user['username']}")

    # 测试3：获取音色配额
    print("\n测试3：获取音色配额")
    used, quota = sync.get_user_voice_quota(f"forum_{unique_id}")
    print(f"  已使用: {used}/{quota}")

    # 测试4：获取存储配额
    print("\n测试4：获取存储配额")
    used, quota = sync.get_user_storage_quota(f"forum_{unique_id}")
    print(f"  已使用: {used:.1f}MB/{quota:.1f}MB")

