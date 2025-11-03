"""
完整流程测试脚本

测试场景：
1. 用户同步测试
2. TTS请求解析和权限验证
3. 音色克隆请求解析和配额验证
4. 用户音色使用权限测试
"""

import sys
import os

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tts_forum_sync import TTSForumUserSync
from tts_request_parser import TTSRequestParser
from tts_permission_manager import PermissionManager
from tts_forum_processor import TTSForumProcessor
from tts_config import DATABASE_PATH
import sqlite3


def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_user_sync():
    """测试1：用户同步"""
    print_section("测试1：用户同步机制")
    
    sync = TTSForumUserSync()
    
    # 测试用户1
    print("\n📝 同步论坛用户: author_id=12345, author_name=张三")
    success, msg = sync.sync_forum_user("12345", "张三")
    print(f"   结果: {msg}")
    
    # 测试用户2
    print("\n📝 同步论坛用户: author_id=67890, author_name=李四")
    success, msg = sync.sync_forum_user("67890", "李四", "lisi@example.com")
    print(f"   结果: {msg}")
    
    # 验证数据库
    print("\n📊 数据库验证:")
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, voice_quota, storage_quota_mb FROM users WHERE user_id LIKE 'forum_%'")
    users = cursor.fetchall()
    for user in users:
        print(f"   - {user[0]}: {user[1]} (配额: {user[2]}个音色, {user[3]}MB)")
    conn.close()


def test_tts_request():
    """测试2：TTS请求处理"""
    print_section("测试2：TTS请求处理（使用公共音色）")
    
    # 模拟论坛帖子数据
    post_data = {
        'title': '【制作AI声音】测试公共音色',
        'content': '''
【文案】今天天气很好，适合出去玩
【选择音色】苏瑶
【语速】1.0
        ''',
        'author_id': '12345',
        'author_name': '张三',
        'thread_id': 'thread_001',
        'thread_url': 'https://tts.lrtcai.com/thread-001.html',
        'post_time': '2024-01-01 12:00:00',
        'tags': ['【制作AI声音】'],
        'attachments': []
    }
    
    processor = TTSForumProcessor()
    
    print("\n📝 处理TTS请求...")
    success, result = processor.process_forum_post(post_data)
    
    if success:
        print("✅ 处理成功！")
        print(f"   请求类型: {result.get('request_type')}")
        print(f"   TTS用户ID: {result.get('tts_user_id')}")
        print(f"   文本: {result.get('tts_text')}")
        print(f"   音色: {result.get('voice_name')}")
        print(f"   语速: {result.get('speed')}")
    else:
        print(f"❌ 处理失败: {result.get('error')}")


def test_voice_clone_request():
    """测试3：音色克隆请求处理"""
    print_section("测试3：音色克隆请求处理")
    
    # 先添加一个公共音色用于测试
    print("\n📝 准备测试数据：添加公共音色...")
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO voices 
        (voice_id, voice_name, owner_id, is_public, file_path, file_size_mb, description)
        VALUES ('public_suyao', '苏瑶', NULL, 1, '/path/to/suyao.pt', 10.5, '系统预置音色')
    """)
    conn.commit()
    conn.close()
    print("   ✅ 公共音色添加成功")
    
    # 模拟音色克隆帖子
    post_data = {
        'title': '【音色克隆】我的声音',
        'content': '''
【音色名称】张三的声音
【是否公开】否
【给自己的音色起个名词】这是我自己的声音
        ''',
        'author_id': '12345',
        'author_name': '张三',
        'thread_id': 'thread_002',
        'thread_url': 'https://tts.lrtcai.com/thread-002.html',
        'post_time': '2024-01-01 13:00:00',
        'tags': ['【音色克隆】'],
        'audio_urls': ['https://example.com/voice.wav'],
        'video_urls': [],
        'attachments': [
            {'name': 'voice.wav', 'size': 8 * 1024 * 1024, 'type': 'original'}
        ]
    }
    
    processor = TTSForumProcessor()
    
    print("\n📝 处理音色克隆请求...")
    success, result = processor.process_forum_post(post_data)
    
    if success:
        print("✅ 处理成功！")
        print(f"   请求类型: {result.get('request_type')}")
        print(f"   TTS用户ID: {result.get('tts_user_id')}")
        print(f"   音色名称: {result.get('clone_voice_name')}")
        print(f"   是否公开: {result.get('clone_is_public')}")
        print(f"   音频URL: {result.get('audio_urls')}")
    else:
        print(f"❌ 处理失败: {result.get('error')}")


def test_permission_validation():
    """测试4：权限验证"""
    print_section("测试4：权限验证机制")
    
    pm = PermissionManager()
    
    # 测试4.1：使用公共音色
    print("\n📝 测试4.1：用户12345使用公共音色'苏瑶'")
    can_use, reason, voice_id = pm.can_use_voice_by_name("forum_12345", "苏瑶")
    print(f"   {reason}")
    
    # 测试4.2：模拟用户12345创建私有音色
    print("\n📝 测试4.2：创建用户12345的私有音色")
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO voices 
        (voice_id, voice_name, owner_id, is_public, file_path, file_size_mb)
        VALUES ('user_12345_voice_001', '张三的声音', 'forum_12345', 0, '/path/to/zhangsan.pt', 8.5)
    """)
    conn.commit()
    conn.close()
    print("   ✅ 私有音色创建成功")
    
    # 测试4.3：用户12345使用自己的音色
    print("\n📝 测试4.3：用户12345使用自己的音色'张三的声音'")
    can_use, reason, voice_id = pm.can_use_voice_by_name("forum_12345", "张三的声音")
    print(f"   {reason}")
    
    # 测试4.4：用户67890尝试使用用户12345的私有音色
    print("\n📝 测试4.4：用户67890尝试使用用户12345的私有音色'张三的声音'")
    can_use, reason, voice_id = pm.can_use_voice_by_name("forum_67890", "张三的声音")
    print(f"   {reason}")


