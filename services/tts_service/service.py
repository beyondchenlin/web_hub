"""
TTSTaskService 封装 IndexTTS2 集成模块，为 Web Hub 提供统一的任务处理接口。

当前实现仅作为骨架，提供路径注入、模块加载和方法占位。后续可在此处
实现真正的任务消费、状态回写与错误处理逻辑。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional


class TTSTaskService:
    """封装 TTS/音色克隆任务处理的服务层接口。"""

    def __init__(self, integration_root: Optional[Path | str] = None) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        default_root = repo_root / "tts" / "custom_integration" / "integration"

        self.integration_root = Path(integration_root or default_root).resolve()
        if not self.integration_root.exists():
            raise FileNotFoundError(f"未找到 TTS 集成目录: {self.integration_root}")

        self._ensure_sys_path()

        # 延迟加载实际模块，避免在初始化时产生副作用
        self._api_service_cls = None
        self._processor_cls = None
        self._reply_uploader_cls = None

    # ------------------------------------------------------------------ #
    # 模块加载与公共工具
    # ------------------------------------------------------------------ #
    def _ensure_sys_path(self) -> None:
        """确保集成目录在 sys.path 中，便于后续按模块名导入。"""
        path_str = str(self.integration_root)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    def _load_api_service(self):
        if self._api_service_cls is None:
            from tts_api_service import TTSAPIService

            self._api_service_cls = TTSAPIService
        return self._api_service_cls()

    def _load_processor(self):
        if self._processor_cls is None:
            from tts_forum_processor import TTSForumProcessor

            self._processor_cls = TTSForumProcessor
        return self._processor_cls()

    def _load_reply_uploader(self):
        if self._reply_uploader_cls is None:
            from tts_forum_reply_uploader import TTSForumReplyUploader

            self._reply_uploader_cls = TTSForumReplyUploader
        return self._reply_uploader_cls()

    # ------------------------------------------------------------------ #
    # 任务处理占位方法
    # ------------------------------------------------------------------ #
    def _download_audio_file(self, audio_url: str, request_id: str) -> Optional[str]:
        """
        从URL下载音频/视频文件到本地

        注意：视频文件的音频提取由 tts_api_service.py 的 _create_voice_fallback 方法处理

        Args:
            audio_url: 音频/视频文件URL
            request_id: 请求ID（用于生成文件名）

        Returns:
            本地文件路径，失败返回None
        """
        import requests
        import os
        from pathlib import Path

        try:
            # 确定保存路径
            uploads_dir = self.integration_root / "uploads" / "temp"
            uploads_dir.mkdir(parents=True, exist_ok=True)

            # 从URL提取文件扩展名
            ext = os.path.splitext(audio_url.split('?')[0])[1] or '.wav'
            local_path = uploads_dir / f"{request_id}{ext}"

            # 下载文件
            print(f"🔽 开始下载文件: {audio_url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(audio_url, headers=headers, timeout=60, stream=True)
            response.raise_for_status()

            # 保存文件
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            file_size_mb = os.path.getsize(local_path) / (1024 * 1024)
            print(f"✅ 文件下载完成: {local_path} ({file_size_mb:.2f} MB)")

            return str(local_path)

        except Exception as e:
            print(f"❌ 文件下载失败: {e}")
            return None

    def _convert_forum_payload_to_tts_format(self, forum_payload: Dict[str, Any], request_type: str) -> Dict[str, Any]:
        """
        将论坛任务payload转换为TTS API期望的格式

        Args:
            forum_payload: 论坛任务payload，包含 thread_id, post_id, author_id, audio_urls 等
            request_type: 请求类型 ('tts' 或 'voice_clone')

        Returns:
            TTS API期望的格式
        """
        import uuid

        # 生成唯一的request_id
        request_id = str(uuid.uuid4())

        # 🎯 提取音频URL（支持多种格式）
        # 格式1：audio_url (单个URL，新格式)
        # 格式2：audio_urls (URL数组，旧格式)
        # 格式3：video_urls (视频文件也可以用于音色克隆，提取音频)
        audio_url = forum_payload.get('audio_url', '')
        if not audio_url:
            audio_urls = forum_payload.get('audio_urls', [])
            audio_url = audio_urls[0] if audio_urls else ''

        # 🎯 如果没有音频URL，尝试从视频URL中提取（视频可以提取音频用于克隆）
        if not audio_url:
            video_urls = forum_payload.get('video_urls', [])
            if video_urls:
                audio_url = video_urls[0]
                print(f"🎬 从视频URL中提取音频: {audio_url}")

        print(f"🔍 [DEBUG] 提取到的audio_url: {audio_url}")

        # 🔧 关键修复：下载音频文件到本地
        audio_file = ''
        if audio_url:
            audio_file = self._download_audio_file(audio_url, request_id)
            if not audio_file:
                print(f"⚠️ 音频文件下载失败，使用URL: {audio_url}")
                audio_file = audio_url  # 回退到URL

        # 🎯 提取文本内容（优先使用core_text，已过滤表单字段）
        title = forum_payload.get('title', '')
        content = forum_payload.get('content', '')
        core_text = forum_payload.get('core_text', '')  # 优先使用过滤后的文本

        # 🎯 使用TTSRequestParser解析帖子内容，提取参数
        parsed_params = {}
        if request_type == 'voice_clone':
            try:
                # 动态导入TTSRequestParser
                import sys
                import os
                tts_integration_path = os.path.join(os.path.dirname(__file__), '..', '..', 'tts', 'custom_integration', 'integration')
                if tts_integration_path not in sys.path:
                    sys.path.insert(0, tts_integration_path)

                from tts_request_parser import TTSRequestParser

                # 解析音色克隆请求
                audio_urls = forum_payload.get('audio_urls', [])
                video_urls = forum_payload.get('video_urls', [])
                success, params = TTSRequestParser.parse_voice_clone_request(
                    title,
                    content,
                    audio_urls=audio_urls,
                    video_urls=video_urls
                )
                if success:
                    parsed_params = params
                    print(f"✅ 解析音色克隆参数成功: 音色名称={params.get('clone_voice_name')}")
                else:
                    print(f"⚠️ 解析音色克隆参数失败: {params.get('error')}")
            except Exception as e:
                print(f"⚠️ TTSRequestParser解析异常: {e}")

        # 🎯 从content中解析音色名称（如果有"选择音色:"字段，用于TTS请求）
        voice_name = forum_payload.get('voice_name', '')
        if not voice_name and content and request_type == 'tts':
            import re
            # 查找"选择音色:"后面的内容
            voice_match = re.search(r'选择音色\s*[:：]\s*([^\n]+)', content)
            if voice_match:
                voice_name = voice_match.group(1).strip()
                print(f"🎤 从帖子内容中解析到音色: {voice_name}")

        if request_type == 'voice_clone':
            # 音色克隆请求
            # 🎯 优先使用解析出的参数，回退到原始数据
            clone_voice_name = parsed_params.get('clone_voice_name') or forum_payload.get('clone_voice_name') or title or '未命名音色'

            return {
                'request_id': request_id,
                'user_id': forum_payload.get('author_id', ''),
                'voice_name': clone_voice_name,
                'description': parsed_params.get('description') or forum_payload.get('description') or core_text or content,
                'audio_file': audio_file,
                'duration': 0,  # 需要实际计算音频时长
                'is_public': parsed_params.get('clone_is_public', False) or forum_payload.get('clone_is_public', False),
                # 保留原始论坛信息
                'thread_id': forum_payload.get('thread_id'),
                'post_id': forum_payload.get('post_id'),
            }
        else:
            # TTS合成请求
            # 🎯 优先使用core_text（已过滤表单字段），回退到content或title
            tts_text = core_text or content or title

            # 🎯 音色名称解析交给 VoiceMapper 统一处理
            # 这里只传递原始的 voice_name，不做任何解析

            return {
                'request_id': request_id,
                'user_id': forum_payload.get('author_id', ''),
                'text': tts_text,
                'voice_name': voice_name,  # 使用解析出的音色名称
                'output_format': 'mp3',
                'speed': forum_payload.get('speed', 1.0),
                'emotion': forum_payload.get('emotion', ''),
                'emotion_weight': forum_payload.get('emotion_weight', 0.5),
                # 保留原始论坛信息
                'thread_id': forum_payload.get('thread_id'),
                'post_id': forum_payload.get('post_id'),
            }

    def handle_tts_task(self, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理语音合成任务。

        Args:
            task_payload: 统一任务结构中的 payload 字段。

        Returns:
            标准化的处理结果，具体结构待后续统一规范。
        """
        # 🔧 数据转换：将论坛任务payload转换为TTS API期望的格式
        converted_payload = self._convert_forum_payload_to_tts_format(task_payload, 'tts')

        # 🔧 解析音色名称（支持"本人音色"等别名）
        user_id = converted_payload.get('user_id')
        voice_name = converted_payload.get('voice_name', '')  # 用户输入的音色名称

        if voice_name:
            try:
                from voice_mapper import VoiceMapper
                mapper = VoiceMapper()
                actual_voice_id, reason = mapper.resolve_voice_name(user_id, voice_name)
                converted_payload['voice_id'] = actual_voice_id
                print(f"🔍 音色解析: {voice_name} → {actual_voice_id}")
                print(f"   说明: {reason}")
            except Exception as e:
                print(f"⚠️ 音色解析失败，使用原始名称: {e}")

        api_service = self._load_api_service()
        success, result = api_service.process_tts_request(converted_payload)
        return {"success": success, "result": result}

    def handle_voice_clone_task(self, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理音色克隆任务。

        Args:
            task_payload: 统一任务结构中的 payload 字段。

        Returns:
            标准化的处理结果。
        """
        # 🔧 数据转换：将论坛任务payload转换为TTS API期望的格式
        converted_payload = self._convert_forum_payload_to_tts_format(task_payload, 'voice_clone')

        api_service = self._load_api_service()
        success, result = api_service.process_voice_clone_request(converted_payload)

        # 🔧 如果克隆成功，保存用户音色映射
        if success and result.get('voice_id'):
            try:
                from voice_mapper import VoiceMapper
                mapper = VoiceMapper()
                mapper.save_user_voice(
                    user_id=converted_payload.get('user_id'),
                    voice_id=result.get('voice_id'),
                    voice_name=converted_payload.get('voice_name'),
                    file_path=result.get('file_path', ''),
                    audio_path=result.get('audio_path', ''),
                    duration=result.get('duration', 0.0),
                    file_size_mb=result.get('file_size_mb', 0.0),
                    is_public=converted_payload.get('is_public', False),
                    description=converted_payload.get('description', ''),
                    set_as_default=True  # 设为用户的默认音色
                )
                print(f"✅ 已保存用户音色映射: {converted_payload.get('user_id')} -> {result.get('voice_id')}")
            except Exception as e:
                print(f"⚠️ 保存用户音色映射失败: {e}")

        return {"success": success, "result": result}

    def format_forum_reply(self, processed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用现有回复模块生成论坛回帖内容，统一封装返回结构。

        Args:
            processed_data: 需要回帖的数据。

        Returns:
            包含回帖正文与附件信息的字典。
        """
        reply_uploader = self._load_reply_uploader()
        reply_type = processed_data.get("request_type")

        if reply_type == "tts":
            reply_content = reply_uploader._generate_tts_reply(
                processed_data.get("request_id", ""),
                processed_data.get("file_name", ""),
                processed_data.get("file_size_mb", 0.0),
                processed_data.get("user_id", ""),
            )
            attachments = [processed_data.get("output_path")] if processed_data.get("output_path") else []
        elif reply_type == "voice_clone":
            reply_content = reply_uploader._generate_voice_clone_reply(
                processed_data.get("request_id", ""),
                processed_data.get("voice_id", ""),
                processed_data.get("voice_name", ""),
                processed_data.get("user_id", ""),
            )
            attachments = []
        else:
            reply_content = f"❌ 未知的任务类型: {reply_type}"
            attachments = []

        return {
            "content": reply_content,
            "attachments": attachments,
        }


__all__ = ["TTSTaskService"]
