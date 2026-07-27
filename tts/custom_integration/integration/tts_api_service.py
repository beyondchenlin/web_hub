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

        # 🎯 初始化数据库连接
        self.db_conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)

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
        voice_name = request_data.get('voice_name', '').strip()
        voice_id_in = request_data.get('voice_id', '').strip()
        speed = request_data.get('speed', 1.0)
        emotion = request_data.get('emotion', '')
        emotion_weight = request_data.get('emotion_weight', 0.5)

        try:
            # 更新状态为处理中
            self._update_request_status(request_id, RequestStatus.PROCESSING)

            logger.info(f"🔄 处理TTS请求: {request_id}")
            logger.info(f"   用户: {user_id}, 文案: {text[:50]}...")
            logger.info(f"   音色: {voice_name or voice_id_in}, 语速: {speed}")

            # 统一权限校验与speaker解析
            resolved_voice_id = None
            if voice_id_in:
                can_use, reason = self.permission_manager.can_use_voice(user_id, voice_id_in)
                if not can_use:
                    logger.error(f"❌ 权限验证失败: {reason}")
                    self._update_request_status(request_id, RequestStatus.FAILED, reason)
                    return False, {'error': reason}
                resolved_voice_id = voice_id_in
            elif voice_name:
                can_use, reason, resolved_voice_id = self.permission_manager.can_use_voice_by_name(
                    user_id, voice_name
                )
                if not can_use or not resolved_voice_id:
                    logger.error(f"❌ 权限验证失败: {reason}")
                    self._update_request_status(request_id, RequestStatus.FAILED, reason)
                    return False, {'error': reason}
            else:
                reason = "❌ 缺少音色参数"
                logger.error(reason)
                self._update_request_status(request_id, RequestStatus.FAILED, reason)
                return False, {'error': reason}

            # 调用TTS API
            audio_data = self._call_tts_api(
                text=text,
                speaker=resolved_voice_id,
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
            
            # 🎯 先预留数据库记录，再创建文件（避免文件垃圾）
            # 如果遇到UNIQUE约束冲突，自动递增编号重试
            max_attempts = 100
            voice_id = None
            base_voice_name = voice_name  # 保存原始音色名称

            for attempt in range(1, max_attempts + 1):
                # 生成 voice_id
                voice_number = self._get_next_voice_number(user_id, base_voice_name)
                temp_voice_id = f"{base_voice_name}_{voice_number + attempt - 1}"

                # 🎯 步骤1：先在数据库中预留记录（状态=创建中）
                success, conflict = self._reserve_voice_id(
                    voice_id=temp_voice_id,
                    voice_name=base_voice_name,
                    user_id=user_id,
                    description=description,
                    duration=duration,
                    is_public=is_public,
                    audio_file=audio_file
                )

                if conflict:
                    # UNIQUE约束冲突，递增编号重试
                    logger.warning(f"⚠️ 音色ID冲突: {temp_voice_id}，尝试下一个编号 (尝试 {attempt}/{max_attempts})")
                    continue
                elif not success:
                    # 其他错误
                    error_msg = "数据库预留失败"
                    logger.error(f"❌ {error_msg}")
                    self._update_request_status(request_id, RequestStatus.FAILED, error_msg)
                    return False, {'error': error_msg}

                # 🎯 步骤2：数据库预留成功，创建音色文件
                logger.info(f"✅ 数据库预留成功: {temp_voice_id}，开始创建音色文件...")
                file_created = self._create_voice_file(
                    audio_file=audio_file,
                    voice_id=temp_voice_id,
                    user_id=user_id
                )

                if file_created:
                    voice_id = temp_voice_id
                    logger.info(f"✅ 音色创建成功: {voice_id}")
                    break
                else:
                    # 文件创建失败，删除数据库记录
                    logger.error(f"❌ 音色文件创建失败，回滚数据库记录: {temp_voice_id}")
                    self._delete_voice_record(temp_voice_id)
                    error_msg = "音色文件创建失败"
                    self._update_request_status(request_id, RequestStatus.FAILED, error_msg)
                    return False, {'error': error_msg}

            if not voice_id:
                error_msg = f"无法创建音色（尝试了{max_attempts}次，都遇到ID冲突）"
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
                # 不再用假音频伪装成功：非200(含引擎500)直接返回 None，
                # 由上游 process_tts_request 统一返回明确的“TTS API调用失败”，
                # 避免把引擎内部错误伪装成高频噪音返回给用户。
                logger.error(f"❌ TTS API返回错误: {response.status_code} | body={response.text[:200]}")
                return None

        except Exception as e:
            logger.error(f"❌ TTS API调用异常: {str(e)}")
            return None
    
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

    def _get_next_voice_number(self, user_id: str, voice_name: str) -> int:
        """
        获取音色的下一个递增编号（全局唯一，不区分用户）

        Args:
            user_id: 用户ID（保留参数，但不使用）
            voice_name: 音色名称

        Returns:
            下一个编号（从1开始）
        """
        try:
            # 🎯 查询数据库中所有该音色名称的编号（不区分用户，确保全局唯一）
            cursor = self.db_conn.cursor()
            cursor.execute('''
                SELECT voice_id FROM voices
                WHERE voice_name = ?
                ORDER BY created_at DESC
            ''', (voice_name,))

            existing_voices = cursor.fetchall()

            if not existing_voices:
                return 1

            # 从voice_id中提取编号
            max_number = 0
            for (voice_id,) in existing_voices:
                # voice_id格式: 冬哥_1, 冬哥_2, ...
                if '_' in voice_id:
                    try:
                        number = int(voice_id.split('_')[-1])
                        max_number = max(max_number, number)
                    except ValueError:
                        continue

            return max_number + 1

        except Exception as e:
            logger.warning(f"⚠️ 获取音色编号失败: {e}，使用默认值1")
            return 1

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

            # 🎯 生成友好的音色ID：音色名称_递增编号
            # 从数据库查询起始编号（作为起点）
            voice_number = self._get_next_voice_number(user_id, voice_name)
            voice_id = f"{voice_name}_{voice_number}"
            logger.info(f"🎯 生成音色ID: {voice_id}")

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

            # 🎯 处理特殊格式：视频文件、非WAV音频格式等，先转换为WAV
            audio_file_to_process = audio_file
            file_ext = os.path.splitext(audio_file)[1].lower()

            # 定义需要转换的格式
            # 视频格式（需要提取音频）
            video_extensions = {'.mp4', '.mov', '.mkv', '.avi', '.flv', '.wmv', '.webm', '.3gp', '.m4v', '.mpg', '.mpeg'}
            # 音频格式（需要转换为WAV以确保兼容性）
            audio_extensions_need_conversion = {'.amr', '.aac', '.m4a', '.ogg', '.opus', '.wma', '.mp3', '.flac'}

            needs_conversion = file_ext in video_extensions or file_ext in audio_extensions_need_conversion

            if needs_conversion:
                if file_ext in video_extensions:
                    logger.info(f"   检测到视频文件 ({file_ext})，使用FFmpeg提取音频...")
                else:
                    logger.info(f"   检测到音频格式 ({file_ext})，使用FFmpeg转换为WAV...")

                try:
                    import subprocess
                    # Build output path from splitext to avoid case-sensitive replace issues (e.g. .MOV)
                    audio_base, _ = os.path.splitext(audio_file)
                    temp_wav = f"{audio_base}_converted.wav"

                    # 🎯 使用项目内置的FFmpeg
                    # 路径：D:\clonetts\tts\indextts2\py312\ffmpeg\bin\ffmpeg.exe
                    ffmpeg_path = os.path.join(
                        os.path.dirname(__file__),
                        '..',
                        '..',
                        'indextts2',
                        'py312',
                        'ffmpeg',
                        'bin',
                        'ffmpeg.exe'
                    )
                    ffmpeg_path = os.path.abspath(ffmpeg_path)

                    # 如果内置FFmpeg不存在，尝试使用系统FFmpeg
                    if not os.path.exists(ffmpeg_path):
                        logger.warning(f"   ⚠️ 内置FFmpeg不存在: {ffmpeg_path}")
                        ffmpeg_path = 'ffmpeg'  # 使用系统PATH中的ffmpeg
                        logger.info(f"   尝试使用系统FFmpeg")
                    else:
                        logger.info(f"   使用内置FFmpeg: {ffmpeg_path}")

                    # 使用FFmpeg转换/提取音频到WAV
                    cmd = [
                        ffmpeg_path, '-i', audio_file,
                        '-vn',           # 不处理视频流（对视频文件重要）
                        '-ar', '22050',  # 采样率
                        '-ac', '1',      # 单声道
                        '-y',            # 覆盖输出文件
                        temp_wav
                    ]

                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0 and os.path.exists(temp_wav):
                        logger.info(f"   ✓ 音频提取/转换成功: {temp_wav}")
                        audio_file_to_process = temp_wav
                    else:
                        logger.error(f"   ❌ FFmpeg处理失败: {result.stderr}")
                        raise Exception(f"音频提取/转换失败: {result.stderr}")

                except FileNotFoundError:
                    logger.error(f"   ❌ 未找到FFmpeg，无法处理该格式")
                    raise Exception("需要安装FFmpeg才能处理视频/AMR格式")
                except Exception as e:
                    logger.error(f"   ❌ 音频提取/转换异常: {e}")
                    raise

            # 加载并标准化音频（22050 Hz）
            logger.info(f"   正在处理音频文件...")
            audio, sr = librosa.load(audio_file_to_process, sr=22050)
            duration = len(audio) / sr
            logger.info(f"   音频时长: {duration:.2f}秒，采样率: {sr}Hz")

            # 🎯 清理临时转换文件
            if audio_file_to_process != audio_file and os.path.exists(audio_file_to_process):
                try:
                    os.remove(audio_file_to_process)
                    logger.info(f"   ✓ 已清理临时文件: {audio_file_to_process}")
                except Exception as e:
                    logger.warning(f"   ⚠️ 清理临时文件失败: {e}")

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
    
    def _reserve_voice_id(self, voice_id: str, voice_name: str, user_id: str,
                          description: str, duration: float, is_public: bool,
                          audio_file: str) -> Tuple[bool, bool]:
        """
        在数据库中预留 voice_id（原子操作）

        Returns:
            (success, conflict):
                - success: 是否预留成功
                - conflict: 是否是UNIQUE约束冲突
        """
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
            return True, False  # 成功，无冲突

        except sqlite3.IntegrityError as e:
            # 🎯 UNIQUE约束冲突
            if 'UNIQUE constraint failed' in str(e):
                logger.debug(f"⚠️ 音色ID已存在: {voice_id}")
                return False, True  # 失败，有冲突
            else:
                logger.error(f"❌ 数据库完整性错误: {str(e)}")
                return False, False  # 失败，其他错误

        except Exception as e:
            logger.error(f"❌ 保存音色信息异常: {str(e)}")
            return False, False  # 失败，其他错误
    
    def _create_voice_file(self, audio_file: str, voice_id: str, user_id: str) -> bool:
        """
        创建音色文件（调用API或本地方案）

        Args:
            audio_file: 音频文件路径
            voice_id: 音色ID
            user_id: 用户ID

        Returns:
            是否创建成功
        """
        try:
            logger.info(f"📡 开始创建音色文件: {voice_id}")
            logger.info(f"   音频文件: {audio_file}")

            # 验证音频文件
            if not os.path.exists(audio_file):
                logger.error(f"❌ 音频文件不存在: {audio_file}")
                return False

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
                    return True
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

            # 方案2: 本地备用方案
            success = self._create_voice_fallback(audio_file, voice_id, user_id)

            if success:
                logger.info(f"✅ 本地方案创建音色成功: {voice_id}")
                return True
            else:
                logger.error(f"❌ 本地方案创建音色失败")
                return False

        except Exception as e:
            logger.error(f"❌ 创建音色文件异常: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _delete_voice_record(self, voice_id: str) -> bool:
        """
        删除数据库中的音色记录（回滚用）

        Args:
            voice_id: 音色ID

        Returns:
            是否删除成功
        """
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM voices WHERE voice_id = ?", (voice_id,))
            conn.commit()
            conn.close()
            logger.info(f"✅ 已删除音色记录: {voice_id}")
            return True
        except Exception as e:
            logger.error(f"❌ 删除音色记录失败: {str(e)}")
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

