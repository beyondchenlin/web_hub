#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
轻量级视频处理系统 - 模型管理器
负责管理和缓存语音识别模型，避免重复加载
"""

import logging
import threading
from typing import Optional, Dict, Any
from funasr import AutoModel

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
        """获取FunASR模型（缓存）"""
        model_key = f"funasr_{lang}"
        
        with self._model_lock:
            if model_key in self._models:
                logger.info(f"✅ 使用缓存的{lang}语音识别模型")
                return self._models[model_key]
            
            logger.info(f"🔄 首次加载{lang}语音识别模型，请稍候...")
            try:
                if lang == 'zh':
                    model = AutoModel(
                        model="iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
                        vad_model="damo/speech_fsmn_vad_zh-cn-16k-common-pytorch",
                        punc_model="damo/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
                        spk_model="damo/speech_campplus_sv_zh-cn_16k-common",
                        # 启用模型缓存
                        cache_dir=None,  # 使用默认缓存目录
                        disable_update=True,  # 禁用自动更新检查
                    )
                else:  # 英文
                    model = AutoModel(
                        model="iic/speech_paraformer_asr-en-16k-vocab4199-pytorch",
                        vad_model="damo/speech_fsmn_vad_zh-cn-16k-common-pytorch",
                        punc_model="damo/punc_ct-transformer_cn-en-common-vocab471067-large",
                        spk_model="damo/speech_campplus_sv_zh-cn_16k-common",
                        # 启用模型缓存
                        cache_dir=None,  # 使用默认缓存目录
                        disable_update=True,  # 禁用自动更新检查
                    )
                
                self._models[model_key] = model
                logger.info(f"✅ {lang}语音识别模型加载完成并缓存")
                return model
                
            except Exception as e:
                logger.error(f"❌ 加载{lang}语音识别模型失败: {e}")
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
