#!/usr/bin/env python3
"""
简化版启动脚本 - 绕过复杂的初始化
"""
import os
import sys

print("=" * 50)
print("  集群监控系统 - 简化启动")
print("=" * 50)
print()

# 1. 设置环境变量
os.environ['FLASK_ENV'] = 'production'
os.environ['FORUM_ENABLED'] = 'true'

# 2. 导入Flask
try:
    from flask import Flask
    print("✓ Flask导入成功")
except ImportError as e:
    print(f"✗ Flask导入失败: {e}")
    sys.exit(1)

# 3. 创建应用
app = Flask(__name__)
app.config['DEBUG'] = False

# 4. 添加基础路由
@app.route('/')
def index():
    return '''
    <html>
    <head><title>TTS监控系统</title></head>
    <body style="font-family: Arial; padding: 20px;">
        <h1>🚀 TTS论坛集成系统</h1>
        <h2>监控节点运行中</h2>
        <p>系统状态: <span style="color: green;">✓ 正常运行</span></p>
        <hr>
        <h3>API端点:</h3>
        <ul>
            <li><a href="/api/status">/api/status</a> - 系统状态</li>
            <li><a href="/health">/health</a> - 健康检查</li>
        </ul>
        <hr>
        <p>如需完整功能，请确保环境配置正确后使用标准启动方式。</p>
    </body>
    </html>
    '''

@app.route('/api/status')
def status():
    return {
        'status': 'online',
        'mode': 'simple',
        'message': '监控节点运行正常'
    }

@app.route('/health')
def health():
    return {'status': 'ok'}

# 5. 启动服务器
if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    
    print()
    print(f"✓ 服务器启动中...")
    print(f"✓ 端口: {port}")
    print(f"✓ 访问: http://localhost:{port}")
    print()
    print("按 Ctrl+C 停止服务")
    print("=" * 50)
    print()
    
    # 尝试使用Waitress
    try:
        from waitress import serve
        print("✓ 使用Waitress生产服务器")
        serve(app, host='0.0.0.0', port=port, threads=4)
    except ImportError:
        print("! 使用Flask开发服务器")
        app.run(host='0.0.0.0', port=port)

