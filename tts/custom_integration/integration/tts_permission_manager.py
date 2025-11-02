"""
TTS权限管理模块

功能：
1. 检查用户是否可以使用指定音色
2. 检查用户音色克隆配额
3. 检查用户存储配额
4. 权限验证和错误处理
"""

import sqlite3
from typing import Tuple, Optional
from tts_config import DATABASE_PATH

class PermissionManager:
    """权限管理器"""
    
    def __init__(self):
        self.db_path = DATABASE_PATH
    
    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # ==================== 音色使用权限 ====================
    
    def can_use_voice(self, user_id: str, voice_id: str) -> Tuple[bool, str]:
        """
        检查用户是否可以使用指定音色
        
        规则：
        1. 公共音色 → 所有人可用
        2. 自己创建的音色 → 可用
        3. 其他人的私有音色 → 不可用
        
        返回: (是否可用, 原因)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 查询音色信息
            cursor.execute("""
                SELECT voice_id, voice_name, owner_id, is_public
                FROM voices
                WHERE voice_id = ?
            """, (voice_id,))
            
            voice = cursor.fetchone()
            
            if not voice:
                return False, f"❌ 音色不存在: {voice_id}"
            
            # 规则1：公共音色
            if voice['is_public']:
                return True, f"✅ 可以使用公共音色: {voice['voice_name']}"
            
            # 规则2：自己创建的音色
            if voice['owner_id'] == user_id:
                return True, f"✅ 可以使用自己的音色: {voice['voice_name']}"
            
            # 规则3：其他人的私有音色
            return False, f"❌ 无权使用他人的私有音色: {voice['voice_name']}"
        
        finally:
            conn.close()
    
    def can_use_voice_by_name(self, user_id: str, voice_name: str) -> Tuple[bool, str, Optional[str]]:
        """
        通过音色名称检查权限
        
        返回: (是否可用, 原因, voice_id)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 查询音色信息
            cursor.execute("""
                SELECT voice_id, voice_name, owner_id, is_public
                FROM voices
                WHERE voice_name = ?
            """, (voice_name,))
            
            voice = cursor.fetchone()
            
            if not voice:
                return False, f"❌ 音色不存在: {voice_name}", None
            
            voice_id = voice['voice_id']
            
            # 规则1：公共音色
            if voice['is_public']:
                return True, f"✅ 可以使用公共音色: {voice_name}", voice_id
            
            # 规则2：自己创建的音色
            if voice['owner_id'] == user_id:
                return True, f"✅ 可以使用自己的音色: {voice_name}", voice_id
            
            # 规则3：其他人的私有音色
            return False, f"❌ 无权使用他人的私有音色: {voice_name}", None
        
        finally:
            conn.close()
    
    # ==================== 音色克隆配额 ====================
    
    def check_voice_quota(self, user_id: str) -> Tuple[bool, str, int, int]:
        """
        检查用户音色克隆配额
        
        返回: (是否有配额, 原因, 当前数量, 配额限制)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 获取用户配额
            cursor.execute("""
                SELECT voice_quota FROM users WHERE user_id = ?
            """, (user_id,))
            
            user = cursor.fetchone()
            if not user:
                return False, f"❌ 用户不存在: {user_id}", 0, 0
            
            quota = user['voice_quota']
            
            # 统计用户已有的音色数
            cursor.execute("""
                SELECT COUNT(*) as count FROM voices
                WHERE owner_id = ?
            """, (user_id,))
            
            current_count = cursor.fetchone()['count']
            
            if current_count >= quota:
                return False, f"❌ 音色配额已满 ({current_count}/{quota})", current_count, quota
            
            return True, f"✅ 配额充足 ({current_count}/{quota})", current_count, quota
        
        finally:
            conn.close()
    
    # ==================== 存储配额 ====================
    
    def check_storage_quota(self, user_id: str, file_size_mb: float) -> Tuple[bool, str, float, float]:
        """
        检查用户存储配额
        
        返回: (是否有空间, 原因, 已用空间, 配额限制)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 获取用户配额
            cursor.execute("""
                SELECT storage_quota_mb FROM users WHERE user_id = ?
            """, (user_id,))
            
            user = cursor.fetchone()
            if not user:
                return False, f"❌ 用户不存在: {user_id}", 0, 0
            
            quota = user['storage_quota_mb']
            
            # 统计用户已用空间
            cursor.execute("""
                SELECT COALESCE(SUM(file_size_mb), 0) as total
                FROM voices
                WHERE owner_id = ?
            """, (user_id,))
            
            used = cursor.fetchone()['total']
            remaining = quota - used
            
            if remaining < file_size_mb:
                return False, f"❌ 存储空间不足 (需要{file_size_mb}MB, 剩余{remaining:.2f}MB)", used, quota
            
            return True, f"✅ 存储空间充足 (剩余{remaining:.2f}MB)", used, quota
        
        finally:
            conn.close()
    
    # ==================== 音色名称检查 ====================
    
    def check_voice_name_duplicate(self, user_id: str, voice_name: str) -> Tuple[bool, str]:
        """
        检查用户是否已有同名音色
        
        返回: (是否可用, 原因)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT COUNT(*) as count FROM voices
                WHERE owner_id = ? AND voice_name = ?
            """, (user_id, voice_name))
            
            count = cursor.fetchone()['count']
            
            if count > 0:
                return False, f"❌ 您已有同名音色: {voice_name}"
            
            return True, f"✅ 音色名称可用: {voice_name}"
        
        finally:
            conn.close()
    
    # ==================== 综合权限检查 ====================
    
    def validate_tts_request(self, user_id: str, voice_name: str, text_length: int) -> Tuple[bool, str]:
        """
        验证TTS请求的所有权限
        
        返回: (是否通过, 错误信息)
        """
        # 检查用户是否存在
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            if not cursor.fetchone():
                return False, f"❌ 用户不存在: {user_id}"
            
            # 检查音色
            can_use, reason, voice_id = self.can_use_voice_by_name(user_id, voice_name)
            if not can_use:
                return False, reason
            
            # 检查文本长度
            if text_length > 10000:
                return False, "❌ 文本过长 (最多10000字符)"
            
            if text_length == 0:
                return False, "❌ 文本不能为空"
            
            return True, "✅ 验证通过"
        
        finally:
            conn.close()
    
    def validate_voice_clone_request(self, user_id: str, voice_name: str, file_size_mb: float) -> Tuple[bool, str]:
        """
        验证音色克隆请求的所有权限
        
        返回: (是否通过, 错误信息)
        """
        # 检查用户是否存在
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            if not cursor.fetchone():
                return False, f"❌ 用户不存在: {user_id}"
            
            # 检查音色配额
            has_quota, quota_reason, _, _ = self.check_voice_quota(user_id)
            if not has_quota:
                return False, quota_reason
            
            # 检查存储配额
            has_storage, storage_reason, _, _ = self.check_storage_quota(user_id, file_size_mb)
            if not has_storage:
                return False, storage_reason
            
            # 检查音色名称
            name_available, name_reason = self.check_voice_name_duplicate(user_id, voice_name)
            if not name_available:
                return False, name_reason
            
            return True, "✅ 验证通过"
        
        finally:
            conn.close()
    
    # ==================== 获取用户信息 ====================
    
    def get_user_voices(self, user_id: str) -> list:
        """获取用户的所有音色（公共 + 私有）"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 获取公共音色
            cursor.execute("""
                SELECT voice_id, voice_name, owner_id, is_public, file_size_mb
                FROM voices
                WHERE is_public = 1
                ORDER BY voice_name
            """)
            public_voices = [dict(row) for row in cursor.fetchall()]
            
            # 获取用户私有音色
            cursor.execute("""
                SELECT voice_id, voice_name, owner_id, is_public, file_size_mb
                FROM voices
                WHERE owner_id = ?
                ORDER BY voice_name
            """, (user_id,))
            private_voices = [dict(row) for row in cursor.fetchall()]
            
            return {
                'public': public_voices,
                'private': private_voices,
                'total': len(public_voices) + len(private_voices)
            }
        
        finally:
            conn.close()


# 全局实例
permission_manager = PermissionManager()


if __name__ == "__main__":
    # 测试
    pm = PermissionManager()
    
    print("=" * 60)
    print("权限管理器测试")
    print("=" * 60)
    
    # 测试1：检查公共音色
    print("\n测试1：检查公共音色")
    can_use, reason = pm.can_use_voice_by_name("test_user", "苏瑶")
    print(f"  {reason}")
    
    # 测试2：检查音色配额
    print("\ntest2：检查音色配额")
    has_quota, reason, current, quota = pm.check_voice_quota("test_user")
    print(f"  {reason}")
    
    # 测试3：获取用户音色
    print("\n测试3：获取用户音色")
    voices = pm.get_user_voices("test_user")
    print(f"  公共音色: {len(voices['public'])}")
    print(f"  私有音色: {len(voices['private'])}")