def test_quota_validation():
    """测试5：配额验证"""
    print_section("测试5：配额验证机制")
    
    pm = PermissionManager()
    
    # 测试5.1：检查音色配额
    print("\n📝 测试5.1：检查用户12345的音色配额")
    has_quota, reason, current, quota = pm.check_voice_quota("forum_12345")
    print(f"   {reason}")
    
    # 测试5.2：检查存储配额
    print("\n📝 测试5.2：检查用户12345的存储配额（需要10MB）")
    has_storage, reason, used, quota = pm.check_storage_quota("forum_12345", 10.0)
    print(f"   {reason}")
    
    # 测试5.3：模拟配额已满的情况
    print("\n📝 测试5.3：模拟配额已满（修改用户配额为1）")
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET voice_quota = 1 WHERE user_id = 'forum_12345'")
    conn.commit()
    conn.close()
    
    has_quota, reason, current, quota = pm.check_voice_quota("forum_12345")
    print(f"   {reason}")
    
    # 恢复配额
    print("\n📝 恢复用户配额为20")
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET voice_quota = 20 WHERE user_id = 'forum_12345'")
    conn.commit()
    conn.close()
    print("   ✅ 配额已恢复")


def test_user_voice_list():
    """测试6：获取用户音色列表"""
    print_section("测试6：获取用户音色列表")
    
    pm = PermissionManager()
    
    print("\n📝 获取用户12345的音色列表...")
    voices = pm.get_user_voices("forum_12345")
    
    print(f"\n📊 音色统计:")
    print(f"   公共音色: {len(voices['public'])}个")
    print(f"   私有音色: {len(voices['private'])}个")
    print(f"   总计: {voices['total']}个")
    
    if voices['public']:
        print("\n   公共音色列表:")
        for v in voices['public']:
            print(f"      - {v['voice_name']} ({v['file_size_mb']:.2f}MB)")
    
    if voices['private']:
        print("\n   私有音色列表:")
        for v in voices['private']:
            print(f"      - {v['voice_name']} ({v['file_size_mb']:.2f}MB)")


def verify_database():
    """验证数据库状态"""
    print_section("数据库最终状态")
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # 用户统计
    cursor.execute("SELECT COUNT(*) FROM users WHERE user_id LIKE 'forum_%'")
    forum_user_count = cursor.fetchone()[0]
    
    # 音色统计
    cursor.execute("SELECT COUNT(*) FROM voices WHERE is_public = 1")
    public_voice_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM voices WHERE is_public = 0")
    private_voice_count = cursor.fetchone()[0]
    
    print(f"\n📊 数据库统计:")
    print(f"   论坛用户数: {forum_user_count}")
    print(f"   公共音色数: {public_voice_count}")
    print(f"   私有音色数: {private_voice_count}")
    
    # 显示所有音色
    print(f"\n📋 所有音色列表:")
    cursor.execute("""
        SELECT voice_id, voice_name, owner_id, is_public, file_size_mb 
        FROM voices 
        ORDER BY is_public DESC, voice_name
    """)
    voices = cursor.fetchall()
    for v in voices:
        voice_type = "公共" if v[3] else "私有"
        owner = v[2] if v[2] else "系统"
        print(f"   - [{voice_type}] {v[1]} (所有者: {owner}, {v[4]:.2f}MB)")
    
    conn.close()


def main():
    """主测试流程"""
    print("\n" + "=" * 70)
    print("  TTS论坛自动化系统 - 完整流程测试")
    print("=" * 70)
    print(f"\n数据库位置: {DATABASE_PATH}")
    
    try:
        # 运行所有测试
        test_user_sync()
        test_tts_request()
        test_voice_clone_request()
        test_permission_validation()
        test_quota_validation()
        test_user_voice_list()
        verify_database()
        
        print("\n" + "=" * 70)
        print("  ✅ 所有测试完成！")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

