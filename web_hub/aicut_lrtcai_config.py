#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
懒人同城号AI-智能剪口播 网站集成配置

网站: https://tts.lrtcai.com/
系统: Discuz! X3.5
功能: AI视频剪辑自动化服务
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

# 确保 shared 可用
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.forum_config import load_forum_settings

@dataclass
class AicutLrtcaiConfig:
    """懒人同城号AI网站配置"""
    
    # 网站基本信息 - 从环境变量读取，统一配置源
    site_name: str = "懒人同城号AI-智能剪口播"
    site_url: str = field(default_factory=lambda: load_forum_settings()["forum"].get("base_url", "https://tts.lrtcai.com") + "/")
    site_type: str = "discuz"
    site_version: str = "X3.5"

    # 论坛配置 - 从环境变量读取
    forum_url: str = field(default_factory=lambda: load_forum_settings()["forum"].get("base_url", "https://tts.lrtcai.com") + "/forum.php")
    mobile_url: str = field(default_factory=lambda: load_forum_settings()["forum"].get("base_url", "https://tts.lrtcai.com") + "/forum.php?mobile=yes")

    # 目标监控板块 - 从环境变量读取
    target_forum_id: int = field(default_factory=lambda: load_forum_settings()["forum"].get("forum_id", 2))
    target_forum_url: str = field(default_factory=lambda: load_forum_settings()["forum"].get("target_url", "https://tts.lrtcai.com/forum-2-1.html"))
    target_forum_name: str = "智能剪口播"

    # 登录配置 - 从环境变量读取
    admin_username: str = field(default_factory=lambda: load_forum_settings()["credentials"].get("username", ""))
    admin_password: str = field(default_factory=lambda: load_forum_settings()["credentials"].get("password", ""))
    
    # Cookie配置（用于保持登录状态）
    cookie_file: str = "cookies/aicut_lrtcai.txt"
    
    # 监控配置 - 从环境变量读取，统一配置源
    monitor_enabled: bool = field(default_factory=lambda: os.environ.get("FORUM_ENABLED", "true").lower() == "true")
    check_interval: int = field(default_factory=lambda: int(os.environ.get("FORUM_CHECK_INTERVAL", "10")))  # 统一使用环境变量
    target_forums: list = None  # 监控的版块ID列表，专门监控板块2
    
    # 回复配置
    auto_reply_enabled: bool = True
    reply_template: str = """🎬 AI智能剪辑已完成！

您的视频已经过AI智能处理，包括：
✨ 自动移除静音片段
🎯 智能语音识别和字幕生成
📝 AI剪辑优化
🎨 添加标题和字幕

📁 处理结果已保存，请查看输出目录获取处理后的视频文件。

---
🤖 懒人同城号AI助手自动回复
💡 让AI为您的视频内容赋能！"""
    
    # 视频处理配置
    supported_formats: list = None  # 支持的视频格式
    max_file_size_mb: int = 500  # 最大文件大小（MB）
    processing_timeout: int = 1800  # 处理超时时间（秒）
    
    # 输出配置
    output_quality: str = "high"  # high, medium, low
    add_watermark: bool = True
    watermark_text: str = "懒人同城号AI"
    
    def __post_init__(self):
        """初始化后处理"""
        if self.supported_formats is None:
            self.supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']
        
        if self.target_forums is None:
            self.target_forums = [2]  # 专门监控板块2（智能剪口播）
        
        # 确保cookie目录存在
        cookie_dir = os.path.dirname(self.cookie_file)
        if cookie_dir:
            os.makedirs(cookie_dir, exist_ok=True)


