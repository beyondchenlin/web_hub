#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""
轻量级视频处理系统 - 资源监控模块

主要功能：
- 系统资源监控（CPU、内存、磁盘、GPU）
- 资源使用历史记录
- 资源告警和限制
- 与原有ResourceMonitor集成
"""

import os
import time
import threading
import subprocess
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


@dataclass
class ResourceSnapshot:
    """资源快照数据类"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    gpu_percent: float = 0.0
    gpu_memory_used_mb: float = 0.0
    gpu_memory_total_mb: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'memory_used_gb': self.memory_used_gb,
            'memory_total_gb': self.memory_total_gb,
            'disk_percent': self.disk_percent,
            'disk_used_gb': self.disk_used_gb,
            'disk_total_gb': self.disk_total_gb,
            'gpu_percent': self.gpu_percent,
            'gpu_memory_used_mb': self.gpu_memory_used_mb,
            'gpu_memory_total_mb': self.gpu_memory_total_mb
        }


class LightweightResourceMonitor:
    """轻量级资源监控器"""
    
    def __init__(self, config):
        self.config = config
        self.running = False
        self.monitor_thread = None
        self.redis_client = None
        
        # 资源数据
        self.current_snapshot: Optional[ResourceSnapshot] = None
        self.history: List[ResourceSnapshot] = []
        self.max_history_size = 1000  # 保留最近1000个快照
        
        # 步骤资源记录（兼容原有ResourceMonitor）
        self.step_resources: Dict[str, Dict[str, float]] = {}
        
        # 线程锁
        self.lock = threading.RLock()
        
        # 初始化
        self._init_redis()
        self._check_dependencies()
    
    def _init_redis(self):
        """初始化Redis连接"""
        if not REDIS_AVAILABLE:
            return
        
        try:
            self.redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                decode_responses=True,
                socket_timeout=5
            )
            self.redis_client.ping()
        except Exception:
            self.redis_client = None
    
    def _check_dependencies(self):
        """检查依赖"""
        if not PSUTIL_AVAILABLE:
            print("警告: psutil不可用，资源监控功能受限")
    
    def start(self):
        """启动监控"""
        if self.running:
            return

        self.running = True

        # 立即收集一次数据
        try:
            snapshot = self._collect_resource_data()
            with self.lock:
                self.current_snapshot = snapshot
                self.history.append(snapshot)
        except Exception as e:
            print(f"初始资源收集失败: {e}")

        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("资源监控已启动")
    
    def stop(self):
        """停止监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("资源监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                snapshot = self._collect_resource_data()
                
                with self.lock:
                    self.current_snapshot = snapshot
                    self.history.append(snapshot)
                    
                    # 限制历史记录大小
                    if len(self.history) > self.max_history_size:
                        self.history = self.history[-self.max_history_size:]
                
                # 保存到Redis
                self._save_to_redis(snapshot)
                
                # 检查资源告警
                self._check_alerts(snapshot)
                
                time.sleep(self.config.resource_check_interval)
                
            except Exception as e:
                print(f"资源监控错误: {e}")
                time.sleep(10)
    
    def _collect_resource_data(self) -> ResourceSnapshot:
        """收集资源数据"""
        timestamp = datetime.now()
        
        # CPU和内存
        if PSUTIL_AVAILABLE:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_gb = memory.used / (1024**3)
            memory_total_gb = memory.total / (1024**3)
            
            # 磁盘使用情况
            try:
                # 确保使用绝对路径
                output_path = os.path.abspath(self.config.output_dir)
                if not os.path.exists(output_path):
                    # 如果输出目录不存在，使用当前工作目录
                    output_path = os.getcwd()

                disk = psutil.disk_usage(output_path)
                disk_percent = (disk.used / disk.total) * 100
                disk_used_gb = disk.used / (1024**3)
                disk_total_gb = disk.total / (1024**3)
            except Exception as e:
                # 如果磁盘检查失败，使用默认值
                print(f"磁盘使用情况检查失败: {e}")
                disk_percent = 0.0
                disk_used_gb = 0.0
                disk_total_gb = 0.0
        else:
            cpu_percent = 0.0
            memory_percent = 0.0
            memory_used_gb = 0.0
            memory_total_gb = 0.0
            disk_percent = 0.0
            disk_used_gb = 0.0
            disk_total_gb = 0.0
        
        # GPU信息
        gpu_percent, gpu_memory_used_mb, gpu_memory_total_mb = self._get_gpu_info()
        
        return ResourceSnapshot(
            timestamp=timestamp,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_gb=memory_used_gb,
            memory_total_gb=memory_total_gb,
            disk_percent=disk_percent,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
            gpu_percent=gpu_percent,
            gpu_memory_used_mb=gpu_memory_used_mb,
            gpu_memory_total_mb=gpu_memory_total_mb
        )
    
    def _get_gpu_info(self) -> tuple:
        """获取GPU信息"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", 
                 "--format=csv,noheader,nounits"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                values = result.stdout.strip().split(",")
                if len(values) >= 3:
                    gpu_percent = float(values[0].strip())
                    gpu_memory_used_mb = float(values[1].strip())
                    gpu_memory_total_mb = float(values[2].strip())
                    return gpu_percent, gpu_memory_used_mb, gpu_memory_total_mb
        except Exception:
            pass
        
        return 0.0, 0.0, 0.0
    
    def _save_to_redis(self, snapshot: ResourceSnapshot):
        """保存到Redis"""
        if not self.redis_client:
            return
        
        try:
            key = f"resource:snapshot:{int(snapshot.timestamp.timestamp())}"
            self.redis_client.setex(key, 3600, str(snapshot.to_dict()))  # 1小时过期
            
            # 保存当前状态
            self.redis_client.setex("resource:current", 300, str(snapshot.to_dict()))  # 5分钟过期
        except Exception:
            pass
    
    def _check_alerts(self, snapshot: ResourceSnapshot):
        """检查资源告警"""
        alerts = []
        
        # 内存告警
        if snapshot.memory_percent > 90:
            alerts.append(f"内存使用率过高: {snapshot.memory_percent:.1f}%")
        elif snapshot.memory_used_gb > self.config.memory_limit_gb * 0.9:
            alerts.append(f"内存使用量接近限制: {snapshot.memory_used_gb:.1f}GB")
        
        # 磁盘告警
        if snapshot.disk_percent > 90:
            alerts.append(f"磁盘使用率过高: {snapshot.disk_percent:.1f}%")
        elif snapshot.disk_used_gb > self.config.disk_limit_gb * 0.9:
            alerts.append(f"磁盘使用量接近限制: {snapshot.disk_used_gb:.1f}GB")
        
        # CPU告警
        if snapshot.cpu_percent > 95:
            alerts.append(f"CPU使用率过高: {snapshot.cpu_percent:.1f}%")
        
        # GPU告警
        if snapshot.gpu_percent > 95:
            alerts.append(f"GPU使用率过高: {snapshot.gpu_percent:.1f}%")
        
        # 记录告警
        for alert in alerts:
            print(f"资源告警: {alert}")
    
    def get_current_usage(self) -> Optional[ResourceSnapshot]:
        """获取当前资源使用情况"""
        with self.lock:
            return self.current_snapshot
    
    def get_usage_str(self) -> str:
        """获取资源使用字符串（兼容原有接口）"""
        snapshot = self.get_current_usage()
        if not snapshot:
            return "资源监控未启动"
        
        return (f"CPU: {snapshot.cpu_percent:.1f}% | "
                f"内存: {snapshot.memory_percent:.1f}% ({snapshot.memory_used_gb:.1f}GB) | "
                f"GPU: {snapshot.gpu_percent:.1f}% | "
                f"GPU内存: {snapshot.gpu_memory_used_mb:.0f}MB")
    
    def record_step_resource(self, step_number: int, step_name: str) -> str:
        """记录步骤资源使用情况（兼容原有接口）"""
        snapshot = self.get_current_usage()
        if not snapshot:
            return "资源监控未启动"
        
        with self.lock:
            self.step_resources[step_name] = {
                'cpu': snapshot.cpu_percent,
                'memory': snapshot.memory_percent,
                'gpu': snapshot.gpu_percent,
                'gpu_memory': snapshot.gpu_memory_used_mb,
                'timestamp': snapshot.timestamp.isoformat()
            }
        
        return self.get_usage_str()
    
    def get_step_resources(self) -> Dict[str, Dict[str, float]]:
        """获取所有步骤的资源使用情况（兼容原有接口）"""
        with self.lock:
            return self.step_resources.copy()
    
    def is_resource_critical(self) -> bool:
        """检查资源是否紧张"""
        snapshot = self.get_current_usage()
        if not snapshot:
            return False
        
        return (snapshot.memory_percent > 90 or 
                snapshot.disk_percent > 95 or
                snapshot.cpu_percent > 98)
    
    def can_start_new_task(self) -> bool:
        """检查是否可以启动新任务"""
        snapshot = self.get_current_usage()
        if not snapshot:
            return True
        
        # 检查内存限制
        if snapshot.memory_used_gb > self.config.memory_limit_gb * 0.8:
            return False
        
        # 检查磁盘限制
        if snapshot.disk_used_gb > self.config.disk_limit_gb * 0.9:
            return False
        
        return True
    
    def get_history(self, hours: int = 1) -> List[ResourceSnapshot]:
        """获取历史数据"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self.lock:
            return [
                snapshot for snapshot in self.history
                if snapshot.timestamp >= cutoff_time
            ]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        snapshot = self.get_current_usage()
        if not snapshot:
            return {}
        
        history_1h = self.get_history(1)
        
        stats = {
            'current': snapshot.to_dict(),
            'history_count': len(history_1h),
            'step_count': len(self.step_resources)
        }
        
        if history_1h:
            cpu_values = [s.cpu_percent for s in history_1h]
            memory_values = [s.memory_percent for s in history_1h]
            
            stats.update({
                'cpu_avg_1h': sum(cpu_values) / len(cpu_values),
                'cpu_max_1h': max(cpu_values),
                'memory_avg_1h': sum(memory_values) / len(memory_values),
                'memory_max_1h': max(memory_values)
            })
        
        return stats
    
    def cleanup_history(self, max_age_hours: int = 24):
        """清理历史数据"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with self.lock:
            self.history = [
                snapshot for snapshot in self.history
                if snapshot.timestamp >= cutoff_time
            ]
