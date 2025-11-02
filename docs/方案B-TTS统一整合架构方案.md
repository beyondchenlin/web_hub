# 方案B：TTS统一整合架构方案

**版本：** 1.0  
**日期：** 2025-11-02  
**状态：** 设计阶段 - 待实施

---

## 📋 目录

1. [架构现状分析](#架构现状分析)
2. [功能重叠分析](#功能重叠分析)
3. [目标架构设计](#目标架构设计)
4. [详细实施计划](#详细实施计划)
5. [向后兼容性](#向后兼容性)
6. [风险评估](#风险评估)
7. [测试策略](#测试策略)

---

## 🔍 架构现状分析

### 当前系统架构

#### TTS独立系统
```
tts/custom_integration/integration/
├── tts_forum_monitor.py              # 论坛监控（60秒轮询）
├── tts_forum_crawler_integration.py  # 爬虫包装（引用web_hub）
├── tts_forum_processor.py            # 请求处理
├── tts_api_service.py                # API调用
├── tts_forum_reply_uploader.py       # 回复上传
├── tts_permission_manager.py         # 权限管理
├── tts_request_parser.py             # 请求解析
└── tts_init_db.py                    # 数据库初始化

运行方式：
python tts/custom_integration/run_tts_system.py
```

#### Web Hub集群系统
```
web_hub/
├── cluster_monitor/
│   ├── forum_monitor.py              # 论坛监控（可配置间隔）
│   ├── enhanced_data_manager.py      # 数据管理
│   └── simple_forum_crawler.py       # 简化爬虫
├── lightweight/
│   ├── queue_manager.py              # 队列管理（VideoTask）
│   ├── task_processor.py             # 任务处理（视频pipeline）
│   └── forum_integration.py          # 论坛集成
├── modules/
│   └── tts_adapter/
│       └── adapter.py                # TTS适配器（已实现）
├── aicut_forum_crawler.py            # 核心爬虫（共享）
├── multi_forum_crawler.py            # 多论坛管理器
└── forum_data_manager.py             # 数据管理

运行方式：
监控节点：python web_hub/cluster_monitor/start_unified.py --mode production --port 8000
工作节点：python web_hub/start_lightweight.py --port 8005
```

#### 共享组件
```
shared/
├── forum_config.py                   # 配置加载（已实现）
└── README.md

services/
└── tts_service/
    └── service.py                    # TTS服务封装（已实现）
```

---

## 🔴 功能重叠分析

### 严重重叠（必须整合）

| 功能模块 | TTS系统 | Web Hub系统 | 重叠度 | 问题描述 |
|---------|---------|------------|--------|---------|
| **论坛监控** | `tts_forum_monitor.py` | `cluster_monitor/forum_monitor.py` | 90% | 两个独立的监控循环，重复检查同一个论坛 |
| **爬虫实例** | `TTSForumCrawlerIntegration` | `ForumIntegration` | 80% | 都创建和管理`AicutForumCrawler`实例 |
| **帖子获取** | `get_new_posts()` | `get_forum_threads()` | 85% | 都调用同一个爬虫的方法 |
| **论坛回复** | `reply_to_post()` | `reply_to_thread()` | 90% | 最终都调用`aicut_forum_crawler.reply_to_thread()` |
| **配置加载** | `load_forum_settings()` | `load_forum_settings()` | 100% | ✅ 已统一使用`shared/forum_config.py` |

### 引用关系问题

```python
# tts/integration/tts_forum_crawler_integration.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'web_hub'))  # ❌ 不优雅
from aicut_forum_crawler import AicutForumCrawler  # 从web_hub引用

# 问题：
# 1. TTS系统通过sys.path hack引用web_hub的组件
# 2. aicut_forum_crawler.py在web_hub/下，应该在共享位置
# 3. 三个地方都创建爬虫实例，没有统一管理
```

### 部分重叠（需要协调）

| 功能模块 | TTS系统 | Web Hub系统 | 差异点 |
|---------|---------|------------|--------|
| **任务模型** | 无统一模型（字典） | `VideoTask` dataclass | 数据结构不一致 |
| **任务队列** | Python `Queue`（内存） | Redis + PriorityQueue | 持久化方式不同 |
| **数据存储** | `tts_voice_system.db` | `forum_posts.db` | 两个独立SQLite数据库 |

### 无重叠（独立保留）

| 功能模块 | 所属系统 | 说明 |
|---------|---------|------|
| **TTS参数解析** | TTS | `tts_request_parser.py` - TTS业务特定 |
| **权限配额管理** | TTS | `tts_permission_manager.py` - TTS业务特定 |
| **TTS API调用** | TTS | `tts_api_service.py` - IndexTTS2 API封装 |
| **视频处理pipeline** | Web Hub | `task_processor.py` - 视频处理流程 |
| **集群负载均衡** | Web Hub | `cluster_monitor/` - 分布式调度 |

---

## 🎯 目标架构设计

### 核心设计理念

```
统一调度架构 = 共享基础组件 + 独立业务逻辑 + 统一任务模型
```

### 架构层次图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         项目根目录                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ shared/ - 共享基础组件层（所有系统共享）                      │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │  ✅ forum_config.py         - 配置加载（已有）              │   │
│  │  🆕 task_model.py           - 统一任务模型                 │   │
│  │  🆕 task_manager.py         - 统一任务管理器               │   │
│  │  🆕 forum_crawler_manager.py - 统一爬虫管理器              │   │
│  │  🆕 forum_reply_manager.py  - 统一回复管理器               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                          ↑   ↑   ↑                                 │
│                          │   │   │                                 │
│        ┌─────────────────┴───┴───┴──────────────────┐              │
│        │                                             │              │
│        ↓                                             ↓              │
│  ┌──────────────┐                            ┌──────────────┐      │
│  │ web_hub/     │                            │ services/    │      │
│  │ 调度与分发层  │                            │ 业务服务层    │      │
│  ├──────────────┤                            ├──────────────┤      │
│  │ 📍 监控节点   │                            │ ✅ tts_service/  │  │
│  │ cluster_     │                            │    service.py    │  │
│  │  monitor/    │                            │                  │  │
│  │  - 统一监控   │                            │ 🆕 video_service/│  │
│  │  - 任务识别   │                            │    service.py    │  │
│  │  - 任务分发   │                            │                  │  │
│  │              │                            │ 🆕 image_service/│  │
│  │ 🔨 工作节点   │                            │    (预留)        │  │
│  │ lightweight/ │                            └────────┬─────────┘  │
│  │  - 任务路由   │                                     │            │
│  │  - 任务执行   │←────────────────────────────────────┘            │
│  │  - 状态上报   │                                                  │
│  │              │                                                  │
│  │ 🧩 适配器层   │                                                  │
│  │ modules/     │                                                  │
│  │  - tts_      │                                                  │
│  │    adapter/  │                                                  │
│  │  - video_    │                                                  │
│  │    adapter/  │                                                  │
│  └──────────────┘                                                  │
│                                                                     │
│  ┌──────────────────────────────────────────┐                      │
│  │ tts/custom_integration/ - TTS业务实现     │                      │
│  ├──────────────────────────────────────────┤                      │
│  │  保留业务逻辑：                            │                      │
│  │  ✅ tts_request_parser.py  - 请求解析     │                      │
│  │  ✅ tts_permission_manager.py - 权限管理  │                      │
│  │  ✅ tts_api_service.py - API调用          │                      │
│  │  ✅ tts_init_db.py - 数据库初始化         │                      │
│  │                                           │                      │
│  │  删除重复组件：                            │                      │
│  │  ❌ tts_forum_monitor.py（改用统一监控）   │                      │
│  │  ❌ tts_forum_crawler_integration.py      │                      │
│  │     （改用shared/forum_crawler_manager）   │                      │
│  │  ❌ tts_forum_reply_uploader.py           │                      │
│  │     （改用shared/forum_reply_manager）     │                      │
│  │  ❌ tts_forum_integration_manager.py      │                      │
│  │     （改用统一任务调度）                    │                      │
│  └──────────────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 数据流程图

```
┌──────────────┐
│ 论坛新帖发布  │
└──────┬───────┘
       │
       ↓
┌─────────────────────────────────────────────────┐
│ 统一监控节点（cluster_monitor/forum_monitor.py）  │
│ - 使用 ForumCrawlerManager 获取新帖            │
│ - 识别任务类型（TTS/视频/图片）                  │
└──────┬──────────────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────────────┐
│ 统一任务管理器（shared/task_manager.py）         │
│ - 创建 UnifiedTask                              │
│ - 保存到 Redis + SQLite                        │
│ - 维护优先级队列                                 │
└──────┬──────────────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────────────┐
│ 任务分发（cluster_monitor）                      │
│ - 选择合适的工作节点                             │
│ - 考虑负载均衡和任务类型                         │
└──────┬──────────────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────────────┐
│ 工作节点（lightweight/）                         │
│ 1. 接收任务                                      │
│ 2. 任务路由器（task_router.py）                 │
│    根据 task_type 选择处理方式                   │
└──────┬──────────────────────────────────────────┘
       │
       ├──────────┬──────────┐
       │          │          │
       ↓          ↓          ↓
┌──────────┐ ┌──────────┐ ┌──────────┐
│ TTS适配器│ │视频适配器│ │图片适配器│
│          │ │          │ │ (预留)  │
└────┬─────┘ └────┬─────┘ └──────────┘
     │            │
     ↓            ↓
┌──────────┐ ┌──────────┐
│TTS服务层 │ │视频服务层│
│services/ │ │services/ │
│tts_      │ │video_    │
│service/  │ │service/  │
└────┬─────┘ └────┬─────┘
     │            │
     ↓            ↓
┌──────────┐ ┌──────────┐
│TTS业务   │ │视频处理  │
│逻辑      │ │pipeline  │
│tts/      │ │          │
│custom_   │ │          │
│integration││         │
└────┬─────┘ └────┬─────┘
     │            │
     └────────┬───┘
              │
              ↓
┌─────────────────────────────────────────────────┐
│ 统一回复管理器（shared/forum_reply_manager.py）  │
│ - 使用 ForumCrawlerManager 发送回复            │
│ - 支持文本、附件、多媒体                         │
└──────┬──────────────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────────────┐
│ 任务状态更新（shared/task_manager.py）           │
│ - 更新任务状态为 COMPLETED                      │
│ - 保存结果和输出文件                             │
└─────────────────────────────────────────────────┘
```

---

## 📝 详细实施计划

### 阶段1：创建共享基础组件（3-4天）

> ⚠️ **依赖提醒**：统一任务模型 (`shared/task_model.py`) 与任务管理器 (`shared/task_manager.py`) 是后续所有阶段的公共依赖，务必优先完成并发布这两个模块，再进行 Web Hub 与 TTS 的改造与联调。

#### 1.1 创建统一任务模型

**文件：** `shared/task_model.py`

**功能：**
- 定义 `TaskType` 枚举（VIDEO, TTS, VOICE_CLONE, IMAGE）
- 定义 `TaskStatus` 枚举（PENDING, PROCESSING, COMPLETED, FAILED...）
- 定义 `TaskPriority` 枚举（LOW, NORMAL, HIGH, URGENT）
- 定义 `UnifiedTask` dataclass（统一所有任务类型）
- 提供序列化/反序列化方法
- 保留 `VideoTask` 别名确保向后兼容

**关键代码结构：**
```python
@dataclass
class UnifiedTask:
    # 基础标识
    task_id: str
    task_type: TaskType
    
    # 来源信息
    source: str  # "forum_post", "api", "manual"
    source_url: Optional[str] = None
    
    # 任务状态
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    
    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 任务载荷（业务数据）
    payload: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据（论坛、用户等信息）
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 结果和错误
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    # 重试控制
    retry_count: int = 0
    max_retries: int = 3
    
    # 工作节点信息
    worker_id: Optional[str] = None
    worker_url: Optional[str] = None
    
    # 输出路径
    output_path: Optional[str] = None
    output_files: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]: ...
    def to_json(self) -> str: ...
    @classmethod
    def from_dict(cls, data: Dict) -> UnifiedTask: ...
    @classmethod
    def from_json(cls, json_str: str) -> UnifiedTask: ...
    
    def is_video_task(self) -> bool: ...
    def is_tts_task(self) -> bool: ...
    def get_forum_info(self) -> Dict: ...

# 向后兼容
VideoTask = UnifiedTask
```

#### 1.2 创建统一任务管理器

**文件：** `shared/task_manager.py`

**功能：**
- 管理所有类型的任务（内存 + Redis双层存储）
- 创建、查询、更新任务
- 任务状态跟踪
- 优先级队列管理
- 分配任务到工作节点
- 获取待处理任务
- 统计信息

**关键接口：**
```python
class UnifiedTaskManager:
    def create_task(self, task_type, source, payload, metadata, ...) -> str
    def get_task(self, task_id: str) -> Optional[UnifiedTask]
    def update_task_status(self, task_id, status, result, error)
    def assign_task(self, task_id, worker_id, worker_url)
    def get_pending_tasks(self, task_type=None, limit=100) -> List[UnifiedTask]
    def get_tasks_by_status(self, status, limit=100) -> List[UnifiedTask]
    def get_stats(self) -> Dict

# 全局单例
def get_task_manager(**kwargs) -> UnifiedTaskManager
```

#### 1.3 创建统一爬虫管理器

**文件：** `shared/forum_crawler_manager.py`

**功能：**
- 统一管理论坛爬虫实例
- 避免重复创建
- 提供统一的爬虫接口
- 支持多论坛配置

**关键代码：**
```python
class ForumCrawlerManager:
    """统一爬虫管理器 - 单例模式"""
    
    def __init__(self):
        self.crawlers = {}  # forum_name -> AicutForumCrawler
        self.lock = threading.Lock()
    
    def get_crawler(self, forum_name: str = "default") -> AicutForumCrawler:
        """获取指定论坛的爬虫实例（懒加载）"""
        with self.lock:
            if forum_name not in self.crawlers:
                settings = load_forum_settings()
                # 根据配置创建爬虫
                self.crawlers[forum_name] = AicutForumCrawler(...)
            return self.crawlers[forum_name]
    
    def get_new_posts(self, forum_name: str = "default") -> List[Dict]:
        """获取新帖子"""
        crawler = self.get_crawler(forum_name)
        return crawler.get_forum_threads()
    
    def get_post_detail(self, post_id: str, forum_name: str = "default") -> Dict:
        """获取帖子详情"""
        crawler = self.get_crawler(forum_name)
        return crawler.get_post_detail(post_id)
    
    def login(self, forum_name: str = "default") -> bool:
        """登录论坛"""
        crawler = self.get_crawler(forum_name)
        return crawler.login()

# 全局单例
_crawler_manager = None

def get_forum_crawler_manager() -> ForumCrawlerManager:
    global _crawler_manager
    if _crawler_manager is None:
        _crawler_manager = ForumCrawlerManager()
    return _crawler_manager
```

#### 1.4 创建统一回复管理器

**文件：** `shared/forum_reply_manager.py`

**功能：**
- 统一管理论坛回复
- 支持文本、附件、多媒体
- 自动选择合适的论坛

**关键代码：**
```python
class ForumReplyManager:
    """统一回复管理器"""
    
    def __init__(self):
        self.crawler_manager = get_forum_crawler_manager()
    
    def reply_to_post(self, 
                     post_id: str,
                     content: str,
                     attachments: List[str] = None,
                     forum_name: str = "default") -> bool:
        """
        回复帖子
        
        Args:
            post_id: 帖子ID
            content: 回复内容
            attachments: 附件文件路径列表
            forum_name: 论坛名称
        
        Returns:
            是否成功
        """
        crawler = self.crawler_manager.get_crawler(forum_name)
        
        # 确保已登录
        if not crawler.logged_in:
            crawler.login()
        
        # 发送回复
        success = crawler.reply_to_thread(post_id, content, attachments)
        return success
    
    def reply_with_task_result(self, task: UnifiedTask, result: Dict) -> bool:
        """根据任务结果自动生成并发送回复"""
        forum_info = task.get_forum_info()
        post_id = forum_info['post_id']
        forum_name = forum_info.get('forum_name', 'default')
        
        # 根据任务类型生成回复内容
        if task.is_tts_task():
            content = self._generate_tts_reply(task, result)
        elif task.is_video_task():
            content = self._generate_video_reply(task, result)
        else:
            content = f"任务处理完成！"
        
        # 收集附件
        attachments = task.output_files if task.output_files else []
        
        # 发送回复
        return self.reply_to_post(post_id, content, attachments, forum_name)
    
    def _generate_tts_reply(self, task, result) -> str:
        """生成TTS任务的回复内容"""
        # 从services/tts_service调用格式化方法
        from services.tts_service import TTSTaskService
        service = TTSTaskService()
        reply_data = service.format_forum_reply({
            **task.metadata,
            **result,
            "request_type": task.task_type.value
        })
        return reply_data.get("content", "TTS处理完成")
    
    def _generate_video_reply(self, task, result) -> str:
        """生成视频任务的回复内容"""
        return f"""
✅ 视频处理完成！

📊 处理结果：
- 原视频：{task.source_url}
- 输出文件：{len(task.output_files)} 个
- 处理时长：{result.get('duration', 'N/A')}

感谢使用AI视频处理服务！
"""

# 全局单例
def get_forum_reply_manager() -> ForumReplyManager:
    ...
```

#### 1.5 更新 shared/__init__.py

```python
"""
Web Hub 共享模块

提供跨模块使用的通用组件：
- 统一任务模型和管理
- 论坛配置加载
- 论坛爬虫管理
- 论坛回复管理
"""

from .task_model import (
    UnifiedTask, 
    TaskType, 
    TaskStatus, 
    TaskPriority,
    VideoTask,  # 向后兼容
)
from .task_manager import UnifiedTaskManager, get_task_manager
from .forum_config import load_forum_settings, get_forum_credentials
from .forum_crawler_manager import ForumCrawlerManager, get_forum_crawler_manager
from .forum_reply_manager import ForumReplyManager, get_forum_reply_manager

__all__ = [
    # 任务模型
    'UnifiedTask',
    'TaskType',
    'TaskStatus',
    'TaskPriority',
    'VideoTask',
    # 任务管理
    'UnifiedTaskManager',
    'get_task_manager',
    # 配置
    'load_forum_settings',
    'get_forum_credentials',
    # 爬虫管理
    'ForumCrawlerManager',
    'get_forum_crawler_manager',
    # 回复管理
    'ForumReplyManager',
    'get_forum_reply_manager',
]
```

---

### 阶段2：修改Web Hub系统（3-4天）

#### 2.1 更新队列管理器

**文件：** `web_hub/lightweight/queue_manager.py`

**修改：**
```python
# 导入统一任务模型
from shared.task_model import UnifiedTask, TaskType, TaskStatus, TaskPriority

# 保留VideoTask作为别名（向后兼容）
VideoTask = UnifiedTask

class QueueManager:
    """队列管理器 - 使用统一任务模型"""
    
    def __init__(self, config):
        self.config = config
        # 使用共享的任务管理器
        from shared.task_manager import get_task_manager
        self.task_manager = get_task_manager(
            redis_host=config.redis_host,
            redis_port=config.redis_port,
            redis_db=config.redis_db
        )
        
        # 内部队列（按任务类型分类）
        self.download_queue = PriorityQueue()
        self.process_queue = PriorityQueue()
        self.upload_queue = PriorityQueue()
    
    def create_task(self, 
                   task_type: TaskType = TaskType.VIDEO,
                   source: str = "manual",
                   source_url: str = None,
                   source_path: str = None,
                   priority: TaskPriority = TaskPriority.NORMAL,
                   payload: Dict = None,
                   metadata: Dict = None) -> str:
        """创建任务（统一接口）"""
        return self.task_manager.create_task(
            task_type=task_type,
            source=source,
            source_url=source_url,
            source_path=source_path,
            priority=priority,
            payload=payload or {},
            metadata=metadata or {}
        )
    
    def get_task(self, task_id: str) -> Optional[UnifiedTask]:
        """获取任务"""
        return self.task_manager.get_task(task_id)
    
    def update_task_status(self, task_id: str, status: TaskStatus, 
                          result: Dict = None, error: str = None):
        """更新任务状态"""
        return self.task_manager.update_task_status(task_id, status, result, error)
    
    # ... 其他方法
```

#### 2.2 创建任务路由器

**文件：** `web_hub/lightweight/task_router.py`

```python
"""
任务路由器 - 根据任务类型分发到不同的处理器
"""
from typing import Dict, Any
from shared.task_model import UnifiedTask, TaskType, TaskStatus
from .logger import get_logger

logger = get_logger("TaskRouter")


class TaskRouter:
    """任务路由器"""
    
    def __init__(self, config):
        self.config = config
        self.adapters = {}
        self._init_adapters()
    
    def _init_adapters(self):
        """初始化适配器"""
        # TTS适配器
        try:
            from modules.tts_adapter import TTSModuleAdapter
            self.adapters[TaskType.TTS] = TTSModuleAdapter()
            self.adapters[TaskType.VOICE_CLONE] = self.adapters[TaskType.TTS]
            logger.info("✅ TTS适配器加载成功")
        except Exception as e:
            logger.error(f"❌ TTS适配器加载失败: {e}")
        
        # 视频适配器（使用现有的处理逻辑）
        # self.adapters[TaskType.VIDEO] = VideoAdapter()  # 后续实现
        
        logger.info(f"任务路由器初始化完成，支持 {len(self.adapters)} 种任务类型")
    
    def can_handle(self, task: UnifiedTask) -> bool:
        """判断是否可以处理该任务"""
        return task.task_type in self.adapters
    
    def route(self, task: UnifiedTask) -> Dict[str, Any]:
        """
        路由任务到对应的适配器
        
        Args:
            task: 统一任务对象
        
        Returns:
            处理结果字典
        """
        if task.task_type not in self.adapters:
            return {
                "success": False,
                "error": f"不支持的任务类型: {task.task_type.value}"
            }
        
        adapter = self.adapters[task.task_type]
        
        try:
            logger.info(f"路由任务 {task.task_id} 到 {task.task_type.value} 适配器")
            
            # 调用适配器处理
            result = adapter.consume(task.task_type.value, {
                **task.payload,
                **task.metadata
            })
            
            return {
                "success": result.success,
                "result": result.payload,
                "reply": result.payload.get("reply")
            }
        
        except Exception as e:
            logger.error(f"任务路由失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }


__all__ = ['TaskRouter']
```

#### 2.3 更新任务处理器

**文件：** `web_hub/lightweight/task_processor.py`

**修改：**
```python
from shared.task_model import UnifiedTask, TaskType, TaskStatus
from .task_router import TaskRouter

class TaskProcessor:
    def __init__(self, config, queue_manager, resource_monitor):
        self.config = config
        self.queue_manager = queue_manager
        self.resource_monitor = resource_monitor
        self.logger = get_logger("TaskProcessor")
        
        # 初始化任务路由器
        self.task_router = TaskRouter(config)
        
        # 线程池
        self.download_executor = ThreadPoolExecutor(...)
        self.process_executor = ThreadPoolExecutor(...)
        self.upload_executor = ThreadPoolExecutor(...)
        
        # ... 其他初始化
    
    def _process_worker(self):
        """处理worker - 支持多种任务类型"""
        while self.running:
            try:
                task = self.queue_manager.get_process_task(timeout=1)
                if not task:
                    continue
                
                # 根据任务类型路由
                if task.task_type == TaskType.VIDEO:
                    # 使用现有的视频处理逻辑
                    self._process_video_task(task)
                elif task.task_type in [TaskType.TTS, TaskType.VOICE_CLONE]:
                    # 使用任务路由器处理TTS任务
                    self._process_routed_task(task)
                else:
                    self.logger.warning(f"未知任务类型: {task.task_type}")
                    
            except Empty:
                pass
            except Exception as e:
                self.logger.error(f"处理worker异常: {e}")
    
    def _process_routed_task(self, task: UnifiedTask):
        """处理通过路由器的任务（TTS等）"""
        try:
            self.logger.info(f"开始处理任务 {task.task_id} ({task.task_type.value})")
            
            # 更新状态
            self.queue_manager.update_task_status(task.task_id, TaskStatus.PROCESSING)
            task.started_at = datetime.now()
            
            # 路由到适配器处理
            result = self.task_router.route(task)
            
            if result["success"]:
                # 处理成功
                task.result = result.get("result")
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                
                # 回复论坛
                if result.get("reply"):
                    self._reply_to_forum(task, result["reply"])
                
                self.queue_manager.update_task_status(
                    task.task_id, 
                    TaskStatus.COMPLETED, 
                    result=result
                )
                self.logger.info(f"✅ 任务完成: {task.task_id}")
            else:
                # 处理失败
                task.status = TaskStatus.FAILED
                task.error_message = result.get("error")
                self.queue_manager.update_task_status(
                    task.task_id, 
                    TaskStatus.FAILED, 
                    error=result.get("error")
                )
                self.logger.error(f"❌ 任务失败: {task.task_id} - {result.get('error')}")
        
        except Exception as e:
            self.logger.error(f"处理任务异常: {e}")
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            self.queue_manager.update_task_status(task.task_id, TaskStatus.FAILED, error=str(e))
    
    def _process_video_task(self, task: UnifiedTask):
        """处理视频任务（保持现有逻辑）"""
        # 现有的视频处理代码...
        pass
    
    def _reply_to_forum(self, task: UnifiedTask, reply_content: Dict):
        """统一的论坛回复"""
        try:
            from shared.forum_reply_manager import get_forum_reply_manager
            
            reply_manager = get_forum_reply_manager()
            
            success = reply_manager.reply_with_task_result(task, reply_content)
            
            if success:
                self.logger.info(f"✅ 论坛回复成功: {task.task_id}")
            else:
                self.logger.error(f"❌ 论坛回复失败: {task.task_id}")
            
            return success
        
        except Exception as e:
            self.logger.error(f"论坛回复异常: {e}")
            return False
```

#### 2.4 更新监控节点

**文件：** `web_hub/cluster_monitor/forum_monitor.py`

**修改：**
```python
from shared.task_model import TaskType
from shared.task_manager import get_task_manager
from shared.forum_crawler_manager import get_forum_crawler_manager

class ForumMonitor:
    def __init__(self, port=8000):
        # ... 现有初始化
        
        # 使用统一的组件
        self.task_manager = get_task_manager()
        self.crawler_manager = get_forum_crawler_manager()
    
    def _identify_task_type(self, post: Dict) -> TaskType:
        """
        识别帖子的任务类型
        
        根据帖子标题和内容中的关键词判断任务类型
        """
        title = post.get('title', '').lower()
        content = post.get('content', '').lower()
        
        # TTS关键词
        tts_keywords = ['tts', '语音合成', '配音', '朗读']
        clone_keywords = ['音色克隆', '声音克隆', 'voice clone', '克隆音色']
        
        # 检查音色克隆
        if any(kw in title or kw in content for kw in clone_keywords):
            return TaskType.VOICE_CLONE
        
        # 检查TTS
        if any(kw in title or kw in content for kw in tts_keywords):
            return TaskType.TTS
        
        # 默认视频任务
        return TaskType.VIDEO
    
    def process_new_post(self, post: Dict):
        """处理新帖子 - 创建统一任务"""
        try:
            # 识别任务类型
            task_type = self._identify_task_type(post)
            
            logger.info(f"识别任务类型: {task_type.value} - 帖子: {post.get('thread_id')}")
            
            # 提取源URL
            source_url = None
            if task_type == TaskType.VIDEO:
                source_url = post.get('video_url') or post.get('video_urls', [None])[0]
            else:
                source_url = post.get('thread_url')
            
            # 创建统一任务
            task_id = self.task_manager.create_task(
                task_type=task_type,
                source="forum_post",
                source_url=source_url,
                priority=TaskPriority.NORMAL,
                payload=self._extract_payload(post, task_type),
                metadata={
                    'forum_name': post.get('forum_name', 'default'),
                    'post_id': post.get('thread_id'),
                    'author_id': post.get('author_id'),
                    'author_name': post.get('author'),
                    'title': post.get('title'),
                    'content': post.get('content'),
                    'post_time': post.get('post_time'),
                    'thread_url': post.get('thread_url'),
                }
            )
            
            logger.info(f"✅ 创建任务: {task_id} ({task_type.value})")
            
            # 分发任务到工作节点
            self._dispatch_task_to_worker(task_id)
            
        except Exception as e:
            logger.error(f"处理新帖失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _extract_payload(self, post: Dict, task_type: TaskType) -> Dict:
        """根据任务类型提取载荷数据"""
        if task_type == TaskType.VIDEO:
            return {
                'video_url': post.get('video_url'),
                'video_urls': post.get('video_urls', []),
            }
        elif task_type in [TaskType.TTS, TaskType.VOICE_CLONE]:
            # TTS特定数据
            return {
                'text': post.get('content', ''),
                'title': post.get('title', ''),
                # 更多TTS参数由request_parser解析
            }
        else:
            return {}
    
    def _dispatch_task_to_worker(self, task_id: str):
        """分发任务到工作节点"""
        task = self.task_manager.get_task(task_id)
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return
        
        # 选择合适的工作节点
        machine = self._select_best_machine(task)
        if not machine:
            logger.warning(f"没有可用的工作节点")
            return
        
        # 发送任务到工作节点
        try:
            response = requests.post(
                f"{machine.url}/api/worker/receive-task",
                json=task.to_dict(),
                timeout=10
            )
            
            if response.status_code == 200:
                # 更新任务分配信息
                self.task_manager.assign_task(
                    task_id, 
                    worker_id=machine.url,
                    worker_url=machine.url
                )
                logger.info(f"✅ 任务分发成功: {task_id} -> {machine.url}")
            else:
                logger.error(f"❌ 任务分发失败: {response.status_code}")
        
        except Exception as e:
            logger.error(f"任务分发异常: {e}")
```

---

### 阶段3：整合TTS系统（3-4天）

#### 3.1 移除重复组件

**需要删除的文件：**
```bash
tts/custom_integration/integration/
├── ❌ tts_forum_monitor.py                 # 改用统一监控
├── ❌ tts_forum_crawler_integration.py     # 改用shared/forum_crawler_manager
├── ❌ tts_forum_reply_uploader.py          # 改用shared/forum_reply_manager
└── ❌ tts_forum_integration_manager.py     # 改用统一任务调度
```

**保留的文件：**
```bash
tts/custom_integration/integration/
├── ✅ tts_request_parser.py      # TTS业务逻辑
├── ✅ tts_permission_manager.py  # TTS业务逻辑
├── ✅ tts_api_service.py         # TTS业务逻辑
├── ✅ tts_init_db.py             # TTS业务逻辑
├── ✅ tts_config.py              # TTS配置
└── ✅ tts_forum_processor.py     # TTS业务逻辑（需要修改）
```

#### 3.2 修改TTS处理器

**文件：** `tts/custom_integration/integration/tts_forum_processor.py`

**修改：**
```python
"""
TTS请求处理器 - 纯业务逻辑，不涉及论坛交互
"""
class TTSForumProcessor:
    """TTS请求处理器"""
    
    def __init__(self, db_path: str = "database/tts_voice_system.db"):
        self.db_path = db_path
        self.parser = TTSRequestParser()
        self.permission_manager = TTSPermissionManager(db_path)
        self.api_service = TTSAPIService()
    
    def process_request(self, task_data: Dict) -> Tuple[bool, Dict]:
        """
        处理TTS请求（纯业务逻辑）
        
        Args:
            task_data: 任务数据字典，包含：
                - post_id: 帖子ID
                - author_id: 作者ID
                - title: 标题
                - content: 内容
                - ... 其他元数据
        
        Returns:
            (success, result) 元组
        """
        try:
            # 1. 解析请求
            request_info = self.parser.parse_request(
                task_data.get('content', ''),
                task_data.get('title', '')
            )
            
            if not request_info['is_tts_request']:
                return False, {"error": "不是有效的TTS请求"}
            
            # 2. 验证权限和配额
            author_id = task_data.get('author_id', '')
            permission_check = self.permission_manager.check_permission(
                author_id, 
                request_info['request_type']
            )
            
            if not permission_check['allowed']:
                return False, {
                    "error": permission_check.get('reason', '权限不足'),
                    "should_reply": True,
                    "reply_content": permission_check.get('message', '')
                }
            
            # 3. 调用API处理
            if request_info['request_type'] == 'tts':
                success, result = self.api_service.process_tts_request(request_info)
            elif request_info['request_type'] == 'voice_clone':
                success, result = self.api_service.process_voice_clone_request(request_info)
            else:
                return False, {"error": f"未知请求类型: {request_info['request_type']}"}
            
            # 4. 更新配额
            if success:
                self.permission_manager.consume_quota(author_id, request_info['request_type'])
            
            return success, result
        
        except Exception as e:
            logger.error(f"处理TTS请求异常: {e}")
            import traceback
            traceback.print_exc()
            return False, {"error": str(e)}
```

#### 3.3 修改services/tts_service/service.py

**文件：** `services/tts_service/service.py`

**修改：**
```python
class TTSTaskService:
    """封装 TTS/音色克隆任务处理的服务层接口"""
    
    def __init__(self, integration_root: Optional[Path | str] = None) -> None:
        # ... 现有初始化代码
        
        # 加载处理器
        self._processor = None
    
    def _load_processor(self):
        """延迟加载TTS处理器"""
        if self._processor is None:
            from tts_forum_processor import TTSForumProcessor
            self._processor = TTSForumProcessor()
        return self._processor
    
    def handle_tts_task(self, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理语音合成任务
        
        Args:
            task_payload: 统一任务的 payload + metadata
        
        Returns:
            标准化的处理结果
        """
        processor = self._load_processor()
        success, result = processor.process_request(task_payload)
        return {"success": success, "result": result}
    
    def handle_voice_clone_task(self, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理音色克隆任务
        
        Args:
            task_payload: 统一任务的 payload + metadata
        
        Returns:
            标准化的处理结果
        """
        processor = self._load_processor()
        success, result = processor.process_request(task_payload)
        return {"success": success, "result": result}
    
    # format_forum_reply 保持不变
```

#### 3.4 创建迁移脚本

**文件：** `tts/custom_integration/migrate_to_unified.py`

```python
"""
TTS系统迁移到统一架构的辅助脚本
"""
import os
import sys

def check_dependencies():
    """检查依赖"""
    print("🔍 检查依赖...")
    
    required = [
        'shared.task_model',
        'shared.task_manager',
        'shared.forum_crawler_manager',
        'shared.forum_reply_manager',
        'services.tts_service',
        'modules.tts_adapter',
    ]
    
    missing = []
    for module in required:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError:
            print(f"  ❌ {module}")
            missing.append(module)
    
    if missing:
        print(f"\n❌ 缺少依赖模块: {', '.join(missing)}")
        print("请先完成共享组件的创建")
        return False
    
    print("✅ 所有依赖检查通过")
    return True

def backup_old_files():
    """备份旧文件"""
    print("\n📦 备份旧文件...")
    
    old_files = [
        'tts_forum_monitor.py',
        'tts_forum_crawler_integration.py',
        'tts_forum_reply_uploader.py',
        'tts_forum_integration_manager.py',
    ]
    
    backup_dir = 'integration/backup_before_unified'
    os.makedirs(backup_dir, exist_ok=True)
    
    for filename in old_files:
        src = f'integration/{filename}'
        if os.path.exists(src):
            dst = f'{backup_dir}/{filename}'
            import shutil
            shutil.copy2(src, dst)
            print(f"  ✅ 备份: {filename}")
    
    print("✅ 备份完成")

def test_unified_system():
    """测试统一系统"""
    print("\n🧪 测试统一系统...")
    
    # 测试任务创建
    from shared.task_manager import get_task_manager
    from shared.task_model import TaskType, TaskPriority
    
    manager = get_task_manager()
    
    task_id = manager.create_task(
        task_type=TaskType.TTS,
        source="test",
        payload={"text": "测试文本"},
        metadata={"test": True}
    )
    
    print(f"  ✅ 创建测试任务: {task_id}")
    
    task = manager.get_task(task_id)
    assert task is not None
    assert task.task_type == TaskType.TTS
    
    print("  ✅ 任务查询成功")
    
    # 测试爬虫管理器
    from shared.forum_crawler_manager import get_forum_crawler_manager
    
    crawler_manager = get_forum_crawler_manager()
    print("  ✅ 爬虫管理器初始化成功")
    
    print("\n✅ 统一系统测试通过")

if __name__ == '__main__':
    print("=" * 60)
    print("TTS系统迁移到统一架构")
    print("=" * 60)
    
    if not check_dependencies():
        sys.exit(1)
    
    backup_old_files()
    
    test_unified_system()
    
    print("\n" + "=" * 60)
    print("✅ 迁移准备完成！")
    print("\n下一步：")
    print("1. 删除旧的重复文件")
    print("2. 使用统一的启动方式")
    print("3. 测试完整流程")
    print("=" * 60)
```

---

### 阶段4：激活多论坛支持（可选，2-3天）

#### 4.1 扩展配置文件

**文件：** `config/forum_settings.yaml`

```yaml
# 多论坛配置示例
forums:
  # 主论坛
  main:
    name: "懒人同城号AI"
    base_url: "https://tts.lrtcai.com"
    target_url: "https://tts.lrtcai.com/forum-2-1.html"
    forum_id: 2
    enabled: true
    check_interval: 10  # 秒
    credentials:
      username: "AI剪辑助手"
      password: "594188@lrtcai"
  
  # 备用论坛（示例）
  backup:
    name: "备用论坛"
    base_url: "https://forum2.example.com"
    target_url: "https://forum2.example.com/forum-5-1.html"
    forum_id: 5
    enabled: false  # 暂时禁用
    check_interval: 30
    credentials:
      username: "AI助手"
      password: "password123"

# 默认论坛（向后兼容）
forum:
  base_url: "https://tts.lrtcai.com"
  target_url: "https://tts.lrtcai.com/forum-2-1.html"
  forum_id: 2

credentials:
  username: "AI剪辑助手"
  password: "594188@lrtcai"
```

#### 4.2 更新配置加载器

**文件：** `shared/forum_config.py`

```python
def load_forum_settings(config_path: str | Path | None = None) -> Dict[str, Any]:
    """加载论坛配置 - 支持多论坛"""
    # ... 现有代码
    
    # 处理多论坛配置
    if 'forums' in config:
        # 验证每个论坛配置
        for forum_name, forum_cfg in config['forums'].items():
            if not forum_cfg.get('base_url') or not forum_cfg.get('target_url'):
                print(f"⚠️ 论坛 {forum_name} 配置不完整")
    
    return config

def get_forum_list() -> List[str]:
    """获取所有论坛名称列表"""
    config = load_forum_settings()
    if 'forums' in config:
        return list(config['forums'].keys())
    return ['default']

def get_forum_config(forum_name: str = 'main') -> Dict:
    """获取指定论坛的配置"""
    config = load_forum_settings()
    
    if 'forums' in config and forum_name in config['forums']:
        return config['forums'][forum_name]
    
    # 回退到默认配置
    return {
        'name': forum_name,
        'base_url': config.get('forum', {}).get('base_url', ''),
        'target_url': config.get('forum', {}).get('target_url', ''),
        'forum_id': config.get('forum', {}).get('forum_id', 0),
        'credentials': config.get('credentials', {})
    }
```

#### 4.3 激活multi_forum_crawler

**文件：** `web_hub/multi_forum_crawler.py`

**修改：**
```python
from shared.forum_crawler_manager import get_forum_crawler_manager
from shared.task_manager import get_task_manager

class MultiForumCrawler:
    """多论坛爬虫管理器 - 使用统一组件"""
    
    def __init__(self):
        self.crawler_manager = get_forum_crawler_manager()
        self.task_manager = get_task_manager()
        self.forum_list = get_forum_list()
        self.running = False
        self.threads = {}
    
    def start_monitoring(self):
        """启动多论坛监控"""
        print(f"🚀 启动多论坛监控，共 {len(self.forum_list)} 个论坛")
        
        self.running = True
        
        for forum_name in self.forum_list:
            forum_cfg = get_forum_config(forum_name)
            
            if not forum_cfg.get('enabled', True):
                print(f"⏭️  跳过禁用的论坛: {forum_name}")
                continue
            
            # 为每个论坛启动独立线程
            thread = threading.Thread(
                target=self._monitor_forum,
                args=(forum_name, forum_cfg),
                daemon=True
            )
            thread.start()
            self.threads[forum_name] = thread
            
            print(f"✅ 论坛监控已启动: {forum_name}")
        
        print("✅ 所有论坛监控已启动")
    
    def _monitor_forum(self, forum_name: str, forum_cfg: Dict):
        """监控单个论坛"""
        check_interval = forum_cfg.get('check_interval', 30)
        
        while self.running:
            try:
                # 获取新帖子
                posts = self.crawler_manager.get_new_posts(forum_name)
                
                if posts:
                    print(f"📨 [{forum_name}] 发现 {len(posts)} 个新帖")
                    
                    for post in posts:
                        # 创建任务
                        self._create_task_from_post(post, forum_name)
                
                time.sleep(check_interval)
            
            except Exception as e:
                print(f"❌ [{forum_name}] 监控异常: {e}")
                time.sleep(check_interval)
    
    def _create_task_from_post(self, post: Dict, forum_name: str):
        """从帖子创建任务"""
        # 识别任务类型
        task_type = self._identify_task_type(post)
        
        # 创建任务（使用统一任务管理器）
        task_id = self.task_manager.create_task(
            task_type=task_type,
            source="forum_post",
            source_url=post.get('thread_url'),
            metadata={
                'forum_name': forum_name,
                'post_id': post.get('thread_id'),
                'author_id': post.get('author_id'),
                'title': post.get('title'),
                'content': post.get('content'),
                # ...
            }
        )
        
        print(f"✅ [{forum_name}] 创建任务: {task_id} ({task_type.value})")
```

---

### 阶段5：统一启动方式（1-2天）

#### 5.1 创建统一启动脚本

**文件：** `start_unified_system.py`（项目根目录）

```python
#!/usr/bin/env python3
"""
统一系统启动脚本

支持的模式：
- monitor: 监控节点（监控论坛，分发任务）
- worker: 工作节点（接收任务，执行处理）
- standalone: 单机模式（监控+处理）
- multi-monitor: 多论坛监控
"""
import argparse
import sys
import os

def start_monitor(port=8000, multi_forum=False):
    """启动监控节点"""
    print(f"🎯 启动监控节点（端口: {port}）")
    
    if multi_forum:
        print("📡 多论坛监控模式")
        from web_hub.multi_forum_crawler import MultiForumCrawler
        crawler = MultiForumCrawler()
        crawler.start_monitoring()
        
        # 同时启动Web界面
        os.system(f"python web_hub/cluster_monitor/start_unified.py --mode production --port {port}")
    else:
        print("📡 单论坛监控模式")
        os.system(f"python web_hub/cluster_monitor/start_unified.py --mode production --port {port}")

def start_worker(port=8005):
    """启动工作节点"""
    print(f"🔨 启动工作节点（端口: {port}）")
    os.system(f"python web_hub/start_lightweight.py --port {port}")

def start_standalone(port=8000):
    """启动单机模式"""
    print(f"🚀 启动单机模式（端口: {port}）")
    print("⚠️  单机模式将同时运行监控和处理")
    
    # TODO: 实现单机模式逻辑
    print("❌ 单机模式暂未实现，请分别启动监控节点和工作节点")

def main():
    parser = argparse.ArgumentParser(description="统一系统启动脚本")
    parser.add_argument('mode', choices=['monitor', 'worker', 'standalone', 'multi-monitor'],
                       help='启动模式')
    parser.add_argument('--port', type=int, default=8000, help='端口号')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 统一任务调度系统")
    print("=" * 60)
    
    if args.mode == 'monitor':
        start_monitor(args.port, multi_forum=False)
    elif args.mode == 'multi-monitor':
        start_monitor(args.port, multi_forum=True)
    elif args.mode == 'worker':
        start_worker(args.port)
    elif args.mode == 'standalone':
        start_standalone(args.port)
    
    print("\n✅ 系统启动完成")
    print("按 Ctrl+C 停止")
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 系统停止")

if __name__ == '__main__':
    main()
```

#### 5.2 更新文档

**文件：** `docs/统一系统使用指南.md`

```markdown
# 统一系统使用指南

## 快速启动

### 单论坛模式

**监控节点：**
```bash
python start_unified_system.py monitor --port 8000
```

**工作节点：**
```bash
python start_unified_system.py worker --port 8005
```

### 多论坛模式

**监控节点：**
```bash
python start_unified_system.py multi-monitor --port 8000
```

**工作节点：**
```bash
python start_unified_system.py worker --port 8005
python start_unified_system.py worker --port 8006  # 第二个工作节点
```

## 配置

### 论坛配置

编辑 `config/forum_settings.yaml`:

```yaml
forums:
  main:
    name: "主论坛"
    base_url: "https://tts.lrtcai.com"
    target_url: "https://tts.lrtcai.com/forum-2-1.html"
    enabled: true
    credentials:
      username: "AI剪辑助手"
      password: "your_password"
```

### 任务类型

系统自动识别任务类型：

- **TTS任务**: 标题或内容包含 "tts", "语音合成", "配音"
- **音色克隆**: 标题或内容包含 "音色克隆", "声音克隆"
- **视频任务**: 默认类型

## 监控

### Web界面

访问: `http://localhost:8000`

查看：
- 任务队列状态
- 工作节点状态
- 任务处理统计

### API接口

```bash
# 查看任务统计
curl http://localhost:8000/api/tasks/stats

# 查看待处理任务
curl http://localhost:8000/api/tasks/pending

# 查看任务详情
curl http://localhost:8000/api/tasks/{task_id}
```

## 故障排除

### Redis连接失败

```bash
# 启动Redis
redis-server

# 验证连接
redis-cli ping
```

### 论坛登录失败

检查配置文件中的用户名和密码是否正确。

### 任务处理失败

查看日志:
```bash
tail -f logs/lightweight.log
tail -f logs/forum_monitor.log
```
```

---

## ✅ 向后兼容性

### 兼容策略

1. **保留VideoTask别名**
   ```python
   # shared/task_model.py
   VideoTask = UnifiedTask  # 向后兼容（实现时请在代码中标注此别名仅用于过渡，后续可逐步移除）
   ```

2. **保留现有API**
   ```python
   # web_hub/lightweight/queue_manager.py
   class QueueManager:
       def create_task(self, source_url=None, source_path=None, ...):
           # 自动转换为UnifiedTask
           return self.task_manager.create_task(
               task_type=TaskType.VIDEO,  # 默认视频任务
               source_url=source_url,
               source_path=source_path,
               ...
           )
   ```

3. **现有视频处理流程不受影响**
   - `task_processor.py` 中的视频处理逻辑保持不变
   - 只有TTS任务使用新的路由机制

4. **渐进式迁移**
   - 先完成共享组件创建
   - 再逐步修改Web Hub
   - 最后整合TTS系统
   - 每个阶段都可独立测试

---

## ⚠️ 风险评估

### 高风险项

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Redis故障 | 任务队列失效 | 内存队列降级，定期备份 |
| 爬虫单点故障 | 所有论坛监控失效 | 爬虫管理器单例，自动重连 |
| 数据库迁移 | 历史数据丢失 | 迁移前完整备份 |

### 中风险项

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 任务模型不兼容 | 旧任务无法读取 | 提供转换工具 |
| 配置格式变更 | 系统无法启动 | 向后兼容+验证脚本 |

### 低风险项

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 适配器加载失败 | 特定任务类型失败 | 优雅降级，记录日志 |
| 多论坛配置错误 | 单个论坛失效 | 独立线程，互不影响 |

---

## 🧪 测试策略

### 单元测试

```python
# tests/test_unified_task.py
def test_task_creation():
    """测试任务创建"""
    from shared.task_model import UnifiedTask, TaskType
    
    task = UnifiedTask(
        task_id="test-123",
        task_type=TaskType.TTS,
        source="test"
    )
    
    assert task.task_id == "test-123"
    assert task.task_type == TaskType.TTS
    assert task.is_tts_task()

def test_task_serialization():
    """测试任务序列化"""
    task = UnifiedTask(...)
    json_str = task.to_json()
    task2 = UnifiedTask.from_json(json_str)
    assert task.task_id == task2.task_id
```

### 集成测试

```python
# tests/test_integration.py
def test_task_flow():
    """测试完整任务流程"""
    # 1. 创建任务
    manager = get_task_manager()
    task_id = manager.create_task(...)
    
    # 2. 分配任务
    manager.assign_task(task_id, "worker1", "http://localhost:8005")
    
    # 3. 更新状态
    manager.update_task_status(task_id, TaskStatus.COMPLETED)
    
    # 4. 验证结果
    task = manager.get_task(task_id)
    assert task.status == TaskStatus.COMPLETED
```

### 端到端测试

```bash
# tests/e2e_test.sh
#!/bin/bash

# 1. 启动系统
python start_unified_system.py monitor --port 8000 &
MONITOR_PID=$!

python start_unified_system.py worker --port 8005 &
WORKER_PID=$!

sleep 5

# 2. 创建测试任务
curl -X POST http://localhost:8000/api/tasks/create \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "tts",
    "source": "test",
    "payload": {"text": "测试文本"}
  }'

# 3. 等待处理完成
sleep 10

# 4. 验证结果
curl http://localhost:8000/api/tasks/stats

# 5. 清理
kill $MONITOR_PID $WORKER_PID
```

---

## 📅 实施时间表

### 第1周：共享组件（3-4天）

- [ ] Day 1: `shared/task_model.py`
- [ ] Day 2: `shared/task_manager.py`
- [ ] Day 3: `shared/forum_crawler_manager.py`
- [ ] Day 4: `shared/forum_reply_manager.py`
- [ ] Day 4: 单元测试

### 第2周：Web Hub整合（3-4天）

- [ ] Day 5: 更新 `queue_manager.py`
- [ ] Day 6: 创建 `task_router.py`
- [ ] Day 7: 更新 `task_processor.py`
- [ ] Day 8: 更新 `forum_monitor.py`
- [ ] Day 8: 集成测试

### 第3周：TTS整合（3-4天）

- [ ] Day 9: 移除重复组件
- [ ] Day 10: 修改 `tts_forum_processor.py`
- [ ] Day 11: 更新 `services/tts_service`
- [ ] Day 12: 完整测试
- [ ] Day 12: 文档更新

### 第4周：多论坛+优化（可选）

- [ ] Day 13-14: 多论坛支持
- [ ] Day 15-16: 性能优化
- [ ] Day 16: 端到端测试

---

## 📚 相关文档

- [统一任务模型设计](./统一任务模型设计.md)
- [共享组件API文档](./共享组件API文档.md)
- [迁移指南](./迁移指南.md)
- [故障排查手册](./故障排查手册.md)

---

## ✅ 验收标准

### 功能验收

- [ ] TTS任务可以通过统一系统处理
- [ ] 视频任务仍然正常工作
- [ ] 多论坛监控正常运行
- [ ] 论坛回复功能正常
- [ ] 任务状态跟踪准确

### 性能验收

- [ ] 任务创建延迟 < 100ms
- [ ] 任务分发延迟 < 500ms
- [ ] Redis响应时间 < 10ms
- [ ] 系统内存占用 < 2GB
- [ ] 支持 100+ 并发任务

### 稳定性验收

- [ ] 连续运行 24 小时无崩溃
- [ ] Redis故障自动降级
- [ ] 单个论坛故障不影响其他论坛
- [ ] 工作节点故障任务可重分配

---

## 📞 支持与反馈

如有问题，请：
1. 查看日志：`logs/` 目录
2. 检查文档：`docs/` 目录
3. 运行诊断：`python tools/diagnose.py`
4. 提交Issue：包含日志和环境信息

---

**文档版本：** 1.0  
**最后更新：** 2025-11-02  
**维护者：** 开发团队

