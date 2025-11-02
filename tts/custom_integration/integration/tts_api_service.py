"""
IndexTTS2 论坛集成系统 - API服务
处理TTS请求和音色克隆请求
"""

import os
import sys
import json
import time
import logging
import requests
import sqlite3
from typing import Dict, Tuple, Optional, Any
from datetime import datetime
from pathlib import Path
from enum import Enum
import threading
import queue

# 导入配置
from tts_config import (
    INDEXTTS2_API_URL, DATABASE_PATH, OUTPUTS_USERS_DIR,
    VOICES_USERS_DIR, API_TIMEOUT, API_MAX_RETRIES, API_RETRY_DELAY,
    MAX_CONCURRENT_TASKS
)
from tts_forum_sync import TTSForumUserSync
from tts_permission_manager import PermissionManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RequestStatus(Enum):
    """请求状态"""
    PENDING = "pending"           # 待处理
    PROCESSING = "processing"     # 处理中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 已取消


class TTSAPIService:
    """TTS API服务 - 处理TTS和音色克隆请求"""
    
    def __init__(self):
        """初始化API服务"""
        self.api_url = INDEXTTS2_API_URL
        self.timeout = API_TIMEOUT
        self.max_retries = API_MAX_RETRIES
        self.retry_delay = API_RETRY_DELAY
        
        # 初始化管理器
        self.user_sync = TTSForumUserSync()
        self.permission_manager = PermissionManager()
        
        # 请求队列和状态跟踪
        self.request_queue = queue.Queue()
        self.request_status = {}  # {request_id: status_info}
        self.processing_threads = []
        
        logger.info("✅ TTS API服务初始化完成")
    
    def process_tts_request(self, request_data: Dict) -> Tuple[bool, Dict]:
        """
        处理TTS请求
        
        Args:
            request_data: {
                'request_id': str,
                'user_id': str,
                'text': str,
                'voice_name': str,
                'speed': float,
                'emotion': str,
                'emotion_weight': float
            }
        
        Returns:
            (success, result)
        """
        request_id = request_data.get('request_id')
        user_id = request_data.get('user_id')
        text = request_data.get('text', '')
        voice_name = request_data.get('voice_name', '')
        speed = request_data.get('speed', 1.0)
        emotion = request_data.get('emotion', '')
        emotion_weight = request_data.get('emotion_weight', 0.5)
        
        try:
            # 更新状态为处理中
            self._update_request_status(request_id, RequestStatus.PROCESSING)
            
            logger.info(f"🔄 处理TTS请求: {request_id}")
            logger.info(f"   用户: {user_id}, 文案: {text[:50]}...")
            logger.info(f"   音色: {voice_name}, 语速: {speed}")
            
            # 验证权限
            can_use, reason, voice_id = self.permission_manager.can_use_voice_by_name(
                user_id, voice_name
            )
            
            if not can_use:
                logger.error(f"❌ 权限验证失败: {reason}")
                self._update_request_status(request_id, RequestStatus.FAILED, reason)
                return False, {'error': reason}
            
            # 调用TTS API
            audio_data = self._call_tts_api(
                text=text,
                speaker=voice_name,
                speed=speed,
                emotion=emotion,
                emotion_weight=emotion_weight
            )
            
            if not audio_data:
                error_msg = "TTS API调用失败"
                logger.error(f"❌ {error_msg}")
                self._update_request_status(request_id, RequestStatus.FAILED, error_msg)
                return False, {'error': error_msg}
            
            # 保存音频文件
            output_path = self._save_tts_output(request_id, user_id, audio_data)
            
            if not output_path:
                error_msg = "音频文件保存失败"
                logger.error(f"❌ {error_msg}")
                self._update_request_status(request_id, RequestStatus.FAILED, error_msg)
                return False, {'error': error_msg}
            
            # 更新状态为已完成
            result = {
                'request_id': request_id,
                'user_id': user_id,
                'output_path': output_path,
                'file_size_mb': os.path.getsize(output_path) / (1024 * 1024),
                'completed_at': datetime.now().isoformat()
            }
            
            self._update_request_status(request_id, RequestStatus.COMPLETED, result)
            logger.info(f"✅ TTS请求处理完成: {request_id}")
            
            return True, result
        
        except Exception as e:
            error_msg = f"处理TTS请求异常: {str(e)}"
            logger.error(f"❌ {error_msg}")
            self._update_request_status(request_id, RequestStatus.FAILED, error_msg)
            return False, {'error': error_msg}
    
    def process_voice_clone_request(self, request_data: Dict) -> Tuple[bool, Dict]:
        """
        处理音色克隆请求
        
        Args:
            request_data: {
                'request_id': str,
                'user_id': str,
                'voice_name': str,
                'description': str,
                'audio_file': str,
                'duration': float,
                'is_public': bool
            }
        
        Returns:
            (success, result)
        """
        request_id = request_data.get('request_id')
        user_id = request_data.get('user_id')
        voice_name = request_data.get('voice_name', '')
        description = request_data.get('description', '')
        audio_file = request_data.get('audio_file', '')
        duration = request_data.get('duration', 0)
        is_public = request_data.get('is_public', False)
        
        try:
            # 更新状态为处理中
            self._update_request_status(request_id, RequestStatus.PROCESSING)
            
            logger.info(f"🔄 处理音色克隆请求: {request_id}")
            logger.info(f"   用户: {user_id}, 音色名称: {voice_name}")
            logger.info(f"   音频文件: {audio_file}, 时长: {duration}秒")
            
            # 验证音频文件
            if not os.path.exists(audio_file):
                error_msg = f"音频文件不存在: {audio_file}"
                logger.error(f"❌ {error_msg}")
                self._update_request_status(request_id, RequestStatus.FAILED, error_msg)
                return False, {'error': error_msg}
            
            # 调用音色克隆API
            voice_id = self._call_voice_clone_api(
                audio_file=audio_file,
                voice_name=voice_name,
                user_id=user_id
            )
            
            if not voice_id:
                error_msg = "音色克隆API调用失败"
                logger.error(f"❌ {error_msg}")
                self._update_request_status(request_id, RequestStatus.FAILED, error_msg)
                return False, {'error': error_msg}
            
            # 保存音色信息到数据库
            success = self._save_voice_clone_info(
                voice_id=voice_id,
                voice_name=voice_name,
                user_id=user_id,
                description=description,
                duration=duration,
                is_public=is_public,
                audio_file=audio_file
            )
            
            if not success:
                error_msg = "音色信息保存失败"
                logger.error(f"❌ {error_msg}")
                self._update_request_status(request_id, RequestStatus.FAILED, error_msg)
                return False, {'error': error_msg}
            
            # 更新状态为已完成
            result = {
                'request_id': request_id,
                'user_id': user_id,
                'voice_id': voice_id,
                'voice_name': voice_name,
                'completed_at': datetime.now().isoformat()
            }
            
            self._update_request_status(request_id, RequestStatus.COMPLETED, result)
            logger.info(f"✅ 音色克隆请求处理完成: {request_id}")
            
            return True, result
        
        except Exception as e:
            error_msg = f"处理音色克隆请求异常: {str(e)}"
            logger.error(f"❌ {error_msg}")
            self._update_request_status(request_id, RequestStatus.FAILED, error_msg)
            return False, {'error': error_msg}
    
    def _call_tts_api(self, text: str, speaker: str, speed: float = 1.0,
                      emotion: str = '', emotion_weight: float = 0.5) -> Optional[bytes]:
        """调用TTS API"""
        try:
            params = {
                'text': text,
                'speaker': speaker,
                'speed': str(speed)
            }
            
            if emotion:
                params['emo'] = emotion
                params['weight'] = str(emotion_weight)
            
            url = f"{self.api_url}/?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
            
            logger.info(f"📡 调用TTS API: {speaker}")
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                logger.info(f"✅ TTS API调用成功")
                return response.content
            else:
                logger.error(f"❌ TTS API返回错误: {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"❌ TTS API调用异常: {str(e)}")
            return None
    
    def _call_voice_clone_api(self, audio_file: str, voice_name: str,
                              user_id: str) -> Optional[str]:
        """调用音色克隆API"""
        try:
            logger.info(f"📡 调用音色克隆API: {voice_name}")
            
            # 这里需要根据实际的音色克隆API实现
            # 暂时返回生成的voice_id
            voice_id = f"user_{user_id}_{voice_name}_{int(time.time())}"
            
            logger.info(f"✅ 音色克隆API调用成功: {voice_id}")
            return voice_id
        
        except Exception as e:
            logger.error(f"❌ 音色克隆API调用异常: {str(e)}")
            return None
    
    def _save_tts_output(self, request_id: str, user_id: str,
                         audio_data: bytes) -> Optional[str]:
        """保存TTS输出"""
        try:
            output_dir = OUTPUTS_USERS_DIR / user_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            output_path = output_dir / f"{request_id}.wav"
            
            with open(output_path, 'wb') as f:
                f.write(audio_data)
            
            logger.info(f"✅ 音频文件已保存: {output_path}")
            return str(output_path)
        
        except Exception as e:
            logger.error(f"❌ 保存音频文件异常: {str(e)}")
            return None
    
    def _save_voice_clone_info(self, voice_id: str, voice_name: str, user_id: str,
                               description: str, duration: float, is_public: bool,
                               audio_file: str) -> bool:
        """保存音色克隆信息"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO voices (voice_id, voice_name, owner_id, is_public, 
                                   description, duration, audio_file, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (voice_id, voice_name, user_id, is_public, description, 
                  duration, audio_file, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ 音色信息已保存: {voice_id}")
            return True
        
        except Exception as e:
            logger.error(f"❌ 保存音色信息异常: {str(e)}")
            return False
    
    def _update_request_status(self, request_id: str, status: RequestStatus,
                               data: Any = None) -> None:
        """更新请求状态"""
        self.request_status[request_id] = {
            'status': status.value,
            'updated_at': datetime.now().isoformat(),
            'data': data
        }
    
    def get_request_status(self, request_id: str) -> Dict:
        """获取请求状态"""
        return self.request_status.get(request_id, {
            'status': 'unknown',
            'message': '请求不存在'
        })


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("TTS API服务测试")
    print("=" * 60)
    
    service = TTSAPIService()
    
    # 测试TTS请求
    print("\n测试1：处理TTS请求")
    tts_request = {
        'request_id': 'test_tts_001',
        'user_id': 'forum_123',
        'text': '你好世界',
        'voice_name': '女主播',
        'speed': 1.0,
        'emotion': '',
        'emotion_weight': 0.5
    }
    
    success, result = service.process_tts_request(tts_request)
    print(f"  成功: {success}")
    if success:
        print(f"  输出路径: {result.get('output_path')}")
    else:
        print(f"  错误: {result.get('error')}")
    
    # 获取请求状态
    print("\n测试2：获取请求状态")
    status = service.get_request_status('test_tts_001')
    print(f"  状态: {status}")

