"""
TTS论坛监控和集成模块

功能：
1. 监控论坛新帖子
2. 自动处理TTS和音色克隆请求
3. 自动回复论坛
4. 管理处理队列
"""

import os
import sys
import time
import json
import logging
import threading
from typing import Dict, List, Optional
from datetime import datetime
from queue import Queue

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tts_forum_processor import TTSForumProcessor
from tts_request_parser import TTSRequestParser

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/tts_forum_monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TTSForumMonitor:
    """TTS论坛监控管理器"""
    
    def __init__(self, forum_crawler=None, db_path: str = "database/tts_voice_system.db"):
        """
        初始化论坛监控
        
        Args:
            forum_crawler: 论坛爬虫实例
            db_path: 数据库路径
        """
        self.forum_crawler = forum_crawler
        self.db_path = db_path
        self.processor = TTSForumProcessor(db_path)
        
        # 处理队列
        self.request_queue = Queue()
        self.processed_requests = {}  # 已处理的请求记录
        
        # 监控状态
        self.running = False
        self.monitor_thread = None
        self.check_interval = 60  # 检查间隔（秒）
        
        logger.info("✅ TTS论坛监控初始化完成")
    
    def start_monitoring(self):
        """启动论坛监控"""
        if self.running:
            logger.warning("⚠️ 监控已在运行中")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("🚀 论坛监控已启动")
    
    def stop_monitoring(self):
        """停止论坛监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("⏹️ 论坛监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        logger.info("🔄 开始监控循环")
        
        while self.running:
            try:
                # 检查新帖子
                self._check_new_posts()
                
                # 处理队列中的请求
                self._process_queue()
                
                # 等待下一次检查
                time.sleep(self.check_interval)
            
            except Exception as e:
                logger.error(f"❌ 监控循环异常: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(self.check_interval)
    
    def _check_new_posts(self):
        """检查新帖子"""
        if not self.forum_crawler:
            logger.warning("⚠️ 论坛爬虫未初始化")
            return
        
        try:
            logger.info("🔍 检查新帖子...")
            
            # 获取新帖子
            new_posts = self.forum_crawler.get_new_posts_simple()
            
            if not new_posts:
                logger.debug("📭 暂无新帖子")
                return
            
            logger.info(f"🆕 发现 {len(new_posts)} 个新帖子")
            
            # 获取每个帖子的详细内容
            for post in new_posts:
                try:
                    thread_id = post.get('thread_id')
                    thread_url = post.get('thread_url')
                    
                    logger.info(f"📝 获取帖子详情: {thread_id}")
                    
                    # 获取帖子详细内容
                    thread_content = self.forum_crawler.get_thread_content(thread_id)
                    
                    if thread_content:
                        # 合并帖子信息
                        post.update(thread_content)
                        
                        # 添加到处理队列
                        self.request_queue.put(post)
                        logger.info(f"✅ 帖子已加入处理队列: {thread_id}")
                    else:
                        logger.warning(f"⚠️ 无法获取帖子详情: {thread_id}")
                
                except Exception as e:
                    logger.error(f"❌ 处理帖子异常: {e}")
        
        except Exception as e:
            logger.error(f"❌ 检查新帖子异常: {e}")
    
    def _process_queue(self):
        """处理队列中的请求"""
        while not self.request_queue.empty():
            try:
                post_data = self.request_queue.get(timeout=1)
                
                thread_id = post_data.get('thread_id')
                logger.info(f"⚙️ 处理帖子: {thread_id}")
                
                # 处理帖子
                success, result = self.processor.process_forum_post(post_data)
                
                if success:
                    logger.info(f"✅ 帖子处理成功: {thread_id}")
                    
                    # 生成回复消息
                    reply_message = self.processor.generate_reply_message(result)
                    
                    # 自动回复论坛
                    self._reply_to_forum(thread_id, reply_message)
                    
                    # 记录处理结果
                    self.processed_requests[thread_id] = {
                        'status': 'success',
                        'result': result,
                        'processed_at': datetime.now().isoformat()
                    }
                else:
                    logger.error(f"❌ 帖子处理失败: {thread_id}")
                    
                    # 生成错误回复
                    error_message = f"❌ 处理失败: {result.get('error', '未知错误')}"
                    
                    # 自动回复论坛
                    self._reply_to_forum(thread_id, error_message)
                    
                    # 记录处理结果
                    self.processed_requests[thread_id] = {
                        'status': 'failed',
                        'error': result.get('error'),
                        'processed_at': datetime.now().isoformat()
                    }
            
            except Exception as e:
                logger.error(f"❌ 处理队列异常: {e}")
    
    def _reply_to_forum(self, thread_id: str, message: str):
        """回复论坛"""
        if not self.forum_crawler:
            logger.warning("⚠️ 论坛爬虫未初始化，无法回复")
            return
        
        try:
            logger.info(f"📤 回复论坛: {thread_id}")
            
            success = self.forum_crawler.reply_to_thread(thread_id, message)
            
            if success:
                logger.info(f"✅ 回复成功: {thread_id}")
            else:
                logger.error(f"❌ 回复失败: {thread_id}")
        
        except Exception as e:
            logger.error(f"❌ 回复论坛异常: {e}")
    
    def get_queue_status(self) -> Dict:
        """获取队列状态"""
        return {
            'queue_size': self.request_queue.qsize(),
            'processed_count': len(self.processed_requests),
            'running': self.running
        }
    
    def get_processed_requests(self, limit: int = 10) -> List[Dict]:
        """获取已处理的请求"""
        items = list(self.processed_requests.items())
        return [
            {
                'thread_id': thread_id,
                **data
            }
            for thread_id, data in items[-limit:]
        ]


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("TTS论坛监控测试")
    print("=" * 60)
    
    monitor = TTSForumMonitor()
    
    print("\n测试1：获取队列状态")
    status = monitor.get_queue_status()
    print(f"  队列大小: {status['queue_size']}")
    print(f"  已处理: {status['processed_count']}")
    print(f"  运行中: {status['running']}")
    
    print("\n✅ 监控模块初始化成功")

