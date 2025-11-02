#!/usr/bin/env python3
"""
视频处理性能追踪模块
"""

import time
import json
import os
import psutil
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import GPUtil


@dataclass
class StageTimingData:
    """单个处理阶段的计时数据"""
    stage_name: str
    start_time: float
    end_time: float
    duration: float
    gpu_accelerated: bool = False
    memory_usage_mb: float = 0.0
    gpu_utilization: float = 0.0
    cpu_utilization: float = 0.0


@dataclass
class VideoProcessingReport:
    """完整的视频处理报告"""
    # 基本信息
    video_filename: str
    original_filename: str
    file_size_mb: float
    video_duration_seconds: float
    processing_start_time: str
    processing_end_time: str
    total_processing_time: float
    
    # 详细计时
    crawl_detection_time: float = 0.0
    download_time: float = 0.0
    stage_timings: List[StageTimingData] = None
    upload_time: float = 0.0
    forum_reply_time: float = 0.0
    
    # 性能统计
    avg_gpu_utilization: float = 0.0
    peak_memory_usage_mb: float = 0.0
    avg_cpu_utilization: float = 0.0
    processing_speed_ratio: float = 0.0  # 处理速度/实时速度
    
    # 质量指标
    success_rate: float = 100.0
    error_messages: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.stage_timings is None:
            self.stage_timings = []
        if self.error_messages is None:
            self.error_messages = []
        if self.warnings is None:
            self.warnings = []


