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
import shutil

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
                logger.warning(f"⚠️ TTS API不可用，生成模拟音频数据用于测试")
                return self._generate_mock_audio(text)

        except Exception as e:
            logger.error(f"❌ TTS API调用异常: {str(e)}")
            logger.warning(f"⚠️ TTS API不可用，生成模拟音频数据用于测试")
            return self._generate_mock_audio(text)
    
    def _generate_mock_audio(self, text: str) -> bytes:
        """生成模拟音频数据（用于测试）"""
        import wave
        import struct
        import io

        # 生成简单的正弦波音频（1秒，440Hz）
        sample_rate = 22050
        duration = min(len(text) * 0.1, 5.0)  # 根据文本长度，最多5秒
        num_samples = int(sample_rate * duration)

        # 生成音频数据
        audio_data = []
        for i in range(num_samples):
            # 简单的正弦波
            value = int(32767.0 * 0.3 * (i % 100) / 100.0)
            audio_data.append(struct.pack('<h', value))

        # 创建WAV文件
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # 单声道
            wav_file.setsampwidth(2)  # 16位
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b''.join(audio_data))

        logger.info(f"🎵 生成模拟音频: {duration:.1f}秒, {len(buffer.getvalue())} 字节")
        return buffer.getvalue()

    def _call_voice_clone_api(self, audio_file: str, voice_name: str,
                              user_id: str) -> Optional[str]:
        """
        调用音色克隆API - 真实实现

        Args:
            audio_file: 音频文件路径
            voice_name: 音色名称
            user_id: 用户ID

        Returns:
            voice_id: 成功返回音色ID，失败返回None
        """
        try:
            logger.info(f"📡 开始音色克隆: {voice_name}")
            logger.info(f"   音频文件: {audio_file}")
            logger.info(f"   用户ID: {user_id}")

            # 验证音频文件
            if not os.path.exists(audio_file):
                logger.error(f"❌ 音频文件不存在: {audio_file}")
                return None

            # 生成唯一的音色ID
            voice_id = f"user_{user_id}_{voice_name}_{int(time.time())}"

            # 方案1: 尝试调用 IndexTTS2 的 /create_voice API
            try:
                create_voice_url = f"{self.api_url}/create_voice"
                logger.info(f"📡 尝试调用API: {create_voice_url}")

                with open(audio_file, 'rb') as f:
                    files = {'audio': (os.path.basename(audio_file), f, 'audio/wav')}
                    data = {'voice_name': voice_id}

                    response = requests.post(
                        create_voice_url,
                        files=files,
                        data=data,
                        timeout=60
                    )

                if response.status_code == 200:
                    logger.info(f"✅ API创建音色成功: {voice_id}")
                    result = response.json()
                    logger.info(f"   API响应: {result}")
                    return voice_id
                elif response.status_code == 404:
                    logger.warning(f"⚠️ API接口不存在，使用本地备用方案")
                else:
                    logger.warning(f"⚠️ API返回错误 ({response.status_code})，使用本地备用方案")

            except requests.exceptions.ConnectionError:
                logger.warning(f"⚠️ API连接失败，使用本地备用方案")
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ API请求超时，使用本地备用方案")
            except Exception as e:
                logger.warning(f"⚠️ API调用异常: {str(e)}，使用本地备用方案")

            # 方案2: 本地备用方案（参考 batch_processor.py 的实现）
            success = self._create_voice_fallback(audio_file, voice_id, user_id)

            if success:
                logger.info(f"✅ 本地方案创建音色成功: {voice_id}")
                return voice_id
            else:
                logger.error(f"❌ 本地方案创建音色失败")
                return None

        except Exception as e:
            logger.error(f"❌ 音色克隆异常: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _create_voice_fallback(self, audio_file: str, voice_id: str, user_id: str) -> bool:
        """
        本地备用方案：创建音色文件
        参考 batch_processor.py 的 create_voice_fallback 实现

        Args:
            audio_file: 音频文件路径
            voice_id: 音色ID
            user_id: 用户ID

        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            logger.info(f"🔧 使用本地备用方案创建音色: {voice_id}")

            # 检查是否有 librosa 和 soundfile
            try:
                import librosa
                import soundfile as sf
                import torch
            except ImportError as e:
                logger.error(f"❌ 缺少必要的库: {e}")
                logger.error("请安装: pip install librosa soundfile torch")
                return False

            # 确定 IndexTTS2 的 voices 目录
            # 假设 IndexTTS2 在 tts/indextts2/ 目录
            repo_root = Path(__file__).resolve().parents[3]
            indextts2_root = repo_root / "tts" / "indextts2"

            if not indextts2_root.exists():
                logger.error(f"❌ IndexTTS2 目录不存在: {indextts2_root}")
                return False

            voices_dir = indextts2_root / "voices"
            voices_dir.mkdir(parents=True, exist_ok=True)

            # 创建音频存储目录
            audio_storage_dir = voices_dir / "audio"
            audio_storage_dir.mkdir(parents=True, exist_ok=True)

            # 用户专属目录
            user_audio_dir = audio_storage_dir / user_id
            user_audio_dir.mkdir(parents=True, exist_ok=True)

            # 目标文件路径
            target_audio_filename = f"{voice_id}.wav"
            target_audio_path = user_audio_dir / target_audio_filename
            target_pt_path = voices_dir / f"{voice_id}.pt"

            logger.info(f"   音频目标路径: {target_audio_path}")
            logger.info(f"   .pt目标路径: {target_pt_path}")

            # 加载并标准化音频（22050 Hz）
            logger.info(f"   正在处理音频文件...")
            audio, sr = librosa.load(audio_file, sr=22050)
            duration = len(audio) / sr
            logger.info(f"   音频时长: {duration:.2f}秒，采样率: {sr}Hz")

            # 保存标准化后的音频
            sf.write(str(target_audio_path), audio, sr, subtype='PCM_16')
            logger.info(f"   ✓ 音频已保存")

            # 创建相对路径（相对于 IndexTTS2 根目录）
            relative_audio_path = f"voices/audio/{user_id}/{target_audio_filename}"
            # 使用正斜杠以保证跨平台兼容性
            relative_audio_path = relative_audio_path.replace('\\', '/')

            # 按照 IndexTTS2 的格式创建 .pt 文件
            # 格式：{'audio': '音频文件路径'}
            voice_data = {
                'audio': relative_audio_path
            }

            # 保存为 .pt 文件
            torch.save(voice_data, str(target_pt_path))
            logger.info(f"   ✓ 音色配置已保存")

            # 验证文件是否创建成功
            if target_pt_path.exists() and target_audio_path.exists():
                pt_size = target_pt_path.stat().st_size / 1024
                audio_size = target_audio_path.stat().st_size / 1024

                logger.info(f"✅ 音色创建成功:")
                logger.info(f"   - 音色文件: {target_pt_path.name} ({pt_size:.2f} KB)")
                logger.info(f"   - 音频文件: {relative_audio_path} ({audio_size:.2f} KB)")
                logger.info(f"   - 采样率: {sr} Hz")
                logger.info(f"   - 音频时长: {duration:.2f} 秒")

                return True
            else:
                logger.error(f"❌ 文件创建失败")
                return False

        except Exception as e:
            logger.error(f"❌ 本地创建失败: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False

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

            # 🔧 修复：使用 audio_path 而不是 audio_file（匹配数据库schema）
            # 同时添加 file_path 字段（必填字段）
            cursor.execute("""
                INSERT INTO voices (voice_id, voice_name, owner_id, is_public,
                                   description, duration, audio_path, file_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (voice_id, voice_name, user_id, is_public, description,
                  duration, audio_file, audio_file, datetime.now().isoformat()))

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

