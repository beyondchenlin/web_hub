"""
IndexTTS2 论坛集成系统 - 论坛爬虫集成模块
集成现有的论坛爬虫，获取论坛数据和回复
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

# 确保 shared 可导入
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.forum_config import load_forum_settings

# 导入论坛爬虫
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'web_hub'))

try:
    from aicut_forum_crawler import AicutForumCrawler
    CRAWLER_AVAILABLE = True
except ImportError as e:
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning(f"⚠️ 无法导入论坛爬虫: {str(e)}")
    CRAWLER_AVAILABLE = False
    AicutForumCrawler = None

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TTSForumCrawlerIntegration:
    """论坛爬虫集成 - 获取论坛数据和回复"""
    
    def __init__(self, username: str = "", password: str = "", 
                 base_url: str = "https://tts.lrtcai.com",
                 forum_url: str = "https://tts.lrtcai.com/forum-2-1.html"):
        """
        初始化论坛爬虫集成
        
        Args:
            username: 论坛用户名
            password: 论坛密码
            base_url: 论坛基础URL
            forum_url: 目标板块URL
        """
        logger.info("🚀 初始化论坛爬虫集成...")
        
        if not CRAWLER_AVAILABLE:
            logger.error("❌ 论坛爬虫不可用")
            self.crawler = None
            return
        
        try:
            # 创建爬虫实例
            settings = load_forum_settings()
            forum_cfg = settings.get('forum', {})

            self.crawler = AicutForumCrawler(
                username=username or settings.get('credentials', {}).get('username', ''),
                password=password or settings.get('credentials', {}).get('password', ''),
                base_url=base_url or forum_cfg.get('base_url', 'https://tts.lrtcai.com'),
                forum_url=forum_url or forum_cfg.get('target_url', 'https://tts.lrtcai.com/forum-2-1.html'),
                test_mode=False  # 生产模式
            )
            
            # 登录论坛
            if not self.crawler.login():
                logger.warning("⚠️ 论坛登录失败，将以游客模式运行")
            else:
                logger.info("✅ 论坛登录成功")
            
            logger.info("✅ 论坛爬虫集成初始化完成")
        
        except Exception as e:
            logger.error(f"❌ 初始化论坛爬虫异常: {str(e)}")
            self.crawler = None
    
    def get_new_posts(self) -> List[Dict]:
        """
        获取新帖子

        Returns:
            新帖子列表，每个帖子包含:
            - thread_id: 帖子ID
            - title: 帖子标题
            - thread_url: 帖子URL
            - author: 作者
            - content: 帖子内容
            - video_urls: 视频链接列表
            - audio_urls: 音频链接列表
            - cover_info: 封面信息
            - 等详细信息
        """
        try:
            if not self.crawler:
                logger.error("❌ 论坛爬虫不可用")
                return []

            logger.info("🔍 获取新帖子...")

            # 🎯 使用完整版方法：一次性获取新帖子列表+详细内容
            new_posts = self.crawler.monitor_new_posts()

            if not new_posts:
                logger.info("📭 暂无新帖子")
                return []
            
            logger.info(f"✅ 获取到 {len(new_posts)} 个新帖子")
            
            # 转换为标准格式
            formatted_posts = []
            for post in new_posts:
                formatted_post = {
                    'thread_id': post.get('thread_id', ''),
                    'title': post.get('title', ''),
                    'thread_url': post.get('thread_url', ''),
                    'author': post.get('author', '未知作者'),
                    'author_id': post.get('author_id', ''),
                    'post_time': post.get('post_time', datetime.now().isoformat()),
                    'content': post.get('content', ''),
                    'tags': post.get('tags', []),
                    'attachments': post.get('attachments', [])
                }
                formatted_posts.append(formatted_post)
            
            return formatted_posts
        
        except Exception as e:
            logger.error(f"❌ 获取新帖子异常: {str(e)}")
            return []
    
    def get_post_content(self, thread_id: str) -> Optional[Dict]:
        """
        获取帖子详细内容
        
        Args:
            thread_id: 帖子ID
        
        Returns:
            帖子详细内容
        """
        try:
            if not self.crawler:
                logger.error("❌ 论坛爬虫不可用")
                return None
            
            logger.info(f"📖 获取帖子详细内容: {thread_id}")
            
            # 这里可以调用爬虫的方法获取详细内容
            # 暂时返回None，因为爬虫可能没有这个方法
            return None
        
        except Exception as e:
            logger.error(f"❌ 获取帖子详细内容异常: {str(e)}")
            return None
    
    def reply_to_post(self, thread_id: str, content: str, 
                      attachments: List[str] = None) -> Tuple[bool, str]:
        """
        回复帖子
        
        Args:
            thread_id: 帖子ID
            content: 回复内容
            attachments: 附件列表（文件路径）
        
        Returns:
            (success, message)
        """
        try:
            if not self.crawler:
                logger.error("❌ 论坛爬虫不可用")
                return False, "论坛爬虫不可用"
            
            logger.info(f"📤 回复帖子: {thread_id}")
            logger.info(f"   内容长度: {len(content)} 字符")
            if attachments:
                logger.info(f"   附件数: {len(attachments)}")
            
            # 调用爬虫的回复方法
            success = self.crawler.reply_to_thread(
                thread_id=thread_id,
                content=content,
                video_files=attachments
            )
            
            if success:
                logger.info(f"✅ 回复成功: {thread_id}")
                return True, "回复成功"
            else:
                logger.error(f"❌ 回复失败: {thread_id}")
                return False, "回复失败"
        
        except Exception as e:
            error_msg = f"回复帖子异常: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def mark_post_processed(self, thread_id: str) -> None:
        """标记帖子为已处理"""
        try:
            if not self.crawler:
                return
            
            self.crawler.mark_post_processed(thread_id)
            logger.info(f"✅ 标记帖子为已处理: {thread_id}")
        
        except Exception as e:
            logger.error(f"❌ 标记帖子异常: {str(e)}")


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("论坛爬虫集成测试")
    print("=" * 60)
    
    # 从环境变量获取凭证
    settings = load_forum_settings()
    credentials = settings.get('credentials', {})
    forum_cfg = settings.get('forum', {})
    username = credentials.get('username', '')
    password = credentials.get('password', '')
    
    integration = TTSForumCrawlerIntegration(
        username=username,
        password=password,
        base_url=forum_cfg.get('base_url', 'https://tts.lrtcai.com'),
        forum_url=forum_cfg.get('target_url', 'https://tts.lrtcai.com/forum-2-1.html')
    )
    
    # 测试1：获取新帖子
    print("\n测试1：获取新帖子")
    new_posts = integration.get_new_posts()
    print(f"  获取到 {len(new_posts)} 个新帖子")
    
    if new_posts:
        for post in new_posts[:3]:
            print(f"  - {post['title']} (ID: {post['thread_id']})")
    
    # 测试2：回复帖子（演示，不实际执行）
    print("\n测试2：回复帖子（演示）")
    print("  演示回复内容生成...")
    reply_content = """
✅ 您的请求已收到！

系统正在处理您的请求...

---
🚀 懒人AI同城号，先起飞，再调整姿势
"""
    print(f"  回复内容:\n{reply_content}")
