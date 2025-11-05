-- 论坛帖子数据表结构定义
-- 支持懒人同城号AI-智能剪口播论坛集成
-- 数据库版本: 2.0
-- 创建日期: 2025-06-18
-- 最后更新: 2025-07-25
-- 数据库类型: SQLite

-- 创建论坛帖子主表
CREATE TABLE IF NOT EXISTS forum_posts (
    -- 主键和基本信息
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id VARCHAR(50) UNIQUE NOT NULL,           -- 论坛帖子ID
    thread_id VARCHAR(50) NOT NULL,                -- 主题ID
    forum_id INTEGER NOT NULL DEFAULT 2,           -- 板块ID (智能剪口播板块为2)
    
    -- 帖子内容信息
    title TEXT NOT NULL,                           -- 帖子标题
    content TEXT,                                  -- 帖子内容
    author_id VARCHAR(50) NOT NULL,                -- 作者ID
    author_name VARCHAR(100) NOT NULL,             -- 作者用户名
    
    -- 封面信息 (智能剪口播专用)
    cover_title_up TEXT,                           -- 封面标题上
    cover_title_middle TEXT,                       -- 封面标题中
    cover_title_down TEXT,                         -- 封面标题下
    cover_info_raw TEXT,                           -- 原始封面信息
    
    -- 媒体文件信息
    video_urls TEXT,                               -- 视频URL列表 (JSON格式)
    audio_urls TEXT,                               -- 音频URL列表 (JSON格式)
    original_filenames TEXT,                       -- 原始文件名列表 (JSON格式)
    media_count INTEGER DEFAULT 0,                 -- 媒体文件总数
    
    -- 处理状态
    processing_status VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, failed
    task_id VARCHAR(50),                           -- 关联的处理任务ID
    output_path TEXT,                              -- 处理后的输出路径

    -- 集群监控专用字段
    machine_url TEXT,                              -- 分配的处理机器URL
    dispatch_time DATETIME,                        -- 任务分发时间
    completion_time DATETIME,                      -- 任务完成时间
    error_message TEXT,                            -- 错误信息
    retry_count INTEGER DEFAULT 0,                 -- 重试次数

    -- 回复状态
    reply_status VARCHAR(20) DEFAULT 'pending',    -- pending, sent, failed
    reply_content TEXT,                            -- 回复内容
    reply_time DATETIME,                           -- 回复时间
    
    -- 时间戳
    post_time DATETIME NOT NULL,                   -- 帖子发布时间
    discovered_time DATETIME DEFAULT CURRENT_TIMESTAMP, -- 发现时间
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,    -- 最后更新时间
    
    -- 元数据
    metadata TEXT,                                 -- 额外元数据 (JSON格式)
    source_url TEXT,                               -- 原始帖子URL
    
    -- 索引字段
    is_processed BOOLEAN DEFAULT FALSE,            -- 是否已处理
    is_replied BOOLEAN DEFAULT FALSE,              -- 是否已回复
    priority INTEGER DEFAULT 1                     -- 处理优先级 (1-5)
);

-- 创建媒体文件详情表
CREATE TABLE IF NOT EXISTS forum_media_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id VARCHAR(50) NOT NULL,                  -- 关联的帖子ID
    file_type VARCHAR(10) NOT NULL,                -- video, audio
    original_url TEXT NOT NULL,                    -- 原始下载URL
    local_path TEXT,                               -- 本地存储路径
    file_size INTEGER,                             -- 文件大小 (字节)
    duration REAL,                                 -- 时长 (秒)
    download_status VARCHAR(20) DEFAULT 'pending', -- pending, downloading, completed, failed
    download_time DATETIME,                        -- 下载完成时间
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (post_id) REFERENCES forum_posts(post_id)
);

-- 创建处理任务记录表
CREATE TABLE IF NOT EXISTS processing_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id VARCHAR(50) UNIQUE NOT NULL,           -- 任务ID
    post_id VARCHAR(50) NOT NULL,                  -- 关联的帖子ID
    task_type VARCHAR(20) DEFAULT 'video_process', -- 任务类型
    status VARCHAR(20) DEFAULT 'pending',          -- 任务状态
    priority INTEGER DEFAULT 1,                    -- 优先级
    
    -- 处理参数
    input_files TEXT,                              -- 输入文件列表 (JSON)
    output_path TEXT,                              -- 输出路径
    processing_config TEXT,                        -- 处理配置 (JSON)
    
    -- 时间记录
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_time DATETIME,
    completed_time DATETIME,
    
    -- 结果信息
    result_files TEXT,                             -- 结果文件列表 (JSON)
    error_message TEXT,                            -- 错误信息
    processing_log TEXT,                           -- 处理日志
    
    FOREIGN KEY (post_id) REFERENCES forum_posts(post_id)
);