class PerformanceTracker:
    """性能追踪器 - 支持多任务并发"""

    def __init__(self):
        # 使用字典存储多个任务的报告，key为task_id
        self.task_reports: Dict[str, VideoProcessingReport] = {}
        self.task_stage_start_times: Dict[str, float] = {}
        self.monitoring_thread: Optional[threading.Thread] = None
        self.monitoring_active = False
        self.performance_samples = []

        # 确保报告目录存在
        self.reports_dir = "logs/performance_reports"
        self.daily_summaries_dir = "logs/daily_summaries"
        os.makedirs(self.reports_dir, exist_ok=True)
        os.makedirs(self.daily_summaries_dir, exist_ok=True)
    
    def start_video_processing(self, video_filename: str, original_filename: str,
                             file_size_mb: float, video_duration_seconds: float) -> str:
        """开始视频处理追踪，返回task_id"""
        task_id = video_filename  # 使用video_filename作为task_id

        self.task_reports[task_id] = VideoProcessingReport(
            video_filename=video_filename,
            original_filename=original_filename,
            file_size_mb=file_size_mb,
            video_duration_seconds=video_duration_seconds,
            processing_start_time=datetime.now().isoformat(),
            processing_end_time="",
            total_processing_time=0.0
        )

        # 开始性能监控（如果还没有启动）
        if not self.monitoring_active:
            self.start_performance_monitoring()

        print(f"📊 开始追踪视频处理: {original_filename} (任务ID: {task_id})")
        print(f"   文件大小: {file_size_mb:.1f} MB")
        print(f"   视频时长: {self._format_duration(video_duration_seconds)}")

        return task_id
    
    def start_stage(self, task_id: str, stage_name: str, gpu_accelerated: bool = False):
        """开始处理阶段"""
        if task_id not in self.task_reports:
            print(f"⚠️ 任务 {task_id} 不存在，无法开始阶段 {stage_name}")
            return

        self.task_stage_start_times[task_id] = time.time()
        print(f"⏱️ 开始 {stage_name}{'(GPU加速)' if gpu_accelerated else ''} (任务: {task_id})")

    def end_stage(self, task_id: str, stage_name: str, gpu_accelerated: bool = False):
        """结束处理阶段"""
        if task_id not in self.task_reports or task_id not in self.task_stage_start_times:
            print(f"⚠️ 任务 {task_id} 不存在或未开始阶段，无法结束阶段 {stage_name}")
            return

        end_time = time.time()
        start_time = self.task_stage_start_times[task_id]
        duration = end_time - start_time

        # 获取当前性能数据
        memory_usage = psutil.virtual_memory().used / 1024 / 1024  # MB
        cpu_usage = psutil.cpu_percent()
        gpu_usage = self._get_gpu_utilization()

        stage_data = StageTimingData(
            stage_name=stage_name,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            gpu_accelerated=gpu_accelerated,
            memory_usage_mb=memory_usage,
            gpu_utilization=gpu_usage,
            cpu_utilization=cpu_usage
        )

        self.task_reports[task_id].stage_timings.append(stage_data)

        print(f"✅ 完成 {stage_name}: {duration:.1f}秒 (任务: {task_id})")
        if gpu_accelerated:
            print(f"   GPU利用率: {gpu_usage:.1f}%")

        # 清理该任务的阶段开始时间
        del self.task_stage_start_times[task_id]
    
    def record_crawl_time(self, task_id: str, duration: float):
        """记录爬取时间"""
        if task_id in self.task_reports:
            self.task_reports[task_id].crawl_detection_time = duration
            print(f"🔍 爬取检测耗时: {duration:.1f}秒 (任务: {task_id})")

    def record_download_time(self, task_id: str, duration: float):
        """记录下载时间"""
        if task_id in self.task_reports:
            self.task_reports[task_id].download_time = duration
            print(f"📥 视频下载耗时: {duration:.1f}秒 (任务: {task_id})")

    def record_upload_time(self, task_id: str, duration: float):
        """记录上传时间"""
        if task_id in self.task_reports:
            self.task_reports[task_id].upload_time = duration
            print(f"📤 文件上传耗时: {duration:.1f}秒 (任务: {task_id})")

    def record_forum_reply_time(self, task_id: str, duration: float):
        """记录论坛回复时间"""
        if task_id in self.task_reports:
            self.task_reports[task_id].forum_reply_time = duration
            print(f"💬 论坛回复耗时: {duration:.1f}秒 (任务: {task_id})")

    def add_warning(self, task_id: str, message: str):
        """添加警告信息"""
        if task_id in self.task_reports:
            self.task_reports[task_id].warnings.append(message)
            print(f"⚠️ 警告: {message} (任务: {task_id})")

    def add_error(self, task_id: str, message: str):
        """添加错误信息"""
        if task_id in self.task_reports:
            self.task_reports[task_id].error_messages.append(message)
            self.task_reports[task_id].success_rate = 0.0
            print(f"❌ 错误: {message} (任务: {task_id})")
    
    def end_video_processing(self, task_id: str) -> VideoProcessingReport:
        """结束视频处理追踪"""
        if task_id not in self.task_reports:
            print(f"⚠️ 任务 {task_id} 不存在，无法结束处理追踪")
            return None

        current_report = self.task_reports[task_id]

        # 计算总处理时间
        end_time = datetime.now()
        current_report.processing_end_time = end_time.isoformat()

        start_time = datetime.fromisoformat(current_report.processing_start_time)
        total_time = (end_time - start_time).total_seconds()
        current_report.total_processing_time = total_time

        # 计算性能统计
        self._calculate_performance_stats(current_report)

        # 保存报告
        self._save_report(current_report)

        # 生成并显示报告
        self._display_completion_report(current_report)

        # 从任务列表中移除已完成的任务
        report = self.task_reports[task_id]
        del self.task_reports[task_id]

        # 如果没有更多任务，停止性能监控
        if not self.task_reports:
            self.stop_performance_monitoring()

        return report
    
    def start_performance_monitoring(self):
        """开始性能监控"""
        self.monitoring_active = True
        self.performance_samples = []
        
        def monitor():
            while self.monitoring_active:
                try:
                    sample = {
                        'timestamp': time.time(),
                        'cpu_percent': psutil.cpu_percent(),
                        'memory_mb': psutil.virtual_memory().used / 1024 / 1024,
                        'gpu_utilization': self._get_gpu_utilization(),
                        'gpu_memory_mb': self._get_gpu_memory_usage()
                    }
                    self.performance_samples.append(sample)
                    time.sleep(1)  # 每秒采样一次
                except Exception as e:
                    print(f"⚠️ 性能监控采样失败: {e}")
                    time.sleep(1)
        
        self.monitoring_thread = threading.Thread(target=monitor, daemon=True)
        self.monitoring_thread.start()
    
    def stop_performance_monitoring(self):
        """停止性能监控"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2)
    
    def _get_gpu_utilization(self) -> float:
        """获取GPU利用率"""
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                return gpus[0].load * 100
        except Exception:
            pass
        return 0.0
    
    def _get_gpu_memory_usage(self) -> float:
        """获取GPU内存使用量(MB)"""
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                return gpus[0].memoryUsed
        except Exception:
            pass
        return 0.0
    
    def _calculate_performance_stats(self, report: VideoProcessingReport):
        """计算性能统计"""
        if not self.performance_samples:
            # 如果没有性能样本，设置默认值
            report.avg_gpu_utilization = 0.0
            report.avg_cpu_utilization = 0.0
            report.peak_memory_usage_mb = 0.0
        else:
            # 计算平均值和峰值
            gpu_utils = [s['gpu_utilization'] for s in self.performance_samples]
            cpu_utils = [s['cpu_percent'] for s in self.performance_samples]
            memory_usages = [s['memory_mb'] for s in self.performance_samples]

            report.avg_gpu_utilization = sum(gpu_utils) / len(gpu_utils) if gpu_utils else 0.0
            report.avg_cpu_utilization = sum(cpu_utils) / len(cpu_utils) if cpu_utils else 0.0
            report.peak_memory_usage_mb = max(memory_usages) if memory_usages else 0.0

        # 计算处理速度比 - 添加安全检查
        if (report.video_duration_seconds > 0 and
            report.total_processing_time > 0):
            report.processing_speed_ratio = (
                report.video_duration_seconds /
                report.total_processing_time
            )
        else:
            # 如果无法计算，设置为0
            report.processing_speed_ratio = 0.0
            print(f"⚠️ 无法计算处理速度比: 视频时长={report.video_duration_seconds}s, 处理时间={report.total_processing_time}s")
    
    def _format_duration(self, seconds: float) -> str:
        """格式化时长"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def _save_report(self, report: VideoProcessingReport):
        """保存报告到文件"""
        if not report:
            return

        # 创建日期目录
        date_str = datetime.now().strftime("%Y-%m-%d")
        date_dir = os.path.join(self.reports_dir, date_str)
        os.makedirs(date_dir, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{report.original_filename}_{timestamp}"

        # 保存JSON格式
        json_path = os.path.join(date_dir, f"{base_name}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(report), f, ensure_ascii=False, indent=2)

        print(f"💾 性能报告已保存: {json_path}")

    def _display_completion_report(self, report: VideoProcessingReport):
        """显示完成报告"""
        if not report:
            return
        
        print("\n" + "=" * 60)
        print("🎬 视频处理完成报告")
        print("=" * 60)
        print(f"📝 基本信息:")
        print(f"   - 视频文件: {report.original_filename}")
        print(f"   - 文件大小: {report.file_size_mb:.1f} MB")
        print(f"   - 视频时长: {self._format_duration(report.video_duration_seconds)}")
        print(f"   - 处理时间: {report.processing_start_time[:19].replace('T', ' ')}")
        
        print(f"\n⏱️ 详细耗时统计:")
        if report.crawl_detection_time > 0:
            print(f"   - 爬取检测: {report.crawl_detection_time:.1f}秒")
        if report.download_time > 0:
            print(f"   - 视频下载: {report.download_time:.1f}秒")
        
        for stage in report.stage_timings:
            gpu_text = " (GPU加速)" if stage.gpu_accelerated else ""
            print(f"   - {stage.stage_name}: {stage.duration:.1f}秒{gpu_text}")
        
        if report.upload_time > 0:
            print(f"   - 文件上传: {report.upload_time:.1f}秒")
        if report.forum_reply_time > 0:
            print(f"   - 论坛回复: {report.forum_reply_time:.1f}秒")
        
        print(f"\n📊 性能统计:")
        print(f"   - 总处理时间: {self._format_duration(report.total_processing_time)}")
        print(f"   - GPU利用率: 平均{report.avg_gpu_utilization:.1f}%")
        print(f"   - 内存峰值: {report.peak_memory_usage_mb:.1f}MB")
        print(f"   - 处理速度: {report.processing_speed_ratio:.2f}x实时")
        
        # 效率分析
        if report.stage_timings:
            slowest_stage = max(report.stage_timings, key=lambda x: x.duration)
            print(f"\n🎯 效率分析:")
            print(f"   - 最耗时阶段: {slowest_stage.stage_name} - {slowest_stage.duration:.1f}秒")
            
            gpu_stages = [s for s in report.stage_timings if s.gpu_accelerated]
            if gpu_stages:
                avg_gpu_util = sum(s.gpu_utilization for s in gpu_stages) / len(gpu_stages)
                print(f"   - GPU加速效果: 平均利用率{avg_gpu_util:.1f}%")
        
        if report.warnings:
            print(f"\n⚠️ 警告信息:")
            for warning in report.warnings:
                print(f"   - {warning}")
        
        if report.error_messages:
            print(f"\n❌ 错误信息:")
            for error in report.error_messages:
                print(f"   - {error}")
        
        print("=" * 60)


# 全局性能追踪器实例
performance_tracker = PerformanceTracker()
