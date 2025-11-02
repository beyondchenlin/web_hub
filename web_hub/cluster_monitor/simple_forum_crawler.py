#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的论坛爬虫 - 专用于集群监控系统
只负责获取帖子列表，不做复杂的内容解析
"""

import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SimpleForumCrawler:
    """简化的论坛爬虫 - 只用于监控新帖子"""
    
    def __init__(self, username: str = "", password: str = "", base_url: str = "", forum_url: str = ""):
        # 从环境变量获取配置
        self.base_url = base_url or os.getenv('FORUM_BASE_URL', "https://aicut.lrtcai.com")
        self.forum_url = forum_url or os.getenv('FORUM_TARGET_URL', "https://aicut.lrtcai.com/forum-2-1.html")
        
        # 论坛账号信息
        self.username = (username or 
                        os.getenv('FORUM_USERNAME') or 
                        os.getenv('AICUT_ADMIN_USERNAME') or 
                        "AI剪辑助手")
        self.password = (password or 
                        os.getenv('FORUM_PASSWORD') or 
                        os.getenv('AICUT_ADMIN_PASSWORD') or 
                        "594188@lrtcai")
        
        # 初始化session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 禁用SSL验证
        self.session.verify = False
        
        self.logged_in = False
        self.processed_threads = set()
        self.first_check_completed = False
        
        # 已处理帖子文件路径
        self.processed_posts_file = "data/processed_posts.json"
        
        # 加载已处理的帖子
        self._load_processed_posts()
        
        print(f"🔍 初始化简化论坛爬虫")
        print(f"📍 目标板块: {self.forum_url}")
        print(f"💾 已处理帖子数: {len(self.processed_threads)}")
    
    def _load_processed_posts(self):
        """加载已处理的帖子列表"""
        try:
            if os.path.exists(self.processed_posts_file):
                with open(self.processed_posts_file, 'r', encoding='utf-8') as f:
                    processed_list = json.load(f)
                    self.processed_threads = set(processed_list)
                    print(f"💾 加载了 {len(self.processed_threads)} 个已处理帖子记录")
        except Exception as e:
            print(f"⚠️ 加载已处理帖子记录失败: {e}")
            self.processed_threads = set()
    
    def _save_processed_posts(self):
        """保存已处理的帖子列表到文件"""
        try:
            # 确保data目录存在
            os.makedirs(os.path.dirname(self.processed_posts_file), exist_ok=True)
            
            with open(self.processed_posts_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.processed_threads), f, ensure_ascii=False, indent=2)
            print(f"💾 已保存 {len(self.processed_threads)} 个已处理帖子记录")
        except Exception as e:
            print(f"❌ 保存已处理帖子记录失败: {e}")
    
    def mark_post_processed(self, post_id: str):
        """标记帖子为已处理并立即保存"""
        self.processed_threads.add(post_id)
        self._save_processed_posts()
    
    def login(self) -> bool:
        """登录论坛"""
        if not self.username or not self.password:
            print("⚠️ 未提供登录信息，以游客模式运行")
            return True
        
        try:
            print(f"🔐 尝试登录用户: {self.username}")
            print(f"🌐 登录URL: {self.base_url}")
            
            # 测试基础连接
            print("🔗 测试论坛连接...")
            test_response = self.session.get(self.base_url, timeout=10)
            print(f"✅ 论坛连接成功，状态码: {test_response.status_code}")
            
            # 获取登录页面
            print("📄 获取登录页面...")
            login_page = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login", timeout=10)
            print(f"📄 登录页面状态码: {login_page.status_code}")
            
            soup = BeautifulSoup(login_page.text, 'html.parser')
            
            # 查找formhash
            form_hash = ""
            form_hash_input = soup.find('input', {'name': 'formhash'})
            if form_hash_input:
                form_hash = form_hash_input.get('value', '')
                print(f"🔑 获取到formhash: {form_hash[:10]}...")
            
            # 登录数据
            login_data = {
                'formhash': form_hash,
                'referer': self.base_url,
                'loginfield': 'username',
                'username': self.username,
                'password': self.password,
                'questionid': 0,
                'answer': '',
                'loginsubmit': 'true'
            }
            
            print("📤 发送登录请求...")
            response = self.session.post(
                f"{self.base_url}/member.php?mod=logging&action=login&loginsubmit=yes&infloat=yes&lssubmit=yes",
                data=login_data,
                allow_redirects=True,
                timeout=10
            )
            
            print(f"📥 登录响应状态码: {response.status_code}")
            
            # 检查登录是否成功
            response_text = response.text
            if ('登录成功' in response_text or 
                'AI剪辑助手' in response_text or 
                self.username in response_text or 
                'ucenter_user' in response_text):
                self.logged_in = True
                print("✅ 登录成功")
                return True
            else:
                print("❌ 登录失败")
                return False
                
        except Exception as e:
            print(f"❌ 登录异常: {e}")
            return False

    def get_forum_threads(self) -> List[Dict[str, Any]]:
        """获取智能剪口播板块的所有帖子"""
        try:
            print(f"📋 获取板块帖子: {self.forum_url}")

            # 获取板块页面
            print("🌐 请求板块页面...")
            response = self.session.get(self.forum_url, timeout=15)
            print(f"📄 板块页面状态码: {response.status_code}")
            response.raise_for_status()

            page_content = response.text
            print(f"📄 页面内容长度: {len(page_content)} 字符")

            soup = BeautifulSoup(page_content, 'html.parser')
            threads = []

            # 查找帖子列表
            print("🔍 查找帖子列表...")
            thread_rows = soup.find_all('tbody')
            print(f"🔍 找到 {len(thread_rows)} 个tbody元素")

            # 如果tbody没找到，尝试其他选择器
            if not thread_rows:
                thread_rows = soup.find_all('tr')
                print(f"🔍 备用方案：找到 {len(thread_rows)} 个tr元素")

            for i, row in enumerate(thread_rows, 1):
                try:
                    # 查找帖子链接
                    thread_link = row.find('a', href=lambda x: x and 'thread-' in x)
                    if not thread_link:
                        continue

                    thread_url = thread_link.get('href')
                    if not thread_url.startswith('http'):
                        thread_url = self.base_url + '/' + thread_url.lstrip('/')

                    # 提取帖子ID
                    thread_id = ""
                    if 'thread-' in thread_url:
                        try:
                            thread_id = thread_url.split('thread-')[1].split('-')[0]
                        except:
                            continue

                    if not thread_id:
                        continue

                    # 获取帖子标题
                    title = thread_link.get_text(strip=True)
                    if not title or title in ['', ' ']:
                        title = f"帖子{thread_id}"

                    # 查找作者信息
                    author = "未知作者"
                    author_link = row.find('a', href=lambda x: x and ('uid-' in x or 'space-uid-' in x))
                    if author_link:
                        author = author_link.get_text(strip=True)

                    thread_info = {
                        'thread_id': thread_id,
                        'title': title,
                        'thread_url': thread_url,
                        'author': author
                    }

                    threads.append(thread_info)
                    print(f"📝 发现帖子 {i}: {title} (ID: {thread_id}) - 作者: {author}")

                except Exception as e:
                    # 跳过解析失败的行
                    continue

            print(f"📊 共发现 {len(threads)} 个帖子")
            return threads

        except Exception as e:
            print(f"❌ 获取板块帖子异常: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_new_posts_simple(self) -> List[Dict[str, Any]]:
        """简化的新帖监控：只获取帖子列表，不解析内容"""
        try:
            print(f"🔍 开始监控智能剪口播板块 ({datetime.now().strftime('%H:%M:%S')})")

            # 获取所有帖子（只有基本信息，不解析内容）
            threads = self.get_forum_threads()

            new_posts = []

            # 生产模式：只处理新帖子，持久化去重
            if not self.first_check_completed:
                # 首次启动：标记现有帖子为已处理，不实际处理
                print("🔄 生产模式首次启动，标记现有帖子为已处理...")
                for thread in threads:
                    thread_id = thread['thread_id']
                    self.mark_post_processed(thread_id)
                    print(f"📝 标记已存在帖子: {thread['title']} (ID: {thread_id})")

                self.first_check_completed = True
                print(f"✅ 首次检查完成，已标记 {len(threads)} 个现有帖子")
                print("🔍 下次检查将处理新发布的帖子")
                return []

            # 正常监控：只处理新帖子
            print("🚀 生产模式：只检查新帖子")
            for thread in threads:
                thread_id = thread['thread_id']

                # 跳过已处理的帖子
                if thread_id in self.processed_threads:
                    continue

                print(f"🆕 发现新帖子: {thread['title']} (ID: {thread_id})")

                # 只返回基本信息，不解析内容
                new_posts.append({
                    'thread_id': thread_id,
                    'title': thread['title'],
                    'thread_url': thread['thread_url'],
                    'author': thread.get('author', '未知作者'),
                    'forum_name': '智能剪口播'
                })

                # 标记为已处理
                self.mark_post_processed(thread_id)

            if new_posts:
                print(f"✅ 发现 {len(new_posts)} 个新帖子")
            else:
                print("📭 暂无新帖子")

            return new_posts

        except Exception as e:
            print(f"❌ 简化监控新帖异常: {e}")
            import traceback
            traceback.print_exc()
            return []
