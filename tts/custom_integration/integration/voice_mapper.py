"""
音色映射管理器
负责管理用户音色的映射关系，支持：
1. 用户克隆音色时保存映射
2. 用户使用"本人音色"时解析为实际音色ID
3. 支持多用户隔离
"""

import sqlite3
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据库路径（与tts_config.py保持一致）
DATABASE_PATH = Path(__file__).parent / "database" / "tts_voice_system.db"


class VoiceMapper:
    """音色映射管理器"""
    
    # 系统预置音色列表
    SYSTEM_VOICES = ["苏瑶", "小美", "小帅", "播音员", "新闻主播"]
    
    # "本人音色"的别名
    MY_VOICE_ALIASES = ["本人音色", "我的音色", "默认音色", "自己的音色"]
    
    def __init__(self, db_path: Optional[Path] = None):
        """初始化音色映射管理器"""
        self.db_path = db_path or DATABASE_PATH
        self._ensure_database()
    
    def _ensure_database(self):
        """确保数据库存在"""
        if not self.db_path.exists():
            logger.warning(f"数据库不存在: {self.db_path}")
            logger.info("请先运行 tts_init_db.py 初始化数据库")
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # ================================================================
    # 音色保存与查询
    # ================================================================
    
    def save_user_voice(
        self,
        user_id: str,
        voice_id: str,
        voice_name: str,
        file_path: str,
        audio_path: str,
        duration: float = 0.0,
        file_size_mb: float = 0.0,
        is_public: bool = False,
        description: str = "",
        set_as_default: bool = True
    ) -> bool:
        """
        保存用户音色到数据库
        
        Args:
            user_id: 用户ID（论坛用户名）
            voice_id: 音色ID（唯一标识）
            voice_name: 音色名称（用户输入的名称）
            file_path: .pt文件路径
            audio_path: 音频文件路径
            duration: 音频时长
            file_size_mb: 文件大小
            is_public: 是否公开
            description: 描述
            set_as_default: 是否设为该用户的默认音色
        
        Returns:
            是否保存成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. 保存音色信息
                cursor.execute('''
                    INSERT OR REPLACE INTO voices (
                        voice_id, voice_name, owner_id, is_public,
                        file_path, audio_path, duration, file_size_mb,
                        description, created_at, usage_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 0)
                ''', (
                    voice_id, voice_name, user_id, is_public,
                    file_path, audio_path, duration, file_size_mb,
                    description
                ))
                
                # 2. 如果设为默认音色，更新用户表
                if set_as_default:
                    # 先确保用户存在
                    cursor.execute('''
                        INSERT OR IGNORE INTO users (
                            user_id, username, password_hash, forum_user_id, forum_username
                        ) VALUES (?, ?, 'forum_user', ?, ?)
                    ''', (user_id, user_id, user_id, user_id))
                    
                    # 更新默认音色
                    cursor.execute('''
                        UPDATE users SET default_voice_id = ? WHERE user_id = ?
                    ''', (voice_id, user_id))
                
                conn.commit()
                logger.info(f"✅ 保存用户音色成功: {user_id} -> {voice_name} ({voice_id})")
                return True
                
        except Exception as e:
            logger.error(f"❌ 保存用户音色失败: {e}")
            return False
    
    def get_user_voice_by_name(self, user_id: str, voice_name: str) -> Optional[str]:
        """
        根据音色名称查询用户的音色ID
        
        Args:
            user_id: 用户ID
            voice_name: 音色名称
        
        Returns:
            音色ID，如果不存在返回None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT voice_id FROM voices
                    WHERE owner_id = ? AND voice_name = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (user_id, voice_name))
                
                row = cursor.fetchone()
                if row:
                    return row['voice_id']
                return None
                
        except Exception as e:
            logger.error(f"❌ 查询用户音色失败: {e}")
            return None
    
    def get_user_default_voice(self, user_id: str) -> Optional[str]:
        """
        获取用户的默认音色ID
        
        Args:
            user_id: 用户ID
        
        Returns:
            默认音色ID，如果不存在返回None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT default_voice_id FROM users WHERE user_id = ?
                ''', (user_id,))
                
                row = cursor.fetchone()
                if row and row['default_voice_id']:
                    return row['default_voice_id']
                return None
                
        except Exception as e:
            logger.error(f"❌ 查询用户默认音色失败: {e}")
            return None
    
    def get_user_voices(self, user_id: str) -> List[Dict]:
        """
        获取用户的所有音色
        
        Args:
            user_id: 用户ID
        
        Returns:
            音色列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT voice_id, voice_name, created_at, usage_count
                    FROM voices
                    WHERE owner_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))
                
                voices = []
                for row in cursor.fetchall():
                    voices.append({
                        'voice_id': row['voice_id'],
                        'voice_name': row['voice_name'],
                        'created_at': row['created_at'],
                        'usage_count': row['usage_count']
                    })
                return voices
                
        except Exception as e:
            logger.error(f"❌ 查询用户音色列表失败: {e}")
            return []
    
    # ================================================================
    # 音色名称解析（核心功能）
    # ================================================================
    
    def resolve_voice_name(self, user_id: str, voice_name: str) -> Tuple[str, str]:
        """
        解析音色名称，支持：
        1. "本人音色" → 用户的默认音色
        2. "张盼盼" → 用户自己克隆的音色
        3. "苏瑶" → 系统预置音色
        
        Args:
            user_id: 用户ID
            voice_name: 用户输入的音色名称
        
        Returns:
            (实际音色ID, 解析说明)
        """
        # 1. 检查是否是"本人音色"别名
        if voice_name in self.MY_VOICE_ALIASES:
            # 若未提供用户ID，则直接回退到系统默认，避免错误地使用空用户的默认音色
            if not user_id or not str(user_id).strip():
                logger.warning("⚠️ 未提供用户ID，'本人音色'回退系统默认")
                return "苏瑶", "未提供用户ID，'本人音色'回退到系统默认音色: 苏瑶"
            default_voice = self.get_user_default_voice(user_id)
            if default_voice:
                logger.info(f"🔍 解析音色: {voice_name} → {default_voice} (用户默认音色)")
                return default_voice, f"使用用户默认音色: {default_voice}"
            else:
                logger.warning(f"⚠️ 用户 {user_id} 没有默认音色，使用系统默认")
                return "苏瑶", "用户没有克隆音色，使用系统默认音色: 苏瑶"

        # 2. 检查是否是用户自己克隆的音色
        user_voice = self.get_user_voice_by_name(user_id, voice_name)
        if user_voice:
            logger.info(f"🔍 解析音色: {voice_name} → {user_voice} (用户克隆音色)")
            return user_voice, f"使用用户克隆的音色: {voice_name}"
        
        # 3. 检查是否是系统预置音色
        if voice_name in self.SYSTEM_VOICES:
            logger.info(f"🔍 解析音色: {voice_name} → {voice_name} (系统音色)")
            return voice_name, f"使用系统音色: {voice_name}"
        
        # 4. 默认使用系统音色
        logger.warning(f"⚠️ 未找到音色 {voice_name}，使用系统默认")
        return "苏瑶", f"未找到音色 {voice_name}，使用系统默认音色: 苏瑶"
    
    # ================================================================
    # 统计与管理
    # ================================================================
    
    def increment_usage_count(self, voice_id: str):
        """增加音色使用次数"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE voices
                    SET usage_count = usage_count + 1,
                        last_used = CURRENT_TIMESTAMP
                    WHERE voice_id = ?
                ''', (voice_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"❌ 更新音色使用次数失败: {e}")
    
    def get_statistics(self, user_id: str) -> Dict:
        """获取用户音色统计信息"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 音色总数
                cursor.execute('''
                    SELECT COUNT(*) as count FROM voices WHERE owner_id = ?
                ''', (user_id,))
                total_voices = cursor.fetchone()['count']
                
                # 默认音色
                default_voice = self.get_user_default_voice(user_id)
                
                # 最常用音色
                cursor.execute('''
                    SELECT voice_id, voice_name, usage_count
                    FROM voices
                    WHERE owner_id = ?
                    ORDER BY usage_count DESC
                    LIMIT 1
                ''', (user_id,))
                most_used = cursor.fetchone()
                
                return {
                    'total_voices': total_voices,
                    'default_voice': default_voice,
                    'most_used_voice': dict(most_used) if most_used else None
                }
                
        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return {}


