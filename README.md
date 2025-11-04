# TTS论坛集成系统 - 使用指南

**版本**: 2.3.0 | **更新**: 2025-11-04

---

## ⚡ 快速开始

### 一步启动（推荐）

**方式A：使用CMD（推荐）**
```bash
# 1. 打开CMD（Win+R，输入cmd，回车）
# 2. 切换到项目目录
cd /d D:\clonetts

# 3. 启动
直接启动.bat
```

**方式B：直接双击**
```
1-启动监控节点.bat
```

就这么简单！启动后访问：http://localhost:8000

**注意**：如遇到编码问题，请使用CMD而不是PowerShell

---

## 📋 系统说明

### 这是什么？

TTS论坛集成系统 - 自动化语音合成服务平台

用户通过论坛发帖即可：
- 🎤 **音色克隆** - 上传音频，克隆声音
- 🔊 **AI语音生成** - 使用音色生成语音

系统自动监控、处理、回复。

### 两个节点说明

| 节点 | 用途 | 必需 | Redis |
|------|------|------|-------|
| **1-监控节点** | 主节点，监控论坛+处理任务 | ✅ 必需 | ❌ 不需要 |
| **2-工作节点** | 辅助节点，分担处理任务 | ❌ 可选 | ✅ 需要 |

**建议**：个人使用只需启动 **1-监控节点** 即可。

---

## 🚀 启动方式

### 方式一：简单模式（推荐）

只启动监控节点，适合个人使用：

```bash
# 双击运行
1-启动监控节点.bat
```

**访问地址**：http://localhost:8000

**优点**：
- ✅ 简单，无需Redis
- ✅ 完整功能
- ✅ 适合大多数场景

### 方式二：集群模式（可选）

如需要高性能分布式处理：

**步骤1**：安装Redis
```bash
tts\indextts2\py312\python.exe web_hub\cluster_monitor\install_redis_windows.py
```

**步骤2**：启动监控节点
```bash
1-启动监控节点.bat
```

**步骤3**：启动工作节点（新窗口）
```bash
2-启动工作节点.bat
```

---

## ⚙️ 配置说明

### 论坛账号配置

编辑 `config/forum_settings.yaml`：

```yaml
credentials:
  username: AI剪辑助手
  password: 你的密码

forums:
  main:
    name: 懒人同城号AI - TTS论坛
    base_url: https://tts.lrtcai.com
    target_url: https://tts.lrtcai.com/forum-2-1.html
    forum_id: 2
    enabled: true
    check_interval: 10
```

### 数据库位置

`tts/custom_integration/integration/database/tts_voice_system.db`

首次启动自动创建。

---

## 📖 论坛发帖格式

### 音色克隆

**标题**：
```
【音色克隆】我的声音
```

**内容**：
```
【音色名称】我的专属音色
【是否公开】否
```

**附件**：上传音频文件（WAV/MP3，10-30秒）

### AI语音生成

**标题**：
```
【制作AI声音】生成语音
```

**内容**：
```
【文案】大家好，欢迎来到我的频道！
【选择音色】我的专属音色
【语速】1.0
【音调】1.0
```

---

## ❓ 常见问题

### Q1: 启动后看到什么？

正常启动显示：
```
🚀 集群监控系统统一启动器
INFO:waitress:Serving on http://0.0.0.0:8000
✅ 系统启动成功！
```

### Q2: 需要Redis吗？

- **监控节点**：❌ 不需要（独立运行）
- **工作节点**：✅ 需要（集群模式）

**建议**：先只用监控节点，够用了。

### Q3: 如何停止服务？

- 按 `Ctrl+C`
- 或关闭命令行窗口

### Q4: 如何查看日志？

```bash
# 监控节点日志
logs\forum_monitor.log

# 工作节点日志
logs\lightweight.log
```

### Q5: 端口被占用？

```bash
# 检查端口
netstat -ano | findstr :8000

# 结束进程
taskkill /PID 进程ID /F
```

### Q6: Python依赖缺失？

```bash
# 安装依赖
tts\indextts2\py312\python.exe -m pip install python-dotenv redis waitress pyyaml
```

---

## 📁 目录结构

```
clonetts/
├── tts\indextts2\py312\        # Python环境（相对路径）
├── config\                      # 配置文件
│   └── forum_settings.yaml
├── web_hub\                     # Web服务
│   ├── cluster_monitor\         # 监控节点
│   └── start_lightweight.py     # 工作节点
├── logs\                        # 日志文件
├── 1-启动监控节点.bat           # ⭐ 主要启动脚本
└── 2-启动工作节点.bat           # 可选启动脚本
```

---

## 🔧 技术栈

- **Python**: 3.10.18（项目内置）
- **Web框架**: Flask + Waitress
- **数据库**: SQLite
- **任务队列**: Redis（可选）
- **TTS引擎**: IndexTTS2

---

## 📞 技术支持

- **GitHub**: https://github.com/beyondchenlin/web_hub
- **论坛**: https://tts.lrtcai.com

---

## 🎯 最佳实践

**日常使用**：
1. 双击 `1-启动监控节点.bat`
2. 等待启动（约5-10秒）
3. 访问 http://localhost:8000
4. 开始使用！

**就这么简单！** 🎉

---

**更新日志**：
- v2.3.0 (2025-11-04): 简化启动脚本，优化文档结构
- v2.2.0 (2025-11-04): 修复编码问题，添加Redis辅助工具
- v2.1.0 (2025-11-04): 新增本人音色映射

