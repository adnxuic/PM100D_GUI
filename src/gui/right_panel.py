#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右侧面板 - 设备控制和状态显示
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
import time


class RightPanel(QWidget):
    """右侧面板类 - 设备控制和状态显示"""
    
    def __init__(self):
        super().__init__()
        self.connected_devices = {}
        self.current_device = None
        
        # 数据采集定时器
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.collect_data)
        
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 标题
        title_label = QLabel("设备控制")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 设备选择区域
        self.create_device_selection_section(layout)
        
        # 设备控制区域
        self.create_device_control_section(layout)
        
        # 实时数据显示区域
        self.create_realtime_data_section(layout)
        
        # 数据采集控制
        self.create_data_acquisition_section(layout)
        
        layout.addStretch()
        
    def create_device_selection_section(self, parent_layout):
        """创建设备选择区域"""
        device_group = QGroupBox("当前设备")
        device_layout = QVBoxLayout(device_group)
        
        self.device_selector = QComboBox()
        self.device_selector.addItem("未选择设备")
        self.device_selector.currentTextChanged.connect(self.on_device_changed)
        device_layout.addWidget(self.device_selector)
        
        parent_layout.addWidget(device_group)
        
    def create_device_control_section(self, parent_layout):
        """创建设备控制区域"""
        control_group = QGroupBox("设备参数设置")
        control_layout = QVBoxLayout(control_group)
        
        # 波长设置
        wavelength_layout = QHBoxLayout()
        wavelength_layout.addWidget(QLabel("波长 (nm):"))
        self.wavelength_spinbox = QSpinBox()
        self.wavelength_spinbox.setRange(400, 1100)
        self.wavelength_spinbox.setValue(1550)
        self.wavelength_spinbox.valueChanged.connect(self.set_wavelength)
        wavelength_layout.addWidget(self.wavelength_spinbox)
        control_layout.addLayout(wavelength_layout)
        
        # 带宽设置
        bandwidth_layout = QHBoxLayout()
        bandwidth_layout.addWidget(QLabel("带宽:"))
        self.bandwidth_combo = QComboBox()
        self.bandwidth_combo.addItems(["LO", "HI"])
        self.bandwidth_combo.currentTextChanged.connect(self.set_bandwidth)
        bandwidth_layout.addWidget(self.bandwidth_combo)
        control_layout.addLayout(bandwidth_layout)
        
        # 平均次数设置
        avg_layout = QHBoxLayout()
        avg_layout.addWidget(QLabel("平均次数:"))
        self.avg_spinbox = QSpinBox()
        self.avg_spinbox.setRange(1, 1000)
        self.avg_spinbox.setValue(10)
        self.avg_spinbox.valueChanged.connect(self.set_avg_count)
        avg_layout.addWidget(self.avg_spinbox)
        control_layout.addLayout(avg_layout)
        
        # 自动量程
        self.auto_range_checkbox = QCheckBox("自动量程")
        self.auto_range_checkbox.setChecked(True)
        self.auto_range_checkbox.toggled.connect(self.set_auto_range)
        control_layout.addWidget(self.auto_range_checkbox)
        
        # 清零按钮
        self.zero_button = QPushButton("设备清零")
        self.zero_button.clicked.connect(self.zero_device)
        control_layout.addWidget(self.zero_button)
        
        # 初始状态禁用控件
        self.set_controls_enabled(False)
        
        parent_layout.addWidget(control_group)
        
    def create_realtime_data_section(self, parent_layout):
        """创建实时数据显示区域"""
        data_group = QGroupBox("实时数据")
        data_layout = QVBoxLayout(data_group)
        
        # 当前功率显示
        power_layout = QHBoxLayout()
        power_layout.addWidget(QLabel("当前功率:"))
        self.power_label = QLabel("-- W")
        self.power_label.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; color: #2E7D32; }")
        power_layout.addWidget(self.power_label)
        power_layout.addStretch()
        data_layout.addLayout(power_layout)
        
        # 数据表格
        self.data_table = QTableWidget(0, 3)
        self.data_table.setHorizontalHeaderLabels(["时间", "设备", "功率 (W)"])
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.data_table.setMaximumHeight(200)
        data_layout.addWidget(self.data_table)
        
        parent_layout.addWidget(data_group)
        
    def create_data_acquisition_section(self, parent_layout):
        """创建数据采集控制区域"""
        acq_group = QGroupBox("数据采集")
        acq_layout = QVBoxLayout(acq_group)
        
        # 采集间隔设置
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("采集间隔 (s):"))
        self.interval_spinbox = QDoubleSpinBox()
        self.interval_spinbox.setRange(0.1, 60.0)
        self.interval_spinbox.setValue(1.0)
        self.interval_spinbox.setSingleStep(0.1)
        interval_layout.addWidget(self.interval_spinbox)
        acq_layout.addLayout(interval_layout)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("开始采集")
        self.start_button.clicked.connect(self.start_acquisition)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("停止采集")
        self.stop_button.clicked.connect(self.stop_acquisition)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        self.clear_button = QPushButton("清除数据")
        self.clear_button.clicked.connect(self.clear_data)
        button_layout.addWidget(self.clear_button)
        
        acq_layout.addLayout(button_layout)
        
        parent_layout.addWidget(acq_group)
        
    def update_device_list(self, devices):
        """更新设备列表"""
        current_text = self.device_selector.currentText()
        self.device_selector.clear()
        
        if not devices:
            self.device_selector.addItem("未选择设备")
            self.set_controls_enabled(False)
        else:
            self.device_selector.addItem("未选择设备")
            for device_id in devices.keys():
                self.device_selector.addItem(device_id)
                
            # 尝试保持之前的选择
            index = self.device_selector.findText(current_text)
            if index >= 0:
                self.device_selector.setCurrentIndex(index)
                
        self.connected_devices = devices
        
    def on_device_changed(self, device_name):
        """设备选择改变"""
        if device_name == "未选择设备" or device_name not in self.connected_devices:
            self.current_device = None
            self.set_controls_enabled(False)
        else:
            self.current_device = self.connected_devices[device_name]['device']
            self.set_controls_enabled(True)
            self.update_controls_from_device()
            
    def set_controls_enabled(self, enabled):
        """设置控件启用状态"""
        self.wavelength_spinbox.setEnabled(enabled)
        self.bandwidth_combo.setEnabled(enabled)
        self.avg_spinbox.setEnabled(enabled)
        self.auto_range_checkbox.setEnabled(enabled)
        self.zero_button.setEnabled(enabled)
        
    def update_controls_from_device(self):
        """从设备更新控件值"""
        if not self.current_device:
            return
            
        try:
            # 更新控件值以匹配设备当前状态
            self.wavelength_spinbox.setValue(int(self.current_device.getWavelength()))
            self.bandwidth_combo.setCurrentText(self.current_device.getBandwidth())
            self.avg_spinbox.setValue(self.current_device.getAvgCount())
            self.auto_range_checkbox.setChecked(self.current_device.getRangeAuto())
        except Exception as e:
            print(f"更新控件失败: {e}")
            
    def set_wavelength(self):
        """设置波长"""
        if self.current_device:
            try:
                self.current_device.setWavelength(self.wavelength_spinbox.value())
            except Exception as e:
                print(f"设置波长失败: {e}")
                
    def set_bandwidth(self):
        """设置带宽"""
        if self.current_device:
            try:
                self.current_device.setBandwidth(self.bandwidth_combo.currentText())
            except Exception as e:
                print(f"设置带宽失败: {e}")
                
    def set_avg_count(self):
        """设置平均次数"""
        if self.current_device:
            try:
                self.current_device.setAvgCount(self.avg_spinbox.value())
            except Exception as e:
                print(f"设置平均次数失败: {e}")
                
    def set_auto_range(self):
        """设置自动量程"""
        if self.current_device:
            try:
                self.current_device.setRangeAuto(self.auto_range_checkbox.isChecked())
            except Exception as e:
                print(f"设置自动量程失败: {e}")
                
    def zero_device(self):
        """设备清零"""
        if self.current_device:
            try:
                self.current_device.zero()
            except Exception as e:
                print(f"设备清零失败: {e}")
                
    def start_acquisition(self):
        """开始数据采集"""
        if not self.connected_devices:
            return
            
        interval_ms = int(self.interval_spinbox.value() * 1000)
        self.data_timer.start(interval_ms)
        
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.interval_spinbox.setEnabled(False)
        
    def stop_acquisition(self):
        """停止数据采集"""
        self.data_timer.stop()
        
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.interval_spinbox.setEnabled(True)
        
    def collect_data(self):
        """采集数据"""
        current_time = time.time()
        
        # 采集所有连接设备的数据
        for device_id, device_info in self.connected_devices.items():
            try:
                power = device_info['device'].getPower()
                
                # 更新实时显示（仅当前选中设备）
                if self.device_selector.currentText() == device_id:
                    self.power_label.setText(f"{power:.6e} W")
                
                # 添加到数据表格
                self.add_data_to_table(current_time, device_id, power)
                
                # 发送数据到绘图组件（通过父窗口访问）
                parent_window = self.parent()
                if parent_window and hasattr(parent_window, 'plot_widget'):
                    parent_window.plot_widget.add_device_data(device_id, current_time, power)
                
            except Exception as e:
                print(f"采集设备 {device_id} 数据失败: {e}")
                
    def add_data_to_table(self, timestamp, device_id, power):
        """添加数据到表格"""
        row = self.data_table.rowCount()
        self.data_table.insertRow(row)
        
        time_str = time.strftime("%H:%M:%S", time.localtime(timestamp))
        self.data_table.setItem(row, 0, QTableWidgetItem(time_str))
        self.data_table.setItem(row, 1, QTableWidgetItem(device_id))
        self.data_table.setItem(row, 2, QTableWidgetItem(f"{power:.6e}"))
        
        # 限制表格行数，保持最新的100行
        if self.data_table.rowCount() > 100:
            self.data_table.removeRow(0)
            
        # 滚动到底部
        self.data_table.scrollToBottom()
        
    def clear_data(self):
        """清除数据"""
        self.data_table.setRowCount(0)
        self.power_label.setText("-- W")