class AicutForumIntegration:
    """懒人同城号AI论坛集成器"""
    
    def __init__(self, config: AicutLrtcaiConfig):
        self.config = config
        self.session = None
        self.logged_in = False
    
    def setup_discuz_integration(self):
        """设置Discuz集成 - 使用专门的智能剪口播板块爬虫"""
        try:
            # 导入专门的板块爬虫
            from aicut_forum_crawler import AicutForumCrawler

            # 创建专门的板块爬虫实例
            self.aicut_crawler = AicutForumCrawler(
                username=self.config.admin_username,
                password=self.config.admin_password
            )

            print(f"✅ 智能剪口播板块爬虫设置完成")
            print(f"📍 监控板块: {self.config.target_forum_name} (ID: {self.config.target_forum_id})")
            print(f"🔗 板块地址: {self.config.target_forum_url}")
            return True

        except ImportError as e:
            print(f"❌ 导入板块爬虫失败: {e}")
            return False
        except Exception as e:
            print(f"❌ 设置板块爬虫失败: {e}")
            return False
    
    def login(self):
        """登录论坛"""
        try:
            if hasattr(self, 'aicut_crawler') and self.aicut_crawler:
                success = self.aicut_crawler.login()
                if success:
                    self.logged_in = True
                    print(f"✅ 成功登录: {self.config.site_name}")
                    return True

            print(f"❌ 登录失败: {self.config.site_name}")
            return False

        except Exception as e:
            print(f"❌ 登录异常: {e}")
            return False
    
    def get_new_posts(self):
        """获取新帖子 - 使用专门的智能剪口播板块爬虫"""
        try:
            print(f"🔍 监控智能剪口播板块...")

            # 使用专门的板块爬虫
            if hasattr(self, 'aicut_crawler'):
                new_posts = self.aicut_crawler.monitor_new_posts()

                # 转换为标准格式
                video_posts = []
                for post in new_posts:
                    # 选择最佳的视频URL
                    video_url = None
                    if post['video_urls']:
                        video_url = post['video_urls'][0]  # 使用第一个视频链接
                    elif post['attachments']:
                        # 使用第一个视频附件
                        for attachment in post['attachments']:
                            if attachment['type'] == 'video':
                                video_url = attachment['url']
                                break

                    if video_url:
                        video_posts.append({
                            'post_id': post['thread_id'],
                            'title': post['title'],
                            'author_id': post['author'],
                            'content': post['content'],
                            'video_url': video_url,
                            'post_url': post['thread_url'],
                            'forum_name': post['forum_name']
                        })

                return video_posts

            return []

        except Exception as e:
            print(f"❌ 获取新帖失败: {e}")
            return []
    
    def reply_to_post(self, post_id: str, content: str = None):
        """回复帖子"""
        try:
            if not self.logged_in:
                if not self.login():
                    return False

            reply_content = content or self.config.reply_template

            # 使用专门的板块爬虫发送回复
            if hasattr(self, 'aicut_crawler'):
                success = self.aicut_crawler.reply_to_thread(
                    thread_id=post_id,
                    content=reply_content
                )

                if success:
                    print(f"✅ 成功回复帖子: {post_id}")
                    return True
                else:
                    print(f"❌ 回复帖子失败: {post_id}")
                    return False

            return False

        except Exception as e:
            print(f"❌ 回复帖子异常: {e}")
            return False
    
    def _has_video_content(self, post: dict) -> bool:
        """检查帖子是否包含视频内容"""
        content = post.get('message', '').lower()
        title = post.get('subject', '').lower()
        
        # 检查关键词
        video_keywords = ['视频', 'video', '剪辑', '口播', 'mp4', 'avi', 'mov']
        
        for keyword in video_keywords:
            if keyword in content or keyword in title:
                return True
        
        # 检查是否有视频链接
        video_url = self._extract_video_url(post)
        return video_url is not None
    
    def _extract_video_url(self, post: dict) -> Optional[str]:
        """从帖子中提取视频URL"""
        import re
        
        content = post.get('message', '')
        
        # 常见视频URL模式
        url_patterns = [
            r'https?://[^\s]+\.(?:mp4|avi|mov|mkv|flv|wmv|webm)',  # 直链视频
            r'https?://[^\s]*(?:youtube|youtu\.be|bilibili|douyin)[^\s]*',  # 视频平台
            r'https?://[^\s]*(?:pan\.baidu|aliyundrive|123pan)[^\s]*',  # 网盘链接
        ]
        
        for pattern in url_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                return matches[0]
        
        return None


def create_aicut_config(admin_username: str = "", admin_password: str = "") -> AicutLrtcaiConfig:
    """创建懒人同城号AI配置"""
    config = AicutLrtcaiConfig()
    
    if admin_username:
        config.admin_username = admin_username
    if admin_password:
        config.admin_password = admin_password
    
    return config


def test_aicut_integration():
    """测试懒人同城号AI集成"""
    print("🧪 测试懒人同城号AI集成")
    print("=" * 50)
    
    # 创建配置（需要提供管理员账号）
    config = create_aicut_config()
    
    # 创建集成器
    integration = AicutForumIntegration(config)
    
    # 测试设置
    if integration.setup_discuz_integration():
        print("✅ Discuz集成设置成功")
        
        # 测试登录（需要提供真实账号）
        if config.admin_username and config.admin_password:
            if integration.login():
                print("✅ 论坛登录成功")
                
                # 测试获取帖子
                posts = integration.get_new_posts()
                print(f"📝 获取到 {len(posts)} 个相关帖子")
                
                for post in posts[:3]:  # 显示前3个
                    print(f"  - {post['title']} (ID: {post['post_id']})")
            else:
                print("❌ 论坛登录失败，请检查账号密码")
        else:
            print("⚠️ 未提供管理员账号，跳过登录测试")
    else:
        print("❌ Discuz集成设置失败")


if __name__ == "__main__":
    test_aicut_integration()
