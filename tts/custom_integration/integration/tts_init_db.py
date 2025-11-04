"""
IndexTTS2 音色克隆系统 - 数据库初始化脚本
创建TTS系统专用数据库，与论坛数据库完全分离
"""
import sqlite3
import os
import hashlib
import secrets
from pathlib import Path
from datetime import datetime
from tts_config import DATABASE_PATH, EXISTING_VOICE_FILES, VOICES_DIR

def hash_password(password: str) -> str:
    """生成密码哈希"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${pwd_hash}"

def init_database():
    """初始化TTS系统数据库"""
    print("=" * 60)
    print("IndexTTS2 音色克隆系统 - 数据库初始化")
    print("=" * 60)
    
    # 创建数据库目录
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # 检查数据库是否已存在
    db_exists = DATABASE_PATH.exists()
    if db_exists:
        print(f"\n⚠️  数据库已存在: {DATABASE_PATH}")
        response = input("是否要重新初始化数据库？这将删除所有现有数据！(yes/no): ")
        if response.lower() != 'yes':
            print("❌ 取消初始化")
            return False
        
        # 备份现有数据库
        backup_path = DATABASE_PATH.parent / f"tts_voice_system_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        import shutil
        shutil.copy(DATABASE_PATH, backup_path)
        print(f"✅ 已备份现有数据库到: {backup_path}")
        
        # 删除现有数据库
        DATABASE_PATH.unlink()
        print(f"✅ 已删除现有数据库")
    
    # 连接数据库
    print(f"\n📁 创建数据库: {DATABASE_PATH}")
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        # ==================== 创建用户表 ====================
        print("\n1️⃣  创建用户表 (users)...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id VARCHAR(50) PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE,
                forum_user_id VARCHAR(50),
                forum_username VARCHAR(100),
                forum_sync_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                voice_quota INTEGER DEFAULT 20,
                storage_quota_mb INTEGER DEFAULT 500,
                is_active BOOLEAN DEFAULT 1,
                is_admin BOOLEAN DEFAULT 0,
                default_voice_id VARCHAR(50)
            )
        ''')
        print("   ✅ 用户表创建成功")
        
        # ==================== 创建音色表 ====================
        print("\n2️⃣  创建音色表 (voices)...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS voices (
                voice_id VARCHAR(50) PRIMARY KEY,
                voice_name VARCHAR(100) NOT NULL,
                owner_id VARCHAR(50),
                is_public BOOLEAN DEFAULT 0,
                file_path VARCHAR(500) NOT NULL,
                audio_path VARCHAR(500),
                duration REAL,
                sample_rate INTEGER DEFAULT 22050,
                file_size_mb REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                usage_count INTEGER DEFAULT 0,
                last_used TIMESTAMP,
                description TEXT,
                FOREIGN KEY (owner_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        print("   ✅ 音色表创建成功")
        
        # ==================== 创建生成记录表 ====================
        print("\n3️⃣  创建生成记录表 (generation_history)...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS generation_history (
                record_id VARCHAR(50) PRIMARY KEY,
                user_id VARCHAR(50),
                voice_id VARCHAR(50),
                text_content TEXT,
                output_path VARCHAR(500),
                duration REAL,
                parameters TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_size_mb REAL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (voice_id) REFERENCES voices(voice_id) ON DELETE SET NULL
            )
        ''')
        print("   ✅ 生成记录表创建成功")
        
        # ==================== 创建索引 ====================
        print("\n4️⃣  创建索引...")
        
        # 用户表索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_forum_id ON users(forum_user_id)')
        
        # 音色表索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_voices_owner ON voices(owner_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_voices_public ON voices(is_public)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_voices_name ON voices(voice_name)')
        
        # 生成记录表索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_user ON generation_history(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_voice ON generation_history(voice_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_created ON generation_history(created_at)')
        
        print("   ✅ 索引创建成功")
        
        # ==================== 插入初始数据 ====================
        print("\n5️⃣  插入初始数据...")
        
        # 创建管理员账户
        admin_password_hash = hash_password("admin123")  # 默认密码，生产环境需修改
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, password_hash, email, is_admin, voice_quota, storage_quota_mb)
            VALUES ('admin', 'admin', ?, 'admin@indextts2.local', 1, 999, 10000)
        ''', (admin_password_hash,))
        print("   ✅ 管理员账户创建成功 (用户名: admin, 密码: admin123)")
        
        # 创建测试用户
        test_password_hash = hash_password("test123")
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, password_hash, email, voice_quota, storage_quota_mb)
            VALUES ('test_user', 'testuser', ?, 'test@indextts2.local', 20, 500)
        ''', (test_password_hash,))
        print("   ✅ 测试用户创建成功 (用户名: testuser, 密码: test123)")
        
        # ==================== 导入现有音色文件 ====================
        print("\n6️⃣  导入现有音色文件...")
        imported_count = 0
        
        for voice_file in EXISTING_VOICE_FILES:
            voice_path = VOICES_DIR / voice_file
            if voice_path.exists():
                voice_name = voice_path.stem  # 去掉.pt后缀
                voice_id = f"public_{voice_name.lower().replace(' ', '_')}"
                file_size_mb = voice_path.stat().st_size / (1024 * 1024)
                
                cursor.execute('''
                    INSERT OR IGNORE INTO voices 
                    (voice_id, voice_name, owner_id, is_public, file_path, file_size_mb, description)
                    VALUES (?, ?, NULL, 1, ?, ?, ?)
                ''', (voice_id, voice_name, str(voice_path), file_size_mb, f"系统预置音色 - {voice_name}"))
                
                if cursor.rowcount > 0:
                    imported_count += 1
                    print(f"   ✅ 导入音色: {voice_name} ({file_size_mb:.2f} MB)")
        
        print(f"\n   📊 共导入 {imported_count} 个公共音色")
        
        # ==================== 提交更改 ====================
        conn.commit()
        print("\n✅ 数据库初始化完成！")
        
        # ==================== 显示统计信息 ====================
        print("\n" + "=" * 60)
        print("数据库统计信息")
        print("=" * 60)
        
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"用户数量: {user_count}")
        
        cursor.execute("SELECT COUNT(*) FROM voices WHERE is_public = 1")
        public_voice_count = cursor.fetchone()[0]
        print(f"公共音色数量: {public_voice_count}")
        
        cursor.execute("SELECT COUNT(*) FROM voices WHERE is_public = 0")
        private_voice_count = cursor.fetchone()[0]
        print(f"私有音色数量: {private_voice_count}")
        
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 数据库初始化失败: {str(e)}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def verify_database():
    """验证数据库结构"""
    print("\n" + "=" * 60)
    print("验证数据库结构")
    print("=" * 60)
    
    if not DATABASE_PATH.exists():
        print("❌ 数据库文件不存在")
        return False
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['users', 'voices', 'generation_history']
        
        print("\n表结构检查:")
        for table in required_tables:
            if table in tables:
                print(f"   ✅ {table}")
            else:
                print(f"   ❌ {table} (缺失)")
                return False
        
        # 检查索引
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        print(f"\n索引数量: {len(indexes)}")
        
        print("\n✅ 数据库结构验证通过")
        return True
        
    except Exception as e:
        print(f"\n❌ 验证失败: {str(e)}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    # 初始化数据库
    success = init_database()
    
    if success:
        # 验证数据库
        verify_database()
        
        print("\n" + "=" * 60)
        print("🎉 数据库初始化完成！")
        print("=" * 60)
        print(f"\n数据库位置: {DATABASE_PATH}")
        print(f"数据库大小: {DATABASE_PATH.stat().st_size / 1024:.2f} KB")
        print("\n默认账户:")
        print("  管理员 - 用户名: admin, 密码: admin123")
        print("  测试用户 - 用户名: testuser, 密码: test123")
        print("\n⚠️  生产环境请立即修改默认密码！")
        print("=" * 60)
    else:
        print("\n❌ 数据库初始化失败")

