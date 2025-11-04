#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
轻量级视频处理系统 - 模型管理器
负责管理和缓存语音识别模型，避免重复加载
"""

import logging
import threading
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class ModelManager:
    """全局模型管理器 - 单例模式"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self._models: Dict[str, Any] = {}
        self._model_lock = threading.Lock()
        logger.info("模型管理器初始化完成")
    
    def get_funasr_model(self, lang: str = 'zh') -> Optional[Any]:
        """ASR 已禁用：返回 None"""
        logger.info("ASR 已禁用：不加载 FunASR 模型")
        return None

    def clear_models(self):
        """清理所有缓存的模型"""
        with self._model_lock:
            self._models.clear()
            logger.info("🧹 已清理所有缓存的模型")
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        with self._model_lock:
            return {
                "cached_models": list(self._models.keys()),
                "model_count": len(self._models)
            }

# 全局模型管理器实例
model_manager = ModelManager()
