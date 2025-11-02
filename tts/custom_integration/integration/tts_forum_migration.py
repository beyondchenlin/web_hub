"""
TTS系统 - 论坛集成数据库迁移脚本

功能：
1. 扩展users表，添加论坛集成字段
2. 创建forum_tts_requests表
3. 创建必要的索引
"""

import sqlite3
import os
from datetime import datetime
from tts_config import DATABASE_PATH

def backup_database():
    """备份现有数据库"""
    if os.path.exists(DATABASE_PATH):
        backup_path = f"{DATABASE_PATH}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        import shutil
        shutil.copy(DATABASE_PATH, backup_path)
        print(f"✅ 数据库已备份: {backup_path}")
        return backup_path
    return None

def migrate_users_table():
    """扩展users表，添加论坛集成字段"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print("\n1️⃣  扩展users表...")
    
    try:
        # 检查是否已有论坛字段
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'forum_user_id' not in columns:
            # 添加论坛集成字段
            cursor.execute("""
                ALTER TABLE users ADD COLUMN forum_user_id VARCHAR(50)
            """)
            print("   ✅ 添加forum_user_id字段")
            
            cursor.execute("""
                ALTER TABLE users ADD COLUMN forum_username VARCHAR(100)
            """)
            print("   ✅ 添加forum_username字段")
            
            cursor.execute("""
                ALTER TABLE users ADD COLUMN forum_sync_time DATETIME
            """)
            print("   ✅ 添加forum_sync_time字段")
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_forum_id ON users(forum_user_id)
            """)
            print("   ✅ 创建forum_user_id索引")
            
            conn.commit()
            print("   ✅ users表扩展完成")
        else:
            print("   ℹ️  论坛字段已存在，跳过")
    
    except Exception as e:
        print(f"   ❌ 扩展users表失败: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()

def create_forum_tts_requests_table():
    """创建论坛TTS请求表"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print("\n2️⃣  创建forum_tts_requests表...")
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forum_tts_requests (
                -- 主键和基本信息
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id VARCHAR(50) UNIQUE NOT NULL,
                post_id VARCHAR(50) UNIQUE NOT NULL,
                thread_id VARCHAR(50) NOT NULL,
                
                -- 帖子信息
                title TEXT NOT NULL,
                content TEXT,
                author_id VARCHAR(50) NOT NULL,
                author_name VARCHAR(100) NOT NULL,
                post_url TEXT NOT NULL,
                post_time DATETIME,
                
                -- 关联TTS用户
                user_id VARCHAR(50),
                
                -- 请求类型
                request_type VARCHAR(20) NOT NULL,
                
                -- TTS请求信息
                tts_text TEXT,
                voice_name VARCHAR(100),
                voice_id VARCHAR(50),
                speed FLOAT DEFAULT 1.0,
                emotion VARCHAR(50),
                emotion_weight FLOAT DEFAULT 0.5,
                
                -- 音色克隆信息
                clone_voice_name VARCHAR(100),
                clone_is_public BOOLEAN DEFAULT 0,
                audio_urls TEXT,
                video_urls TEXT,
                original_filenames TEXT,
                
                -- 处理状态
                processing_status VARCHAR(20) DEFAULT 'pending',
                
                -- 输出结果
                tts_output_path TEXT,
                cloned_voice_id VARCHAR(50),
                output_file_url TEXT,
                
                -- 回复状态
                reply_status VARCHAR(20) DEFAULT 'pending',
                reply_content TEXT,
                reply_time DATETIME,
                
                -- 时间戳
                discovered_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                started_time DATETIME,
                completed_time DATETIME,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                
                -- 错误处理
                error_message TEXT,
                error_type VARCHAR(50),
                retry_count INTEGER DEFAULT 0,
                
                -- 元数据
                metadata TEXT,
                
                -- 外键约束
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (voice_id) REFERENCES voices(voice_id),
                FOREIGN KEY (cloned_voice_id) REFERENCES voices(voice_id)
            )
        """)
        print("   ✅ forum_tts_requests表创建成功")
        
        conn.commit()
    
    except Exception as e:
        print(f"   ❌ 创建forum_tts_requests表失败: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()

def create_forum_tts_indexes():
    """创建论坛TTS请求表的索引"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print("\n3️⃣  创建forum_tts_requests索引...")
    
    indexes = [
        ("idx_forum_tts_post_id", "CREATE INDEX IF NOT EXISTS idx_forum_tts_post_id ON forum_tts_requests(post_id)"),
        ("idx_forum_tts_user_id", "CREATE INDEX IF NOT EXISTS idx_forum_tts_user_id ON forum_tts_requests(user_id)"),
        ("idx_forum_tts_author_id", "CREATE INDEX IF NOT EXISTS idx_forum_tts_author_id ON forum_tts_requests(author_id)"),
        ("idx_forum_tts_status", "CREATE INDEX IF NOT EXISTS idx_forum_tts_status ON forum_tts_requests(processing_status)"),
        ("idx_forum_tts_type", "CREATE INDEX IF NOT EXISTS idx_forum_tts_type ON forum_tts_requests(request_type)"),
        ("idx_forum_tts_discovered", "CREATE INDEX IF NOT EXISTS idx_forum_tts_discovered ON forum_tts_requests(discovered_time)"),
    ]
    
    try:
        for idx_name, sql in indexes:
            cursor.execute(sql)
            print(f"   ✅ 创建索引: {idx_name}")
        
        conn.commit()
        print("   ✅ 所有索引创建完成")
    
    except Exception as e:
        print(f"   ❌ 创建索引失败: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()

def verify_migration():
    """验证迁移结果"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print("\n4️⃣  验证迁移结果...")
    
    try:
        # 检查users表
        cursor.execute("PRAGMA table_info(users)")
        users_columns = [col[1] for col in cursor.fetchall()]
        
        required_columns = ['forum_user_id', 'forum_username', 'forum_sync_time']
        for col in required_columns:
            if col in users_columns:
                print(f"   ✅ users表包含{col}字段")
            else:
                print(f"   ❌ users表缺少{col}字段")
        
        # 检查forum_tts_requests表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='forum_tts_requests'")
        if cursor.fetchone():
            print("   ✅ forum_tts_requests表存在")
            
            cursor.execute("PRAGMA table_info(forum_tts_requests)")
            columns = [col[1] for col in cursor.fetchall()]
            print(f"   ✅ forum_tts_requests表包含{len(columns)}个字段")
        else:
            print("   ❌ forum_tts_requests表不存在")
        
        # 检查索引
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_forum_tts%'")
        indexes = cursor.fetchall()
        print(f"   ✅ 创建了{len(indexes)}个forum_tts索引")
        
        print("\n✅ 迁移验证完成")
    
    except Exception as e:
        print(f"   ❌ 验证失败: {e}")
        raise
    
    finally:
        conn.close()

def main():
    print("=" * 60)
    print("TTS系统 - 论坛集成数据库迁移")
    print("=" * 60)
    
    try:
        # 备份数据库
        backup_database()
        
        # 执行迁移
        migrate_users_table()
        create_forum_tts_requests_table()
        create_forum_tts_indexes()
        
        # 验证迁移
        verify_migration()
        
        print("\n" + "=" * 60)
        print("🎉 数据库迁移完成！")
        print("=" * 60)
        print("\n下一步：")
        print("1. 运行 python import_forum_users.py 导入论坛用户")
        print("2. 启动论坛监控和TTS处理服务")
        print("=" * 60)
    
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()