-- 创建系统配置表
CREATE TABLE IF NOT EXISTS system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key VARCHAR(100) UNIQUE NOT NULL,       -- 配置键
    config_value TEXT,                             -- 配置值
    config_type VARCHAR(20) DEFAULT 'string',      -- 配置类型: string, int, bool, json
    description TEXT,                              -- 配置描述
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
-- 论坛帖子表索引
CREATE INDEX IF NOT EXISTS idx_forum_posts_post_id ON forum_posts(post_id);
CREATE INDEX IF NOT EXISTS idx_forum_posts_thread_id ON forum_posts(thread_id);
CREATE INDEX IF NOT EXISTS idx_forum_posts_author_id ON forum_posts(author_id);
CREATE INDEX IF NOT EXISTS idx_forum_posts_processing_status ON forum_posts(processing_status);
CREATE INDEX IF NOT EXISTS idx_forum_posts_reply_status ON forum_posts(reply_status);
CREATE INDEX IF NOT EXISTS idx_forum_posts_post_time ON forum_posts(post_time);
CREATE INDEX IF NOT EXISTS idx_forum_posts_discovered_time ON forum_posts(discovered_time);
CREATE INDEX IF NOT EXISTS idx_forum_posts_is_processed ON forum_posts(is_processed);
CREATE INDEX IF NOT EXISTS idx_forum_posts_is_replied ON forum_posts(is_replied);
CREATE INDEX IF NOT EXISTS idx_forum_posts_priority ON forum_posts(priority);
CREATE INDEX IF NOT EXISTS idx_forum_posts_machine_url ON forum_posts(machine_url);
CREATE INDEX IF NOT EXISTS idx_forum_posts_dispatch_time ON forum_posts(dispatch_time);

-- 媒体文件表索引
CREATE INDEX IF NOT EXISTS idx_media_files_post_id ON forum_media_files(post_id);
CREATE INDEX IF NOT EXISTS idx_media_files_file_type ON forum_media_files(file_type);
CREATE INDEX IF NOT EXISTS idx_media_files_download_status ON forum_media_files(download_status);

-- 处理任务表索引
CREATE INDEX IF NOT EXISTS idx_processing_tasks_task_id ON processing_tasks(task_id);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_post_id ON processing_tasks(post_id);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_status ON processing_tasks(status);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_priority ON processing_tasks(priority);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_created_time ON processing_tasks(created_time);

-- 系统配置表索引
CREATE INDEX IF NOT EXISTS idx_system_config_key ON system_config(config_key);

-- 插入初始配置数据 - 统一配置源，使用10秒监控间隔
INSERT OR IGNORE INTO system_config (config_key, config_value, config_type, description) VALUES
('forum_enabled', 'true', 'bool', '是否启用论坛监控功能'),
('forum_check_interval', '10', 'int', '论坛检查间隔(秒) - 统一为10秒高频监控'),
('target_forum_id', '2', 'int', '目标论坛板块ID'),
('target_forum_url', 'https://tts.lrtcai.com/forum-2-1.html', 'string', '目标论坛URL'),
('auto_reply_enabled', 'true', 'bool', '是否启用自动回复'),
('max_concurrent_downloads', '3', 'int', '最大并发下载数'),
('media_storage_days', '30', 'int', '媒体文件保存天数'),
('database_version', '2.0', 'string', '数据库版本'),
('last_check_time', '', 'string', '最后检查时间'),
('processed_posts_count', '0', 'int', '已处理帖子数量');

-- 创建触发器：自动更新 last_updated 字段
CREATE TRIGGER IF NOT EXISTS update_forum_posts_timestamp
    AFTER UPDATE ON forum_posts
    FOR EACH ROW
BEGIN
    UPDATE forum_posts SET last_updated = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 创建触发器：自动更新系统配置的 updated_time 字段
CREATE TRIGGER IF NOT EXISTS update_system_config_timestamp
    AFTER UPDATE ON system_config
    FOR EACH ROW
BEGIN
    UPDATE system_config SET updated_time = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 数据维护和清理脚本
-- 清理过期的媒体文件记录 (超过30天)
-- DELETE FROM forum_media_files
-- WHERE download_time < datetime('now', '-30 days')
-- AND download_status = 'completed';

-- 清理已完成的旧任务记录 (超过7天)
-- DELETE FROM processing_tasks
-- WHERE completed_time < datetime('now', '-7 days')
-- AND status = 'completed';

-- 统计查询示例
-- 查看待处理的帖子
-- SELECT post_id, title, author_name, post_time
-- FROM forum_posts
-- WHERE processing_status = 'pending'
-- ORDER BY priority DESC, post_time ASC;

-- 查看处理统计
-- SELECT
--     processing_status,
--     COUNT(*) as count,
--     AVG(CASE WHEN completed_time IS NOT NULL AND started_time IS NOT NULL
--         THEN (julianday(completed_time) - julianday(started_time)) * 24 * 60
--         ELSE NULL END) as avg_processing_minutes
-- FROM processing_tasks
-- GROUP BY processing_status;

-- 数据库版本和迁移信息
-- 当前版本: 2.0
-- 创建日期: 2025-06-18
-- 最后更新: 2025-07-25 (添加cover_title_middle字段支持)
-- 兼容性: SQLite 3.x
-- 字符编码: UTF-8

-- 备份建议:
-- 1. 定期备份整个数据库文件
-- 2. 导出重要数据为CSV格式
-- 3. 保留处理日志用于故障排查

-- 性能优化建议:
-- 1. 定期运行 VACUUM 命令整理数据库
-- 2. 使用 ANALYZE 命令更新统计信息
-- 3. 监控索引使用情况，必要时添加新索引
