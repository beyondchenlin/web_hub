# 集群监控系统 - 统一文档

## 📋 概述

集群监控系统是一个独立的论坛监控和任务分发系统，用于监控论坛新帖并将处理任务分发给集群中的工作节点。

### 🎯 主要功能

- **论坛监控**：自动监控论坛新帖
- **任务分发**：智能分发任务到可用的工作节点
- **集群管理**：管理多台处理机器的状态和负载均衡
- **Web界面**：提供直观的监控和管理界面
- **独立部署**：可独立运行，不依赖外部系统

## 🚀 快速开始

### 统一启动器

系统提供了统一的启动器 `start_unified.py`，支持多种模式：

```bash
# 开发模式（默认）
python start_unified.py --mode dev --port 8000

# 生产模式
python start_unified.py --mode production --port 8000

# 独立模式（自动配置）
python start_unified.py --mode standalone --port 8000

# 自动安装依赖
python start_unified.py --install-deps

# 只检查环境
python start_unified.py --check-only
```

### 传统启动方式（兼容）

```bash
# 开发模式
python start.py --port 8000

# 生产模式
python start_production.py --port 8000

# 独立模式
python start_standalone.py --port 8000
```

## ⚙️ 配置说明

### 环境配置文件 (.env)

系统会自动创建默认配置文件，主要配置项：

```env
# 论坛监控配置
FORUM_ENABLED=true
FORUM_CHECK_INTERVAL=10
FORUM_BASE_URL=https://aicut.lrtcai.com
FORUM_TARGET_URL=https://aicut.lrtcai.com/forum-2-1.html
FORUM_USERNAME=your_username_here
FORUM_PASSWORD=your_secure_password_here

# 论坛功能配置
FORUM_AUTO_REPLY_ENABLED=true
FORUM_TEST_MODE=false
FORUM_TEST_ONCE=false

# 任务分发配置
TASK_DISPATCH_STRATEGY=least_busy
REQUEST_TIMEOUT=30
MAX_RETRIES=3

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=logs/forum_monitor.log

# Web界面配置
WEB_REFRESH_INTERVAL=10
```

### 机器配置文件 (machines.txt)

配置集群中的工作节点：

```txt
# 配置格式: IP地址:端口:优先级
localhost:8003:1    # 本地工作节点1 - 高优先级
localhost:8004:2    # 本地工作节点2 - 中等优先级
192.168.1.100:8003:3  # 远程节点1
192.168.1.101:8003:4  # 远程节点2
```

## 📦 依赖管理

### 自动安装依赖

```bash
python start_unified.py --install-deps
```

### 手动安装依赖

```bash
pip install Flask Werkzeug requests urllib3 python-dotenv psutil beautifulsoup4 lxml redis waitress
```

### 依赖检查

```bash
python dependency_manager.py
```

## 🏗️ 系统架构

### 核心组件

- **forum_monitor.py** - 主监控器
- **config.py** - 统一配置管理
- **utils.py** - 通用工具函数
- **dependency_manager.py** - 依赖管理器
- **logger_manager.py** - 日志管理器

### 数据管理

- **enhanced_data_manager.py** - SQLite + Redis 数据管理器
- **standalone_data_manager.py** - 独立数据管理器

### Web界面

- **templates/index.html** - 主页模板
- **static/css/style.css** - 样式文件

### API接口

- **improved_api.py** - 改进版任务分发API

## 🔧 部署模式

### 开发模式

- 使用Flask开发服务器
- 详细的调试输出
- 自动重载

### 生产模式

- 使用Waitress（Windows）或Gunicorn（Unix）
- 优化的日志输出
- 多进程支持

### 独立模式

- 自动创建配置文件
- 适合快速部署
- 包含默认设置

## 📊 监控界面

访问 `http://localhost:8000` 查看监控界面，包含：

- 系统运行状态
- 处理机器状态
- 任务统计信息
- 控制按钮（启动/停止监控）

## 🔌 API接口

### 基础API

- `GET /` - 监控界面
- `GET /api/machines` - 获取机器列表
- `POST /api/start-monitoring` - 启动监控
- `POST /api/stop-monitoring` - 停止监控
- `POST /api/check-machines` - 检查机器状态

### 改进版API

- `POST /api/send-task-v2` - 发送任务（改进版）
- `GET /api/cluster-status` - 获取集群状态

## 🛠️ 故障排除

### 常见问题

1. **端口被占用**
   - 系统会自动寻找可用端口
   - 或手动指定其他端口

2. **依赖缺失**
   - 使用 `--install-deps` 自动安装
   - 或手动安装缺失的包

3. **Redis连接失败**
   - 系统会自动降级到SQLite模式
   - 检查Redis服务是否启动

4. **论坛登录失败**
   - 检查用户名和密码配置
   - 系统会以游客模式继续运行

### 日志查看

```bash
# 查看实时日志
tail -f logs/forum_monitor.log

# 查看错误日志
grep "ERROR" logs/forum_monitor.log
```

## 📈 性能优化

### 生产环境建议

1. 使用生产模式启动
2. 配置适当的Worker进程数
3. 启用日志文件记录
4. 定期清理日志文件

### 集群配置建议

1. 根据机器性能设置优先级
2. 合理配置检查间隔
3. 监控机器负载状态
4. 及时处理离线节点

## 🔄 更新说明

### v2.0 重构版本

- ✅ 合并了重复的启动脚本
- ✅ 统一了端口检测逻辑
- ✅ 简化了Redis检查
- ✅ 统一了依赖管理
- ✅ 提取了HTML模板
- ✅ 统一了配置管理
- ✅ 清理了调试代码
- ✅ 统一了API接口
- ✅ 整理了文档

### 代码优化

- 减少了约30-40%的重复代码
- 提高了代码可维护性
- 改善了错误处理
- 优化了日志输出

## 📞 支持

如有问题，请检查：

1. 配置文件是否正确
2. 依赖是否完整安装
3. 网络连接是否正常
4. 日志文件中的错误信息

---

**注意**：本系统设计为独立运行，不依赖外部文件。所有必需的组件都包含在 `cluster_monitor` 目录中。