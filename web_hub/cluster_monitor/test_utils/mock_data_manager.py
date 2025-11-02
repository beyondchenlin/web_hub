#!/usr/bin/env python3
"""
模拟数据管理器
功能：生成模拟统计数据，与真实数据合并显示，支持持久化存储
"""

import json
import os
import random
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional


class MockDataManager:
    """模拟数据管理器"""
    
    def __init__(self, data_file: str = "data/mock_stats.json"):
        self.data_file = data_file
        self.data_dir = os.path.dirname(data_file)
        
        # 确保数据目录存在
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        # 模拟数据
        self.mock_stats = {
            'total_tasks_sent': 20000,      # 基础数据：发送任务2万个
            'successful_tasks': 19995,      # 基础数据：成功任务19995个
            'failed_tasks': 5,              # 基础数据：失败任务5个
            'new_posts_found': 20000,       # 基础数据：新发现帖子20000个
            'last_update': datetime.now().isoformat(),
            'session_start': datetime.now().isoformat()
        }
        
        # 真实数据偏移（累计真实数据）
        self.real_data_offset = {
            'total_tasks_sent': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'new_posts_found': 0
        }
        
        # 加载持久化数据
        self.load_data()
        
        # 更新控制
        self.update_interval = 10  # 10秒更新一次
        self.is_running = False
        self.update_thread = None
        
        # 随机更新范围
        self.update_ranges = {
            'total_tasks_sent': (1, 3),     # 每次增加1-3个任务
            'successful_tasks': (1, 3),     # 每次增加1-3个成功任务
            'failed_tasks': (0, 1),         # 每次可能增加0-1个失败任务
            'new_posts_found': (1, 5)       # 每次增加1-5个新发现帖子
        }
    
    def load_data(self):
        """加载持久化数据"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.mock_stats.update(data.get('mock_stats', {}))
                    self.real_data_offset.update(data.get('real_data_offset', {}))
                    print(f"✅ 模拟数据加载成功: {self.data_file}")
                    print(f"   发送任务: {self.mock_stats['total_tasks_sent']}")
                    print(f"   成功任务: {self.mock_stats['successful_tasks']}")
                    print(f"   失败任务: {self.mock_stats['failed_tasks']}")
                    print(f"   新发现帖子: {self.mock_stats['new_posts_found']}")
            else:
                print(f"📝 创建新的模拟数据文件: {self.data_file}")
                self.save_data()
        except Exception as e:
            print(f"⚠️ 加载模拟数据失败: {e}")
    
    def save_data(self):
        """保存持久化数据"""
        try:
            data = {
                'mock_stats': self.mock_stats,
                'real_data_offset': self.real_data_offset,
                'last_saved': datetime.now().isoformat()
            }
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 模拟数据保存成功: {self.data_file}")
        except Exception as e:
            print(f"❌ 保存模拟数据失败: {e}")
    
    def start_mock_updates(self):
        """启动模拟数据更新"""
        if self.is_running:
            return
        
        self.is_running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        print(f"🚀 模拟数据更新已启动，间隔: {self.update_interval}秒")
    
    def stop_mock_updates(self):
        """停止模拟数据更新"""
        self.is_running = False
        if self.update_thread:
            self.update_thread.join(timeout=1)
        print("🛑 模拟数据更新已停止")
    
    def _update_loop(self):
        """模拟数据更新循环"""
        while self.is_running:
            try:
                self.update_mock_data()
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"❌ 模拟数据更新异常: {e}")
                time.sleep(self.update_interval)
    
    def update_mock_data(self):
        """更新模拟数据"""
        # 随机更新各项统计
        updates = {}
        
        # 发送任务和新发现帖子保持一致
        new_posts = random.randint(*self.update_ranges['new_posts_found'])
        new_tasks = new_posts  # 发送任务数等于新发现帖子数
        
        # 成功任务数应该略小于发送任务数
        success_rate = random.uniform(0.95, 0.99)  # 95%-99%的成功率
        new_success = int(new_tasks * success_rate)
        new_failed = new_tasks - new_success
        
        # 更新统计数据
        self.mock_stats['total_tasks_sent'] += new_tasks
        self.mock_stats['successful_tasks'] += new_success
        self.mock_stats['failed_tasks'] += new_failed
        self.mock_stats['new_posts_found'] += new_posts
        self.mock_stats['last_update'] = datetime.now().isoformat()
        
        updates = {
            'total_tasks_sent': new_tasks,
            'successful_tasks': new_success,
            'failed_tasks': new_failed,
            'new_posts_found': new_posts
        }
        
        # 打印更新信息
        if any(updates.values()):
            print(f"📊 模拟数据更新: +{new_tasks}发送, +{new_success}成功, +{new_failed}失败, +{new_posts}新帖")
        
        # 保存数据
        self.save_data()
    
    def add_real_data(self, key: str, value: int):
        """添加真实数据"""
        if key in self.real_data_offset:
            self.real_data_offset[key] += value
            print(f"📈 真实数据累加: {key} +{value}")
            self.save_data()
    
    def get_combined_stats(self) -> Dict:
        """获取模拟数据与真实数据的合并结果"""
        combined_stats = {}
        
        for key in ['total_tasks_sent', 'successful_tasks', 'failed_tasks', 'new_posts_found']:
            mock_value = self.mock_stats.get(key, 0)
            real_value = self.real_data_offset.get(key, 0)
            combined_stats[key] = mock_value + real_value
        
        # 添加其他统计信息
        combined_stats['last_forum_check'] = datetime.now().strftime('%H:%M:%S')
        combined_stats['start_time'] = datetime.now()
        combined_stats['last_update'] = self.mock_stats.get('last_update')
        
        return combined_stats
    
    def get_mock_stats(self) -> Dict:
        """获取纯模拟数据"""
        return self.mock_stats.copy()
    
    def get_real_stats(self) -> Dict:
        """获取纯真实数据"""
        return self.real_data_offset.copy()
    
    def reset_mock_data(self):
        """重置模拟数据到初始状态"""
        self.mock_stats = {
            'total_tasks_sent': 20000,
            'successful_tasks': 19995,
            'failed_tasks': 5,
            'new_posts_found': 20000,
            'last_update': datetime.now().isoformat(),
            'session_start': datetime.now().isoformat()
        }
        self.save_data()
        print("🔄 模拟数据已重置到初始状态")
    
    def reset_real_data(self):
        """重置真实数据累计"""
        self.real_data_offset = {
            'total_tasks_sent': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'new_posts_found': 0
        }
        self.save_data()
        print("🔄 真实数据累计已重置")
    
    def get_status(self) -> Dict:
        """获取管理器状态"""
        return {
            'is_running': self.is_running,
            'update_interval': self.update_interval,
            'data_file': self.data_file,
            'last_update': self.mock_stats.get('last_update'),
            'session_start': self.mock_stats.get('session_start'),
            'combined_stats': self.get_combined_stats(),
            'mock_stats': self.get_mock_stats(),
            'real_stats': self.get_real_stats()
        }


# 全局模拟数据管理器实例
_mock_data_manager = None


def get_mock_data_manager() -> MockDataManager:
    """获取模拟数据管理器单例"""
    global _mock_data_manager
    if _mock_data_manager is None:
        _mock_data_manager = MockDataManager()
    return _mock_data_manager


def main():
    """测试模拟数据管理器"""
    print("🧪 测试模拟数据管理器")
    
    manager = get_mock_data_manager()
    
    # 显示初始状态
    print("\n📊 初始统计数据:")
    stats = manager.get_combined_stats()
    for key, value in stats.items():
        if key in ['total_tasks_sent', 'successful_tasks', 'failed_tasks', 'new_posts_found']:
            print(f"   {key}: {value}")
    
    # 启动模拟更新
    manager.start_mock_updates()
    
    # 模拟一些真实数据
    print("\n📈 模拟真实数据...")
    manager.add_real_data('total_tasks_sent', 2)
    manager.add_real_data('successful_tasks', 2)
    manager.add_real_data('new_posts_found', 3)
    
    # 显示合并后的数据
    print("\n📊 合并后的统计数据:")
    stats = manager.get_combined_stats()
    for key, value in stats.items():
        if key in ['total_tasks_sent', 'successful_tasks', 'failed_tasks', 'new_posts_found']:
            print(f"   {key}: {value}")
    
    # 等待一段时间观察更新
    print("\n⏳ 等待20秒观察模拟数据更新...")
    time.sleep(20)
    
    # 显示最终数据
    print("\n📊 最终统计数据:")
    stats = manager.get_combined_stats()
    for key, value in stats.items():
        if key in ['total_tasks_sent', 'successful_tasks', 'failed_tasks', 'new_posts_found']:
            print(f"   {key}: {value}")
    
    # 停止更新
    manager.stop_mock_updates()
    
    print("\n✅ 测试完成")


if __name__ == "__main__":
    main()