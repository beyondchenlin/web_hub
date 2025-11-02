"""
IndexTTS2 论坛集成系统 - 完整集成管理器
整合所有模块：监控、处理、API、上传
"""

import os
import sys
import logging
import threading
import time
import sqlite3
from typing import Dict, Tuple, Optional
from datetime import datetime
from pathlib import Path
import uuid

# 导入所有模块
from tts_config import DATABASE_PATH
from tts_forum_monitor import TTSForumMonitor
from tts_forum_processor import TTSForumProcessor
from tts_api_service import TTSAPIService
from tts_forum_reply_uploader import TTSForumReplyUploader
from tts_forum_sync import TTSForumUserSync
from tts_forum_crawler_integration import TTSForumCrawlerIntegration

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TTSForumIntegrationManager:
    """完整的论坛集成管理器"""
    
    def __init__(self):
        """初始化集成管理器"""
        logger.info("🚀 初始化论坛集成管理器...")

        # 初始化论坛爬虫集成
        import os
        username = os.getenv('FORUM_USERNAME', 'AI剪辑助手')
        password = os.getenv('FORUM_PASSWORD', '594188@lrtcai')

        self.crawler_integration = TTSForumCrawlerIntegration(
            username=username,
            password=password
        )

        # 初始化所有模块
        self.monitor = TTSForumMonitor(None)  # 论坛监控
        self.processor = TTSForumProcessor()  # 请求处理
        self.api_service = TTSAPIService()    # API服务
        self.uploader = TTSForumReplyUploader()  # 回复上传
        self.user_sync = TTSForumUserSync()   # 用户同步

        # 状态跟踪
        self.is_running = False
        self.processing_thread = None
        self.processed_count = 0
        self.failed_count = 0

        logger.info("✅ 论坛集成管理器初始化完成")
    
    def start(self):
        """启动集成系统"""
        if self.is_running:
            logger.warning("⚠️ 系统已在运行中")
            return
        
        logger.info("🚀 启动论坛集成系统...")
        self.is_running = True
        
        # 启动处理线程
        self.processing_thread = threading.Thread(
            target=self._processing_loop,
            daemon=True
        )
        self.processing_thread.start()
        
        logger.info("✅ 论坛集成系统已启动")
    
    def stop(self):
        """停止集成系统"""
        logger.info("🛑 停止论坛集成系统...")
        self.is_running = False
        
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
        
        logger.info("✅ 论坛集成系统已停止")
    
    def _processing_loop(self):
        """主处理循环"""
        logger.info("🔄 启动主处理循环...")
        
        while self.is_running:
            try:
                # 1. 检查新帖子
                new_posts = self._check_new_posts()
                
                if new_posts:
                    logger.info(f"📬 发现 {len(new_posts)} 个新帖子")
                    
                    # 2. 处理每个帖子
                    for post in new_posts:
                        self._process_single_post(post)
                
                # 3. 检查待处理的请求
                pending_requests = self._get_pending_requests()
                
                if pending_requests:
                    logger.info(f"⏳ 发现 {len(pending_requests)} 个待处理请求")
                    
                    # 4. 处理待处理的请求
                    for request in pending_requests:
                        self._process_pending_request(request)
                
                # 5. 等待一段时间后继续
                time.sleep(60)  # 每60秒检查一次
            
            except Exception as e:
                logger.error(f"❌ 处理循环异常: {str(e)}")
                time.sleep(10)
    
    def _check_new_posts(self) -> list:
        """检查新帖子"""
        try:
            logger.info("🔍 检查新帖子...")

            # 调用论坛爬虫获取新帖子
            new_posts = self.crawler_integration.get_new_posts()

            if new_posts:
                logger.info(f"✅ 获取到 {len(new_posts)} 个新帖子")
            else:
                logger.info("📭 暂无新帖子")

            return new_posts

        except Exception as e:
            logger.error(f"❌ 检查新帖子异常: {str(e)}")
            return []
    
    def _process_single_post(self, post: Dict) -> None:
        """处理单个帖子"""
        try:
            logger.info(f"📝 处理帖子: {post.get('thread_id')}")
            
            # 1. 处理论坛帖子
            success, result = self.processor.process_forum_post(post)
            
            if not success:
                logger.error(f"❌ 帖子处理失败: {result.get('error')}")
                # 上传错误回复
                self.uploader.upload_error_reply(
                    request_id=post.get('thread_id'),
                    thread_id=post.get('thread_id'),
                    error_message=result.get('error', '未知错误')
                )
                self.failed_count += 1
                return
            
            # 2. 创建API请求
            request_id = str(uuid.uuid4())
            request_type = result.get('request_type')
            
            logger.info(f"✅ 帖子处理成功: {request_type}")
            
            # 3. 保存请求到数据库
            self._save_request_to_db(
                request_id=request_id,
                thread_id=post.get('thread_id'),
                user_id=result.get('tts_user_id'),
                request_type=request_type,
                request_data=result
            )
            
            self.processed_count += 1
        
        except Exception as e:
            logger.error(f"❌ 处理帖子异常: {str(e)}")
            self.failed_count += 1
    
    def _process_pending_request(self, request: Dict) -> None:
        """处理待处理的请求"""
        try:
            request_id = request.get('request_id')
            request_type = request.get('request_type')
            thread_id = request.get('thread_id')
            user_id = request.get('user_id')
            request_data = request.get('request_data')
            
            logger.info(f"🔄 处理待处理请求: {request_id} ({request_type})")
            
            # 根据请求类型调用相应的API
            if request_type == 'tts':
                success, result = self.api_service.process_tts_request(request_data)
                
                if success:
                    # 上传结果到论坛
                    self.uploader.upload_tts_result(
                        request_id=request_id,
                        thread_id=thread_id,
                        output_path=result.get('output_path'),
                        user_id=user_id
                    )
                else:
                    # 上传错误回复
                    self.uploader.upload_error_reply(
                        request_id=request_id,
                        thread_id=thread_id,
                        error_message=result.get('error', '未知错误')
                    )
            
            elif request_type == 'voice_clone':
                success, result = self.api_service.process_voice_clone_request(request_data)
                
                if success:
                    # 上传结果到论坛
                    self.uploader.upload_voice_clone_result(
                        request_id=request_id,
                        thread_id=thread_id,
                        voice_id=result.get('voice_id'),
                        voice_name=result.get('voice_name'),
                        user_id=user_id
                    )
                else:
                    # 上传错误回复
                    self.uploader.upload_error_reply(
                        request_id=request_id,
                        thread_id=thread_id,
                        error_message=result.get('error', '未知错误')
                    )
        
        except Exception as e:
            logger.error(f"❌ 处理待处理请求异常: {str(e)}")
    
    def _get_pending_requests(self) -> list:
        """获取待处理的请求"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM forum_tts_requests
                WHERE processing_status = 'pending'
                ORDER BY discovered_time ASC
                LIMIT 10
            """)

            requests = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return requests

        except Exception as e:
            logger.error(f"❌ 获取待处理请求异常: {str(e)}")
            return []
    
    def _save_request_to_db(self, request_id: str, thread_id: str, user_id: str,
                           request_type: str, request_data: Dict) -> None:
        """保存请求到数据库"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()

            import json

            # 提取请求数据中的字段
            tts_text = request_data.get('text', '')
            voice_name = request_data.get('voice_name', '')
            speed = request_data.get('speed', 1.0)
            emotion = request_data.get('emotion', '')
            emotion_weight = request_data.get('emotion_weight', 0.5)

            cursor.execute("""
                INSERT INTO forum_tts_requests
                (request_id, thread_id, user_id, request_type,
                 tts_text, voice_name, speed, emotion, emotion_weight,
                 processing_status, discovered_time, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (request_id, thread_id, user_id, request_type,
                  tts_text, voice_name, speed, emotion, emotion_weight,
                  'pending', datetime.now().isoformat(), json.dumps(request_data)))

            conn.commit()
            conn.close()

            logger.info(f"✅ 请求已保存到数据库: {request_id}")

        except Exception as e:
            logger.error(f"❌ 保存请求到数据库异常: {str(e)}")
    
    def get_status(self) -> Dict:
        """获取系统状态"""
        return {
            'is_running': self.is_running,
            'processed_count': self.processed_count,
            'failed_count': self.failed_count,
            'timestamp': datetime.now().isoformat()
        }


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("论坛集成管理器测试")
    print("=" * 60)
    
    manager = TTSForumIntegrationManager()
    
    # 测试1：获取系统状态
    print("\n测试1：获取系统状态")
    status = manager.get_status()
    print(f"  运行状态: {status['is_running']}")
    print(f"  已处理: {status['processed_count']}")
    print(f"  失败: {status['failed_count']}")
    
    # 测试2：启动系统
    print("\n测试2：启动系统")
    manager.start()
    print("  系统已启动")
    
    # 等待一段时间
    time.sleep(5)
    
    # 测试3：获取系统状态
    print("\n测试3：获取系统状态")
    status = manager.get_status()
    print(f"  运行状态: {status['is_running']}")
    
    # 测试4：停止系统
    print("\n测试4：停止系统")
    manager.stop()
    print("  系统已停止")

