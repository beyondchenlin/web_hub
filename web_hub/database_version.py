#!/usr/bin/env python3
"""
数据库版本管理配置
单一真理源 - 所有版本信息的权威定义
"""

# 数据库版本配置
DATABASE_VERSION = "2.0"
DATABASE_SCHEMA_DATE = "2025-06-18"
DATABASE_LAST_UPDATE = "2025-07-25"

# 版本历史和变更记录
VERSION_HISTORY = {
    "1.0": {
        "date": "2025-06-18",
        "description": "初始版本，基础论坛集成功能",
        "changes": [
            "创建forum_posts主表",
            "创建forum_media_files表", 
            "创建processing_tasks表",
            "创建system_config表",
            "基础索引和触发器"
        ]
    },
    "2.0": {
        "date": "2025-07-25", 
        "description": "添加封面标题中间字段支持",
        "changes": [
            "添加cover_title_middle字段到forum_posts表",
            "完善封面标题三段式支持",
            "优化数据库初始化逻辑"
        ]
    }
}

# 必需字段定义 - 用于数据库结构验证
REQUIRED_COLUMNS = {
    "forum_posts": [
        "post_id", "thread_id", "title", "author_id", "author_name",
        "cover_title_up", "cover_title_middle", "cover_title_down",
        "video_urls", "audio_urls", "original_filenames",
        "processing_status", "post_time"
    ]
}

def get_current_version():
    """获取当前数据库版本"""
    return DATABASE_VERSION

def get_version_info(version=None):
    """获取版本信息"""
    if version is None:
        version = DATABASE_VERSION
    return VERSION_HISTORY.get(version, {})

def get_required_columns(table_name):
    """获取指定表的必需字段列表"""
    return REQUIRED_COLUMNS.get(table_name, [])

if __name__ == "__main__":
    print(f"当前数据库版本: {DATABASE_VERSION}")
    print(f"创建日期: {DATABASE_SCHEMA_DATE}")
    print(f"最后更新: {DATABASE_LAST_UPDATE}")
    print("\n版本历史:")
    for version, info in VERSION_HISTORY.items():
        print(f"  {version}: {info['description']} ({info['date']})")
