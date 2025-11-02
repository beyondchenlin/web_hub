"""
TTS论坛请求处理器

功能：
1. 从论坛爬虫获取新帖子
2. 解析TTS和音色克隆请求
3. 验证权限和配额
4. 调用TTS API处理
5. 自动回复论坛
"""

import json
import logging
from typing import Dict, Tuple, Optional, List
from datetime import datetime

from tts_request_parser import TTSRequestParser
from tts_permission_manager import PermissionManager
from tts_forum_sync import TTSForumUserSync

logger = logging.getLogger(__name__)


class TTSForumProcessor:
    """TTS论坛请求处理器"""
    
    def __init__(self, db_path: str = "database/tts_voice_system.db"):
        """
        初始化论坛处理器

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self.parser = TTSRequestParser()
        self.permission_manager = PermissionManager()
        self.user_sync = TTSForumUserSync(db_path)
    
    def process_forum_post(self, post_data: Dict) -> Tuple[bool, Dict]:
        """
        处理论坛帖子
        
        Args:
            post_data: 论坛爬虫返回的帖子数据
        
        Returns:
            (是否成功, 处理结果)
        """
        try:
            # 第1步：同步用户
            logger.info(f"📝 处理帖子: {post_data.get('title', '未知')}")
            
            author_id = post_data.get('author_id', '')
            author_name = post_data.get('author_name', '')
            
            if author_id:
                success, msg = self.user_sync.sync_forum_user(author_id, author_name)
                logger.info(f"👤 用户同步: {msg}")
            
            # 第2步：智能识别请求类型
            detection = self.parser.detect_request_type(post_data)
            logger.info(f"🧠 识别结果: {detection['type']} (置信度: {detection['confidence']}%)")
            
            if detection['type'] == 'unknown':
                return False, {
                    'error': '无法识别请求类型',
                    'detection': detection
                }
            
            # 第3步：解析请求参数
            success, parse_result = self.parser.parse_forum_post(post_data)
            
            if not success:
                logger.error(f"❌ 解析失败: {parse_result.get('error', '未知错误')}")
                return False, parse_result
            
            # 第4步：验证权限和配额
            tts_user_id = f"forum_{author_id}"
            
            if parse_result['request_type'] == 'tts':
                # TTS请求：验证音色权限
                voice_name = parse_result.get('voice_name', '')

                # 如果是"本人音色"，使用用户自己的音色
                if voice_name == '本人音色' or not voice_name:
                    voice_name = f"user_{author_id}_voice"
                    parse_result['voice_name'] = voice_name

                # 通过音色名称检查权限
                can_use, reason, voice_id = self.permission_manager.can_use_voice_by_name(tts_user_id, voice_name)

                if not can_use:
                    logger.error(f"❌ 权限验证失败: {reason}")
                    return False, {'error': reason}

                logger.info(f"✅ 权限验证通过: {voice_name}")
                parse_result['voice_id'] = voice_id
            
            elif parse_result['request_type'] == 'voice_clone':
                # 音色克隆请求：验证音色配额
                has_quota, reason, used, quota = self.permission_manager.check_voice_quota(tts_user_id)
                
                if not has_quota:
                    logger.error(f"❌ 配额验证失败: {reason}")
                    return False, {'error': reason}
                
                logger.info(f"✅ 配额验证通过: {used}/{quota}")
                
                # 验证存储配额
                file_size_mb = parse_result.get('file_size_mb', 0)
                has_storage, reason, used_mb, quota_mb = self.permission_manager.check_storage_quota(
                    tts_user_id, file_size_mb
                )
                
                if not has_storage:
                    logger.error(f"❌ 存储配额验证失败: {reason}")
                    return False, {'error': reason}
                
                logger.info(f"✅ 存储配额验证通过: {used_mb:.1f}MB/{quota_mb:.1f}MB")
            
            # 第5步：返回处理结果
            parse_result.update({
                'tts_user_id': tts_user_id,
                'author_id': author_id,
                'author_name': author_name,
                'post_id': post_data.get('thread_id'),
                'thread_id': post_data.get('thread_id'),
                'post_url': post_data.get('thread_url'),
                'post_time': post_data.get('post_time'),
                'processed_at': datetime.now().isoformat(),
                'status': 'pending'
            })
            
            logger.info(f"✅ 帖子处理成功")
            return True, parse_result
        
        except Exception as e:
            logger.error(f"❌ 处理帖子异常: {e}")
            import traceback
            traceback.print_exc()
            return False, {'error': f'处理异常: {str(e)}'}
    
    def generate_reply_message(self, process_result: Dict) -> str:
        """
        生成论坛回复消息
        
        Args:
            process_result: 处理结果
        
        Returns:
            回复消息
        """
        request_type = process_result.get('request_type', 'unknown')
        
        if request_type == 'tts':
            return self._generate_tts_reply(process_result)
        elif request_type == 'voice_clone':
            return self._generate_clone_reply(process_result)
        else:
            return "❌ 无法识别请求类型"
    
    def _generate_tts_reply(self, result: Dict) -> str:
        """生成TTS请求的回复"""
        return f"""
✅ 您的TTS请求已收到并处理！

📋 请求信息：
- 文案：{result.get('tts_text', '')[:50]}...
- 音色：{result.get('voice_name', '未知')}
- 语速：{result.get('speed', 1.0)}
- 情感：{result.get('emotion', '无') if result.get('emotion') else '无'}

⏳ 处理状态：处理中...
🔗 请求ID：{result.get('post_id', 'N/A')}

系统将在处理完成后自动回复您的帖子。
"""
    
    def _generate_clone_reply(self, result: Dict) -> str:
        """生成音色克隆请求的回复"""
        return f"""
✅ 您的音色克隆请求已收到并处理！

📋 请求信息：
- 音色名称：{result.get('clone_voice_name', '未知')}
- 描述：{result.get('description', '无')}
- 是否公开：{'是' if result.get('clone_is_public') else '否'}

⏳ 处理状态：处理中...
🔗 请求ID：{result.get('post_id', 'N/A')}

系统将在处理完成后自动回复您的帖子。
"""


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("TTS论坛请求处理器测试")
    print("=" * 60)

    processor = TTSForumProcessor()

    # 测试1：处理TTS请求（使用公共音色）
    print("\n测试1：处理TTS请求（使用公共音色）")
    import time
    unique_id = str(int(time.time()))
    post_data_1 = {
        'title': '【制作AI声音】女主播.WAV',
        'content': '【文案】你好世界\n【选择音色】女主播',
        'tags': ['【制作AI声音】'],
        'thread_id': f'thread_{unique_id}',
        'thread_url': 'http://example.com/thread-123',
        'author_id': unique_id,
        'author_name': f'forumuser_{unique_id}',
        'post_time': datetime.now().isoformat(),
        'attachments': []
    }

    success, result = processor.process_forum_post(post_data_1)
    print(f"  成功: {success}")
    if success:
        print(f"  请求类型: {result['request_type']}")
        print(f"  用户ID: {result['tts_user_id']}")
        print(f"  音色: {result['voice_name']}")
        reply = processor.generate_reply_message(result)
        print(f"  回复消息:\n{reply}")
    else:
        print(f"  错误: {result.get('error', '未知错误')}")

