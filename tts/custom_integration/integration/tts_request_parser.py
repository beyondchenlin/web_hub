"""
TTS请求解析模块

功能：
1. 识别帖子类型（TTS或音色克隆）
2. 从帖子内容提取参数
3. 验证参数格式
"""

import re
import json
from typing import Dict, Tuple, Optional, List

class TTSRequestParser:
    """TTS请求解析器"""

    # 帖子类型标记（支持多种格式）
    TTS_MARKERS = ["【制作AI声音】", "[制作AI声音]", "制作AI声音"]
    VOICE_CLONE_MARKERS = ["【音色克隆】", "[音色克隆]", "音色克隆"]

    # 兼容旧代码
    TTS_MARKER = "【制作AI声音】"
    VOICE_CLONE_MARKER = "【音色克隆】"

    # 参数标记（支持括号格式和冒号格式）
    PARAM_MARKERS = {
        'text': ['【文案】', '[文案]', '文案:', '【文本】', '[文本]', '文本:', '【内容】', '[内容]', '内容:'],
        'voice': ['【选择音色】', '[选择音色]', '选择音色:', '【音色】', '[音色]', '音色:', '【声音】', '[声音]', '声音:'],
        'speed': ['【语速】', '[语速]', '语速:', '【速度】', '[速度]', '速度:'],
        'emotion': ['【情感】', '[情感]', '情感:', '【感情】', '[感情]', '感情:'],
        'emotion_weight': ['【情感权重】', '[情感权重]', '情感权重:', '【权重】', '[权重]', '权重:'],
        'voice_name': ['【音色名称】', '[音色名称]', '音色名称:', '【克隆名称】', '[克隆名称]', '克隆名称:'],
        'is_public': ['【是否公开】', '[是否公开]', '是否公开:', '【公开】', '[公开]', '公开:'],
        'description': ['【描述】', '[描述]', '描述:', '【说明】', '[说明]', '说明:', '【给自己的音色起个名词】', '[给自己的音色起个名词]'],
    }

    @staticmethod
    def detect_request_type(post_data: Dict) -> Dict:
        """
        智能识别请求类型

        返回: {
            'type': 'tts' | 'voice_clone' | 'unknown',
            'confidence': 0-100,
            'reason': str,
            'method': str
        }
        """
        title = post_data.get('title', '')
        content = post_data.get('content', '')
        tags = post_data.get('tags', [])
        attachments = post_data.get('attachments', [])

        # 第1步：检查标签（优先级最高）- 支持多种格式
        # 检查TTS标记
        for marker in TTSRequestParser.TTS_MARKERS:
            if marker in title or any(marker in tag for tag in tags):
                return {
                    'type': 'tts',
                    'confidence': 99,
                    'reason': f'帖子标签明确标注为 {marker}',
                    'method': 'tag_detection'
                }

        # 检查音色克隆标记
        for marker in TTSRequestParser.VOICE_CLONE_MARKERS:
            if marker in title or any(marker in tag for tag in tags):
                return {
                    'type': 'voice_clone',
                    'confidence': 99,
                    'reason': f'帖子标签明确标注为 {marker}',
                    'method': 'tag_detection'
                }

        # 第2步：检查内容字段
        # 检查TTS相关字段
        if any(marker in content for marker in TTSRequestParser.PARAM_MARKERS['text']):
            return {
                'type': 'tts',
                'confidence': 95,
                'reason': '内容包含文案字段',
                'method': 'field_detection'
            }

        # 检查"选择音色"字段（TTS请求特有）
        if any(marker in content for marker in TTSRequestParser.PARAM_MARKERS['voice']):
            return {
                'type': 'tts',
                'confidence': 90,
                'reason': '内容包含选择音色字段',
                'method': 'field_detection'
            }

        # 检查音色克隆相关字段
        if any(marker in content for marker in TTSRequestParser.PARAM_MARKERS['voice_name']):
            return {
                'type': 'voice_clone',
                'confidence': 95,
                'reason': '内容包含音色名称字段',
                'method': 'field_detection'
            }

        # 第3步：检查附件特征
        if attachments:
            audio_count = sum(1 for a in attachments if a.get('type') in ['audio', 'generated'])
            video_count = sum(1 for a in attachments if a.get('type') == 'video')
            original_count = sum(1 for a in attachments if a.get('type') == 'original')

            # 仅有生成的音频文件
            if audio_count > 0 and video_count == 0 and original_count == 0:
                return {
                    'type': 'tts',
                    'confidence': 90,
                    'reason': '仅包含生成的音频文件',
                    'method': 'attachment_detection'
                }

            # 有原始音频/视频文件
            if (video_count > 0 or original_count > 0) and audio_count == 0:
                return {
                    'type': 'voice_clone',
                    'confidence': 90,
                    'reason': '包含原始音频/视频文件',
                    'method': 'attachment_detection'
                }

        # 第4步：检查文件大小
        if attachments:
            total_size = sum(a.get('size', 0) for a in attachments)
            if total_size > 0:
                size_mb = total_size / (1024 * 1024)
                if size_mb < 5:
                    return {
                        'type': 'tts',
                        'confidence': 85,
                        'reason': f'文件总大小 {size_mb:.1f}MB < 5MB',
                        'method': 'size_detection'
                    }
                else:
                    return {
                        'type': 'voice_clone',
                        'confidence': 85,
                        'reason': f'文件总大小 {size_mb:.1f}MB > 5MB',
                        'method': 'size_detection'
                    }

        # 无法判断
        return {
            'type': 'unknown',
            'confidence': 0,
            'reason': '无法识别请求类型',
            'method': 'unknown'
        }

    @staticmethod
    def is_tts_request(title: str) -> bool:
        """检查是否是TTS请求"""
        return TTSRequestParser.TTS_MARKER in title

    @staticmethod
    def is_voice_clone_request(title: str) -> bool:
        """检查是否是音色克隆请求"""
        return TTSRequestParser.VOICE_CLONE_MARKER in title
    
    @staticmethod
    def extract_parameter(content: str, markers: List[str]) -> str:
        """
        从内容中提取参数

        支持格式：
        1. 【标记】内容【下一个标记】
        2. [标记]内容[下一个标记]
        3. 标记:\n内容
        """
        for marker in markers:
            # 查找标记位置
            start_idx = content.find(marker)
            if start_idx == -1:
                continue

            # 从标记后开始
            start_idx += len(marker)

            # 跳过冒号后的空白字符（如果是冒号格式）
            if marker.endswith(':'):
                # 冒号格式：取到下一行或下一个标记
                remaining = content[start_idx:]
                # 查找下一个换行符
                newline_idx = remaining.find('\n')
                if newline_idx != -1:
                    # 取第一行作为值
                    value = remaining[:newline_idx].strip()
                    if value:
                        return value
                    # 如果第一行为空，取下一行
                    remaining = remaining[newline_idx+1:]
                    next_newline = remaining.find('\n')
                    if next_newline != -1:
                        value = remaining[:next_newline].strip()
                    else:
                        value = remaining.strip()
                    if value:
                        return value
                else:
                    value = remaining.strip()
                    if value:
                        return value
            else:
                # 括号格式：查找下一个标记（支持【、[和换行）
                end_idx_1 = content.find('【', start_idx)
                end_idx_2 = content.find('[', start_idx)
                end_idx_3 = content.find('\n', start_idx)

                # 收集所有有效的结束位置
                end_indices = [idx for idx in [end_idx_1, end_idx_2, end_idx_3] if idx != -1]

                if not end_indices:
                    # 如果没有下一个标记，取到末尾
                    value = content[start_idx:].strip()
                else:
                    # 取最近的一个
                    end_idx = min(end_indices)
                    value = content[start_idx:end_idx].strip()

                if value:
                    return value

        return ""
    
    @staticmethod
    def parse_tts_request(title: str, content: str) -> Tuple[bool, Dict]:
        """
        解析TTS请求

        返回: (是否成功, 参数字典)
        """
        try:
            # 提取文本（必需）
            text = TTSRequestParser.extract_parameter(
                content,
                TTSRequestParser.PARAM_MARKERS['text']
            )

            # 如果没有找到【文案】字段，尝试提取所有非参数行作为文案
            if not text:
                # 移除所有参数行和参数值行，剩余的就是文案
                lines = content.split('\n')
                text_lines = []

                # 定义所有参数标记
                all_markers = []
                for markers in TTSRequestParser.PARAM_MARKERS.values():
                    all_markers.extend(markers)
                all_markers.extend(TTSRequestParser.TTS_MARKERS)
                all_markers.extend(TTSRequestParser.VOICE_CLONE_MARKERS)

                skip_next = False  # 标记是否跳过下一行（参数值）

                for i, line in enumerate(lines):
                    line = line.strip()

                    # 如果上一行是参数标记，跳过当前行（参数值）
                    if skip_next:
                        skip_next = False
                        continue

                    # 跳过空行
                    if not line:
                        continue

                    # 检查是否是参数行
                    is_param_line = any(marker in line for marker in all_markers)

                    if is_param_line:
                        # 如果参数标记以冒号结尾，下一行是参数值，需要跳过
                        if any(line.endswith(marker) for marker in all_markers if marker.endswith(':')):
                            skip_next = True
                        continue

                    # 不是参数行，加入文案
                    text_lines.append(line)

                text = '\n'.join(text_lines).strip()

            if not text:
                return False, {'error': '❌ 缺少【文本】参数'}
            
            # 提取音色（可选，默认：苏瑶）
            voice_name = TTSRequestParser.extract_parameter(
                content,
                TTSRequestParser.PARAM_MARKERS['voice']
            ) or "苏瑶"
            
            # 提取语速（可选，默认：1.0）
            speed_str = TTSRequestParser.extract_parameter(
                content,
                TTSRequestParser.PARAM_MARKERS['speed']
            )
            try:
                speed = float(speed_str) if speed_str else 1.0
                # 验证范围
                if speed < 0.5 or speed > 2.0:
                    speed = 1.0
            except ValueError:
                speed = 1.0
            
            # 提取情感（可选）
            emotion = TTSRequestParser.extract_parameter(
                content,
                TTSRequestParser.PARAM_MARKERS['emotion']
            ) or ""
            
            # 提取情感权重（可选，默认：0.5）
            weight_str = TTSRequestParser.extract_parameter(
                content,
                TTSRequestParser.PARAM_MARKERS['emotion_weight']
            )
            try:
                emotion_weight = float(weight_str) if weight_str else 0.5
                # 验证范围
                if emotion_weight < 0 or emotion_weight > 1.0:
                    emotion_weight = 0.5
            except ValueError:
                emotion_weight = 0.5
            
            return True, {
                'request_type': 'tts',
                'tts_text': text,
                'voice_name': voice_name,
                'speed': speed,
                'emotion': emotion,
                'emotion_weight': emotion_weight
            }
        
        except Exception as e:
            return False, {'error': f'❌ 解析失败: {str(e)}'}
    
    @staticmethod
    def parse_voice_clone_request(title: str, content: str, audio_urls: List[str] = None, video_urls: List[str] = None) -> Tuple[bool, Dict]:
        """
        解析音色克隆请求
        
        返回: (是否成功, 参数字典)
        """
        try:
            # 提取音色名称（必需）
            voice_name = TTSRequestParser.extract_parameter(
                content,
                TTSRequestParser.PARAM_MARKERS['voice_name']
            )
            
            if not voice_name:
                return False, {'error': '❌ 缺少【音色名称】参数'}
            
            # 检查是否有音频文件
            if not audio_urls and not video_urls:
                return False, {'error': '❌ 缺少音频或视频文件'}
            
            # 提取是否公开（可选，默认：否）
            is_public_str = TTSRequestParser.extract_parameter(
                content,
                TTSRequestParser.PARAM_MARKERS['is_public']
            )
            is_public = is_public_str.lower() in ['是', 'yes', 'true', '1']
            
            # 提取描述（可选）
            description = TTSRequestParser.extract_parameter(
                content,
                TTSRequestParser.PARAM_MARKERS['description']
            ) or ""
            
            return True, {
                'request_type': 'voice_clone',
                'clone_voice_name': voice_name,
                'clone_is_public': is_public,
                'description': description,
                'audio_urls': audio_urls or [],
                'video_urls': video_urls or []
            }
        
        except Exception as e:
            return False, {'error': f'❌ 解析失败: {str(e)}'}
    
    @staticmethod
    def parse_forum_post(post_data: Dict) -> Tuple[bool, Dict]:
        """
        解析论坛帖子（智能识别）

        输入: 论坛爬虫返回的帖子数据
        返回: (是否成功, 解析结果)
        """
        try:
            title = post_data.get('title', '')
            content = post_data.get('content', '')
            audio_urls = post_data.get('audio_urls', [])
            video_urls = post_data.get('video_urls', [])

            # 智能识别请求类型
            detection = TTSRequestParser.detect_request_type(post_data)

            if detection['type'] == 'tts':
                success, params = TTSRequestParser.parse_tts_request(title, content)
                if success:
                    # 添加论坛信息和识别信息
                    params.update({
                        'post_id': post_data.get('thread_id'),
                        'thread_id': post_data.get('thread_id'),
                        'title': title,
                        'author_id': post_data.get('author_id'),
                        'author_name': post_data.get('author'),
                        'post_url': post_data.get('thread_url'),
                        'post_time': post_data.get('post_time'),
                        'detection': detection,
                    })
                    return True, params
                else:
                    return False, params

            elif detection['type'] == 'voice_clone':
                success, params = TTSRequestParser.parse_voice_clone_request(
                    title, content, audio_urls, video_urls
                )
                if success:
                    # 添加论坛信息和识别信息
                    params.update({
                        'post_id': post_data.get('thread_id'),
                        'thread_id': post_data.get('thread_id'),
                        'title': title,
                        'author_id': post_data.get('author'),
                        'author_name': post_data.get('author'),
                        'post_url': post_data.get('thread_url'),
                        'post_time': post_data.get('post_time'),
                        'original_filenames': post_data.get('original_filenames', []),
                        'detection': detection,
                    })
                    return True, params
                else:
                    return False, params

            else:
                # 无法识别
                return False, {
                    'error': f'❌ 无法识别请求类型 (置信度: {detection["confidence"]}%)',
                    'detection': detection
                }

        except Exception as e:
            return False, {'error': f'❌ 解析失败: {str(e)}'}


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("TTS请求解析器测试（包含智能识别）")
    print("=" * 60)

    # 测试1：智能识别 - TTS请求（有标签）
    print("\n测试1：智能识别 - TTS请求（有标签）")
    post_data_1 = {
        'title': '【制作AI声音】盼盼.WAV',
        'content': '【文案】你好世界\n【选择音色】盼盼\n【语速】1.0',
        'tags': ['【制作AI声音】'],
        'attachments': [
            {'name': 'output_12345.wav', 'size': 2.5 * 1024 * 1024, 'type': 'audio'}
        ]
    }
    detection = TTSRequestParser.detect_request_type(post_data_1)
    print(f"  识别类型: {detection['type']}")
    print(f"  置信度: {detection['confidence']}%")
    print(f"  原因: {detection['reason']}")
    print(f"  方法: {detection['method']}")

    # 测试2：智能识别 - 音色克隆请求（有标签）
    print("\n测试2：智能识别 - 音色克隆请求（有标签）")
    post_data_2 = {
        'title': '【音色克隆】张盼盼',
        'content': '【音色名称】张盼盼\n【给自己的音色起个名词】我的专属音色',
        'tags': ['【音色克隆】'],
        'attachments': [
            {'name': 'voice_sample.mp4', 'size': 45 * 1024 * 1024, 'type': 'video'}
        ]
    }
    detection = TTSRequestParser.detect_request_type(post_data_2)
    print(f"  识别类型: {detection['type']}")
    print(f"  置信度: {detection['confidence']}%")
    print(f"  原因: {detection['reason']}")
    print(f"  方法: {detection['method']}")

    # 测试3：智能识别 - 无标签但有字段
    print("\n测试3：智能识别 - 无标签但有字段（音色克隆）")
    post_data_3 = {
        'title': '我的声音',
        'content': '【音色名称】我的声音\n【上传音频】...',
        'tags': [],
        'attachments': [
            {'name': 'my_voice.wav', 'size': 8 * 1024 * 1024, 'type': 'original'}
        ]
    }
    detection = TTSRequestParser.detect_request_type(post_data_3)
    print(f"  识别类型: {detection['type']}")
    print(f"  置信度: {detection['confidence']}%")
    print(f"  原因: {detection['reason']}")
    print(f"  方法: {detection['method']}")

    # 测试4：完整解析 - TTS请求
    print("\n测试4：完整解析 - TTS请求")
    tts_content = """
    【文案】今天天气很好，适合出去玩
    【选择音色】女主播
    【语速】1.2
    【情感】高兴
    """
    success, params = TTSRequestParser.parse_tts_request("【制作AI声音】生成语音", tts_content)
    print(f"  成功: {success}")
    if success:
        print(f"  文本: {params['tts_text']}")
        print(f"  音色: {params['voice_name']}")
        print(f"  语速: {params['speed']}")

    # 测试5：完整解析 - 音色克隆请求
    print("\n测试5：完整解析 - 音色克隆请求")
    clone_content = """
    【音色名称】张三的声音
    【是否公开】否
    【给自己的音色起个名词】这是我自己的声音
    """
    success, params = TTSRequestParser.parse_voice_clone_request(
        "【音色克隆】我的声音",
        clone_content,
        audio_urls=["http://example.com/voice.wav"]
    )
    print(f"  成功: {success}")
    if success:
        print(f"  音色名称: {params['clone_voice_name']}")
        print(f"  是否公开: {params['clone_is_public']}")

