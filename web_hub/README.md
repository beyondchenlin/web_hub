# Web Hub - 论坛自动化处理中枢

## 📋 项目简介

Web Hub 是一个基于集群架构的论坛自动化处理系统，支持监控论坛、分发任务、处理请求并自动回复。

### 核心功能

- 🔍 **论坛监控** - 自动监控论坛新帖子
- 🎯 **任务分发** - 智能分发任务到工作节点
- 🔄 **任务队列** - Redis队列管理
- 📊 **资源监控** - 系统资源实时监控
- 🌐 **Web界面** - 直观的监控和管理界面
- 🤖 **模块化处理** - 支持集成多种处理模块（TTS、视频处理等）

## 🏗️ 系统架构

```
web_hub/
├── cluster_monitor/      # 监控节点（监控论坛，分发任务）
├── lightweight/          # 工作节点（接收任务，执行处理）
├── aicut_forum_crawler.py # 论坛爬虫
├── data/                 # 数据目录
├── logs/                 # 日志目录
└── requirements/         # 依赖管理
```

### 集群架构

- **监控节点（Monitor Node）**：监控论坛，发现新帖并分发任务
- **工作节点（Worker Node）**：接收任务，执行处理流程

## 🚀 快速启动

### 1. 启动监控节点

```bash
# 从仓库根目录启动（推荐）
python web_hub/cluster_monitor/start_unified.py --mode production --port 8000

# 或使用批处理脚本（Windows）
1-启动监控节点.bat
```

### 2. 启动工作节点

```bash
# 从仓库根目录启动（推荐）
python web_hub/start_lightweight.py --port 8005

# 或使用批处理脚本（Windows）
2-启动工作节点.bat
```

### 3. 访问Web界面

打开浏览器访问：`http://localhost:8000`

## 📦 依赖安装

```bash
# 基础依赖
pip install -r requirements/requirements-01-base.txt

# 平台依赖（选择一个）
pip install -r requirements/requirements-02-platform-gpu.txt     # GPU
pip install -r requirements/requirements-02-platform-cpu.txt     # CPU

# 其他依赖
pip install -r requirements/requirements-03-text.txt
pip install -r requirements/requirements-04-ai.txt
pip install -r requirements/requirements-07-app.txt
```

## 🔧 配置

### 机器列表配置

编辑 `cluster_monitor/machines.txt`：

```
# 格式: IP地址:端口:优先级
localhost:8005:1
localhost:8006:2
```

### 环境变量

```bash
# 复制根目录示例为实际配置
# cp .env.example .env

# 在项目根目录 .env 中设置论坛账号（不要提交到仓库）
FORUM_USERNAME=
FORUM_PASSWORD=
# 兼容变量（可选）
# AICUT_ADMIN_USERNAME=
# AICUT_ADMIN_PASSWORD=

# 开发环境模拟数据（生产请保持 false）
ENABLE_MOCK_DATA=false

# 论坛地址请在 YAML 中配置：
# config/forum_settings.yaml

# Redis配置（可选）
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 🔐 安全与配置最佳实践

- 使用“项目根目录”的 .env 统一管理敏感信息（账号、密码等）
- 切勿提交 .env 到代码仓库；参考 .env.example / web_hub/cluster_monitor/.env.template
- Windows 请确认不要把 .env 保存成 .env.txt（显示文件扩展名以检查）
- 我们已将启动脚本改为“从根目录启动”，因此 .env 应放在仓库根目录
- 可用命令快速验证环境（不启动服务）：

```bash
python web_hub/cluster_monitor/start_unified.py --check-only
```
```

## 📚 文档

- [如何启动系统](docs/如何启动系统.md)
- [新环境部署指南](docs/新环境部署指南.md)
- [Claude命令快捷方式配置](docs/Claude命令快捷方式配置指南.md)

## 🎯 集群特性

### 负载均衡策略

- ✅ 优先选择空闲机器
- ✅ 按优先级分发任务
- ✅ 任务数量均衡
- ✅ 故障自动跳过

### 监控功能

- 🖥️ 实时机器状态（在线/离线、忙碌/空闲）
- 📋 任务分发统计（成功率、失败率）
- 🎯 负载均衡状态
- ⚙️ 集群管理（启动/停止监控、检查机器）

## 🔌 模块集成

系统支持集成多种处理模块：

- **TTS模块** - 音色克隆和语音合成（即将集成）
- **视频处理** - 视频剪辑和处理（已移除，可重新集成）
- **其他模块** - 可根据需求扩展

## 📝 API接口

### 监控节点API

```bash
# 启动论坛监控
curl -X POST http://localhost:8000/api/start-monitoring

# 检查机器状态
curl http://localhost:8000/api/machines/status

# 查看集群状态
curl http://localhost:8000/api/cluster/status
```

### 工作节点API

```bash
# 检查工作节点状态
curl http://localhost:8005/api/worker/status

# 发送任务到工作节点
curl -X POST -H "Content-Type: application/json" \
  -d '{"url":"https://tts.lrtcai.com/forum.php?mod=viewthread&tid=121"}' \
  http://localhost:8005/api/worker/receive-task
```

## 🛠️ 开发

### 项目结构

```
web_hub/
├── cluster_monitor/          # 监控节点
│   ├── forum_monitor.py      # 论坛监控
│   ├── improved_api.py       # API接口
│   ├── enhanced_data_manager.py  # 数据管理
│   └── ...
├── lightweight/              # 工作节点
│   ├── task_processor.py     # 任务处理
│   ├── queue_manager.py      # 队列管理
│   ├── resource_monitor.py   # 资源监控
│   ├── web_server.py         # Web服务
│   └── ...
├── aicut_forum_crawler.py    # 论坛爬虫
├── forum_data_manager.py     # 论坛数据管理
└── ...
```

## 📄 许可证

见 [LICENSE](LICENSE) 文件

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**最后更新**: 2025-11-05
**版本**: v6.0 (Web Hub)
