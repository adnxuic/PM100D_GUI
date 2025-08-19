#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分光路噪声抑制处理器
实现双通道数据处理和噪声抑制
"""

import numpy as np
from typing import Tuple, Dict, List, Optional, Callable
import threading
from enum import Enum
from .lms_filter import LMSFilter, AdaptiveLMSFilter


class NoiseSuppressionMode(Enum):
    """噪声抑制模式"""
    RATIO = "ratio"                  # 比值法
    DIFFERENCE = "difference"        # 差值法
    LMS_ADAPTIVE = "lms_adaptive"    # LMS自适应滤波
    HYBRID = "hybrid"                # 混合方法
    NORMALIZED_RATIO = "norm_ratio"  # 归一化比值法


class ChannelRole(Enum):
    """通道角色定义"""
    MAIN = "main"          # 主信号通道
    REFERENCE = "reference" # 参考信号通道
    MONITOR = "monitor"    # 监控信号通道


class DualPathProcessor:
    """
    分光路噪声抑制处理器
    
    支持多种噪声抑制方法：
    1. 比值法：主信号/参考信号，消除共模噪声
    2. 差值法：主信号-k*参考信号，k为标定系数
    3. LMS自适应滤波：实时自适应噪声抑制
    4. 混合方法：结合多种方法的优势
    """
    
    def __init__(self, suppression_mode: NoiseSuppressionMode = NoiseSuppressionMode.RATIO,
                 buffer_size: int = 1000, enable_auto_calibration: bool = True):
        """
        初始化分光路处理器
        
        参数:
            suppression_mode (NoiseSuppressionMode): 噪声抑制模式
            buffer_size (int): 数据缓存大小
            enable_auto_calibration (bool): 是否启用自动标定
        """
        self.suppression_mode = suppression_mode
        self.buffer_size = buffer_size
        self.enable_auto_calibration = enable_auto_calibration
        
        # 数据缓存
        self.main_buffer = []
        self.reference_buffer = []
        self.output_buffer = []
        self.noise_buffer = []
        
        # 处理参数
        self.calibration_ratio = 1.0      # 标定比值
        self.difference_coefficient = 1.0  # 差值法系数
        self.smoothing_factor = 0.95      # 平滑因子
        
        # LMS滤波器（可选）
        self.lms_filter = None
        if suppression_mode in [NoiseSuppressionMode.LMS_ADAPTIVE, NoiseSuppressionMode.HYBRID]:
            self.lms_filter = AdaptiveLMSFilter(
                initial_filter_length=32,
                initial_step_size=0.01,
                adaptation_interval=50
            )
        
        # 统计信息
        self.sample_count = 0
        self.calibration_samples = 100  # 标定所需样本数
        self.statistics = {
            'snr_improvement': 0.0,
            'noise_reduction_ratio': 0.0,
            'correlation_coefficient': 0.0,
            'signal_stability': 0.0,
            'processing_efficiency': 0.0
        }
        
        # 线程安全
        self._lock = threading.Lock()
        
        # 回调函数
        self.status_callback: Optional[Callable] = None
        self.data_callback: Optional[Callable] = None
        
        print(f"分光路处理器初始化完成: 模式={suppression_mode.value}, 缓存大小={buffer_size}")
    
    def set_callbacks(self, status_callback: Optional[Callable] = None,
                     data_callback: Optional[Callable] = None):
        """
        设置回调函数
        
        参数:
            status_callback: 状态更新回调
            data_callback: 数据输出回调
        """
        self.status_callback = status_callback
        self.data_callback = data_callback
    
    def update_mode(self, new_mode: NoiseSuppressionMode):
        """
        更新噪声抑制模式
        
        参数:
            new_mode (NoiseSuppressionMode): 新的抑制模式
        """
        with self._lock:
            old_mode = self.suppression_mode
            self.suppression_mode = new_mode
            
            # 根据新模式初始化或销毁LMS滤波器
            if new_mode in [NoiseSuppressionMode.LMS_ADAPTIVE, NoiseSuppressionMode.HYBRID]:
                if self.lms_filter is None:
                    self.lms_filter = AdaptiveLMSFilter()
                    print("已创建LMS滤波器")
            else:
                if self.lms_filter is not None:
                    self.lms_filter = None
                    print("已释放LMS滤波器")
            
            print(f"噪声抑制模式已更改: {old_mode.value} → {new_mode.value}")
            
            if self.status_callback:
                self.status_callback(f"模式已切换至: {new_mode.value}")
    
    def calibrate(self, main_samples: List[float], reference_samples: List[float]) -> bool:
        """
        使用标定数据进行系统标定
        
        参数:
            main_samples (List[float]): 主信号标定数据
            reference_samples (List[float]): 参考信号标定数据
        
        返回:
            bool: 标定是否成功
        """
        if len(main_samples) != len(reference_samples) or len(main_samples) < 10:
            print("标定失败: 数据不足或长度不匹配")
            return False
        
        try:
            with self._lock:
                main_array = np.array(main_samples)
                ref_array = np.array(reference_samples)
                
                # 计算标定比值（比值法）
                valid_indices = ref_array != 0
                if np.sum(valid_indices) > len(ref_array) // 2:
                    ratios = main_array[valid_indices] / ref_array[valid_indices]
                    self.calibration_ratio = np.median(ratios)  # 使用中位数避免异常值
                else:
                    self.calibration_ratio = np.mean(main_array) / np.mean(ref_array)
                
                # 计算差值法系数（最小二乘法）
                correlation_matrix = np.corrcoef(main_array, ref_array)
                if correlation_matrix.shape == (2, 2):
                    correlation_coeff = correlation_matrix[0, 1]
                    if abs(correlation_coeff) > 0.1:  # 确保相关性足够
                        self.difference_coefficient = (np.std(main_array) / np.std(ref_array)) * correlation_coeff
                    else:
                        self.difference_coefficient = 1.0
                
                # 更新统计信息
                self.statistics['correlation_coefficient'] = abs(correlation_coeff) if 'correlation_coeff' in locals() else 0.0
                
                print(f"标定完成: 比值={self.calibration_ratio:.4f}, 差值系数={self.difference_coefficient:.4f}")
                print(f"相关系数: {self.statistics['correlation_coefficient']:.3f}")
                
                if self.status_callback:
                    self.status_callback(f"标定完成，相关性: {self.statistics['correlation_coefficient']:.3f}")
                
                return True
                
        except Exception as e:
            print(f"标定过程出错: {e}")
            return False
    
    def process_sample(self, main_signal: float, reference_signal: float) -> Tuple[float, Dict]:
        """
        处理单个信号样本
        
        参数:
            main_signal (float): 主信号值
            reference_signal (float): 参考信号值
        
        返回:
            Tuple[float, Dict]: (处理后信号, 处理信息)
        """
        with self._lock:
            self.sample_count += 1
            
            # 添加到缓存
            self.main_buffer.append(main_signal)
            self.reference_buffer.append(reference_signal)
            
            # 维护缓存大小
            if len(self.main_buffer) > self.buffer_size:
                self.main_buffer.pop(0)
                self.reference_buffer.pop(0)
            
            # 如果启用自动标定且样本足够
            if (self.enable_auto_calibration and 
                len(self.main_buffer) == self.calibration_samples and
                self.sample_count == self.calibration_samples):
                self.calibrate(self.main_buffer, self.reference_buffer)
            
            # 根据模式处理信号
            processed_signal, processing_info = self._process_by_mode(main_signal, reference_signal)
            
            # 更新统计信息
            self._update_statistics(main_signal, reference_signal, processed_signal)
            
            # 记录输出
            self.output_buffer.append(processed_signal)
            if len(self.output_buffer) > self.buffer_size:
                self.output_buffer.pop(0)
            
            # 调用数据回调
            if self.data_callback:
                self.data_callback(processed_signal, processing_info)
            
            return processed_signal, processing_info
    
    def _process_by_mode(self, main_signal: float, reference_signal: float) -> Tuple[float, Dict]:
        """
        根据当前模式处理信号
        """
        processing_info = {
            'mode': self.suppression_mode.value,
            'noise_estimate': 0.0,
            'suppression_gain': 0.0,
            'snr_improvement': 0.0
        }
        
        if self.suppression_mode == NoiseSuppressionMode.RATIO:
            # 比值法
            if abs(reference_signal) > 1e-12:  # 避免除零
                processed_signal = main_signal / reference_signal * self.calibration_ratio
                noise_estimate = main_signal - processed_signal
            else:
                processed_signal = main_signal
                noise_estimate = 0.0
        
        elif self.suppression_mode == NoiseSuppressionMode.NORMALIZED_RATIO:
            # 归一化比值法
            if len(self.reference_buffer) > 10:
                ref_mean = np.mean(self.reference_buffer[-10:])
                main_mean = np.mean(self.main_buffer[-10:])
                if abs(ref_mean) > 1e-12 and abs(main_mean) > 1e-12:
                    normalized_ref = reference_signal / ref_mean
                    normalized_main = main_signal / main_mean
                    ratio = normalized_main / normalized_ref if abs(normalized_ref) > 1e-12 else 1.0
                    processed_signal = main_signal / ratio
                else:
                    processed_signal = main_signal
            else:
                processed_signal = main_signal
            noise_estimate = main_signal - processed_signal
        
        elif self.suppression_mode == NoiseSuppressionMode.DIFFERENCE:
            # 差值法
            noise_estimate = self.difference_coefficient * reference_signal
            processed_signal = main_signal - noise_estimate
        
        elif self.suppression_mode == NoiseSuppressionMode.LMS_ADAPTIVE:
            # LMS自适应滤波
            if self.lms_filter is not None:
                processed_signal, noise_estimate = self.lms_filter.filter_sample(main_signal, reference_signal)
                # 获取LMS性能指标
                lms_metrics = self.lms_filter.get_adaptive_metrics()
                processing_info.update({
                    'lms_converged': lms_metrics['is_converged'],
                    'lms_stability': lms_metrics['stability_index'],
                    'lms_noise_reduction': lms_metrics['noise_reduction_db']
                })
            else:
                processed_signal = main_signal
                noise_estimate = 0.0
        
        elif self.suppression_mode == NoiseSuppressionMode.HYBRID:
            # 混合方法：结合比值法和LMS
            # 首先应用比值法
            if abs(reference_signal) > 1e-12:
                ratio_result = main_signal / reference_signal * self.calibration_ratio
            else:
                ratio_result = main_signal
            
            # 然后应用LMS滤波
            if self.lms_filter is not None:
                processed_signal, lms_noise = self.lms_filter.filter_sample(ratio_result, reference_signal)
                noise_estimate = main_signal - processed_signal
            else:
                processed_signal = ratio_result
                noise_estimate = main_signal - ratio_result
        
        else:
            # 默认：无处理
            processed_signal = main_signal
            noise_estimate = 0.0
        
        # 应用平滑滤波
        if len(self.output_buffer) > 0:
            processed_signal = (self.smoothing_factor * self.output_buffer[-1] + 
                              (1 - self.smoothing_factor) * processed_signal)
        
        # 计算抑制增益
        if abs(main_signal) > 1e-12:
            processing_info['suppression_gain'] = abs(noise_estimate) / abs(main_signal)
        
        processing_info['noise_estimate'] = noise_estimate
        self.noise_buffer.append(noise_estimate)
        if len(self.noise_buffer) > self.buffer_size:
            self.noise_buffer.pop(0)
        
        return processed_signal, processing_info
    
    def _update_statistics(self, main_signal: float, reference_signal: float, processed_signal: float):
        """更新统计信息"""
        if len(self.main_buffer) < 10:
            return
        
        # 计算最近样本的统计
        recent_main = self.main_buffer[-10:]
        recent_processed = self.output_buffer[-9:] + [processed_signal]  # 包含当前处理结果
        recent_noise = self.noise_buffer[-9:] + [main_signal - processed_signal]
        
        # 计算SNR改善
        main_std = np.std(recent_main)
        processed_std = np.std(recent_processed)
        if main_std > 0 and processed_std > 0:
            snr_improvement = 20 * np.log10(main_std / processed_std)
            self.statistics['snr_improvement'] = max(0, snr_improvement)
        
        # 计算噪声抑制比
        noise_power = np.mean(np.array(recent_noise) ** 2)
        signal_power = np.mean(np.array(recent_processed) ** 2)
        if signal_power > 0:
            self.statistics['noise_reduction_ratio'] = noise_power / (signal_power + noise_power)
        
        # 计算信号稳定性（变异系数的倒数）
        if processed_std > 0:
            processed_mean = np.mean(recent_processed)
            cv = processed_std / abs(processed_mean) if abs(processed_mean) > 0 else float('inf')
            self.statistics['signal_stability'] = 1.0 / (1.0 + cv)
        
        # 更新相关系数
        if len(self.main_buffer) >= 20 and len(self.reference_buffer) >= 20:
            correlation_matrix = np.corrcoef(self.main_buffer[-20:], self.reference_buffer[-20:])
            if correlation_matrix.shape == (2, 2):
                self.statistics['correlation_coefficient'] = abs(correlation_matrix[0, 1])
    
    def get_performance_summary(self) -> Dict:
        """
        获取性能总结
        
        返回:
            Dict: 性能指标字典
        """
        with self._lock:
            summary = {
                'mode': self.suppression_mode.value,
                'sample_count': self.sample_count,
                'calibration_ratio': self.calibration_ratio,
                'difference_coefficient': self.difference_coefficient,
                'buffer_utilization': len(self.main_buffer) / self.buffer_size,
                **self.statistics
            }
            
            # 添加LMS滤波器指标（如果存在）
            if self.lms_filter is not None:
                lms_metrics = self.lms_filter.get_performance_metrics()
                summary['lms_metrics'] = lms_metrics
            
            return summary
    
    def reset(self):
        """重置处理器状态"""
        with self._lock:
            self.main_buffer.clear()
            self.reference_buffer.clear()
            self.output_buffer.clear()
            self.noise_buffer.clear()
            
            self.sample_count = 0
            self.calibration_ratio = 1.0
            self.difference_coefficient = 1.0
            
            # 重置统计信息
            for key in self.statistics:
                self.statistics[key] = 0.0
            
            # 重置LMS滤波器
            if self.lms_filter is not None:
                self.lms_filter.reset()
            
            print("分光路处理器已重置")
            
            if self.status_callback:
                self.status_callback("处理器已重置")
    
    def export_data(self) -> Dict:
        """
        导出处理数据
        
        返回:
            Dict: 包含原始数据和处理结果的字典
        """
        with self._lock:
            return {
                'main_signals': self.main_buffer.copy(),
                'reference_signals': self.reference_buffer.copy(),
                'processed_signals': self.output_buffer.copy(),
                'noise_estimates': self.noise_buffer.copy(),
                'statistics': self.statistics.copy(),
                'parameters': {
                    'mode': self.suppression_mode.value,
                    'calibration_ratio': self.calibration_ratio,
                    'difference_coefficient': self.difference_coefficient,
                    'smoothing_factor': self.smoothing_factor
                }
            }
    
    def get_real_time_status(self) -> str:
        """
        获取实时状态字符串
        
        返回:
            str: 状态描述
        """
        summary = self.get_performance_summary()
        
        status_parts = [
            f"模式: {summary['mode']}",
            f"样本数: {summary['sample_count']}",
            f"SNR改善: {summary['snr_improvement']:.1f}dB",
            f"相关性: {summary['correlation_coefficient']:.3f}",
            f"稳定性: {summary['signal_stability']:.3f}"
        ]
        
        if self.lms_filter and 'lms_metrics' in summary:
            lms = summary['lms_metrics']
            status_parts.append(f"LMS: {'收敛' if lms['is_converged'] else '收敛中'}")
        
        return " | ".join(status_parts)


class MultiChannelProcessor:
    """
    多通道处理器
    
    支持多个PM100D设备的协同噪声抑制
    可以处理多主信号-多参考信号的复杂场景
    """
    
    def __init__(self):
        """初始化多通道处理器"""
        self.processors: Dict[str, DualPathProcessor] = {}
        self.channel_roles: Dict[str, ChannelRole] = {}
        self.processing_graph: Dict[str, List[str]] = {}  # 处理图：主信号 -> 参考信号列表
        
        self._lock = threading.Lock()
        
        print("多通道处理器初始化完成")
    
    def add_channel(self, channel_id: str, role: ChannelRole, 
                   suppression_mode: NoiseSuppressionMode = NoiseSuppressionMode.RATIO):
        """
        添加处理通道
        
        参数:
            channel_id (str): 通道标识
            role (ChannelRole): 通道角色
            suppression_mode (NoiseSuppressionMode): 噪声抑制模式
        """
        with self._lock:
            if channel_id not in self.processors:
                self.processors[channel_id] = DualPathProcessor(suppression_mode)
                self.channel_roles[channel_id] = role
                print(f"已添加通道: {channel_id}, 角色: {role.value}")
    
    def setup_processing_pair(self, main_channel: str, reference_channel: str):
        """
        设置处理对：主信号通道和参考信号通道
        
        参数:
            main_channel (str): 主信号通道ID
            reference_channel (str): 参考信号通道ID
        """
        with self._lock:
            if main_channel not in self.processing_graph:
                self.processing_graph[main_channel] = []
            
            if reference_channel not in self.processing_graph[main_channel]:
                self.processing_graph[main_channel].append(reference_channel)
                print(f"已设置处理对: {main_channel} -> {reference_channel}")
    
    def process_multi_sample(self, channel_data: Dict[str, float]) -> Dict[str, float]:
        """
        处理多通道样本数据
        
        参数:
            channel_data (Dict[str, float]): 通道ID -> 信号值的字典
        
        返回:
            Dict[str, float]: 处理后的信号数据
        """
        processed_data = {}
        
        with self._lock:
            for main_channel, ref_channels in self.processing_graph.items():
                if main_channel in channel_data and main_channel in self.processors:
                    main_signal = channel_data[main_channel]
                    
                    # 如果有参考信号，使用第一个进行处理
                    if ref_channels and ref_channels[0] in channel_data:
                        reference_signal = channel_data[ref_channels[0]]
                        processed_signal, _ = self.processors[main_channel].process_sample(
                            main_signal, reference_signal)
                    else:
                        processed_signal = main_signal  # 无参考信号时直接输出
                    
                    processed_data[main_channel] = processed_signal
            
            # 对于没有配置处理对的通道，直接输出
            for channel_id, value in channel_data.items():
                if channel_id not in processed_data:
                    processed_data[channel_id] = value
        
        return processed_data
    
    def get_all_performance_summaries(self) -> Dict[str, Dict]:
        """获取所有通道的性能总结"""
        with self._lock:
            summaries = {}
            for channel_id, processor in self.processors.items():
                summaries[channel_id] = processor.get_performance_summary()
            return summaries
