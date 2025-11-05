"""
测试论坛分类信息字段
分析两个页面的HTML结构，找出唯一的分类标识

根据用户截图，Discuz论坛的分类信息：
- 制作AI声音: 变量名 myvoice
- 音色克隆: 变量名 clone
"""

import requests
from bs4 import BeautifulSoup
import re

# 🔐 使用登录凭证
USERNAME = "admin_ltcai"
PASSWORD = "Chenlin@2025"
BASE_URL = "https://tts.lrtcai.com"

def login_forum():
    """登录论坛"""
    session = requests.Session()

    try:
        print("🔐 登录论坛...")
        # 获取登录页面
        login_page = session.get(f"{BASE_URL}/member.php?mod=logging&action=login", timeout=10)
        soup = BeautifulSoup(login_page.text, 'html.parser')

        # 获取formhash
        form_hash = ""
        form_hash_input = soup.find('input', {'name': 'formhash'})
        if form_hash_input:
            form_hash = form_hash_input.get('value', '')

        # 登录数据
        login_data = {
            'formhash': form_hash,
            'referer': BASE_URL,
            'loginfield': 'username',
            'username': USERNAME,
            'password': PASSWORD,
            'questionid': 0,
            'answer': '',
            'loginsubmit': 'true'
        }

        # 发送登录请求
        response = session.post(
            f"{BASE_URL}/member.php?mod=logging&action=login&loginsubmit=yes&infloat=yes&lssubmit=yes&inajax=1",
            data=login_data,
            allow_redirects=True,
            timeout=10
        )

        if response.status_code == 200:
            print("✅ 登录成功")
            return session
        else:
            print(f"❌ 登录失败: {response.status_code}")
            return None

    except Exception as e:
        print(f"❌ 登录异常: {e}")
        return None

