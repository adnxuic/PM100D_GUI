#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LMS自适应滤波器实现
用于降低激光源光强抖动噪声
"""

import numpy as np
from typing import Tuple, Optional
import threading


class LMSFilter:
    """
    最小均方(LMS)自适应滤波器
    
    用于实时噪声抑制，特别适用于激光功率测量中的光强抖动噪声
    通过参考信号和主信号的自适应处理，实现噪声的有效抑制
    """
    
    def __init__(self, filter_length: int = 32, step_size: float = 0.01, 
                 leakage: float = 0.999):
        """
        初始化LMS滤波器
        
        参数:
            filter_length (int): 滤波器长度（抽头数）
            step_size (float): 学习率/步长参数 (0 < μ < 1)
            leakage (float): 泄漏因子，防止滤波器发散 (0 < λ ≤ 1)
        """
        self.filter_length = filter_length
        self.step_size = step_size
        self.leakage = leakage
        
        # 初始化滤波器权重
        self.weights = np.zeros(filter_length)
        
        # 输入信号缓存（参考信号）
        self.reference_buffer = np.zeros(filter_length)
        
        # 性能统计
        self.adaptation_history = []  # 自适应过程历史
        self.error_power_history = []  # 误差功率历史
        self.convergence_factor = 0.95  # 收敛判定因子
        
        # 线程安全锁
        self._lock = threading.Lock()
        
        # 统计信息
        self.sample_count = 0
        self.total_error_power = 0.0
        self.noise_reduction_db = 0.0
        
        print(f"LMS滤波器初始化完成: 长度={filter_length}, 步长={step_size}, 泄漏因子={leakage}")
    
    def update_parameters(self, step_size: Optional[float] = None, 
                         leakage: Optional[float] = None):
        """
        更新滤波器参数
        
        参数:
            step_size (float, optional): 新的学习率
            leakage (float, optional): 新的泄漏因子
        """
        with self._lock:
            if step_size is not None:
                self.step_size = max(0.001, min(0.1, step_size))
                print(f"更新LMS步长: {self.step_size}")
            
            if leakage is not None:
                self.leakage = max(0.9, min(1.0, leakage))
                print(f"更新泄漏因子: {self.leakage}")
    
    def reset(self):
        """重置滤波器状态"""
        with self._lock:
            self.weights = np.zeros(self.filter_length)
            self.reference_buffer = np.zeros(self.filter_length)
            self.adaptation_history.clear()
            self.error_power_history.clear()
            self.sample_count = 0
            self.total_error_power = 0.0
            self.noise_reduction_db = 0.0
            print("LMS滤波器已重置")
    
    def filter_sample(self, main_signal: float, reference_signal: float) -> Tuple[float, float]:
        """
        处理单个信号样本
        
        参数:
            main_signal (float): 主信号（待去噪的信号）
            reference_signal (float): 参考信号（噪声相关信号）
        
        返回:
            Tuple[float, float]: (滤波后信号, 误差信号)
        """
        with self._lock:
            # 更新参考信号缓存
            self.reference_buffer = np.roll(self.reference_buffer, 1)
            self.reference_buffer[0] = reference_signal
            
            # 计算滤波器输出（噪声估计）
            noise_estimate = np.dot(self.weights, self.reference_buffer)
            
            # 计算误差信号（滤波后的主信号）
            error_signal = main_signal - noise_estimate
            
            # 更新滤波器权重（LMS算法）
            self.weights = self.leakage * self.weights + \
                          self.step_size * error_signal * self.reference_buffer
            
            # 统计信息更新
            self.sample_count += 1
            error_power = error_signal ** 2
            self.total_error_power += error_power
            
            # 记录适应过程
            if self.sample_count % 10 == 0:  # 每10个样本记录一次
                avg_error_power = self.total_error_power / self.sample_count
                self.error_power_history.append(avg_error_power)
                
                # 计算噪声抑制效果
                if len(self.error_power_history) > 10:
                    initial_power = np.mean(self.error_power_history[:10])
                    current_power = avg_error_power
                    if current_power > 0 and initial_power > 0:
                        self.noise_reduction_db = 10 * np.log10(initial_power / current_power)
                        self.noise_reduction_db = max(0, self.noise_reduction_db)  # 确保非负
            
            return error_signal, noise_estimate
    
    def batch_filter(self, main_signals: np.ndarray, 
                    reference_signals: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        批处理信号滤波
        
        参数:
            main_signals (np.ndarray): 主信号数组
            reference_signals (np.ndarray): 参考信号数组
        
        返回:
            Tuple[np.ndarray, np.ndarray]: (滤波后信号数组, 噪声估计数组)
        """
        if len(main_signals) != len(reference_signals):
            raise ValueError("主信号和参考信号长度必须相等")
        
        filtered_signals = np.zeros_like(main_signals)
        noise_estimates = np.zeros_like(main_signals)
        
        for i, (main, ref) in enumerate(zip(main_signals, reference_signals)):
            filtered_signals[i], noise_estimates[i] = self.filter_sample(main, ref)
        
        return filtered_signals, noise_estimates
    
    def get_filter_response(self) -> np.ndarray:
        """
        获取滤波器频率响应（用于调试和监控）
        
        返回:
            np.ndarray: 滤波器权重向量
        """
        with self._lock:
            return self.weights.copy()
    
    def get_performance_metrics(self) -> dict:
        """
        获取滤波器性能指标
        
        返回:
            dict: 性能指标字典
        """
        with self._lock:
            avg_error_power = self.total_error_power / max(1, self.sample_count)
            
            # 计算收敛状态
            is_converged = False
            if len(self.error_power_history) >= 20:
                recent_variance = np.var(self.error_power_history[-20:])
                is_converged = recent_variance < avg_error_power * 0.01
            
            # 计算权重能量（稳定性指标）
            weight_energy = np.sum(self.weights ** 2)
            
            return {
                'sample_count': self.sample_count,
                'average_error_power': avg_error_power,
                'noise_reduction_db': self.noise_reduction_db,
                'is_converged': is_converged,
                'weight_energy': weight_energy,
                'step_size': self.step_size,
                'leakage_factor': self.leakage,
                'filter_length': self.filter_length,
                'max_weight': np.max(np.abs(self.weights)),
                'stability_index': 1.0 / (1.0 + weight_energy)  # 稳定性指数
            }
    
    def is_stable(self) -> bool:
        """
        检查滤波器是否稳定
        
        返回:
            bool: True表示稳定
        """
        with self._lock:
            # 检查权重是否发散
            max_weight = np.max(np.abs(self.weights))
            weight_energy = np.sum(self.weights ** 2)
            
            # 稳定性判据
            is_weight_bounded = max_weight < 10.0  # 权重幅值限制
            is_energy_bounded = weight_energy < 100.0  # 权重能量限制
            
            return is_weight_bounded and is_energy_bounded
    
    def auto_adjust_parameters(self):
        """
        自动调整滤波器参数以优化性能
        """
        with self._lock:
            if self.sample_count < 100:
                return  # 样本太少，不进行调整
            
            metrics = self.get_performance_metrics()
            
            # 如果滤波器不稳定，减小步长
            if not self.is_stable():
                self.step_size *= 0.8
                print(f"检测到不稳定，降低步长至: {self.step_size:.4f}")
            
            # 如果收敛太慢，适当增加步长
            elif len(self.error_power_history) > 50:
                recent_improvement = (self.error_power_history[-50] - 
                                    self.error_power_history[-1]) / self.error_power_history[-50]
                if recent_improvement < 0.1:  # 改善不足10%
                    self.step_size = min(0.05, self.step_size * 1.1)
                    print(f"收敛较慢，增加步长至: {self.step_size:.4f}")
    
    def __str__(self) -> str:
        """字符串表示"""
        metrics = self.get_performance_metrics()
        return (f"LMS滤波器状态:\n"
                f"  样本数: {metrics['sample_count']}\n"
                f"  噪声抑制: {metrics['noise_reduction_db']:.2f} dB\n"
                f"  收敛状态: {'已收敛' if metrics['is_converged'] else '收敛中'}\n"
                f"  稳定性: {'稳定' if self.is_stable() else '不稳定'}")


