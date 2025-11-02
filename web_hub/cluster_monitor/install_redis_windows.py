#!/usr/bin/env python3
"""
Windows Redis 自动安装脚本
自动下载并安装Redis服务器
"""

import os
import sys
import subprocess
import urllib.request
import zipfile
import shutil
from pathlib import Path


def check_chocolatey():
    """检查Chocolatey是否安装"""
    try:
        result = subprocess.run(['choco', '--version'], 
                              capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print("✅ Chocolatey已安装")
            return True
    except:
        pass
    
    print("❌ Chocolatey未安装")
    return False


def install_redis_with_chocolatey():
    """使用Chocolatey安装Redis"""
    try:
        print("🔄 使用Chocolatey安装Redis...")
        result = subprocess.run(['choco', 'install', 'redis-64', '-y'], 
                              capture_output=True, text=True, shell=True)
        
        if result.returncode == 0:
            print("✅ Redis安装成功")
            return True
        else:
            print(f"❌ Chocolatey安装失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Chocolatey安装异常: {e}")
        return False


def download_redis_manually():
    """手动下载Redis"""
    redis_url = "https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip"
    redis_dir = Path("C:/Redis")
    redis_zip = "redis.zip"
    
    try:
        print("🔄 手动下载Redis...")
        print(f"下载地址: {redis_url}")
        
        # 下载Redis
        urllib.request.urlretrieve(redis_url, redis_zip)
        print("✅ Redis下载完成")
        
        # 创建安装目录
        redis_dir.mkdir(exist_ok=True)
        
        # 解压Redis
        with zipfile.ZipFile(redis_zip, 'r') as zip_ref:
            zip_ref.extractall(redis_dir)
        
        # 清理下载文件
        os.remove(redis_zip)
        
        print(f"✅ Redis安装到: {redis_dir}")
        return True
        
    except Exception as e:
        print(f"❌ 手动安装失败: {e}")
        return False


def start_redis_service():
    """启动Redis服务"""
    redis_paths = [
        "C:/Redis/redis-server.exe",
        "C:/Redis/Redis-x64-5.0.14.1/redis-server.exe",
        "C:/ProgramData/chocolatey/lib/redis-64/tools/redis-server.exe"
    ]
    
    for redis_path in redis_paths:
        if os.path.exists(redis_path):
            try:
                print(f"🚀 启动Redis服务: {redis_path}")
                # 在后台启动Redis
                subprocess.Popen([redis_path], shell=True)
                print("✅ Redis服务已启动")
                return True
            except Exception as e:
                print(f"❌ 启动失败: {e}")
                continue
    
    print("❌ 找不到Redis可执行文件")
    return False


def test_redis_connection():
    """测试Redis连接 - 使用简化版检查"""
    try:
        # 使用简化版Redis检查
        from check_redis_simple import test_redis_connection as simple_test
        return simple_test()
    except ImportError:
        # 如果简化版不可用，使用内置检查
        try:
            import redis
            client = redis.Redis(host='localhost', port=6379, db=1, socket_timeout=3)
            client.ping()
            print("✅ Redis连接测试成功")
            return True
        except ImportError:
            print("❌ Python redis包未安装")
            print("请运行: pip install redis")
            return False
        except Exception as e:
            print(f"❌ Redis连接失败: {e}")
            return False


def install_python_redis():
    """安装Python Redis包"""
    try:
        print("🔄 安装Python Redis包...")
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', 'redis'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Python Redis包安装成功")
            return True
        else:
            print(f"❌ Python Redis包安装失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 安装异常: {e}")
        return False


def main():
    """主函数"""
    print("🚀 Windows Redis 自动安装脚本")
    print("=" * 50)
    
    # 1. 安装Python Redis包
    if not install_python_redis():
        print("❌ Python Redis包安装失败，请手动安装")
        return
    
    # 2. 安装Redis服务器
    redis_installed = False
    
    # 尝试Chocolatey安装
    if check_chocolatey():
        redis_installed = install_redis_with_chocolatey()
    
    # 如果Chocolatey失败，尝试手动安装
    if not redis_installed:
        print("🔄 尝试手动安装Redis...")
        redis_installed = download_redis_manually()
    
    if not redis_installed:
        print("❌ Redis服务器安装失败")
        print("💡 请手动安装Redis:")
        print("   1. 访问: https://github.com/tporadowski/redis/releases")
        print("   2. 下载 Redis-x64-xxx.zip")
        print("   3. 解压到 C:/Redis")
        print("   4. 运行 redis-server.exe")
        return
    
    # 3. 启动Redis服务
    print("🔄 启动Redis服务...")
    if start_redis_service():
        # 等待服务启动
        import time
        time.sleep(3)
        
        # 4. 测试连接
        if test_redis_connection():
            print("\n🎉 Redis安装和配置完成！")
            print("现在可以启动监控系统:")
            print("python start_standalone.py")
        else:
            print("\n⚠️ Redis服务已安装但连接失败")
            print("请检查Redis服务是否正常运行")
    else:
        print("\n⚠️ Redis安装完成但启动失败")
        print("请手动启动Redis服务")


if __name__ == "__main__":
    main()