def analyze_page(session, url, page_name):
    """分析页面结构"""
    print(f"\n{'='*60}")
    print(f"分析页面: {page_name}")
    print(f"URL: {url}")
    print(f"{'='*60}")

    try:
        response = session.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 🎯 重点：查找分类变量名（myvoice 或 clone）
        print("\n🎯 查找分类变量名和分类ID:")

        html_text = response.text

        # 查找 typeid 或 sortid 参数
        typeid_matches = re.findall(r'typeid[=\s]*["\']?(\d+)', html_text, re.I)
        sortid_matches = re.findall(r'sortid[=\s]*["\']?(\d+)', html_text, re.I)

        if typeid_matches:
            print(f"  ✅ 找到 typeid: {set(typeid_matches)}")
        if sortid_matches:
            print(f"  ✅ 找到 sortid: {set(sortid_matches)}")

        # 查找分类变量名
        if 'myvoice' in html_text.lower():
            print("  ✅ 找到变量名: myvoice → 制作AI声音")
            # 提取相关上下文
            for line in html_text.split('\n'):
                if 'myvoice' in line.lower():
                    print(f"    {line.strip()[:200]}")
                    if 'typeid' in line.lower() or 'sortid' in line.lower():
                        break

        if 'clone' in html_text.lower():
            # 排除 voice_clone 等其他包含clone的词
            for line in html_text.split('\n'):
                if re.search(r'\bclone\b', line.lower()) and ('typeid' in line.lower() or 'sortid' in line.lower() or 'sort' in line.lower()):
                    print("  ✅ 找到变量名: clone → 音色克隆")
                    print(f"    {line.strip()[:200]}")
                    break

        # 1. 查找caption元素
        print("\n🔍 1. Caption元素:")
        captions = soup.find_all('caption')
        for i, caption in enumerate(captions):
            print(f"  Caption {i+1}: {caption.get_text(strip=True)}")
            print(f"    属性: {caption.attrs}")
        
        # 2. 查找分类相关的元素
        print("\n🔍 2. 分类信息 (typeid/sortid):")
        # 查找所有包含typeid或sortid的元素
        for tag in soup.find_all(attrs={'class': re.compile(r'.*type.*|.*sort.*|.*category.*', re.I)}):
            print(f"  标签: {tag.name}, class={tag.get('class')}, text={tag.get_text(strip=True)[:50]}")
        
        # 查找所有包含typeid或sortid的属性
        for tag in soup.find_all(attrs=re.compile(r'typeid|sortid', re.I)):
            print(f"  标签: {tag.name}, 属性={tag.attrs}")
        
        # 3. 查找帖子标题区域
        print("\n🔍 3. 帖子标题区域:")
        title_area = soup.find('div', id='pt')
        if title_area:
            print(f"  面包屑导航: {title_area.get_text(strip=True)}")
        
        # 4. 查找主题分类标签
        print("\n🔍 4. 主题分类标签:")
        # Discuz通常在这些位置显示分类
        for selector in ['span.tps', 'a.xi2', 'em.xi1', 'span[id^="thread_subject"]']:
            elements = soup.select(selector)
            for elem in elements:
                print(f"  {selector}: {elem.get_text(strip=True)}")
        
        # 5. 查找帖子详情区域的分类信息
        print("\n🔍 5. 帖子详情区域:")
        post_area = soup.find('div', class_='pct')
        if post_area:
            # 查找所有em标签（通常用于分类标签）
            em_tags = post_area.find_all('em')
            for em in em_tags:
                print(f"  <em>: {em.get_text(strip=True)}, class={em.get('class')}")
            
            # 查找所有span标签
            span_tags = post_area.find_all('span', class_=re.compile(r'.*'))
            for span in span_tags[:5]:  # 只显示前5个
                print(f"  <span>: {span.get_text(strip=True)[:30]}, class={span.get('class')}")
        
        # 6. 查找表单中的隐藏字段
        print("\n🔍 6. 表单隐藏字段:")
        hidden_inputs = soup.find_all('input', type='hidden')
        for inp in hidden_inputs:
            name = inp.get('name', '')
            value = inp.get('value', '')
            if 'type' in name.lower() or 'sort' in name.lower() or 'class' in name.lower():
                print(f"  {name} = {value}")
        
        # 7. 查找JavaScript中的变量
        print("\n🔍 7. JavaScript变量:")
        scripts = soup.find_all('script')
        for script in scripts:
            script_text = script.string or ''
            # 查找typeid或sortid变量
            if 'typeid' in script_text.lower() or 'sortid' in script_text.lower():
                # 提取相关行
                lines = script_text.split('\n')
                for line in lines:
                    if 'typeid' in line.lower() or 'sortid' in line.lower():
                        print(f"  {line.strip()[:100]}")
        
        # 8. 查找帖子元数据
        print("\n🔍 8. 帖子元数据:")
        # 查找所有data-*属性
        for tag in soup.find_all(attrs=lambda x: x and any(k.startswith('data-') for k in x.keys())):
            data_attrs = {k: v for k, v in tag.attrs.items() if k.startswith('data-')}
            if data_attrs:
                print(f"  {tag.name}: {data_attrs}")
                break  # 只显示第一个
        
        # 9. 查找帖子主题区域的所有class
        print("\n🔍 9. 主题区域的class属性:")
        main_content = soup.find('div', id='ct')
        if main_content:
            # 查找所有带class的div
            divs_with_class = main_content.find_all('div', class_=True, limit=10)
            for div in divs_with_class:
                classes = div.get('class', [])
                text = div.get_text(strip=True)[:30]
                print(f"  class={classes}, text={text}")
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 登录论坛
    session = login_forum()

    if session:
        # 分析两个页面
        analyze_page(session, "https://tts.lrtcai.com/thread-22-1-1.html", "制作AI声音")
        analyze_page(session, "https://tts.lrtcai.com/thread-20-1-1.html", "音色克隆")
    else:
        print("❌ 无法登录，跳过分析")