class AdaptiveLMSFilter(LMSFilter):
    """
    自适应LMS滤波器
    
    在基本LMS滤波器基础上增加自适应功能：
    - 自动调整学习率
    - 自适应滤波器长度
    - 智能噪声检测
    """
    
    def __init__(self, initial_filter_length: int = 32, 
                 initial_step_size: float = 0.01,
                 adaptation_interval: int = 100):
        """
        初始化自适应LMS滤波器
        
        参数:
            initial_filter_length (int): 初始滤波器长度
            initial_step_size (float): 初始学习率
            adaptation_interval (int): 参数自适应间隔（样本数）
        """
        super().__init__(initial_filter_length, initial_step_size)
        
        self.adaptation_interval = adaptation_interval
        self.last_adaptation_sample = 0
        
        # 性能监控
        self.performance_window = []
        self.window_size = 50
        
        print(f"自适应LMS滤波器初始化完成，自适应间隔: {adaptation_interval}")
    
    def filter_sample(self, main_signal: float, reference_signal: float) -> Tuple[float, float]:
        """
        自适应滤波处理
        """
        # 执行标准LMS滤波
        filtered_signal, noise_estimate = super().filter_sample(main_signal, reference_signal)
        
        # 记录性能
        self.performance_window.append(abs(filtered_signal))
        if len(self.performance_window) > self.window_size:
            self.performance_window.pop(0)
        
        # 定期执行参数自适应
        if (self.sample_count - self.last_adaptation_sample) >= self.adaptation_interval:
            self.auto_adjust_parameters()
            self.last_adaptation_sample = self.sample_count
        
        return filtered_signal, noise_estimate
    
    def get_adaptive_metrics(self) -> dict:
        """
        获取自适应相关的性能指标
        """
        base_metrics = self.get_performance_metrics()
        
        # 计算信号变异系数
        if len(self.performance_window) > 10:
            signal_mean = np.mean(self.performance_window)
            signal_std = np.std(self.performance_window)
            coefficient_of_variation = signal_std / signal_mean if signal_mean > 0 else 0
        else:
            coefficient_of_variation = 0
        
        adaptive_metrics = {
            'adaptation_interval': self.adaptation_interval,
            'samples_since_adaptation': self.sample_count - self.last_adaptation_sample,
            'coefficient_of_variation': coefficient_of_variation,
            'performance_window_size': len(self.performance_window),
        }
        
        return {**base_metrics, **adaptive_metrics}
