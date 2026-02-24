# 多机部署 - IndexTTS2 音色克隆 API 改造计划

> 状态：预留方案，当前单机部署无需改动
> 创建时间：2026-02-24

## 1. 现状

### 1.1 当前架构

```
集群监控 (cluster_monitor, 端口 8080)
    ↓ 按 machines.txt 分发任务
工作节点 (localhost:8105)
    ↓ TTS合成 / 音色克隆
IndexTTS2 (localhost:9880, cy_app.pyd)
```

### 1.2 IndexTTS2 API 现有接口

| 路由 | 方法 | 用途 | 示例 |
|------|------|------|------|
| `/` | GET/POST | TTS 合成 | `/?text=你好&speaker=苏瑶&speed=1.0` |

**没有 `/create_voice` 接口。** `cy_app.pyd` 是编译的二进制，无法直接修改。

### 1.3 音色克隆当前流程

```
tts_api_service.py
  → 尝试 POST /create_voice  → 404（接口不存在）
  → fallback 到本地方案：
      1. FFmpeg 提取/转换音频
      2. 本地调用模型生成 .pt 文件
      3. 保存到 voices/ 目录
```

单机部署下本地 fallback 完全可用，无需改动。

### 1.4 TTS合成时的音色解析流程

```
service.py
  → VoiceMapper.resolve_voice_name(user_id, "本人音色")
  → 有克隆音色 → 返回 voice_id（数据库中的真实ID）  ✅
  → 无克隆音色 → 返回 "苏瑶"（硬编码名称）
      → 被当作 voice_id 传给 can_use_voice()
      → 数据库 voices 表查不到 voice_id="苏瑶"  ❌
```

**已知问题**：`voice_mapper.py` 回退到系统默认时返回的是音色名称而非 voice_id，
导致 `tts_permission_manager.py` 查数据库失败。详见第 4 节。

## 2. 多机部署面临的问题

### 2.1 音色文件不共享

- 节点 A 克隆音色 → `.pt` 文件保存在节点 A 本地
- 节点 B 收到 TTS 任务 → 找不到该 `.pt` 文件

### 2.2 数据库不共享

- 每个节点有独立的 `tts_voice_system.db`（SQLite）
- 节点 A 写入的音色记录，节点 B 看不到

### 2.3 音色克隆无法远程调用

- 本地 fallback 依赖本机的 IndexTTS2 模型
- 如果某节点没有 GPU / 没部署模型，无法执行克隆

## 3. 改造方案

### 3.1 短期：新增 `/create_voice` 代理服务

在 IndexTTS2 旁边起一个轻量 FastAPI 服务，提供 `/create_voice` 接口。

```python
# 文件位置建议：tts/indextts2/voice_api_proxy.py

from fastapi import FastAPI, UploadFile, Form
app = FastAPI()

@app.post("/create_voice")
async def create_voice(audio: UploadFile, voice_name: str = Form(...)):
    """
    接收音频文件，调用本地模型生成 .pt 音色文件。
    复用 batch_processor.py 中 create_voice_fallback 的逻辑。
    """
    # 1. 保存上传的音频到临时文件
    # 2. 如果是视频格式，用 FFmpeg 提取音频
    # 3. 调用 IndexTTS2 模型生成 .pt
    # 4. 返回 { "voice_id": "xxx", "file_path": "xxx.pt" }
    pass
```

**部署方式**：与 `cy_app` 的 FastAPI 合并（如果能注入路由），或独立端口运行。

### 3.2 中期：共享存储

| 方案 | 适用场景 | 复杂度 |
|------|---------|--------|
| NFS/SMB 共享 `voices/` 目录 | 局域网多机 | 低 |
| MinIO/S3 对象存储 | 跨网络 / 云部署 | 中 |
| 克隆完成后同步到所有节点 | 节点数少 | 低 |

### 3.3 中期：数据库迁移

SQLite → MySQL/PostgreSQL，所有节点连同一个数据库。

涉及文件：
- `tts/custom_integration/integration/tts_config.py` — `DATABASE_PATH`
- `tts/custom_integration/integration/voice_mapper.py` — `sqlite3.connect`
- `tts/custom_integration/integration/tts_permission_manager.py` — `sqlite3.connect`
- `tts/custom_integration/integration/tts_forum_sync.py` — `sqlite3.connect`
- `tts/custom_integration/integration/tts_api_service.py` — `sqlite3.connect`

### 3.4 配置项预留

当前已有的环境变量（`tts_config.py`）：
```python
INDEXTTS2_HOST = os.getenv("INDEXTTS2_HOST", "localhost")
INDEXTTS2_PORT = int(os.getenv("INDEXTTS2_PORT", "9880"))
```

多机部署时每个节点设置不同的 `INDEXTTS2_HOST` 即可指向对应的 GPU 机器。

## 4. 已知待修复问题

### 4.1 voice_mapper 默认音色回退 bug

**文件**：`services/tts_service/service.py:264`、`tts/.../voice_mapper.py:243`

**问题**：用户没有克隆音色时，`resolve_voice_name` 返回 `"苏瑶"`（名称字符串），
被 `service.py` 写入 `converted_payload['voice_id']`，
然后 `tts_api_service.py` 用它查数据库 `WHERE voice_id = '苏瑶'`，查不到。

**修复方向**：
- 方案 A：`voice_mapper` 回退时返回数据库中实际存在的 `voice_id`
- 方案 B：`service.py` 判断返回值是系统音色名称时，不设 `voice_id`，保留 `voice_name`，
  让 `tts_api_service` 走 `can_use_voice_by_name` 分支
- 方案 C：初始化数据库时把系统音色插入 `voices` 表（`is_public=1, owner_id='system'`）

## 5. 涉及的关键文件

| 文件 | 职责 |
|------|------|
| `tts/indextts2/cy_app.pyd` | IndexTTS2 核心（编译二进制，不可修改） |
| `tts/indextts2/app.py` | 启动 FastAPI + Gradio + Workers |
| `tts/indextts2/batch_processor.py` | 批量 TTS，含 `create_voice_fallback` 参考实现 |
| `tts/custom_integration/integration/tts_config.py` | API 地址、端口、数据库路径配置 |
| `tts/custom_integration/integration/tts_api_service.py` | TTS/克隆请求处理，含 `/create_voice` 调用 |
| `tts/custom_integration/integration/voice_mapper.py` | 音色名称解析、默认音色回退 |
| `tts/custom_integration/integration/tts_permission_manager.py` | 音色权限校验 |
| `services/tts_service/service.py` | Web Hub 与 TTS 集成的服务层 |
| `web_hub/cluster_monitor/machines.txt` | 集群节点配置 |
| `web_hub/cluster_monitor/config.py` | 任务分发策略配置 |

## 6. 改造优先级

| 优先级 | 任务 | 阶段 |
|--------|------|------|
| P0 | 修复 voice_mapper 默认音色回退 bug（第 4.1 节） | 现在 |
| P1 | 新增 `/create_voice` 代理服务 | 多机部署前 |
| P2 | 音色文件共享存储 | 多机部署时 |
| P2 | SQLite → MySQL/PostgreSQL | 多机部署时 |
| P3 | 统一配置中心（替代分散的 .env / yaml） | 长期优化 |
