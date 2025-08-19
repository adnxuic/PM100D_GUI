#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据可视化组件
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.font_manager as fm
import platform

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
    """数据绘图组件"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        
        # 创建matplotlib图形
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        
        # 创建子图
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title('PM100D 功率监测')
        self.ax.set_xlabel('时间 (s)')
        self.ax.set_ylabel('功率 (W)')
        self.ax.grid(True, alpha=0.3)
        
        layout.addWidget(self.canvas)
        
        # 初始化数据存储
        self.time_data = []
        self.power_data = {}  # 存储每个设备的功率数据
        
    def add_device_data(self, device_id, time_point, power_value):
        """添加设备数据点"""
        print(f"PlotWidget: 接收数据 - 设备={device_id}, 时间={time_point}, 功率={power_value:.6e}")
        
        if device_id not in self.power_data:
            self.power_data[device_id] = []
            print(f"PlotWidget: 为设备 {device_id} 创建新的数据列表")
            
        # 确保时间数据同步
        if len(self.time_data) <= len(self.power_data[device_id]):
            self.time_data.append(time_point)
            print(f"PlotWidget: 添加时间点，当前时间数据长度: {len(self.time_data)}")
            
        self.power_data[device_id].append(power_value)
        print(f"PlotWidget: 设备 {device_id} 数据点数: {len(self.power_data[device_id])}")
        print(f"PlotWidget: 当前所有设备: {list(self.power_data.keys())}")
        
        # 更新图形
        self.update_plot()
        
    def update_plot(self):
        """更新图形显示"""
        self.ax.clear()
        
        # 重新设置标题和标签
        self.ax.set_title('PM100D 功率监测')
        self.ax.set_xlabel('时间 (s)')
        self.ax.set_ylabel('功率 (W)')
        self.ax.grid(True, alpha=0.3)
        
        # 绘制每个设备的数据
        for device_id, power_values in self.power_data.items():
            if power_values and len(power_values) <= len(self.time_data):
                time_subset = self.time_data[:len(power_values)]
                self.ax.plot(time_subset, power_values, 
                           marker='o', markersize=3, 
                           label=device_id, linewidth=1.5)
        
        # 显示图例
        if self.power_data:
            self.ax.legend()
            
        # 刷新画布
        self.canvas.draw()
        
    def clear_device_data(self, device_id):
        """清除指定设备的数据"""
        if device_id in self.power_data:
            data_count = len(self.power_data[device_id])
            del self.power_data[device_id]
            print(f"PlotWidget: 清除设备 {device_id} 的数据，共删除 {data_count} 个数据点")
            self.update_plot()
            
    def clear_all_data(self):
        """清除所有数据"""
        total_devices = len(self.power_data)
        total_time_points = len(self.time_data)
        total_data_points = sum(len(data) for data in self.power_data.values())
        
        self.time_data.clear()
        self.power_data.clear()
        
        print(f"PlotWidget: 清除所有数据 - 设备数: {total_devices}, 时间点数: {total_time_points}, 总数据点数: {total_data_points}")
        self.update_plot()
