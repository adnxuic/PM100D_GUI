#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据可视化组件 - 支持噪声滤波对比显示
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QComboBox
from PySide6.QtCore import Qt, Signal
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.font_manager as fm
import matplotlib.patches as patches
import platform
import numpy as np

# 配置matplotlib中文字体
def setup_chinese_font():
    """设置matplotlib中文字体支持"""
    system = platform.system()
    
    if system == "Windows":
        # Windows系统常见中文字体
        fonts = ['SimHei', 'Microsoft YaHei', 'SimSun', 'KaiTi']
    elif system == "Darwin":  # macOS
        fonts = ['Hiragino Sans GB', 'STHeiti', 'Arial Unicode MS']
    else:  # Linux
        fonts = ['WenQuanYi Micro Hei', 'DejaVu Sans', 'Liberation Sans']
    
    # 尝试设置第一个可用的字体
    for font in fonts:
        try:
            if any(font in f.name for f in fm.fontManager.ttflist):
                plt.rcParams['font.sans-serif'] = [font]
                plt.rcParams['axes.unicode_minus'] = False  # 正确显示负号
                print(f"已设置matplotlib字体为: {font}")
                return
        except Exception:
            continue
    
    # 如果都不可用，设置为不显示警告
    import warnings
    warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib.font_manager')

# 初始化字体设置
setup_chinese_font()


