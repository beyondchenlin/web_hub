#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理Redis中的任务队列
用于解决任务metadata缺失问题
"""

import redis
import json
import sys

def clear_redis_tasks():
    """清理Redis中的所有任务数据"""
    try:
        # 连接Redis
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        print("🔍 检查Redis连接...")
        r.ping()
        print("✅ Redis连接成功")
        
        # 清理各种队列
        queues_to_clear = [
            'download_queue',
            'process_queue', 
            'upload_queue',
            'failed_tasks'
        ]
        
        total_cleared = 0
        
        for queue_name in queues_to_clear:
            queue_length = r.llen(queue_name)
            if queue_length > 0:
                print(f"🧹 清理队列 {queue_name}: {queue_length} 个任务")
                r.delete(queue_name)
                total_cleared += queue_length
            else:
                print(f"✅ 队列 {queue_name} 已为空")
        
        # 清理任务数据
        print("🔍 查找任务数据...")
        task_keys = r.keys('task:*')
        if task_keys:
            print(f"🧹 清理任务数据: {len(task_keys)} 个任务")
            r.delete(*task_keys)
            total_cleared += len(task_keys)
        else:
            print("✅ 没有找到任务数据")
        
        # 清理其他相关数据
        other_keys = r.keys('queue_stats') + r.keys('task_stats:*')
        if other_keys:
            print(f"🧹 清理统计数据: {len(other_keys)} 个键")
            r.delete(*other_keys)
        
        print(f"✅ 清理完成！总共清理了 {total_cleared} 个项目")
        print("💡 现在可以重新启动系统，新任务将包含正确的metadata")
        
    except redis.ConnectionError:
        print("❌ 无法连接到Redis，请确保Redis服务正在运行")
        return False
    except Exception as e:
        print(f"❌ 清理过程中出错: {e}")
        return False
    
    return True

def show_current_tasks():
    """显示当前Redis中的任务"""
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        
        print("📊 当前Redis中的任务状态:")
        
        queues = ['download_queue', 'process_queue', 'upload_queue', 'failed_tasks']
        for queue_name in queues:
            length = r.llen(queue_name)
            print(f"   {queue_name}: {length} 个任务")
        
        task_keys = r.keys('task:*')
        print(f"   任务数据: {len(task_keys)} 个")
        
        # 显示一些任务的metadata示例
        if task_keys:
            print("\n📝 任务metadata示例:")
            for i, key in enumerate(task_keys[:3]):  # 只显示前3个
                try:
                    task_data = r.get(key)
                    if task_data:
                        task_dict = json.loads(task_data)
                        metadata = task_dict.get('metadata', {})
                        print(f"   任务 {i+1}:")
                        print(f"     ID: {task_dict.get('task_id', 'N/A')}")
                        print(f"     post_id: {metadata.get('post_id', '❌ 缺失')}")
                        print(f"     cover_title_up: {metadata.get('cover_title_up', '❌ 缺失')}")
                        print(f"     cover_title_down: {metadata.get('cover_title_down', '❌ 缺失')}")
                except Exception as e:
                    print(f"     ❌ 解析任务数据失败: {e}")
        
    except Exception as e:
        print(f"❌ 查看任务状态失败: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--show":
        show_current_tasks()
    elif len(sys.argv) > 1 and sys.argv[1] == "--clear":
        if clear_redis_tasks():
            print("\n🚀 建议现在重新启动集群工作器:")
            print("python start_lightweight.py --cluster-worker --port 8005")
    else:
        print("用法:")
        print("  python clear_redis_tasks.py --show   # 显示当前任务状态")
        print("  python clear_redis_tasks.py --clear  # 清理所有任务")
