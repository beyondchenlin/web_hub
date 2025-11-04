#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
懒人同城号AI - 智能剪口播板块专用爬虫

专门监控: https://tts.lrtcai.com/forum-2-1.html
板块ID: 2
板块名称: 智能剪口播
"""

import os
import re
import json
import sys
import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import urllib.parse
from pathlib import Path

# 确保可以导入 shared 模块
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.forum_config import load_forum_settings

# 尝试导入 Selenium（可选）
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class AicutForumCrawler:
    """懒人同城号AI论坛爬虫 - 专门监控智能剪口播板块"""

    def __init__(self, username: str = "", password: str = "", test_mode: bool = True, test_once: bool = False,
                 base_url: str = "", forum_url: str = ""):
        # 统一从配置文件加载默认设置
        settings = load_forum_settings()
        forum_cfg = settings.get("forum", {})
        credentials_cfg = settings.get("credentials", {})

        # 允许外部参数或环境变量覆盖
        self.base_url = base_url or os.getenv('FORUM_BASE_URL') or forum_cfg["base_url"]
        self.forum_url = forum_url or os.getenv('FORUM_TARGET_URL') or forum_cfg["target_url"]

        self.username = (
            username or
            os.getenv('FORUM_USERNAME') or
            os.getenv('AICUT_ADMIN_USERNAME') or
            credentials_cfg.get("username", "")
        )
        self.password = (
            password or
            os.getenv('FORUM_PASSWORD') or
            os.getenv('AICUT_ADMIN_PASSWORD') or
            credentials_cfg.get("password", "")
        )

        # 模式配置
        self.test_mode = test_mode  # 测试模式：重启后处理所有帖子；生产模式：持久化去重
        self.test_once = test_once  # 单次运行模式：处理一轮后停止
        self.processed_posts_file = "data/processed_posts.json"  # 已处理帖子的持久化文件

        # 会话管理
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

        # 禁用SSL验证以避免连接问题
        self.session.verify = False

        # 禁用SSL警告
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.logged_in = False
        self.last_check_time = 0
        self.processed_threads = set()  # 已处理的帖子ID
        self.first_check_completed = False  # 标记是否完成首次检查

        # 初始化已处理帖子列表
        self._load_processed_posts()

        print(f"🔍 初始化智能剪口播板块爬虫")
        print(f"📍 目标板块: {self.forum_url}")
        print(f"🎛️ 运行模式: {'🧪 测试模式' if self.test_mode else '🚀 生产模式'}")
        if not self.test_mode:
            print(f"💾 已处理帖子数: {len(self.processed_threads)}")

    def _load_processed_posts(self):
        """加载已处理的帖子列表"""
        if self.test_mode:
            # 测试模式：不加载历史记录，每次重启都是全新开始
            self.processed_threads = set()
            print("🧪 测试模式：不加载历史处理记录")
            return

        # 生产模式：从文件加载已处理的帖子ID
        try:
            # 确保data目录存在
            os.makedirs(os.path.dirname(self.processed_posts_file), exist_ok=True)

            if os.path.exists(self.processed_posts_file):
                with open(self.processed_posts_file, 'r', encoding='utf-8') as f:
                    processed_list = json.load(f)
                    self.processed_threads = set(processed_list)
                    print(f"💾 生产模式：加载了 {len(self.processed_threads)} 个已处理帖子记录")
            else:
                self.processed_threads = set()
                print("💾 生产模式：未找到历史记录文件，从空开始")
        except Exception as e:
            print(f"⚠️ 加载已处理帖子记录失败: {e}")
            self.processed_threads = set()

    def _save_processed_posts(self):
        """保存已处理的帖子列表到文件"""
        if self.test_mode:
            # 测试模式：不保存到文件
            return

        try:
            # 确保data目录存在
            os.makedirs(os.path.dirname(self.processed_posts_file), exist_ok=True)

            with open(self.processed_posts_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.processed_threads), f, ensure_ascii=False, indent=2)
            print(f"💾 已保存 {len(self.processed_threads)} 个已处理帖子记录")
        except Exception as e:
            print(f"❌ 保存已处理帖子记录失败: {e}")

    def mark_post_processed(self, post_id: str):
        """标记帖子为已处理并立即保存（生产模式）"""
        self.processed_threads.add(post_id)

        if not self.test_mode:
            # 生产模式：立即保存到文件
            self._save_processed_posts()
    
    def login(self) -> bool:
        """登录论坛"""
        if not self.username or not self.password:
            print("⚠️ 未提供登录信息，以游客模式运行")
            print(f"🔍 用户名: '{self.username}', 密码: {'已设置' if self.password else '未设置'}")
            return True

        try:
            print(f"🔐 尝试登录用户: {self.username}")
            print(f"🌐 登录URL: {self.base_url}")

            # 首先测试基础连接
            print("🔗 测试论坛连接...")
            test_response = self.session.get(self.base_url, timeout=10)
            print(f"✅ 论坛连接成功，状态码: {test_response.status_code}")

            # 获取登录页面
            print("📄 获取登录页面...")
            login_page = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login", timeout=10)
            print(f"📄 登录页面状态码: {login_page.status_code}")

            soup = BeautifulSoup(login_page.text, 'html.parser')

            # 查找登录表单的必要字段
            form_hash = ""
            form_hash_input = soup.find('input', {'name': 'formhash'})
            if form_hash_input:
                form_hash = form_hash_input.get('value', '')
                print(f"🔑 获取到formhash: {form_hash[:10]}...")
            else:
                print("⚠️ 未找到formhash字段")

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
            # 发送登录请求
            response = self.session.post(
                f"{self.base_url}/member.php?mod=logging&action=login&loginsubmit=yes&infloat=yes&lssubmit=yes&inajax=1",
                data=login_data,
                allow_redirects=True,
                timeout=10
            )

            print(f"📥 登录响应状态码: {response.status_code}")

            # 🔧 关键修复：检查登录是否成功
            response_text = response.text

            # 检查是否有明确的错误信息
            if '密码错误' in response_text:
                print("❌ 登录失败：密码错误")
                return False
            elif '用户名不存在' in response_text:
                print("❌ 登录失败：用户名不存在")
                return False
            elif response.status_code == 503:
                print("⚠️ 服务器限流（503），但可能已登录")
                # 检查cookies判断是否已登录
                if any(cookie.name in ['cdb_sid', 'cdb_auth'] for cookie in self.session.cookies):
                    self.logged_in = True
                    print("✅ 检测到登录cookie，登录成功")
                    return True
                return False

            # 检查登录成功的标志
            # 1. 重定向脚本（Discuz常见的登录成功响应）
            # 2. 包含用户名
            # 3. 包含登录成功提示
            # 4. 检查cookie
            if ('window.location.href' in response_text or  # 重定向脚本
                'reload="1"' in response_text or  # 重载标志
                '登录成功' in response_text or
                self.username in response_text or
                any(cookie.name in ['cdb_sid', 'cdb_auth'] for cookie in self.session.cookies)):
                self.logged_in = True
                print("✅ 登录成功")
                return True
            else:
                print("❌ 登录失败：未检测到登录成功标志")
                print(f"响应内容前200字符: {response_text[:200]}...")
                return False

        except Exception as e:
            print(f"❌ 登录异常: {e}")
            import traceback
            traceback.print_exc()
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

            # 保存页面内容用于调试
            page_content = response.text
            print(f"📄 页面内容长度: {len(page_content)} 字符")

            soup = BeautifulSoup(page_content, 'html.parser')
            threads = []

            # 查找帖子列表 - 尝试多种选择器
            print("🔍 查找帖子列表...")

            # 方法1: 查找tbody标签
            thread_rows = soup.find_all('tbody')
            print(f"🔍 找到 {len(thread_rows)} 个tbody元素")

            # 方法2: 如果tbody没找到，尝试其他选择器
            if not thread_rows:
                thread_rows = soup.find_all('tr')
                print(f"🔍 备用方案：找到 {len(thread_rows)} 个tr元素")

            # 方法3: 查找包含thread链接的元素
            if not thread_rows:
                thread_links = soup.find_all('a', href=re.compile(r'thread-\d+-\d+-\d+\.html'))
                print(f"🔍 直接查找：找到 {len(thread_links)} 个thread链接")
                # 将链接转换为行格式
                thread_rows = [link.parent for link in thread_links if link.parent]

            processed_thread_ids = set()  # 避免重复处理

            for i, row in enumerate(thread_rows):
                try:
                    # 查找帖子链接 - 优先查找带标题的链接（class="xst"）
                    thread_link = row.find('a', class_='xst', href=re.compile(r'thread-\d+-\d+-\d+\.html'))

                    # 如果没找到，查找所有thread链接，选择有文本的
                    if not thread_link:
                        all_thread_links = row.find_all('a', href=re.compile(r'thread-\d+-\d+-\d+\.html'))
                        for link in all_thread_links:
                            if link.get_text(strip=True):
                                thread_link = link
                                break

                    # 如果还是没找到，使用第一个thread链接
                    if not thread_link:
                        thread_link = row.find('a', href=re.compile(r'thread-\d+-\d+-\d+\.html'))

                    if not thread_link:
                        continue

                    # 提取帖子信息
                    thread_url = thread_link.get('href')
                    if not thread_url.startswith('http'):
                        thread_url = self.base_url + '/' + thread_url.lstrip('/')

                    # 提取帖子ID
                    thread_id_match = re.search(r'thread-(\d+)-', thread_url)
                    if not thread_id_match:
                        continue

                    thread_id = thread_id_match.group(1)

                    # 避免重复处理
                    if thread_id in processed_thread_ids:
                        continue
                    processed_thread_ids.add(thread_id)

                    # 获取帖子标题
                    title = thread_link.get_text(strip=True)

                    # 如果标题为空，尝试从其他thread链接获取
                    if not title:
                        all_thread_links = row.find_all('a', href=re.compile(r'thread-\d+-\d+-\d+\.html'))
                        for link in all_thread_links:
                            link_text = link.get_text(strip=True)
                            if link_text:
                                title = link_text
                                break

                    # 查找作者信息
                    author_link = row.find('a', href=re.compile(r'space-uid-\d+\.html'))
                    author = author_link.get_text(strip=True) if author_link else "未知用户"

                    # 查找发帖时间
                    time_elements = row.find_all('em')
                    post_time = ""
                    for elem in time_elements:
                        text = elem.get_text(strip=True)
                        if '小时前' in text or '分钟前' in text or '天前' in text or '-' in text:
                            post_time = text
                            break

                    thread_info = {
                        'thread_id': thread_id,
                        'title': title,
                        'author': author,
                        'thread_url': thread_url,
                        'post_time': post_time,
                        'forum_id': 2,
                        'forum_name': '智能剪口播'
                    }

                    threads.append(thread_info)
                    print(f"📝 发现帖子 {len(threads)}: {title} (ID: {thread_id}) - 作者: {author}")

                except Exception as e:
                    print(f"⚠️ 解析第 {i+1} 个帖子行失败: {e}")
                    continue

            print(f"📊 共发现 {len(threads)} 个帖子")

            # 如果没有找到帖子，输出调试信息
            if not threads:
                print("🔍 未找到帖子，输出页面调试信息...")
                print(f"页面标题: {soup.title.get_text() if soup.title else '无标题'}")
                # 查找可能的错误信息
                error_divs = soup.find_all('div', class_=['error', 'message'])
                for error_div in error_divs:
                    print(f"错误信息: {error_div.get_text(strip=True)}")

                # 输出页面的前1000个字符用于调试
                print("页面内容预览:")
                print(page_content[:1000])
                print("..." if len(page_content) > 1000 else "")

            return threads

        except Exception as e:
            print(f"❌ 获取板块帖子异常: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_thread_content(self, thread_url: str) -> Dict[str, Any]:
        """获取帖子详细内容"""
        try:
            print(f"📖 获取帖子内容: {thread_url}")
            
            response = self.session.get(thread_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找帖子内容 - 尝试多种选择器以获取完整内容
            content = ""

            # 尝试多种内容选择器，优先选择包含更多信息的
            content_selectors = [
                # 最佳选择器：包含完整内容和封面标题
                'div.pct',
                # 完整帖子内容区域
                'div.postmessage',
                'div.t_fsz',
                'td.t_f',
                # 更广泛的内容区域
                'div.plhin',
                # 备用选择器
                'div[id^="postmessage_"]',
                'td[id^="postmessage_"]'
            ]

            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    content = content_div.get_text(separator='\n', strip=True)
                    print(f"📄 使用选择器提取内容: {selector} (长度: {len(content)})")
                    break

            # 如果仍然没有找到内容，尝试从整个页面提取
            if not content:
                # 查找包含帖子内容的主要区域
                main_content = soup.find('div', {'id': 'ct'}) or soup.find('div', class_='wp')
                if main_content:
                    content = main_content.get_text(separator='\n', strip=True)
                    print(f"📄 使用主要区域提取内容 (长度: {len(content)})")
                else:
                    # 最后的备用方案
                    content = soup.get_text(separator='\n', strip=True)
                    print(f"📄 使用整页内容提取 (长度: {len(content)})")
            
            # 查找视频链接和文件名
            video_urls, original_filenames = self._extract_video_urls_and_names(str(soup))

            # 查找音频链接
            audio_urls = self._extract_audio_urls(str(soup))

            # 查找附件
            attachments = self._extract_attachments(soup)

            # 提取封面信息
            cover_info = self._extract_cover_info(content)

            # 结构化内容处理
            structured_content = self._process_structured_content(content)

            return {
                'content': content,                                    # 原始内容
                'structured_content': structured_content,             # 结构化内容
                'core_text': structured_content.get('core_text', ''), # 核心文本（用于热词）
                'video_urls': video_urls,
                'original_filenames': original_filenames,
                'audio_urls': audio_urls,
                'attachments': attachments,
                'cover_info': cover_info,
                'has_video': len(video_urls) > 0 or len(attachments) > 0,
                'has_audio': len(audio_urls) > 0
            }
            
        except Exception as e:
            print(f"❌ 获取帖子内容失败: {e}")
            return {
                'content': "",
                'video_urls': [],
                'audio_urls': [],
                'attachments': [],
                'cover_info': {},
                # 🎯 源头修复：错误情况下也提供空的封面标题字段
                'cover_title_up': '',
                'cover_title_down': '',
                'has_video': False,
                'has_audio': False
            }
    
    def _extract_video_urls_and_names(self, html_content: str) -> Tuple[List[str], List[str]]:
        """从HTML内容中提取视频链接和对应的文件名"""
        video_urls = []
        video_names = []

        # 首先尝试解析HTML <a> 标签格式: <a href="链接">文件名</a>
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # 查找所有包含视频链接的 <a> 标签
        video_links = soup.find_all('a', href=re.compile(r'https?://[^"\']*\.(?:mp4|avi|mov|mkv|flv|wmv|webm)', re.IGNORECASE))

        for link in video_links:
            url = link.get('href')
            filename = link.get_text(strip=True)

            if url and filename:
                video_urls.append(url)
                # 清理文件名，确保有正确的扩展名
                clean_filename = filename.strip()
                if not any(clean_filename.lower().endswith(ext) for ext in ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']):
                    clean_filename += '.mp4'
                video_names.append(clean_filename)
                print(f"📝 HTML链接解析: {url} -> {clean_filename}")

        # 如果没有找到HTML链接，尝试解析BBCode格式的链接: [url=链接]文件名[/url]
        if not video_urls:
            bbcode_pattern = r'\[url=(https?://[^\]]+\.(?:mp4|avi|mov|mkv|flv|wmv|webm)[^\]]*)\]([^[]+)\[/url\]'
            bbcode_matches = re.findall(bbcode_pattern, html_content, re.IGNORECASE)

            for url, filename in bbcode_matches:
                video_urls.append(url)
                # 清理文件名，确保有正确的扩展名
                clean_filename = filename.strip()
                if not any(clean_filename.lower().endswith(ext) for ext in ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']):
                    clean_filename += '.mp4'
                video_names.append(clean_filename)
                print(f"📝 BBCode解析: {url} -> {clean_filename}")

        # 如果都没有找到，使用传统的URL提取方式
        if not video_urls:
            # 视频URL模式 - 针对您网站的腾讯云COS存储
            patterns = [
                # 腾讯云COS视频链接 (您网站使用的存储)
                r'https?://lrtcai-\d+\.cos\.ap-[^/]+\.myqcloud\.com/[^\s<>"\']*\.(?:mp4|avi|mov|mkv|flv|wmv|webm)',
                # 通用直链视频
                r'https?://[^\s<>"\']+\.(?:mp4|avi|mov|mkv|flv|wmv|webm)',
                # 视频平台链接
                r'https?://[^\s<>"\']*(?:youtube|youtu\.be|bilibili|douyin)[^\s<>"\']*',
                # 网盘链接
                r'https?://[^\s<>"\']*(?:pan\.baidu|aliyundrive|123pan)[^\s<>"\']*',
            ]

            for pattern in patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                video_urls.extend(matches)

            # 去重并过滤
            unique_urls = list(set(video_urls))

            # 过滤掉音频文件（.mp3等）
            video_only_urls = []
            for url in unique_urls:
                if not any(url.lower().endswith(ext) for ext in ['.mp3', '.wav', '.aac', '.flac']):
                    video_only_urls.append(url)

            video_urls = video_only_urls
            # 对于传统方式提取的URL，从URL中提取文件名
            video_names = [self._extract_filename_from_url(url) for url in video_urls]

        return video_urls, video_names

    def _extract_video_urls(self, html_content: str) -> List[str]:
        """从HTML内容中提取视频链接（保持向后兼容）"""
        video_urls, _ = self._extract_video_urls_and_names(html_content)
        return video_urls

    def _extract_filename_from_url(self, url: str) -> str:
        """从URL中提取原始文件名，保持中文字符"""
        try:
            import urllib.parse
            import os

            # 解析URL
            parsed_url = urllib.parse.urlparse(url)

            # 从路径中提取文件名
            path = parsed_url.path
            if not path:
                return ""

            # 获取路径的最后一部分（文件名）
            filename = os.path.basename(path)

            if not filename:
                return ""

            # URL解码，处理中文字符
            filename = urllib.parse.unquote(filename, encoding='utf-8')

            # 验证文件名是否为视频文件
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']
            if not any(filename.lower().endswith(ext) for ext in video_extensions):
                # 如果没有视频扩展名，添加.mp4
                if '.' not in filename:
                    filename += '.mp4'
                else:
                    # 替换扩展名为.mp4
                    name_without_ext = os.path.splitext(filename)[0]
                    filename = name_without_ext + '.mp4'

            # 清理文件名中的非法字符（保留中文）
            # 移除Windows文件名中不允许的字符，但保留中文
            illegal_chars = r'[<>:"/\\|?*]'
            filename = re.sub(illegal_chars, '_', filename)

            # 限制文件名长度
            if len(filename) > 200:
                name_part, ext_part = os.path.splitext(filename)
                max_name_length = 200 - len(ext_part)
                filename = name_part[:max_name_length] + ext_part

            return filename

        except Exception as e:
            print(f"⚠️ 无法从URL提取文件名: {e}")
            return ""

    def extract_original_filenames(self, video_urls: List[str], html_content: str = None) -> List[str]:
        """提取视频URL列表对应的原始文件名列表"""
        if html_content:
            # 如果提供了HTML内容，重新解析以获取准确的文件名
            urls, filenames = self._extract_video_urls_and_names(html_content)
            # 返回与提供的video_urls匹配的文件名
            result_filenames = []
            for url in video_urls:
                if url in urls:
                    idx = urls.index(url)
                    result_filenames.append(filenames[idx])
                else:
                    # 备用方案：从URL提取
                    filename = self._extract_filename_from_url(url)
                    result_filenames.append(filename if filename else f"video_{len(result_filenames)+1}.mp4")
            return result_filenames
        else:
            # 传统方式：从URL提取文件名
            filenames = []
            for url in video_urls:
                filename = self._extract_filename_from_url(url)
                if filename:
                    filenames.append(filename)
                    print(f"📝 提取文件名: {url} -> {filename}")
                else:
                    # 如果无法提取，使用URL的最后部分作为备用
                    import os
                    backup_name = os.path.basename(url.split('?')[0])  # 移除查询参数
                    if not backup_name.endswith('.mp4'):
                        backup_name += '.mp4'
                    filenames.append(backup_name)
                    print(f"📝 备用文件名: {url} -> {backup_name}")
            return filenames

    def _extract_audio_urls(self, html_content: str) -> List[str]:
        """从HTML内容中提取音频链接"""
        audio_urls = []

        # 音频URL模式 - 针对您网站的腾讯云COS存储
        patterns = [
            # 腾讯云COS音频链接（增加amr格式支持）
            r'https?://lrtcai-\d+\.cos\.ap-[^/]+\.myqcloud\.com/[^\s<>"\']*\.(?:mp3|wav|aac|flac|m4a|amr)',
            # 通用音频链接（增加amr格式支持）
            r'https?://[^\s<>"\']+\.(?:mp3|wav|aac|flac|m4a|amr)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            audio_urls.extend(matches)

        # 去重
        return list(set(audio_urls))

    def _extract_cover_info(self, content: str) -> Dict[str, str]:
        """提取封面信息 - 使用统一的up/down函数"""
        cover_info = {}

        try:
            # 🎯 使用统一的封面标题提取函数（视频处理模块，TTS系统可选）
            from pre.stage.unified_content_processor import extract_cover_title_up, extract_cover_title_middle, extract_cover_title_down

            # 提取封面标题上、中、下
            cover_title_up = extract_cover_title_up(content)
            cover_title_middle = extract_cover_title_middle(content)
            cover_title_down = extract_cover_title_down(content)

            # 🎯 使用统一的up/middle/down字段名，只保存和显示有内容的标题
            extracted_titles = []

            if cover_title_up:
                cover_info['cover_title_up'] = cover_title_up
                extracted_titles.append(f"上标题: '{cover_title_up}'")

            if cover_title_middle:
                cover_info['cover_title_middle'] = cover_title_middle
                extracted_titles.append(f"中标题: '{cover_title_middle}'")

            if cover_title_down:
                cover_info['cover_title_down'] = cover_title_down
                extracted_titles.append(f"下标题: '{cover_title_down}'")

            # 统一显示提取到的标题
            if extracted_titles:
                print("📝 提取到的封面标题:")
                for title in extracted_titles:
                    print(f"   {title}")
        except ImportError:
            # TTS系统不需要视频处理模块，跳过封面标题提取
            pass

        return cover_info

    def _process_structured_content(self, content: str) -> Dict[str, Any]:
        """处理结构化内容"""
        try:
            # 导入内容处理器
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))

            try:
                from pre.stage.unified_content_processor import process_forum_content_unified

                # 使用统一结构化处理器
                structured = process_forum_content_unified(content)

                return {
                    'core_text': structured.core_text,
                    'system_tags': structured.system_tags or [],
                    'cover_title_up': structured.cover_title_up,
                    'cover_title_middle': structured.cover_title_middle,
                    'cover_title_down': structured.cover_title_down,
                    'urls': structured.urls or [],
                    'bbcode_tags': structured.bbcode_tags or [],
                    'content_type': structured.content_type,
                    'has_media_content': structured.has_media_content,
                    'original_length': structured.original_length,
                    'core_text_length': structured.core_text_length,
                    'filtered_elements_count': structured.filtered_elements_count
                }

            except ImportError:
                print("⚠️ 统一内容处理器不可用，使用基础处理")
                return self._basic_content_processing(content)

        except Exception as e:
            print(f"❌ 结构化内容处理失败: {e}")
            return self._basic_content_processing(content)

    def _basic_content_processing(self, content: str) -> Dict[str, Any]:
        """基础内容处理（备用方案）"""
        import re

        # 基础清理
        core_text = content

        # 移除系统标识
        core_text = re.sub(r'懒人智能剪辑\s*', '', core_text)

        # 移除封面信息
        core_text = re.sub(r'封面标题[上中下]?\s*[:：]\s*[^\n]*', '', core_text)

        # 移除链接
        core_text = re.sub(r'https?://[^\s]+', '', core_text)
        core_text = re.sub(r'\[url[^\]]*\].*?\[/url\]', '', core_text, flags=re.IGNORECASE)

        # 清理空格
        core_text = re.sub(r'\s+', ' ', core_text).strip()

        return {
            'core_text': core_text,
            'system_tags': [],
            'cover_title_up': '',
            'cover_title_down': '',
            'urls': [],
            'bbcode_tags': [],
            'content_type': 'text_only',
            'has_media_content': False,
            'original_length': len(content),
            'core_text_length': len(core_text),
            'filtered_elements_count': 0
        }

    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """提取附件信息"""
        attachments = []
        
        # 查找附件链接
        attach_links = soup.find_all('a', href=re.compile(r'attachment\.php'))
        
        for link in attach_links:
            attach_url = link.get('href')
            if not attach_url.startswith('http'):
                attach_url = self.base_url + '/' + attach_url.lstrip('/')
            
            attach_name = link.get_text(strip=True)
            
            # 检查是否为视频文件
            if any(ext in attach_name.lower() for ext in ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']):
                attachments.append({
                    'name': attach_name,
                    'url': attach_url,
                    'type': 'video'
                })
        
        return attachments
    
    def monitor_new_posts(self) -> List[Dict[str, Any]]:
        """监控新帖子 - 智能模式切换版本"""
        try:
            print(f"🔍 开始监控智能剪口播板块 ({datetime.now().strftime('%H:%M:%S')})")

            # 获取所有帖子
            threads = self.get_forum_threads()

            new_video_posts = []

            # 测试模式 vs 生产模式的不同处理逻辑
            if self.test_mode:
                # 🧪 测试模式：处理所有帖子（包括已处理过的）
                print("🧪 测试模式：检查所有帖子")
                for thread in threads:
                    thread_id = thread['thread_id']

                    print(f"🔍 检查帖子: {thread['title']} (ID: {thread_id})")

                    # 获取帖子详细内容
                    thread_content = self.get_thread_content(thread['thread_url'])

                    # 🎯 支持三种类型的帖子：
                    # 1. 视频帖子（视频处理）
                    # 2. 音频帖子（音色克隆）
                    # 3. 纯文本帖子（TTS合成）
                    has_media = thread_content['has_video'] or thread_content['has_audio']
                    has_text = bool(thread_content.get('content', '').strip())

                    if has_media or has_text:
                        # 合并信息
                        media_post = {**thread, **thread_content}
                        new_video_posts.append(media_post)

                        if has_media:
                            print(f"🎬 发现媒体帖子: {thread['title']}")
                            print(f"   视频链接: {len(thread_content['video_urls'])} 个")
                            print(f"   音频链接: {len(thread_content['audio_urls'])} 个")
                            print(f"   附件: {len(thread_content['attachments'])} 个")

                            # 显示具体链接
                            for i, url in enumerate(thread_content['video_urls'], 1):
                                print(f"     视频{i}: {url}")
                            for i, url in enumerate(thread_content['audio_urls'], 1):
                                print(f"     音频{i}: {url}")
                        else:
                            print(f"📝 发现文本帖子: {thread['title']}")
                            print(f"   内容长度: {len(thread_content.get('content', ''))} 字符")

                        # 显示封面信息
                        if thread_content['cover_info']:
                            print(f"   封面信息: {thread_content['cover_info']}")
                    else:
                        print(f"⚠️ 帖子无有效内容: {thread['title']}")

                    # 测试模式：标记为已处理（仅在内存中）
                    self.processed_threads.add(thread_id)

            else:
                # 🚀 生产模式：只处理新帖子，持久化去重
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

                    # 获取帖子详细内容
                    thread_content = self.get_thread_content(thread['thread_url'])

                    # 🎯 支持三种类型的帖子：
                    # 1. 视频帖子（视频处理）
                    # 2. 音频帖子（音色克隆）
                    # 3. 纯文本帖子（TTS合成）
                    has_media = thread_content['has_video'] or thread_content['has_audio']
                    has_text = bool(thread_content.get('content', '').strip())

                    if has_media or has_text:
                        # 合并信息
                        media_post = {**thread, **thread_content}
                        new_video_posts.append(media_post)

                        if has_media:
                            print(f"🎬 发现媒体帖子: {thread['title']}")
                            print(f"   视频链接: {len(thread_content['video_urls'])} 个")
                            print(f"   音频链接: {len(thread_content['audio_urls'])} 个")
                            print(f"   附件: {len(thread_content['attachments'])} 个")

                            # 显示具体链接
                            for i, url in enumerate(thread_content['video_urls'], 1):
                                print(f"     视频{i}: {url}")
                            for i, url in enumerate(thread_content['audio_urls'], 1):
                                print(f"     音频{i}: {url}")
                        else:
                            print(f"📝 发现文本帖子: {thread['title']}")
                            print(f"   内容长度: {len(thread_content.get('content', ''))} 字符")

                        # 显示封面信息
                        if thread_content['cover_info']:
                            print(f"   封面信息: {thread_content['cover_info']}")
                    else:
                        print(f"⚠️ 新帖子无有效内容: {thread['title']}")

                    # 生产模式：标记为已处理并立即保存
                    self.mark_post_processed(thread_id)

            if new_video_posts:
                print(f"✅ 发现 {len(new_video_posts)} 个新的视频帖子")
            else:
                print("📭 暂无新的视频帖子")

            return new_video_posts

        except Exception as e:
            print(f"❌ 监控新帖失败: {e}")
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

    def reply_to_thread(self, thread_id: str, content: str, video_files: List[str] = None) -> bool:
        """回复帖子，支持上传视频文件"""
        try:
            if not self.logged_in:
                print("⚠️ 未登录，无法回复帖子")
                return False

            print(f"📤 回复帖子: {thread_id}")
            if video_files:
                print(f"📁 准备上传 {len(video_files)} 个视频文件")

            # 如果有视频文件，使用完整的回复页面而不是快速回复
            if video_files:
                return self._reply_with_attachments(thread_id, content, video_files)
            else:
                return self._reply_text_only(thread_id, content)

        except Exception as e:
            print(f"❌ 回复帖子异常: {e}")
            return False

    def _reply_text_only(self, thread_id: str, content: str) -> bool:
        """纯文本回复（快速回复）"""
        try:
            # 构建回复URL
            reply_url = f"{self.base_url}/forum.php?mod=post&action=reply&tid={thread_id}&infloat=yes&handlekey=fastpost"

            # 获取回复页面获取formhash
            reply_page = self.session.get(reply_url)
            soup = BeautifulSoup(reply_page.text, 'html.parser')

            form_hash = ""
            form_hash_input = soup.find('input', {'name': 'formhash'})
            if form_hash_input:
                form_hash = form_hash_input.get('value', '')

            # 回复数据
            reply_data = {
                'formhash': form_hash,
                'posttime': int(time.time()),
                'message': content,
                'replysubmit': 'yes',
                'infloat': 'yes',
                'handlekey': 'fastpost',
                'inajax': '1'
            }

            # 发送回复
            response = self.session.post(
                f"{self.base_url}/forum.php?mod=post&action=reply&tid={thread_id}&infloat=yes&handlekey=fastpost&inajax=1",
                data=reply_data
            )

            if '回复发布成功' in response.text or 'succeed' in response.text.lower():
                print(f"✅ 回复成功: {thread_id}")
                return True
            else:
                print(f"❌ 回复失败: {thread_id}")
                print(f"响应: {response.text[:200]}...")
                return False

        except Exception as e:
            print(f"❌ 文本回复异常: {e}")
            return False

    def _reply_with_attachments(self, thread_id: str, content: str, video_files: List[str]) -> bool:
        """带附件的回复 - 支持腾讯云上传按钮"""
        try:
            import os

            # 构建完整回复页面URL
            reply_url = f"{self.base_url}/forum.php?mod=post&action=reply&tid={thread_id}"

            # 获取回复页面
            reply_page = self.session.get(reply_url)
            soup = BeautifulSoup(reply_page.text, 'html.parser')

            # 获取formhash
            form_hash = ""
            form_hash_input = soup.find('input', {'name': 'formhash'})
            if form_hash_input:
                form_hash = form_hash_input.get('value', '')

            print(f"📝 获取到formhash: {form_hash[:10]}...")

            # 检查是否有腾讯云上传按钮
            tencent_upload_button = self._find_tencent_upload_button(soup)
            if tencent_upload_button:
                print("🔍 发现腾讯云上传按钮，尝试使用腾讯云上传...")
                success = self._upload_via_tencent_cloud(thread_id, content, video_files, form_hash, soup)
                if success:
                    return True
                else:
                    print("⚠️ 腾讯云上传失败，回退到传统上传方式...")

            # 传统文件上传方式
            return self._upload_via_traditional_method(thread_id, content, video_files, form_hash)

        except Exception as e:
            print(f"❌ 带附件回复异常: {e}")
            # 如果附件上传失败，尝试纯文本回复
            print("🔄 尝试纯文本回复...")
            return self._reply_text_only(thread_id, content)

    def _find_tencent_upload_button(self, soup: BeautifulSoup) -> bool:
        """查找腾讯云上传按钮"""
        try:
            # 查找可能的腾讯云上传按钮
            tencent_buttons = soup.find_all(['button', 'input', 'a'], string=re.compile(r'腾讯云|上传|云存储', re.I))

            # 查找包含腾讯云相关class或id的元素
            tencent_elements = soup.find_all(['div', 'button', 'input'],
                                           attrs={'class': re.compile(r'tencent|cloud|upload', re.I)})
            tencent_elements.extend(soup.find_all(['div', 'button', 'input'],
                                                attrs={'id': re.compile(r'tencent|cloud|upload', re.I)}))

            if tencent_buttons or tencent_elements:
                print(f"🔍 发现 {len(tencent_buttons)} 个腾讯云按钮，{len(tencent_elements)} 个相关元素")
                return True

            return False
        except Exception as e:
            print(f"❌ 查找腾讯云上传按钮失败: {e}")
            return False

    def _upload_via_tencent_cloud(self, thread_id: str, content: str, video_files: List[str],
                                 form_hash: str, soup: BeautifulSoup) -> bool:
        """通过腾讯云上传按钮上传文件"""
        try:
            print("🚀 尝试腾讯云上传方式...")

            # 直接使用发现的腾讯云API端点
            tencent_api_url = f"{self.base_url}/source/plugin/tencentcos/upload_api.php"

            uploaded_files = []

            for video_file in video_files:
                if not os.path.exists(video_file):
                    print(f"⚠️ 文件不存在，跳过: {video_file}")
                    continue

                file_size = os.path.getsize(video_file) / (1024 * 1024)  # MB
                print(f"☁️ 腾讯云上传: {os.path.basename(video_file)} ({file_size:.1f} MB)")

                try:
                    with open(video_file, 'rb') as f:
                        files = {
                            'Filedata': (os.path.basename(video_file), f, 'video/mp4')
                        }

                        data = {
                            'filetype': 'video'
                        }

                        response = self.session.post(
                            tencent_api_url,
                            data=data,
                            files=files,
                            timeout=300
                        )

                        if response.status_code == 200:
                            try:
                                import json
                                response_data = json.loads(response.text)

                                if response_data.get('code') == 0 and 'data' in response_data:
                                    file_info = response_data['data']
                                    tencent_url = file_info.get('url')
                                    aid = file_info.get('aid')
                                    filename = file_info.get('filename')

                                    if tencent_url:
                                        uploaded_files.append({
                                            'url': tencent_url,
                                            'aid': aid,
                                            'filename': filename,
                                            'original_file': video_file
                                        })
                                        print(f"✅ 腾讯云上传成功: {filename}")
                                        print(f"📎 腾讯云URL: {tencent_url}")
                                    else:
                                        print(f"❌ 腾讯云响应缺少URL: {response.text}")
                                else:
                                    print(f"❌ 腾讯云上传失败: {response_data.get('message', '未知错误')}")

                            except json.JSONDecodeError:
                                print(f"❌ 腾讯云响应解析失败: {response.text[:200]}")
                        else:
                            print(f"❌ 腾讯云上传HTTP错误: {response.status_code}")

                except Exception as e:
                    print(f"❌ 腾讯云上传异常: {e}")

            if uploaded_files:
                print(f"🎉 腾讯云上传完成，成功上传 {len(uploaded_files)} 个文件")
                # 发送包含腾讯云链接的回复
                return self._send_reply_with_tencent_links(thread_id, content, uploaded_files, form_hash)
            else:
                print("❌ 没有文件成功上传到腾讯云")
                return False

        except Exception as e:
            print(f"❌ 腾讯云上传异常: {e}")
            return False

    def _send_reply_with_tencent_links(self, thread_id: str, content: str,
                                     uploaded_files: List[Dict], form_hash: str) -> bool:
        """发送包含腾讯云链接的回复"""
        try:
            print("📝 发送包含腾讯云BBCode链接的回复...")

            # 构建包含腾讯云文件信息的回复内容
            enhanced_content = content + "\n\n🎬 视频文件已通过腾讯云上传成功！\n\n📁 上传文件列表："

            for i, file_info in enumerate(uploaded_files, 1):
                filename = file_info['filename']
                tencent_url = file_info['url']
                aid = file_info.get('aid', '')

                # 使用BBCode格式的URL标签
                bbcode_link = f"[url={tencent_url}][color=#2B7ACD][b]{filename}[/b][/color][/url]"

                enhanced_content += f"\n{i}. {bbcode_link}"
                if aid:
                    enhanced_content += f" (附件ID: {aid})"
                enhanced_content += "\n"

            enhanced_content += "\n🚀 上传方式: 腾讯云COS"
            enhanced_content += "\n⚡ 支持高速下载和在线播放"
            enhanced_content += "\n🔗 点击文件名即可下载或播放"
            enhanced_content += f"\n🕒 上传时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            # 发送回复
            reply_data = {
                'formhash': form_hash,
                'posttime': int(time.time()),
                'message': enhanced_content,
                'replysubmit': 'yes',
                'wysiwyg': '0',
                'checkbox': '0'
            }

            response = self.session.post(
                f"{self.base_url}/forum.php?mod=post&action=reply&tid={thread_id}",
                data=reply_data,
                timeout=60
            )

            # 检查回复结果
            if '发布成功' in response.text or '回复发布成功' in response.text or 'succeed' in response.text.lower():
                print(f"✅ 腾讯云BBCode链接回复成功: {thread_id}")
                print(f"📁 包含 {len(uploaded_files)} 个腾讯云BBCode链接")

                # 显示生成的BBCode链接
                print("🔗 生成的BBCode链接:")
                for i, file_info in enumerate(uploaded_files, 1):
                    filename = file_info['filename']
                    tencent_url = file_info['url']
                    bbcode_link = f"[url={tencent_url}][color=#2B7ACD][b]{filename}[/b][/color][/url]"
                    print(f"  {i}. {bbcode_link}")

                return True
            else:
                print(f"❌ 腾讯云BBCode链接回复失败: {thread_id}")
                print(f"响应状态: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ 腾讯云BBCode链接回复异常: {e}")
            return False

    def _upload_via_traditional_method(self, thread_id: str, content: str, video_files: List[str],
                                     form_hash: str) -> bool:
        """传统文件上传方式"""
        try:
            import os

            # 准备文件上传
            files = {}

            # 检查文件是否存在并准备上传
            valid_files = []
            for i, video_file in enumerate(video_files):
                if os.path.exists(video_file):
                    file_size = os.path.getsize(video_file) / (1024 * 1024)  # MB
                    print(f"📁 准备上传文件 {i+1}: {os.path.basename(video_file)} ({file_size:.1f} MB)")

                    # 不限制文件大小，直接添加到上传列表
                    valid_files.append(video_file)

                    # 准备文件上传数据
                    file_key = f'attach_{i+1}'
                    files[file_key] = (
                        os.path.basename(video_file),
                        open(video_file, 'rb'),
                        'video/mp4'
                    )
                else:
                    print(f"⚠️ 文件不存在，跳过: {video_file}")

            if not valid_files:
                print("⚠️ 没有有效的文件可上传，使用纯文本回复")
                return self._reply_text_only(thread_id, content)

            # 构建回复数据
            reply_data = {
                'formhash': form_hash,
                'posttime': int(time.time()),
                'message': content,
                'replysubmit': 'yes',
                'wysiwyg': '0',
                'checkbox': '0'
            }

            print(f"📤 开始传统方式上传回复（包含 {len(valid_files)} 个文件）...")

            # 发送带附件的回复
            response = self.session.post(
                f"{self.base_url}/forum.php?mod=post&action=reply&tid={thread_id}",
                data=reply_data,
                files=files,
                timeout=300  # 5分钟超时，因为文件上传可能需要较长时间
            )

            # 关闭文件句柄
            for file_obj in files.values():
                if hasattr(file_obj[1], 'close'):
                    file_obj[1].close()

            # 检查回复结果
            if '发布成功' in response.text or '回复发布成功' in response.text or 'succeed' in response.text.lower():
                print(f"✅ 传统方式上传成功: {thread_id}")
                print(f"📁 成功上传 {len(valid_files)} 个视频文件")
                return True
            else:
                print(f"❌ 传统方式上传失败: {thread_id}")
                print(f"响应状态: {response.status_code}")
                print(f"响应内容: {response.text[:500]}...")
                return False

        except Exception as e:
            print(f"❌ 传统上传方式异常: {e}")
            return False


def test_crawler():
    """测试爬虫功能"""
    print("🧪 测试智能剪口播板块爬虫")
    print("=" * 50)
    
    # 创建爬虫实例
    crawler = AicutForumCrawler()
    
    # 测试获取帖子列表
    threads = crawler.get_forum_threads()
    print(f"📊 获取到 {len(threads)} 个帖子")
    
    # 测试获取帖子内容
    if threads:
        first_thread = threads[0]
        print(f"\n📖 测试获取帖子内容: {first_thread['title']}")
        content = crawler.get_thread_content(first_thread['thread_url'])
        print(f"内容长度: {len(content['content'])}")
        print(f"视频链接: {content['video_urls']}")
        print(f"附件: {len(content['attachments'])}")
    
    # 测试监控功能
    print(f"\n🔍 测试监控功能...")
    new_posts = crawler.monitor_new_posts()
    print(f"发现 {len(new_posts)} 个新的视频帖子")


if __name__ == "__main__":
    test_crawler()