class PlotWidget(QWidget):
    """数据绘图组件 - 支持噪声滤波对比显示"""
    
    # 信号定义
    view_mode_changed = Signal(str)  # 视图模式改变信号
    
    def __init__(self):
        super().__init__()
        
        # 显示模式
        self.view_mode = "raw"  # raw, filtered, comparison, snr
        self.show_noise_estimate = False
        self.show_statistics = True
        
        # 数据存储扩展
        self.time_data = []
        self.power_data = {}          # 原始功率数据
        self.filtered_data = {}       # 滤波后数据
        self.noise_data = {}          # 噪声估计数据
        self.snr_data = {}            # SNR数据
        self.processing_info = {}     # 处理信息
        
        # 统计信息
        self.statistics = {}
        
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        main_layout = QVBoxLayout(self)
        
        # 控制面板
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)
        
        # 创建matplotlib图形
        self.figure = Figure(figsize=(12, 8), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        
        # 根据显示模式创建子图
        self.create_subplots()
        
        main_layout.addWidget(self.canvas)
        
    def create_control_panel(self):
        """创建控制面板"""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        
        # 视图模式选择
        layout.addWidget(QLabel("显示模式:"))
        self.view_combo = QComboBox()
        self.view_combo.addItems([
            "原始数据", "滤波数据", "对比显示", "SNR分析"
        ])
        self.view_combo.currentTextChanged.connect(self.on_view_mode_changed)
        layout.addWidget(self.view_combo)
        
        # 噪声估计显示
        self.noise_checkbox = QCheckBox("显示噪声估计")
        self.noise_checkbox.toggled.connect(self.on_noise_display_toggled)
        layout.addWidget(self.noise_checkbox)
        
        # 统计信息显示
        self.stats_checkbox = QCheckBox("显示统计信息")
        self.stats_checkbox.setChecked(True)
        self.stats_checkbox.toggled.connect(self.on_stats_display_toggled)
        layout.addWidget(self.stats_checkbox)
        
        # 清除数据按钮
        clear_btn = QPushButton("清除绘图")
        clear_btn.clicked.connect(self.clear_all_data)
        layout.addWidget(clear_btn)
        
        # 导出图片按钮
        export_btn = QPushButton("导出图片")
        export_btn.clicked.connect(self.export_plot)
        layout.addWidget(export_btn)
        
        layout.addStretch()  # 添加弹性空间
        
        return panel
        
    def create_subplots(self):
        """根据显示模式创建子图"""
        self.figure.clear()
        
        if self.view_mode == "raw":
            # 单子图显示原始数据
            self.ax_main = self.figure.add_subplot(111)
            self.setup_axis(self.ax_main, "PM100D 原始功率监测", "时间 (s)", "功率 (W)")
            
        elif self.view_mode == "filtered":
            # 单子图显示滤波数据
            self.ax_main = self.figure.add_subplot(111)
            self.setup_axis(self.ax_main, "PM100D 滤波后功率监测", "时间 (s)", "功率 (W)")
            
        elif self.view_mode == "comparison":
            # 双子图对比显示
            self.ax_main = self.figure.add_subplot(211)
            self.ax_filtered = self.figure.add_subplot(212, sharex=self.ax_main)
            
            self.setup_axis(self.ax_main, "原始信号", "时间 (s)", "功率 (W)")
            self.setup_axis(self.ax_filtered, "滤波后信号", "时间 (s)", "功率 (W)")
            
        elif self.view_mode == "snr":
            # 三子图：原始、滤波、SNR
            self.ax_main = self.figure.add_subplot(311)
            self.ax_filtered = self.figure.add_subplot(312, sharex=self.ax_main)
            self.ax_snr = self.figure.add_subplot(313, sharex=self.ax_main)
            
            self.setup_axis(self.ax_main, "原始信号", "", "功率 (W)")
            self.setup_axis(self.ax_filtered, "滤波信号", "", "功率 (W)")
            self.setup_axis(self.ax_snr, "SNR改善", "时间 (s)", "dB")
        
        self.figure.tight_layout()
    
    def setup_axis(self, ax, title, xlabel, ylabel):
        """设置坐标轴"""
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        
    def on_view_mode_changed(self, mode_text):
        """视图模式改变处理"""
        mode_map = {
            "原始数据": "raw",
            "滤波数据": "filtered", 
            "对比显示": "comparison",
            "SNR分析": "snr"
        }
        
        self.view_mode = mode_map.get(mode_text, "raw")
        self.create_subplots()
        self.update_plot()
        
        self.view_mode_changed.emit(self.view_mode)
        
    def on_noise_display_toggled(self, checked):
        """噪声显示切换"""
        self.show_noise_estimate = checked
        self.update_plot()
        
    def on_stats_display_toggled(self, checked):
        """统计信息显示切换"""
        self.show_statistics = checked
        self.update_plot()
        
    def add_device_data(self, device_id, time_point, power_value, filtered_value=None, 
                       noise_estimate=None, processing_info=None):
        """
        添加设备数据点（扩展支持滤波数据）
        
        参数:
            device_id (str): 设备ID
            time_point (float): 时间点
            power_value (float): 原始功率值
            filtered_value (float, optional): 滤波后功率值
            noise_estimate (float, optional): 噪声估计值
            processing_info (dict, optional): 处理信息
        """
        print(f"PlotWidget: 接收数据 - 设备={device_id}, 时间={time_point}, 原始={power_value:.6e}")
        
        # 初始化设备数据存储
        if device_id not in self.power_data:
            self.power_data[device_id] = []
            self.filtered_data[device_id] = []
            self.noise_data[device_id] = []
            self.snr_data[device_id] = []
            self.processing_info[device_id] = []
            print(f"PlotWidget: 为设备 {device_id} 创建新的数据存储")
        
        # 确保时间数据同步
        if len(self.time_data) <= len(self.power_data[device_id]):
            self.time_data.append(time_point)
        
        # 添加原始数据
        self.power_data[device_id].append(power_value)
        
        # 添加滤波数据
        if filtered_value is not None:
            self.filtered_data[device_id].append(filtered_value)
            print(f"PlotWidget: 滤波值={filtered_value:.6e}")
        else:
            self.filtered_data[device_id].append(power_value)  # 无滤波时使用原始值
        
        # 添加噪声估计
        if noise_estimate is not None:
            self.noise_data[device_id].append(noise_estimate)
        else:
            self.noise_data[device_id].append(0.0)
        
        # 计算并添加SNR数据
        snr_value = self.calculate_snr_improvement(device_id)
        self.snr_data[device_id].append(snr_value)
        
        # 保存处理信息
        if processing_info is not None:
            self.processing_info[device_id].append(processing_info)
        else:
            self.processing_info[device_id].append({})
        
        # 更新统计信息
        self.update_device_statistics(device_id)
        
        # 更新图形
        self.update_plot()
        
    def calculate_snr_improvement(self, device_id, window_size=20):
        """
        计算SNR改善
        
        参数:
            device_id (str): 设备ID
            window_size (int): 计算窗口大小
        
        返回:
            float: SNR改善值 (dB)
        """
        if (len(self.power_data[device_id]) < window_size or 
            len(self.filtered_data[device_id]) < window_size):
            return 0.0
        
        try:
            # 计算最近窗口的标准差
            raw_recent = np.array(self.power_data[device_id][-window_size:])
            filtered_recent = np.array(self.filtered_data[device_id][-window_size:])
            
            raw_std = np.std(raw_recent)
            filtered_std = np.std(filtered_recent)
            
            if raw_std > 0 and filtered_std > 0:
                snr_improvement = 20 * np.log10(raw_std / filtered_std)
                return max(0, snr_improvement)  # 确保非负
            else:
                return 0.0
                
        except Exception as e:
            print(f"计算SNR改善失败: {e}")
            return 0.0
    
    def update_device_statistics(self, device_id):
        """
        更新设备统计信息
        
        参数:
            device_id (str): 设备ID
        """
        if device_id not in self.statistics:
            self.statistics[device_id] = {}
        
        if len(self.power_data[device_id]) < 10:
            return
        
        try:
            # 计算基本统计
            raw_data = np.array(self.power_data[device_id][-50:])  # 最近50个点
            filtered_data = np.array(self.filtered_data[device_id][-50:])
            
            self.statistics[device_id] = {
                'raw_mean': np.mean(raw_data),
                'raw_std': np.std(raw_data),
                'filtered_mean': np.mean(filtered_data),
                'filtered_std': np.std(filtered_data),
                'noise_reduction_ratio': 1 - (np.std(filtered_data) / np.std(raw_data)) if np.std(raw_data) > 0 else 0,
                'snr_improvement': self.snr_data[device_id][-1] if self.snr_data[device_id] else 0,
                'sample_count': len(self.power_data[device_id])
            }
            
        except Exception as e:
            print(f"更新统计信息失败: {e}")
        
    def update_plot(self):
        """更新图形显示（根据显示模式）"""
        if not hasattr(self, 'ax_main'):
            return
        
        # 清除所有子图
        if hasattr(self, 'ax_main'):
            self.ax_main.clear()
        if hasattr(self, 'ax_filtered'):
            self.ax_filtered.clear()
        if hasattr(self, 'ax_snr'):
            self.ax_snr.clear()
        
        # 根据视图模式绘制
        if self.view_mode == "raw":
            self.plot_raw_data()
        elif self.view_mode == "filtered":
            self.plot_filtered_data()
        elif self.view_mode == "comparison":
            self.plot_comparison_data()
        elif self.view_mode == "snr":
            self.plot_snr_analysis()
        
        # 添加统计信息文本
        if self.show_statistics:
            self.add_statistics_text()
        
        # 刷新画布
        self.canvas.draw()
    
    def plot_raw_data(self):
        """绘制原始数据"""
        self.setup_axis(self.ax_main, "PM100D 原始功率监测", "时间 (s)", "功率 (W)")
        
        for device_id, power_values in self.power_data.items():
            if power_values and len(power_values) <= len(self.time_data):
                time_subset = self.time_data[:len(power_values)]
                self.ax_main.plot(time_subset, power_values, 
                                marker='o', markersize=2, alpha=0.7,
                                label=f"{device_id} (原始)", linewidth=1.5)
                
                # 可选显示噪声估计
                if self.show_noise_estimate and device_id in self.noise_data:
                    noise_values = self.noise_data[device_id][:len(time_subset)]
                    self.ax_main.plot(time_subset, noise_values,
                                    '--', alpha=0.5, linewidth=1,
                                    label=f"{device_id} (噪声估计)")
        
        if self.power_data:
            self.ax_main.legend()
    
    def plot_filtered_data(self):
        """绘制滤波数据"""
        self.setup_axis(self.ax_main, "PM100D 滤波后功率监测", "时间 (s)", "功率 (W)")
        
        for device_id, filtered_values in self.filtered_data.items():
            if filtered_values and len(filtered_values) <= len(self.time_data):
                time_subset = self.time_data[:len(filtered_values)]
                self.ax_main.plot(time_subset, filtered_values,
                                marker='s', markersize=2, alpha=0.8,
                                label=f"{device_id} (滤波)", linewidth=1.5)
        
        if self.filtered_data:
            self.ax_main.legend()
    
    def plot_comparison_data(self):
        """绘制对比数据"""
        # 原始信号子图
        self.setup_axis(self.ax_main, "原始信号", "", "功率 (W)")
        for device_id, power_values in self.power_data.items():
            if power_values and len(power_values) <= len(self.time_data):
                time_subset = self.time_data[:len(power_values)]
                self.ax_main.plot(time_subset, power_values,
                                marker='o', markersize=1.5, alpha=0.7,
                                label=f"{device_id}", linewidth=1)
        
        if self.power_data:
            self.ax_main.legend(loc='upper right', fontsize=9)
        
        # 滤波信号子图
        self.setup_axis(self.ax_filtered, "滤波后信号", "时间 (s)", "功率 (W)")
        for device_id, filtered_values in self.filtered_data.items():
            if filtered_values and len(filtered_values) <= len(self.time_data):
                time_subset = self.time_data[:len(filtered_values)]
                self.ax_filtered.plot(time_subset, filtered_values,
                                    marker='s', markersize=1.5, alpha=0.8,
                                    label=f"{device_id}", linewidth=1)
        
        if self.filtered_data:
            self.ax_filtered.legend(loc='upper right', fontsize=9)
    
    def plot_snr_analysis(self):
        """绘制SNR分析"""
        # 原始信号
        self.setup_axis(self.ax_main, "原始信号", "", "功率 (W)")
        for device_id, power_values in self.power_data.items():
            if power_values and len(power_values) <= len(self.time_data):
                time_subset = self.time_data[:len(power_values)]
                self.ax_main.plot(time_subset, power_values,
                                alpha=0.6, linewidth=1, label=f"{device_id}")
        
        # 滤波信号
        self.setup_axis(self.ax_filtered, "滤波信号", "", "功率 (W)")
        for device_id, filtered_values in self.filtered_data.items():
            if filtered_values and len(filtered_values) <= len(self.time_data):
                time_subset = self.time_data[:len(filtered_values)]
                self.ax_filtered.plot(time_subset, filtered_values,
                                    alpha=0.8, linewidth=1, label=f"{device_id}")
        
        # SNR改善
        self.setup_axis(self.ax_snr, "SNR改善", "时间 (s)", "dB")
        for device_id, snr_values in self.snr_data.items():
            if snr_values and len(snr_values) <= len(self.time_data):
                time_subset = self.time_data[:len(snr_values)]
                self.ax_snr.plot(time_subset, snr_values,
                               linewidth=2, label=f"{device_id}")
        
        # 添加图例
        if self.power_data:
            self.ax_main.legend(loc='upper right', fontsize=8)
            self.ax_filtered.legend(loc='upper right', fontsize=8)
            self.ax_snr.legend(loc='upper right', fontsize=8)
    
    def add_statistics_text(self):
        """添加统计信息文本"""
        if not self.statistics:
            return
        
        # 选择合适的子图添加文本
        target_ax = self.ax_main if hasattr(self, 'ax_main') else None
        if target_ax is None:
            return
        
        # 构建统计文本
        stats_lines = []
        for device_id, stats in self.statistics.items():
            if stats:
                line = (f"{device_id}: SNR↑{stats.get('snr_improvement', 0):.1f}dB "
                       f"噪声抑制{stats.get('noise_reduction_ratio', 0)*100:.1f}% "
                       f"样本{stats.get('sample_count', 0)}")
                stats_lines.append(line)
        
        if stats_lines:
            stats_text = "\n".join(stats_lines)
            # 在图的右上角添加文本框
            target_ax.text(0.02, 0.98, stats_text, transform=target_ax.transAxes,
                          fontsize=8, verticalalignment='top',
                          bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    def export_plot(self):
        """导出当前图片"""
        from PySide6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出图片", f"PM100D_plot_{self.view_mode}.png", 
            "PNG files (*.png);;PDF files (*.pdf);;All files (*.*)"
        )
        
        if file_path:
            try:
                self.figure.savefig(file_path, dpi=300, bbox_inches='tight')
                print(f"图片已导出: {file_path}")
            except Exception as e:
                print(f"导出失败: {e}")
        
    def clear_device_data(self, device_id):
        """清除指定设备的数据（扩展支持所有数据类型）"""
        data_cleared = {}
        
        if device_id in self.power_data:
            data_cleared['raw'] = len(self.power_data[device_id])
            del self.power_data[device_id]
        
        if device_id in self.filtered_data:
            data_cleared['filtered'] = len(self.filtered_data[device_id])
            del self.filtered_data[device_id]
        
        if device_id in self.noise_data:
            data_cleared['noise'] = len(self.noise_data[device_id])
            del self.noise_data[device_id]
        
        if device_id in self.snr_data:
            data_cleared['snr'] = len(self.snr_data[device_id])
            del self.snr_data[device_id]
        
        if device_id in self.processing_info:
            data_cleared['processing'] = len(self.processing_info[device_id])
            del self.processing_info[device_id]
        
        if device_id in self.statistics:
            del self.statistics[device_id]
        
        total_cleared = sum(data_cleared.values())
        print(f"PlotWidget: 清除设备 {device_id} 的数据，共删除 {total_cleared} 个数据点")
        print(f"数据类型分布: {data_cleared}")
        
        self.update_plot()
    
    def clear_all_data(self):
        """清除所有数据（扩展支持所有数据类型）"""
        # 统计清除前的数据
        total_devices = len(self.power_data)
        total_time_points = len(self.time_data)
        
        data_summary = {
            'raw_points': sum(len(data) for data in self.power_data.values()),
            'filtered_points': sum(len(data) for data in self.filtered_data.values()),
            'noise_points': sum(len(data) for data in self.noise_data.values()),
            'snr_points': sum(len(data) for data in self.snr_data.values())
        }
        
        # 清除所有数据
        self.time_data.clear()
        self.power_data.clear()
        self.filtered_data.clear()
        self.noise_data.clear()
        self.snr_data.clear()
        self.processing_info.clear()
        self.statistics.clear()
        
        total_cleared = sum(data_summary.values())
        print(f"PlotWidget: 清除所有数据")
        print(f"  设备数: {total_devices}, 时间点数: {total_time_points}")
        print(f"  总数据点数: {total_cleared}")
        print(f"  数据分布: {data_summary}")
        
        self.update_plot()
    
    def get_device_statistics(self, device_id):
        """
        获取设备统计信息
        
        参数:
            device_id (str): 设备ID
        
        返回:
            dict: 统计信息字典
        """
        if device_id not in self.statistics:
            return {}
        
        return self.statistics[device_id].copy()
    
    def get_all_statistics(self):
        """
        获取所有设备的统计信息
        
        返回:
            dict: 设备ID -> 统计信息的字典
        """
        return {device_id: stats.copy() for device_id, stats in self.statistics.items()}
    
    def export_data(self, file_path):
        """
        导出所有数据到文件
        
        参数:
            file_path (str): 导出文件路径
        """
        try:
            import pandas as pd
            
            # 准备导出数据
            export_data = []
            
            max_length = len(self.time_data)
            
            for i in range(max_length):
                row = {'time': self.time_data[i] if i < len(self.time_data) else None}
                
                # 为每个设备添加数据列
                for device_id in self.power_data.keys():
                    # 原始数据
                    if i < len(self.power_data[device_id]):
                        row[f'{device_id}_raw'] = self.power_data[device_id][i]
                    else:
                        row[f'{device_id}_raw'] = None
                    
                    # 滤波数据
                    if device_id in self.filtered_data and i < len(self.filtered_data[device_id]):
                        row[f'{device_id}_filtered'] = self.filtered_data[device_id][i]
                    else:
                        row[f'{device_id}_filtered'] = None
                    
                    # 噪声估计
                    if device_id in self.noise_data and i < len(self.noise_data[device_id]):
                        row[f'{device_id}_noise'] = self.noise_data[device_id][i]
                    else:
                        row[f'{device_id}_noise'] = None
                    
                    # SNR数据
                    if device_id in self.snr_data and i < len(self.snr_data[device_id]):
                        row[f'{device_id}_snr'] = self.snr_data[device_id][i]
                    else:
                        row[f'{device_id}_snr'] = None
                
                export_data.append(row)
            
            # 创建DataFrame并导出
            df = pd.DataFrame(export_data)
            
            if file_path.endswith('.csv'):
                df.to_csv(file_path, index=False)
            elif file_path.endswith('.xlsx'):
                df.to_excel(file_path, index=False)
            else:
                # 默认CSV格式
                df.to_csv(file_path + '.csv', index=False)
            
            print(f"数据导出完成: {file_path}")
            return True
            
        except Exception as e:
            print(f"数据导出失败: {e}")
            return False
    
    def set_filter_enabled(self, device_id, enabled):
        """
        设置设备的滤波器启用状态
        
        参数:
            device_id (str): 设备ID
            enabled (bool): 是否启用滤波
        """
        # 这个方法将在集成到数据流时使用
        print(f"设备 {device_id} 滤波器{'启用' if enabled else '禁用'}")
        
        # 可以在这里实现滤波器状态的持久化存储
        if not hasattr(self, '_filter_states'):
            self._filter_states = {}
        
        self._filter_states[device_id] = enabled