# ================================================================
# 测试代码
# ================================================================

if __name__ == "__main__":
    print("🧪 测试音色映射管理器\n")
    
    mapper = VoiceMapper()
    
    # 测试1: 保存用户音色
    print("=" * 60)
    print("测试1: 保存用户音色")
    print("=" * 60)
    
    success = mapper.save_user_voice(
        user_id="admin_lrtcai",
        voice_id="user_admin_lrtcai_张盼盼_1730123456",
        voice_name="张盼盼",
        file_path="voices/user_admin_lrtcai_张盼盼_1730123456.pt",
        audio_path="voices/audio/admin_lrtcai/张盼盼.wav",
        duration=15.2,
        file_size_mb=1.29,
        is_public=False,
        description="这是盼盼的声音",
        set_as_default=True
    )
    print(f"保存结果: {'✅ 成功' if success else '❌ 失败'}\n")
    
    # 测试2: 解析"本人音色"
    print("=" * 60)
    print("测试2: 解析'本人音色'")
    print("=" * 60)
    
    voice_id, reason = mapper.resolve_voice_name("admin_lrtcai", "本人音色")
    print(f"输入: 本人音色")
    print(f"解析结果: {voice_id}")
    print(f"说明: {reason}\n")
    
    # 测试3: 解析音色名称
    print("=" * 60)
    print("测试3: 解析音色名称")
    print("=" * 60)
    
    voice_id, reason = mapper.resolve_voice_name("admin_lrtcai", "张盼盼")
    print(f"输入: 张盼盼")
    print(f"解析结果: {voice_id}")
    print(f"说明: {reason}\n")
    
    # 测试4: 解析系统音色
    print("=" * 60)
    print("测试4: 解析系统音色")
    print("=" * 60)
    
    voice_id, reason = mapper.resolve_voice_name("admin_lrtcai", "苏瑶")
    print(f"输入: 苏瑶")
    print(f"解析结果: {voice_id}")
    print(f"说明: {reason}\n")
    
    # 测试5: 获取用户统计
    print("=" * 60)
    print("测试5: 获取用户统计")
    print("=" * 60)
    
    stats = mapper.get_statistics("admin_lrtcai")
    print(f"统计信息: {stats}\n")
    
    print("🎉 测试完成！")

