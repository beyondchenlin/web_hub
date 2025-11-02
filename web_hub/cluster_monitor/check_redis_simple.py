#!/usr/bin/env python3
"""
简化版Redis检测脚本
避免编码问题，专注核心功能检测
"""

import socket
import sys


def check_python_redis():
    """检查Python Redis包"""
    try:
        import redis
        print(f"✅ Python redis包已安装 (版本: {redis.__version__})")
        return True
    except ImportError:
        print("❌ Python redis包未安装")
        print("   安装命令: pip install redis")
        return False


def check_redis_service():
    """检查Redis服务是否运行"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(('localhost', 6379))
        sock.close()
        
        if result == 0:
            print("✅ Redis服务正在运行 (端口6379)")
            return True
        else:
            print("❌ Redis服务未运行 (端口6379)")
            return False
    except Exception as e:
        print(f"❌ 检查Redis服务失败: {e}")
        return False


def test_redis_connection():
    """测试Redis连接和读写"""
    try:
        import redis
        
        # 连接Redis
        client = redis.Redis(host='localhost', port=6379, db=1, socket_timeout=3)
        
        # 测试ping
        client.ping()
        print("✅ Redis连接成功")
        
        # 测试读写
        test_key = "test_monitor_system"
        test_value = "hello_from_monitor"
        
        client.set(test_key, test_value, ex=60)  # 60秒过期
        retrieved = client.get(test_key)
        
        if retrieved and retrieved.decode() == test_value:
            print("✅ Redis读写测试成功")
            client.delete(test_key)  # 清理
            return True
        else:
            print("❌ Redis读写测试失败")
            return False
            
    except ImportError:
        print("❌ 无法测试: Python redis包未安装")
        return False
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")
        return False


def main():
    """主检测函数"""
    print("🔍 Redis 快速检测")
    print("=" * 40)
    
    # 检测结果
    python_ok = check_python_redis()
    service_ok = check_redis_service()
    connection_ok = False
    
    if python_ok and service_ok:
        connection_ok = test_redis_connection()
    
    # 总结
    print("\n📊 检测结果:")
    print("=" * 40)
    
    if python_ok and service_ok and connection_ok:
        print("🎉 Redis完全可用!")
        print("✅ Python包: 已安装")
        print("✅ Redis服务: 正在运行")
        print("✅ 连接测试: 成功")
        print("\n🚀 可以启动监控系统:")
        print("   python start_standalone.py")
        return True
        
    elif python_ok and service_ok:
        print("⚠️ Redis基本可用，但连接测试失败")
        print("✅ Python包: 已安装")
        print("✅ Redis服务: 正在运行")
        print("❌ 连接测试: 失败")
        print("\n🔧 请检查Redis配置")
        return False
        
    else:
        print("❌ Redis不完全可用")
        print(f"{'✅' if python_ok else '❌'} Python包")
        print(f"{'✅' if service_ok else '❌'} Redis服务")
        print(f"{'✅' if connection_ok else '❌'} 连接测试")
        
        print("\n📖 解决方案:")
        if not python_ok:
            print("1. 安装Python Redis包: pip install redis")
        if not service_ok:
            print("2. 启动Redis服务:")
            print("   Windows: redis-server")
            print("   Linux: sudo systemctl start redis-server")
            print("   macOS: brew services start redis")
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
