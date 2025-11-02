"""
IndexTTS2 论坛集成系统 - 论坛回复上传模块
处理生成的音频/音色上传到论坛
"""

import os
import sys
import logging
import sqlite3
from typing import Dict, Tuple, Optional, List
from datetime import datetime
from pathlib import Path

# 确保 shared 可导入
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.forum_config import load_forum_settings

# 导入配置
from tts_config import DATABASE_PATH
from tts_forum_processor import TTSForumProcessor
from tts_forum_crawler_integration import TTSForumCrawlerIntegration

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TTSForumReplyUploader:
    """论坛回复上传器 - 处理生成的音频/音色上传到论坛"""

    def __init__(self):
        """初始化回复上传器"""
        self.processor = TTSForumProcessor()

        # 初始化论坛爬虫集成
        settings = load_forum_settings()
        forum_cfg = settings.get('forum', {})
        credentials_cfg = settings.get('credentials', {})

        self.crawler_integration = TTSForumCrawlerIntegration(
            username=credentials_cfg.get('username', ''),
            password=credentials_cfg.get('password', ''),
            base_url=forum_cfg.get('base_url', 'https://tts.lrtcai.com'),
            forum_url=forum_cfg.get('target_url', 'https://tts.lrtcai.com/forum-2-1.html')
        )

        logger.info("✅ 论坛回复上传器初始化完成")
    
    def upload_tts_result(self, request_id: str, thread_id: str, 
                          output_path: str, user_id: str) -> Tuple[bool, str]:
        """
        上传TTS结果到论坛
        
        Args:
            request_id: 请求ID
            thread_id: 论坛帖子ID
            output_path: 输出音频文件路径
            user_id: 用户ID
        
        Returns:
            (success, message)
        """
        try:
            logger.info(f"📤 上传TTS结果: {request_id}")
            
            # 验证文件存在
            if not os.path.exists(output_path):
                error_msg = f"输出文件不存在: {output_path}"
                logger.error(f"❌ {error_msg}")
                return False, error_msg
            
            # 获取文件信息
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            file_name = os.path.basename(output_path)
            
            # 生成回复内容
            reply_content = self._generate_tts_reply(
                request_id=request_id,
                file_name=file_name,
                file_size_mb=file_size_mb,
                user_id=user_id
            )
            
            # 上传到论坛
            success = self._upload_to_forum(
                thread_id=thread_id,
                content=reply_content,
                attachments=[output_path]
            )
            
            if success:
                logger.info(f"✅ TTS结果上传成功: {request_id}")
                # 更新数据库状态
                self._update_request_status(request_id, 'uploaded')
                return True, "上传成功"
            else:
                error_msg = "论坛上传失败"
                logger.error(f"❌ {error_msg}")
                return False, error_msg
        
        except Exception as e:
            error_msg = f"上传TTS结果异常: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def upload_voice_clone_result(self, request_id: str, thread_id: str,
                                  voice_id: str, voice_name: str,
                                  user_id: str) -> Tuple[bool, str]:
        """
        上传音色克隆结果到论坛
        
        Args:
            request_id: 请求ID
            thread_id: 论坛帖子ID
            voice_id: 音色ID
            voice_name: 音色名称
            user_id: 用户ID
        
        Returns:
            (success, message)
        """
        try:
            logger.info(f"📤 上传音色克隆结果: {request_id}")
            
            # 生成回复内容
            reply_content = self._generate_voice_clone_reply(
                request_id=request_id,
                voice_id=voice_id,
                voice_name=voice_name,
                user_id=user_id
            )
            
            # 上传到论坛
            success = self._upload_to_forum(
                thread_id=thread_id,
                content=reply_content,
                attachments=[]
            )
            
            if success:
                logger.info(f"✅ 音色克隆结果上传成功: {request_id}")
                # 更新数据库状态
                self._update_request_status(request_id, 'uploaded')
                return True, "上传成功"
            else:
                error_msg = "论坛上传失败"
                logger.error(f"❌ {error_msg}")
                return False, error_msg
        
        except Exception as e:
            error_msg = f"上传音色克隆结果异常: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def upload_error_reply(self, request_id: str, thread_id: str,
                          error_message: str) -> Tuple[bool, str]:
        """
        上传错误回复到论坛
        
        Args:
            request_id: 请求ID
            thread_id: 论坛帖子ID
            error_message: 错误信息
        
        Returns:
            (success, message)
        """
        try:
            logger.info(f"📤 上传错误回复: {request_id}")
            
            # 生成错误回复内容
            reply_content = f"""
❌ 处理失败

请求ID: {request_id}
错误信息: {error_message}

请检查您的请求参数是否正确，或联系管理员。
"""
            
            # 上传到论坛
            success = self._upload_to_forum(
                thread_id=thread_id,
                content=reply_content,
                attachments=[]
            )
            
            if success:
                logger.info(f"✅ 错误回复上传成功: {request_id}")
                return True, "上传成功"
            else:
                error_msg = "论坛上传失败"
                logger.error(f"❌ {error_msg}")
                return False, error_msg
        
        except Exception as e:
            error_msg = f"上传错误回复异常: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def _generate_tts_reply(self, request_id: str, file_name: str,
                           file_size_mb: float, user_id: str) -> str:
        """生成TTS回复内容"""
        return f"""
✅ 您的TTS请求已处理完成！

📋 请求信息：
- 请求ID: {request_id}
- 用户: {user_id}
- 处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📁 生成的音频：
- 文件名: {file_name}
- 文件大小: {file_size_mb:.2f} MB

🎵 您可以下载上面的音频文件进行试听。

感谢使用IndexTTS2系统！
"""
    
    def _generate_voice_clone_reply(self, request_id: str, voice_id: str,
                                   voice_name: str, user_id: str) -> str:
        """生成音色克隆回复内容"""
        return f"""
✅ 您的音色克隆请求已处理完成！

📋 请求信息：
- 请求ID: {request_id}
- 用户: {user_id}
- 处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🎤 克隆的音色：
- 音色ID: {voice_id}
- 音色名称: {voice_name}

✨ 您现在可以在【制作AI声音】中使用这个音色了！

感谢使用IndexTTS2系统！
"""
    
    def _upload_to_forum(self, thread_id: str, content: str,
                        attachments: List[str] = None) -> bool:
        """上传到论坛"""
        try:
            logger.info(f"📡 上传到论坛: thread_id={thread_id}")
            logger.info(f"   内容长度: {len(content)} 字符")
            if attachments:
                logger.info(f"   附件数: {len(attachments)}")

            # 调用论坛爬虫的回复功能
            success, message = self.crawler_integration.reply_to_post(
                thread_id=thread_id,
                content=content,
                attachments=attachments
            )

            if success:
                logger.info(f"✅ 论坛回复成功: {message}")
                return True
            else:
                logger.error(f"❌ 论坛回复失败: {message}")
                return False

        except Exception as e:
            logger.error(f"❌ 上传到论坛异常: {str(e)}")
            return False
    
    def _update_request_status(self, request_id: str, status: str) -> None:
        """更新请求状态"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE forum_tts_requests
                SET processing_status = ?, last_updated = ?
                WHERE request_id = ?
            """, (status, datetime.now().isoformat(), request_id))

            conn.commit()
            conn.close()

            logger.info(f"✅ 请求状态已更新: {request_id} -> {status}")

        except Exception as e:
            logger.error(f"❌ 更新请求状态异常: {str(e)}")


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("论坛回复上传器测试")
    print("=" * 60)
    
    uploader = TTSForumReplyUploader()
    
    # 测试生成TTS回复
    print("\n测试1：生成TTS回复")
    reply = uploader._generate_tts_reply(
        request_id='test_001',
        file_name='output.wav',
        file_size_mb=2.5,
        user_id='forum_123'
    )
    print(reply)
    
    # 测试生成音色克隆回复
    print("\n测试2：生成音色克隆回复")
    reply = uploader._generate_voice_clone_reply(
        request_id='test_002',
        voice_id='user_123_myvoice',
        voice_name='我的声音',
        user_id='forum_123'
    )
    print(reply)
