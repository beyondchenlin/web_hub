"""
测试音色克隆功能
"""

import os
import sys
from pathlib import Path

# 确保 shared 可导入
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tts_api_service import TTSAPIService
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_voice_clone():
    """测试音色克隆功能"""
    
    print("=" * 80)
    print("🎤 测试音色克隆功能")
    print("=" * 80)
    
    # 初始化API服务
    api_service = TTSAPIService()
    
    # 测试音频文件（使用 IndexTTS2 的示例音频）
    repo_root = Path(__file__).resolve().parents[3]
    test_audio_file = repo_root / "tts" / "indextts2" / "examples" / "voice_01.wav"
    
    if not test_audio_file.exists():
        print(f"❌ 测试音频文件不存在: {test_audio_file}")
        print("请确保 IndexTTS2 的示例音频存在")
        return False
    
    print(f"\n📁 测试音频文件: {test_audio_file}")
    print(f"   文件大小: {test_audio_file.stat().st_size / 1024:.2f} KB")
    
    # 测试参数
    test_voice_name = "测试音色_01"
    test_user_id = "test_user_123"
    
    print(f"\n🎯 测试参数:")
    print(f"   音色名称: {test_voice_name}")
    print(f"   用户ID: {test_user_id}")
    
    # 调用音色克隆API
    print(f"\n🚀 开始音色克隆...")
    voice_id = api_service._call_voice_clone_api(
        audio_file=str(test_audio_file),
        voice_name=test_voice_name,
        user_id=test_user_id
    )
    
    if voice_id:
        print(f"\n✅ 音色克隆成功！")
        print(f"   Voice ID: {voice_id}")
        
        # 验证生成的文件
        indextts2_root = repo_root / "tts" / "indextts2"
        pt_file = indextts2_root / "voices" / f"{voice_id}.pt"
        audio_file = indextts2_root / "voices" / "audio" / test_user_id / f"{voice_id}.wav"
        
        print(f"\n📦 生成的文件:")
        if pt_file.exists():
            print(f"   ✓ 音色配置: {pt_file} ({pt_file.stat().st_size / 1024:.2f} KB)")
        else:
            print(f"   ✗ 音色配置文件不存在: {pt_file}")
            
        if audio_file.exists():
            print(f"   ✓ 音频文件: {audio_file} ({audio_file.stat().st_size / 1024:.2f} KB)")
        else:
            print(f"   ✗ 音频文件不存在: {audio_file}")
        
        # 读取 .pt 文件内容
        if pt_file.exists():
            try:
                import torch
                voice_data = torch.load(str(pt_file))
                print(f"\n📄 .pt 文件内容:")
                print(f"   {voice_data}")
            except Exception as e:
                print(f"\n⚠️ 无法读取 .pt 文件: {e}")
        
        print(f"\n" + "=" * 80)
        print(f"✅ 测试完成！音色克隆功能正常工作")
        print(f"=" * 80)
        return True
    else:
        print(f"\n❌ 音色克隆失败！")
        print(f"=" * 80)
        return False


def test_voice_clone_request():
    """测试完整的音色克隆请求流程"""
    
    print("\n" + "=" * 80)
    print("🎤 测试完整的音色克隆请求流程")
    print("=" * 80)
    
    # 初始化API服务
    api_service = TTSAPIService()
    
    # 测试音频文件
    repo_root = Path(__file__).resolve().parents[3]
    test_audio_file = repo_root / "tts" / "indextts2" / "examples" / "voice_02.wav"
    
    if not test_audio_file.exists():
        print(f"❌ 测试音频文件不存在: {test_audio_file}")
        return False
    
    # 构建请求数据
    request_data = {
        'request_id': 'test_clone_001',
        'user_id': 'forum_user_456',
        'voice_name': '论坛用户音色',
        'description': '这是一个测试音色',
        'audio_file': str(test_audio_file),
        'duration': 10.5,
        'is_public': False
    }
    
    print(f"\n📋 请求数据:")
    for key, value in request_data.items():
        if key == 'audio_file':
            print(f"   {key}: {Path(value).name}")
        else:
            print(f"   {key}: {value}")
    
    # 处理音色克隆请求
    print(f"\n🚀 处理音色克隆请求...")
    success, result = api_service.process_voice_clone_request(request_data)
    
    if success:
        print(f"\n✅ 音色克隆请求处理成功！")
        print(f"\n📊 结果:")
        for key, value in result.items():
            print(f"   {key}: {value}")
        
        print(f"\n" + "=" * 80)
        print(f"✅ 完整流程测试通过！")
        print(f"=" * 80)
        return True
    else:
        print(f"\n❌ 音色克隆请求处理失败！")
        print(f"\n错误信息: {result}")
        print(f"=" * 80)
        return False


if __name__ == "__main__":
    print("\n" + "🎯" * 40)
    print("音色克隆功能测试")
    print("🎯" * 40 + "\n")
    
    # 测试1: 基础音色克隆
    test1_result = test_voice_clone()
    
    # 测试2: 完整请求流程
    test2_result = test_voice_clone_request()
    
    # 总结
    print("\n" + "=" * 80)
    print("📊 测试总结")
    print("=" * 80)
    print(f"测试1 - 基础音色克隆: {'✅ 通过' if test1_result else '❌ 失败'}")
    print(f"测试2 - 完整请求流程: {'✅ 通过' if test2_result else '❌ 失败'}")
    print("=" * 80)
    
    if test1_result and test2_result:
        print("\n🎉 所有测试通过！音色克隆功能已成功实现！")
    else:
        print("\n⚠️ 部分测试失败，请检查日志")

