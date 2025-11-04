"""
测试解析器对论坛帖子格式的兼容性（pytest 版本，放置于 tests/ 目录）
"""

import sys
from pathlib import Path

# 确保可以从上级目录导入 tts_request_parser.py
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir.parent))

from tts_request_parser import TTSRequestParser


def test_voice_clone_post():
    """测试音色克隆帖子解析（方括号格式）"""
    # 模拟论坛帖子数据（使用方括号）
    post_data = {
        'thread_id': '123',
        'title': '[音色克隆]盼盼.WAV',
        'content': '''[音色名称]盼盼
[是否公开]是
[描述]这是盼盼的声音，适合播报新闻''',
        'audio_urls': ['https://lrtcai-xxx.cos.ap-beijing.myqcloud.com/盼盼.WAV'],
        'video_urls': [],
        'author': 'admin_lrtcai',
        'tags': []
    }

    # 1. 类型检测
    detection = TTSRequestParser.detect_request_type(post_data)
    assert detection['type'] == 'voice_clone'

    # 2. 参数解析
    success, params = TTSRequestParser.parse_forum_post(post_data)
    assert success is True
    assert params.get('request_type') == 'voice_clone'
    assert params.get('clone_voice_name') == '盼盼'
    assert params.get('clone_is_public') is True
    assert '这是盼盼的声音' in params.get('description', '')


def test_voice_clone_post_chinese_brackets():
    """测试音色克隆帖子解析（中文书名号格式）"""
    # 模拟论坛帖子数据（使用中文书名号）
    post_data = {
        'thread_id': '124',
        'title': '【音色克隆】张三的声音',
        'content': '''【音色名称】张三
【是否公开】否
【描述】这是张三的声音''',
        'audio_urls': ['https://lrtcai-xxx.cos.ap-beijing.myqcloud.com/张三.WAV'],
        'video_urls': [],
        'author': 'user123',
        'tags': []
    }

    detection = TTSRequestParser.detect_request_type(post_data)
    assert detection['type'] == 'voice_clone'

    success, params = TTSRequestParser.parse_forum_post(post_data)
    assert success is True
    assert params.get('clone_voice_name') == '张三'
    assert params.get('clone_is_public') is False


def test_tts_post():
    """测试TTS生成帖子解析（方括号格式）"""
    post_data = {
        'thread_id': '456',
        'title': '[制作AI声音]你好 这是测试',
        'content': '''[文案]你好，这是测试。欢迎使用AI声音克隆系统！
[选择音色]盼盼
[语速]1.0
[情感]开心
[情感权重]0.8''',
        'audio_urls': [],
        'video_urls': [],
        'author': 'admin_lrtcai',
        'tags': []
    }

    detection = TTSRequestParser.detect_request_type(post_data)
    assert detection['type'] == 'tts'

    success, params = TTSRequestParser.parse_forum_post(post_data)
    assert success is True
    assert params.get('request_type') == 'tts'
    assert '欢迎使用AI声音克隆系统' in params.get('tts_text', '')
    assert params.get('voice_name') == '盼盼'
    assert float(params.get('speed')) == 1.0
    assert params.get('emotion') == '开心'


def test_tts_post_chinese_brackets():
    """测试TTS生成帖子解析（中文书名号格式）"""
    post_data = {
        'thread_id': '457',
        'title': '【制作AI声音】新闻播报',
        'content': '''【文案】今天天气晴朗，适合外出游玩
【选择音色】张三
【语速】1.2
【情感】平静
【情感权重】0.5''',
        'audio_urls': [],
        'video_urls': [],
        'author': 'user123',
        'tags': []
    }

    detection = TTSRequestParser.detect_request_type(post_data)
    assert detection['type'] == 'tts'

    success, params = TTSRequestParser.parse_forum_post(post_data)
    assert success is True
    assert '今天天气晴朗' in params.get('tts_text', '')
    assert params.get('voice_name') == '张三'
    assert float(params.get('speed')) == 1.2
    assert params.get('emotion') == '平静'

