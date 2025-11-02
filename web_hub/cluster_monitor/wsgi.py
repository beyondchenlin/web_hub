#!/usr/bin/env python3
"""
WSGI应用入口文件
用于Gunicorn等WSGI服务器
"""

import os
import sys

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from forum_monitor import ForumMonitor

# 创建应用实例
def create_app(port=8000):  # 改为默认8000端口
    """创建Flask应用实例"""
    monitor = ForumMonitor(port)
    return monitor.app

# WSGI应用对象
application = create_app()
app = application

if __name__ == "__main__":
    # 直接运行时使用开发服务器，从环境变量获取端口或使用默认8000
    import os
    port = int(os.getenv('PORT', 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
