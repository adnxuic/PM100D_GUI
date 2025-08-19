#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右侧面板 - 设备控制和状态显示
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QSlider, QProgressBar, QTabWidget, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
import time
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from component.lms_filter import LMSFilter, AdaptiveLMSFilter
    from component.dual_path_processor import DualPathProcessor, NoiseSuppressionMode
except ImportError as e:
    print(f"导入滤波器组件失败: {e}")
    LMSFilter = None
    AdaptiveLMSFilter = None
    DualPathProcessor = None
    NoiseSuppressionMode = None


class RightPanel(QWidget):
    """右侧面板类 - 设备控制和状态显示"""
    
    # 信号定义
    acquisition_stopped = Signal()  # 数据采集停止信号
    
    def __init__(self):
        super().__init__()
        self.connected_devices = {}
        self.plot_widget = None  # 绘图组件引用
        self.main_window = None  # 主窗口引用
        
        # 数据采集定时器
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.collect_data)
        
        # 滤波器系统
        self.filter_enabled = False
        self.noise_processors = {}  # 设备ID -> DualPathProcessor
        self.main_reference_mapping = {}  # 主信号设备 -> 参考信号设备的映射
        self.filter_performance_timer = QTimer()
        self.filter_performance_timer.timeout.connect(self.update_filter_performance)
        self.filter_performance_timer.start(2000)  # 每2秒更新一次滤波性能
        
        self.init_ui()
    
    def set_plot_widget(self, plot_widget):
        """设置绘图组件引用"""
        self.plot_widget = plot_widget
        print(f"RightPanel: 绘图组件引用已设置 - {plot_widget is not None}")
    
    def set_main_window(self, main_window):
        """设置主窗口引用"""
        self.main_window = main_window
        print(f"RightPanel: 主窗口引用已设置 - {main_window is not None}")
        
    def init_ui(self):
        """初始化用户界面（带滚动区域）"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 标题（固定在顶部，不滚动）
        title_label = QLabel("设备控制")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-bottom: 1px solid #ccc;")
        main_layout.addWidget(title_label)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameStyle(QFrame.NoFrame)
        
        # 创建滚动内容容器
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(10)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        
        # 添加所有组件到滚动内容
        # 设备选择区域
        self.create_device_selection_section(scroll_layout)
        
        # 设备控制区域
        self.create_device_control_section(scroll_layout)
        
        # 实时数据显示区域
        self.create_realtime_data_section(scroll_layout)
        
        # 数据采集控制
        self.create_data_acquisition_section(scroll_layout)
        
        # 噪声滤波控制
        self.create_noise_filter_section(scroll_layout)
        
        # 添加弹性空间到滚动内容
        scroll_layout.addStretch()
        
        # 设置滚动区域的内容
        scroll_area.setWidget(scroll_content)
        
        # 将滚动区域添加到主布局
        main_layout.addWidget(scroll_area)
        
    def create_device_selection_section(self, parent_layout):
        """创建设备选择区域"""
        device_group = QGroupBox("设备选择栏")
        device_layout = QVBoxLayout(device_group)
        
        # 说明标签
        info_label = QLabel("选择要操作和记录数据的PM100D设备:")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        device_layout.addWidget(info_label)
        
        # 设备选择复选框容器
        from PySide6.QtWidgets import QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setMaximumHeight(120)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.device_checkboxes_widget = QWidget()
        self.device_checkboxes_layout = QVBoxLayout(self.device_checkboxes_widget)
        self.device_checkboxes_layout.setContentsMargins(5, 5, 5, 5)
        
        # 设备复选框字典
        self.device_checkboxes = {}
        
        # 空状态标签
        self.no_devices_label = QLabel("暂无连接的设备")
        self.no_devices_label.setStyleSheet("color: #999; font-style: italic; padding: 20px; text-align: center;")
        self.device_checkboxes_layout.addWidget(self.no_devices_label)
        
        scroll_area.setWidget(self.device_checkboxes_widget)
        device_layout.addWidget(scroll_area)
        
        # 批量选择按钮
        batch_select_layout = QHBoxLayout()
        
        self.select_all_button = QPushButton("全选")
        self.select_all_button.clicked.connect(self.select_all_devices)
        self.select_all_button.setEnabled(False)
        batch_select_layout.addWidget(self.select_all_button)
        
        self.select_none_button = QPushButton("全不选")
        self.select_none_button.clicked.connect(self.select_none_devices)
        self.select_none_button.setEnabled(False)
        batch_select_layout.addWidget(self.select_none_button)
        
        device_layout.addLayout(batch_select_layout)
        
        # 选中设备状态
        self.selected_devices_label = QLabel("已选中设备: 0")
        self.selected_devices_label.setStyleSheet("font-weight: bold; color: #2E7D32; margin-top: 5px;")
        device_layout.addWidget(self.selected_devices_label)
        
        parent_layout.addWidget(device_group)
        
    def create_device_control_section(self, parent_layout):
        """创建设备控制区域"""
        control_group = QGroupBox("设备参数设置")
        control_layout = QVBoxLayout(control_group)
        
        # 操作提示
        tip_label = QLabel("参数设置将应用到所有选中的设备")
        tip_label.setStyleSheet("color: #666; font-size: 10px; font-style: italic; margin-bottom: 5px;")
        control_layout.addWidget(tip_label)
        
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
        
        # 选中设备操作按钮
        selected_device_layout = QHBoxLayout()
        self.sync_selected_button = QPushButton("同步选中设备")
        self.sync_selected_button.clicked.connect(self.sync_selected_devices)
        self.sync_selected_button.setToolTip("将当前参数应用到所有选中的设备")
        self.sync_selected_button.setEnabled(False)
        selected_device_layout.addWidget(self.sync_selected_button)
        
        self.zero_selected_button = QPushButton("清零选中设备")
        self.zero_selected_button.clicked.connect(self.zero_selected_devices)
        self.zero_selected_button.setToolTip("对所有选中的设备执行清零操作")
        self.zero_selected_button.setEnabled(False)
        selected_device_layout.addWidget(self.zero_selected_button)
        
        control_layout.addLayout(selected_device_layout)
        
        # 自动保存选项
        self.auto_save_checkbox = QCheckBox("停止采集时自动保存数据")
        self.auto_save_checkbox.setChecked(True)
        self.auto_save_checkbox.toggled.connect(self.on_auto_save_toggled)
        control_layout.addWidget(self.auto_save_checkbox)
        

        
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
        self.data_table.setMaximumHeight(150)
        self.data_table.setMinimumHeight(100)
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
        """更新设备选择栏"""
        # 保存当前选中的设备
        previously_selected = self.get_selected_devices()
        
        # 清除现有的复选框
        for device_id, checkbox in self.device_checkboxes.items():
            self.device_checkboxes_layout.removeWidget(checkbox)
            checkbox.deleteLater()
        self.device_checkboxes.clear()
        
        # 更新连接的设备
        self.connected_devices = devices
        
        if not devices:
            # 没有设备时显示空状态
            self.no_devices_label.show()
            self.select_all_button.setEnabled(False)
            self.select_none_button.setEnabled(False)
            self.set_controls_enabled(False)
        else:
            # 隐藏空状态标签
            self.no_devices_label.hide()
            
            # 为每个设备创建复选框
            for device_id in devices.keys():
                checkbox = QCheckBox(f"{device_id}")
                checkbox.setToolTip(f"选择 {device_id} 进行操作和数据记录")
                checkbox.toggled.connect(self.on_device_selection_changed)
                
                # 恢复之前的选中状态
                if device_id in previously_selected:
                    checkbox.setChecked(True)
                
                self.device_checkboxes[device_id] = checkbox
                self.device_checkboxes_layout.addWidget(checkbox)
            
            self.select_all_button.setEnabled(True)
            self.select_none_button.setEnabled(True)
        
        # 更新选中设备状态
        self.update_selected_devices_display()
        
    def get_selected_devices(self):
        """获取选中的设备ID列表"""
        selected = []
        for device_id, checkbox in self.device_checkboxes.items():
            if checkbox.isChecked():
                selected.append(device_id)
        return selected
    
    def select_all_devices(self):
        """选择所有设备"""
        for checkbox in self.device_checkboxes.values():
            checkbox.setChecked(True)
    
    def select_none_devices(self):
        """取消选择所有设备"""
        for checkbox in self.device_checkboxes.values():
            checkbox.setChecked(False)
            
    def on_device_selection_changed(self):
        """设备选择状态改变"""
        selected_devices = self.get_selected_devices()
        has_selection = len(selected_devices) > 0
        
        # 更新控件启用状态
        self.set_controls_enabled(has_selection)
        
        # 更新选中设备显示
        self.update_selected_devices_display()
        
        # 如果有选中的设备，从第一个设备更新控件值
        if has_selection:
            self.update_controls_from_selected_devices()
        
        print(f"设备选择已更改: {selected_devices}")
    
    def update_selected_devices_display(self):
        """更新选中设备状态显示"""
        selected_devices = self.get_selected_devices()
        count = len(selected_devices)
        
        if count == 0:
            self.selected_devices_label.setText("已选中设备: 0")
            self.selected_devices_label.setStyleSheet("font-weight: bold; color: #999; margin-top: 5px;")
        else:
            self.selected_devices_label.setText(f"已选中设备: {count} ({', '.join(selected_devices)})")
            self.selected_devices_label.setStyleSheet("font-weight: bold; color: #2E7D32; margin-top: 5px;")
            
    def set_controls_enabled(self, enabled):
        """设置控件启用状态"""
        self.wavelength_spinbox.setEnabled(enabled)
        self.bandwidth_combo.setEnabled(enabled)
        self.avg_spinbox.setEnabled(enabled)
        self.auto_range_checkbox.setEnabled(enabled)
        
        # 选中设备操作按钮的启用状态
        self.sync_selected_button.setEnabled(enabled)
        self.zero_selected_button.setEnabled(enabled)
        
    def update_controls_from_selected_devices(self):
        """从选中的设备更新控件值（使用第一个选中设备的参数）"""
        selected_devices = self.get_selected_devices()
        if not selected_devices:
            return
            
        # 使用第一个选中设备的参数作为显示值
        first_device_id = selected_devices[0]
        if first_device_id not in self.connected_devices:
            return
            
        try:
            device = self.connected_devices[first_device_id]['device']
            # 更新控件值以匹配第一个选中设备的当前状态
            self.wavelength_spinbox.setValue(int(device.getWavelength()))
            self.bandwidth_combo.setCurrentText(device.getBandwidth())
            self.avg_spinbox.setValue(device.getAvgCount())
            self.auto_range_checkbox.setChecked(device.getRangeAuto())
            
            print(f"控件已更新为设备 {first_device_id} 的参数")
        except Exception as e:
            print(f"更新控件失败: {e}")
            
    def set_wavelength(self):
        """设置波长到选中的设备"""
        self._apply_to_selected_devices('setWavelength', self.wavelength_spinbox.value())
                
    def set_bandwidth(self):
        """设置带宽到选中的设备"""
        self._apply_to_selected_devices('setBandwidth', self.bandwidth_combo.currentText())
                
    def set_avg_count(self):
        """设置平均次数到选中的设备"""
        self._apply_to_selected_devices('setAvgCount', self.avg_spinbox.value())
                
    def set_auto_range(self):
        """设置自动量程到选中的设备"""
        self._apply_to_selected_devices('setRangeAuto', self.auto_range_checkbox.isChecked())
                
    def _apply_to_selected_devices(self, method_name, value):
        """应用设置到选中设备的辅助方法"""
        selected_devices = self.get_selected_devices()
        if not selected_devices:
            print(f"没有选中的设备，跳过 {method_name} 设置")
            return
            
        success_count = 0
        failed_devices = []
        
        for device_id in selected_devices:
            try:
                device = self.connected_devices[device_id]['device']
                method = getattr(device, method_name)
                method(value)
                success_count += 1
            except Exception as e:
                print(f"设备 {device_id} {method_name} 设置失败: {e}")
                failed_devices.append(device_id)
        
        if failed_devices:
            print(f"设置 {method_name}={value}: 成功 {success_count} 个设备, 失败 {len(failed_devices)} 个设备 ({', '.join(failed_devices)})")
        else:
            print(f"设置 {method_name}={value}: 成功应用到所有 {success_count} 个选中设备")
                
    def sync_selected_devices(self):
        """同步选中设备参数"""
        selected_devices = self.get_selected_devices()
        if not selected_devices:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "同步设备", "请先选择要同步的设备")
            return
            
        wavelength = self.wavelength_spinbox.value()
        bandwidth = self.bandwidth_combo.currentText()
        avg_count = self.avg_spinbox.value()
        auto_range = self.auto_range_checkbox.isChecked()
        
        success_count = 0
        failed_devices = []
        
        for device_id in selected_devices:
            try:
                device = self.connected_devices[device_id]['device']
                device.setWavelength(wavelength)
                device.setBandwidth(bandwidth)
                device.setAvgCount(avg_count)
                device.setRangeAuto(auto_range)
                success_count += 1
                print(f"设备 {device_id} 参数同步成功")
            except Exception as e:
                failed_devices.append(device_id)
                print(f"设备 {device_id} 参数同步失败: {e}")
        
        # 显示同步结果
        from PySide6.QtWidgets import QMessageBox
        if failed_devices:
            msg = f"参数同步完成！\n\n成功: {success_count}个设备\n失败: {len(failed_devices)}个设备\n\n失败的设备: {', '.join(failed_devices)}"
            QMessageBox.warning(self, "参数同步", msg)
        else:
            QMessageBox.information(self, "参数同步", f"所有 {success_count} 个选中设备参数同步成功！\n\n设置:\n波长: {wavelength}nm\n带宽: {bandwidth}\n平均次数: {avg_count}\n自动量程: {'开启' if auto_range else '关闭'}")
            
    def zero_selected_devices(self):
        """对选中设备执行清零操作"""
        selected_devices = self.get_selected_devices()
        if not selected_devices:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "设备清零", "请先选择要清零的设备")
            return
            
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, '确认清零', 
            f'确定要对选中的 {len(selected_devices)} 个设备执行清零操作吗？\n\n选中设备: {", ".join(selected_devices)}\n\n注意：清零过程中请确保所有传感器都被遮挡。',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        success_count = 0
        failed_devices = []
        
        for device_id in selected_devices:
            try:
                device = self.connected_devices[device_id]['device']
                print(f"正在对设备 {device_id} 执行清零...")
                device.zero()
                success_count += 1
                print(f"设备 {device_id} 清零成功")
            except Exception as e:
                failed_devices.append(device_id)
                print(f"设备 {device_id} 清零失败: {e}")
        
        # 显示清零结果
        if failed_devices:
            msg = f"设备清零完成！\n\n成功: {success_count}个设备\n失败: {len(failed_devices)}个设备\n\n失败的设备: {', '.join(failed_devices)}"
            QMessageBox.warning(self, "设备清零", msg)
        else:
            QMessageBox.information(self, "设备清零", f"所有 {success_count} 个选中设备清零操作完成！")
                
    def start_acquisition(self):
        """开始数据采集"""
        selected_devices = self.get_selected_devices()
        if not selected_devices:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "数据采集", "请先选择要采集数据的设备")
            return
            
        interval_ms = int(self.interval_spinbox.value() * 1000)
        self.data_timer.start(interval_ms)
        
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.interval_spinbox.setEnabled(False)
        
        # 更新状态栏
        if self.main_window and hasattr(self.main_window, 'acquisition_status_label'):
            auto_save_status = "开启" if self.auto_save_checkbox.isChecked() else "关闭"
            device_count = len(selected_devices)
            self.main_window.acquisition_status_label.setText(f"数据采集: 运行中 ({device_count}个设备, 自动保存: {auto_save_status})")
        
        print(f"开始数据采集 - 选中设备: {', '.join(selected_devices)}")
        
    def stop_acquisition(self):
        """停止数据采集"""
        self.data_timer.stop()
        
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.interval_spinbox.setEnabled(True)
        
        print(f"停止采集 - 自动保存开关状态: {self.auto_save_checkbox.isChecked()}")
        
        # 更新状态栏
        if self.main_window and hasattr(self.main_window, 'acquisition_status_label'):
            self.main_window.acquisition_status_label.setText("数据采集: 停止")
        
        # 如果启用了自动保存，发出停止采集信号
        if self.auto_save_checkbox.isChecked():
            print("发出停止采集信号，触发自动保存...")
            self.acquisition_stopped.emit()
        else:
            print("自动保存已关闭，不会自动保存数据")
        
    def collect_data(self):
        """采集数据（只采集选中设备的数据，支持滤波处理）"""
        current_time = time.time()
        selected_devices = self.get_selected_devices()
        
        if not selected_devices:
            print("没有选中设备，停止数据采集")
            self.stop_acquisition()
            return
            
        print(f"开始数据采集 - 时间戳: {current_time}")
        print(f"选中设备数量: {len(selected_devices)}")
        
        # 存储原始数据用于滤波处理
        raw_data = {}
        
        # 第一步：采集所有选中设备的原始数据
        for device_id in selected_devices:
            if device_id not in self.connected_devices:
                print(f"设备 {device_id} 已断开连接，跳过采集")
                continue
                
            try:
                print(f"正在采集设备 {device_id} 的数据...")
                device_info = self.connected_devices[device_id]
                power = device_info['device'].getPower()
                raw_data[device_id] = power
                print(f"设备 {device_id} 功率值: {power:.6e} W")
                
            except Exception as e:
                print(f"采集设备 {device_id} 数据失败: {e}")
                continue
        
        # 第二步：处理滤波（如果启用）
        processed_data = {}
        noise_estimates = {}
        processing_info = {}
        
        if self.filter_enabled and self.noise_processors and raw_data:
            print("执行噪声滤波处理...")
            
            for device_id, raw_power in raw_data.items():
                # 获取参考信号
                ref_device_id = self.main_reference_mapping.get(device_id)
                ref_power = raw_data.get(ref_device_id, raw_power) if ref_device_id else raw_power
                
                # 执行滤波处理
                if device_id in self.noise_processors:
                    try:
                        processor = self.noise_processors[device_id]
                        filtered_power, proc_info = processor.process_sample(raw_power, ref_power)
                        
                        processed_data[device_id] = filtered_power
                        noise_estimates[device_id] = proc_info.get('noise_estimate', 0.0)
                        processing_info[device_id] = proc_info
                        
                        print(f"设备 {device_id} 滤波处理: 原始={raw_power:.6e}W, 滤波后={filtered_power:.6e}W, "
                              f"噪声估计={noise_estimates[device_id]:.6e}W")
                        
                    except Exception as e:
                        print(f"设备 {device_id} 滤波处理失败: {e}")
                        # 滤波失败时使用原始数据
                        processed_data[device_id] = raw_power
                        noise_estimates[device_id] = 0.0
                        processing_info[device_id] = {}
                else:
                    # 没有对应处理器时使用原始数据
                    processed_data[device_id] = raw_power
                    noise_estimates[device_id] = 0.0
                    processing_info[device_id] = {}
        else:
            # 滤波未启用时直接使用原始数据
            processed_data = raw_data.copy()
            for device_id in raw_data:
                noise_estimates[device_id] = 0.0
                processing_info[device_id] = {}
        
        # 第三步：更新界面显示和数据存储
        for device_id in selected_devices:
            if device_id not in raw_data:
                continue
                
            raw_power = raw_data[device_id]
            filtered_power = processed_data.get(device_id, raw_power)
            noise_estimate = noise_estimates.get(device_id, 0.0)
            proc_info = processing_info.get(device_id, {})
            
            try:
                # 更新实时显示（显示第一个选中设备的功率）
                if device_id == selected_devices[0]:
                    if self.filter_enabled:
                        # 滤波启用时显示滤波后的值
                        self.power_label.setText(f"{filtered_power:.6e} W (滤波)")
                    else:
                        self.power_label.setText(f"{raw_power:.6e} W")
                
                # 添加到数据表格（显示滤波后的值）
                display_power = filtered_power if self.filter_enabled else raw_power
                self.add_data_to_table(current_time, device_id, display_power)
                
                # 发送数据到绘图组件（包含原始和滤波数据）
                if self.plot_widget is not None:
                    self.plot_widget.add_device_data(
                        device_id=device_id,
                        time_point=current_time,
                        power_value=raw_power,
                        filtered_value=filtered_power,
                        noise_estimate=noise_estimate,
                        processing_info=proc_info
                    )
                    
                    print(f"向绘图组件发送数据: 设备={device_id}, 原始={raw_power:.6e}W, "
                          f"滤波={filtered_power:.6e}W")
                    
                    # 验证数据是否成功添加
                    if hasattr(self.plot_widget, 'power_data'):
                        device_data_count = len(self.plot_widget.power_data.get(device_id, []))
                        print(f"设备 {device_id} 当前数据点数: {device_data_count}")
                else:
                    print(f"错误: plot_widget 引用为空，无法保存数据到图形组件")
                
            except Exception as e:
                print(f"更新设备 {device_id} 界面数据失败: {e}")
        
        # 记录处理统计
        if self.filter_enabled:
            total_devices = len(raw_data)
            filtered_devices = len(processed_data)
            print(f"本轮处理统计: 总设备数={total_devices}, 滤波设备数={filtered_devices}")
                
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
        print("RightPanel: 清除数据按钮被点击")
        table_rows = self.data_table.rowCount()
        self.data_table.setRowCount(0)
        self.power_label.setText("-- W")
        print(f"RightPanel: 清除了数据表格的 {table_rows} 行数据")
        
        # 同时清除绘图组件的数据
        if self.plot_widget is not None:
            print("RightPanel: 同时清除绘图组件的数据")
            self.plot_widget.clear_all_data()
        else:
            print("RightPanel: 绘图组件引用为空，无法清除绘图组件数据")
    
    def on_auto_save_toggled(self, checked):
        """自动保存选项切换时的响应"""
        status = "启用" if checked else "禁用"
        print(f"自动保存功能已{status}")
        
        # 如果主窗口存在，更新状态栏
        if self.main_window and hasattr(self.main_window, 'status_bar'):
            self.main_window.status_bar.showMessage(f"自动保存功能已{status}", 2000)
    
    def create_noise_filter_section(self, parent_layout):
        """创建噪声滤波控制区域"""
        filter_group = QGroupBox("噪声滤波系统")
        filter_layout = QVBoxLayout(filter_group)
        
        # 滤波器总开关
        filter_enable_layout = QHBoxLayout()
        self.filter_enable_checkbox = QCheckBox("启用噪声滤波")
        self.filter_enable_checkbox.toggled.connect(self.on_filter_enable_toggled)
        filter_enable_layout.addWidget(self.filter_enable_checkbox)
        
        self.filter_status_label = QLabel("状态: 未启用")
        self.filter_status_label.setStyleSheet("color: #666; font-style: italic;")
        filter_enable_layout.addWidget(self.filter_status_label)
        filter_enable_layout.addStretch()
        
        filter_layout.addLayout(filter_enable_layout)
        
        # 创建滤波器选项卡
        self.filter_tabs = QTabWidget()
        self.filter_tabs.setMinimumHeight(400)  # 设置最小高度确保内容显示完整
        filter_layout.addWidget(self.filter_tabs)
        
        # 分光路设置选项卡
        self.create_dual_path_tab()
        
        # LMS滤波器选项卡
        self.create_lms_filter_tab()
        
        # 性能监控选项卡
        self.create_performance_monitor_tab()
        
        # 初始状态禁用所有控件
        self.set_filter_controls_enabled(False)
        
        parent_layout.addWidget(filter_group)
    
    def create_dual_path_tab(self):
        """创建分光路设置选项卡"""
        dual_path_tab = QWidget()
        layout = QVBoxLayout(dual_path_tab)
        
        # 抑制模式选择
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("抑制模式:"))
        self.suppression_mode_combo = QComboBox()
        if NoiseSuppressionMode:
            mode_items = [
                ("比值法", NoiseSuppressionMode.RATIO),
                ("差值法", NoiseSuppressionMode.DIFFERENCE), 
                ("归一化比值", NoiseSuppressionMode.NORMALIZED_RATIO),
                ("LMS自适应", NoiseSuppressionMode.LMS_ADAPTIVE),
                ("混合方法", NoiseSuppressionMode.HYBRID)
            ]
            for name, mode in mode_items:
                self.suppression_mode_combo.addItem(name, mode)
        self.suppression_mode_combo.currentTextChanged.connect(self.on_suppression_mode_changed)
        mode_layout.addWidget(self.suppression_mode_combo)
        layout.addLayout(mode_layout)
        
        # 设备配对设置
        pairing_group = QGroupBox("设备配对设置")
        pairing_layout = QVBoxLayout(pairing_group)
        
        # 配对列表
        self.device_pairing_table = QTableWidget(0, 3)
        self.device_pairing_table.setHorizontalHeaderLabels(["主信号设备", "参考信号设备", "状态"])
        self.device_pairing_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.device_pairing_table.setMaximumHeight(100)
        self.device_pairing_table.setMinimumHeight(80)
        pairing_layout.addWidget(self.device_pairing_table)
        
        # 配对控制按钮
        pairing_control_layout = QHBoxLayout()
        self.add_pairing_button = QPushButton("添加配对")
        self.add_pairing_button.clicked.connect(self.add_device_pairing)
        pairing_control_layout.addWidget(self.add_pairing_button)
        
        self.remove_pairing_button = QPushButton("删除配对")
        self.remove_pairing_button.clicked.connect(self.remove_device_pairing)
        pairing_control_layout.addWidget(self.remove_pairing_button)
        
        self.auto_pair_button = QPushButton("自动配对")
        self.auto_pair_button.clicked.connect(self.auto_pair_devices)
        pairing_control_layout.addWidget(self.auto_pair_button)
        
        pairing_layout.addLayout(pairing_control_layout)
        layout.addWidget(pairing_group)
        
        # 标定控制
        calibration_group = QGroupBox("系统标定")
        cal_layout = QVBoxLayout(calibration_group)
        
        cal_control_layout = QHBoxLayout()
        self.calibration_button = QPushButton("开始标定")
        self.calibration_button.clicked.connect(self.start_calibration)
        cal_control_layout.addWidget(self.calibration_button)
        
        self.calibration_progress = QProgressBar()
        self.calibration_progress.setVisible(False)
        cal_control_layout.addWidget(self.calibration_progress)
        
        cal_layout.addLayout(cal_control_layout)
        
        self.calibration_status_label = QLabel("标定状态: 未标定")
        self.calibration_status_label.setStyleSheet("font-size: 10px; color: #666;")
        cal_layout.addWidget(self.calibration_status_label)
        
        layout.addWidget(calibration_group)
        
        self.filter_tabs.addTab(dual_path_tab, "分光路设置")
    
    def create_lms_filter_tab(self):
        """创建LMS滤波器选项卡"""
        lms_tab = QWidget()
        layout = QVBoxLayout(lms_tab)
        
        # LMS参数调整
        params_group = QGroupBox("LMS参数")
        params_layout = QVBoxLayout(params_group)
        
        # 滤波器长度
        length_layout = QHBoxLayout()
        length_layout.addWidget(QLabel("滤波器长度:"))
        self.filter_length_spinbox = QSpinBox()
        self.filter_length_spinbox.setRange(8, 128)
        self.filter_length_spinbox.setValue(32)
        self.filter_length_spinbox.valueChanged.connect(self.on_lms_params_changed)
        length_layout.addWidget(self.filter_length_spinbox)
        params_layout.addLayout(length_layout)
        
        # 学习率
        step_size_layout = QVBoxLayout()
        step_size_layout.addWidget(QLabel("学习率 (μ):"))
        
        step_size_control_layout = QHBoxLayout()
        self.step_size_slider = QSlider(Qt.Horizontal)
        self.step_size_slider.setRange(1, 100)  # 0.001 to 0.1
        self.step_size_slider.setValue(10)  # 0.01
        self.step_size_slider.valueChanged.connect(self.on_step_size_changed)
        step_size_control_layout.addWidget(self.step_size_slider)
        
        self.step_size_label = QLabel("0.010")
        self.step_size_label.setMinimumWidth(50)
        step_size_control_layout.addWidget(self.step_size_label)
        
        step_size_layout.addLayout(step_size_control_layout)
        params_layout.addLayout(step_size_layout)
        
        # 泄漏因子
        leakage_layout = QVBoxLayout()
        leakage_layout.addWidget(QLabel("泄漏因子 (λ):"))
        
        leakage_control_layout = QHBoxLayout()
        self.leakage_slider = QSlider(Qt.Horizontal)
        self.leakage_slider.setRange(900, 1000)  # 0.9 to 1.0
        self.leakage_slider.setValue(995)  # 0.995
        self.leakage_slider.valueChanged.connect(self.on_leakage_changed)
        leakage_control_layout.addWidget(self.leakage_slider)
        
        self.leakage_label = QLabel("0.995")
        self.leakage_label.setMinimumWidth(50)
        leakage_control_layout.addWidget(self.leakage_label)
        
        leakage_layout.addLayout(leakage_control_layout)
        params_layout.addLayout(leakage_layout)
        
        # 自动调整选项
        self.auto_adjust_checkbox = QCheckBox("自动参数调整")
        self.auto_adjust_checkbox.setChecked(True)
        self.auto_adjust_checkbox.toggled.connect(self.on_auto_adjust_toggled)
        params_layout.addWidget(self.auto_adjust_checkbox)
        
        layout.addWidget(params_group)
        
        # LMS控制按钮
        control_layout = QHBoxLayout()
        self.reset_lms_button = QPushButton("重置滤波器")
        self.reset_lms_button.clicked.connect(self.reset_lms_filters)
        control_layout.addWidget(self.reset_lms_button)
        
        self.lms_test_button = QPushButton("测试滤波器")
        self.lms_test_button.clicked.connect(self.test_lms_filters)
        control_layout.addWidget(self.lms_test_button)
        
        layout.addLayout(control_layout)
        
        self.filter_tabs.addTab(lms_tab, "LMS参数")
    
    def create_performance_monitor_tab(self):
        """创建性能监控选项卡"""
        perf_tab = QWidget()
        layout = QVBoxLayout(perf_tab)
        
        # 性能指标显示
        metrics_group = QGroupBox("实时性能指标")
        metrics_layout = QVBoxLayout(metrics_group)
        
        # SNR改善显示
        snr_layout = QHBoxLayout()
        snr_layout.addWidget(QLabel("SNR改善:"))
        self.snr_value_label = QLabel("0.0 dB")
        self.snr_value_label.setStyleSheet("font-weight: bold; color: #2E7D32;")
        snr_layout.addWidget(self.snr_value_label)
        snr_layout.addStretch()
        metrics_layout.addLayout(snr_layout)
        
        # 噪声抑制率
        noise_reduction_layout = QHBoxLayout()
        noise_reduction_layout.addWidget(QLabel("噪声抑制率:"))
        self.noise_reduction_label = QLabel("0.0%")
        self.noise_reduction_label.setStyleSheet("font-weight: bold; color: #2E7D32;")
        noise_reduction_layout.addWidget(self.noise_reduction_label)
        noise_reduction_layout.addStretch()
        metrics_layout.addLayout(noise_reduction_layout)
        
        # 收敛状态
        convergence_layout = QHBoxLayout()
        convergence_layout.addWidget(QLabel("收敛状态:"))
        self.convergence_label = QLabel("未启动")
        self.convergence_label.setStyleSheet("font-style: italic; color: #666;")
        convergence_layout.addWidget(self.convergence_label)
        convergence_layout.addStretch()
        metrics_layout.addLayout(convergence_layout)
        
        layout.addWidget(metrics_group)
        
        # 处理统计
        stats_group = QGroupBox("处理统计")
        stats_layout = QVBoxLayout(stats_group)
        
        self.processing_stats_text = QTextEdit()
        self.processing_stats_text.setMaximumHeight(80)
        self.processing_stats_text.setMinimumHeight(60)
        self.processing_stats_text.setReadOnly(True)
        self.processing_stats_text.setStyleSheet("font-family: monospace; font-size: 9px;")
        stats_layout.addWidget(self.processing_stats_text)
        
        layout.addWidget(stats_group)
        
        # 导出功能
        export_layout = QHBoxLayout()
        self.export_filter_data_button = QPushButton("导出滤波数据")
        self.export_filter_data_button.clicked.connect(self.export_filter_data)
        export_layout.addWidget(self.export_filter_data_button)
        
        self.export_performance_button = QPushButton("导出性能报告")
        self.export_performance_button.clicked.connect(self.export_performance_report)
        export_layout.addWidget(self.export_performance_button)
        
        layout.addLayout(export_layout)
        
        self.filter_tabs.addTab(perf_tab, "性能监控")
    
    def set_filter_controls_enabled(self, enabled):
        """设置滤波器控件的启用状态"""
        self.filter_tabs.setEnabled(enabled)
        
        # 更新状态标签
        if enabled:
            self.filter_status_label.setText("状态: 已启用")
            self.filter_status_label.setStyleSheet("color: #2E7D32; font-weight: bold;")
        else:
            self.filter_status_label.setText("状态: 未启用")
            self.filter_status_label.setStyleSheet("color: #666; font-style: italic;")
    
    # 滤波器事件处理方法
    def on_filter_enable_toggled(self, checked):
        """滤波器启用状态切换"""
        self.filter_enabled = checked
        self.set_filter_controls_enabled(checked)
        
        if checked:
            print("噪声滤波系统已启用")
            # 为选中的设备创建处理器
            self.setup_noise_processors()
        else:
            print("噪声滤波系统已禁用")
            # 清理处理器
            self.noise_processors.clear()
            self.main_reference_mapping.clear()
        
        # 更新主窗口状态栏
        if self.main_window and hasattr(self.main_window, 'status_bar'):
            status = "启用" if checked else "禁用"
            self.main_window.status_bar.showMessage(f"噪声滤波系统已{status}", 3000)
    
    def on_suppression_mode_changed(self):
        """抑制模式改变"""
        if not self.filter_enabled:
            return
        
        current_text = self.suppression_mode_combo.currentText()
        current_mode = self.suppression_mode_combo.currentData()
        
        print(f"切换抑制模式: {current_text}")
        
        # 更新所有处理器的模式
        for processor in self.noise_processors.values():
            if processor and hasattr(processor, 'update_mode'):
                processor.update_mode(current_mode)
    
    def on_step_size_changed(self, value):
        """学习率滑块改变"""
        step_size = value / 1000.0  # 0.001 to 0.1
        self.step_size_label.setText(f"{step_size:.3f}")
        
        # 更新LMS滤波器参数
        self.update_lms_parameters()
    
    def on_leakage_changed(self, value):
        """泄漏因子滑块改变"""
        leakage = value / 1000.0  # 0.9 to 1.0
        self.leakage_label.setText(f"{leakage:.3f}")
        
        # 更新LMS滤波器参数
        self.update_lms_parameters()
    
    def on_lms_params_changed(self):
        """LMS参数改变"""
        self.update_lms_parameters()
    
    def on_auto_adjust_toggled(self, checked):
        """自动调整切换"""
        status = "启用" if checked else "禁用"
        print(f"LMS自动参数调整已{status}")
    
    def update_lms_parameters(self):
        """更新LMS滤波器参数"""
        if not self.filter_enabled:
            return
        
        step_size = self.step_size_slider.value() / 1000.0
        leakage = self.leakage_slider.value() / 1000.0
        
        for processor in self.noise_processors.values():
            if processor and hasattr(processor, 'lms_filter') and processor.lms_filter:
                processor.lms_filter.update_parameters(step_size, leakage)
    
    def setup_noise_processors(self):
        """设置噪声处理器"""
        if not DualPathProcessor:
            print("警告: DualPathProcessor未可用，无法创建噪声处理器")
            return
        
        selected_devices = self.get_selected_devices()
        if len(selected_devices) < 2:
            print("警告: 需要至少2个设备才能进行噪声处理")
            return
        
        # 获取当前抑制模式
        current_mode = self.suppression_mode_combo.currentData()
        if not current_mode:
            current_mode = NoiseSuppressionMode.RATIO if NoiseSuppressionMode else None
        
        # 为每个设备创建处理器
        for device_id in selected_devices:
            if device_id not in self.noise_processors:
                try:
                    processor = DualPathProcessor(
                        suppression_mode=current_mode,
                        buffer_size=500,
                        enable_auto_calibration=True
                    )
                    
                    # 设置回调函数
                    def status_callback(msg, dev_id=device_id):
                        print(f"处理器 {dev_id}: {msg}")
                    
                    processor.set_callbacks(status_callback=status_callback)
                    
                    self.noise_processors[device_id] = processor
                    print(f"为设备 {device_id} 创建噪声处理器")
                    
                except Exception as e:
                    print(f"创建设备 {device_id} 的处理器失败: {e}")
        
        # 自动配对设备
        self.auto_pair_devices()
    
    def add_device_pairing(self):
        """添加设备配对"""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("添加设备配对")
        layout = QFormLayout(dialog)
        
        # 主信号设备选择
        main_combo = QComboBox()
        selected_devices = self.get_selected_devices()
        main_combo.addItems(selected_devices)
        layout.addRow("主信号设备:", main_combo)
        
        # 参考信号设备选择
        ref_combo = QComboBox()
        ref_combo.addItems(selected_devices)
        layout.addRow("参考信号设备:", ref_combo)
        
        # 确认按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec() == QDialog.Accepted:
            main_device = main_combo.currentText()
            ref_device = ref_combo.currentText()
            
            if main_device != ref_device:
                self.add_pairing_to_table(main_device, ref_device)
                self.main_reference_mapping[main_device] = ref_device
                print(f"添加配对: {main_device} -> {ref_device}")
    
    def add_pairing_to_table(self, main_device, ref_device, status="活动"):
        """添加配对到表格"""
        row = self.device_pairing_table.rowCount()
        self.device_pairing_table.insertRow(row)
        
        self.device_pairing_table.setItem(row, 0, QTableWidgetItem(main_device))
        self.device_pairing_table.setItem(row, 1, QTableWidgetItem(ref_device))
        self.device_pairing_table.setItem(row, 2, QTableWidgetItem(status))
    
    def remove_device_pairing(self):
        """删除设备配对"""
        current_row = self.device_pairing_table.currentRow()
        if current_row >= 0:
            # 获取要删除的配对
            main_device = self.device_pairing_table.item(current_row, 0).text()
            
            # 从映射中删除
            if main_device in self.main_reference_mapping:
                del self.main_reference_mapping[main_device]
            
            # 从表格中删除
            self.device_pairing_table.removeRow(current_row)
            print(f"删除配对: {main_device}")
    
    def auto_pair_devices(self):
        """自动配对设备"""
        selected_devices = self.get_selected_devices()
        
        # 清空现有配对
        self.device_pairing_table.setRowCount(0)
        self.main_reference_mapping.clear()
        
        if len(selected_devices) >= 2:
            # 简单策略：第一个设备作为主信号，第二个作为参考
            for i in range(0, len(selected_devices), 2):
                if i + 1 < len(selected_devices):
                    main_device = selected_devices[i]
                    ref_device = selected_devices[i + 1]
                    
                    self.add_pairing_to_table(main_device, ref_device)
                    self.main_reference_mapping[main_device] = ref_device
            
            print(f"自动配对完成: {len(self.main_reference_mapping)} 对设备")
    
    def start_calibration(self):
        """开始系统标定"""
        if not self.noise_processors:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "标定失败", "请先启用噪声滤波系统")
            return
        
        self.calibration_button.setEnabled(False)
        self.calibration_progress.setVisible(True)
        self.calibration_progress.setRange(0, 100)
        
        # 模拟标定过程
        self.calibration_timer = QTimer()
        self.calibration_progress_value = 0
        
        def update_calibration():
            self.calibration_progress_value += 10
            self.calibration_progress.setValue(self.calibration_progress_value)
            
            if self.calibration_progress_value >= 100:
                self.calibration_timer.stop()
                self.calibration_button.setEnabled(True)
                self.calibration_progress.setVisible(False)
                self.calibration_status_label.setText("标定状态: 标定完成")
                self.calibration_status_label.setStyleSheet("font-size: 10px; color: #2E7D32; font-weight: bold;")
                print("系统标定完成")
        
        self.calibration_timer.timeout.connect(update_calibration)
        self.calibration_timer.start(500)  # 每500ms更新一次
        
        print("开始系统标定...")
    
    def reset_lms_filters(self):
        """重置LMS滤波器"""
        for processor in self.noise_processors.values():
            if processor and hasattr(processor, 'lms_filter') and processor.lms_filter:
                processor.lms_filter.reset()
        
        print("LMS滤波器已重置")
    
    def test_lms_filters(self):
        """测试LMS滤波器"""
        if not self.noise_processors:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "测试滤波器", "没有可测试的滤波器")
            return
        
        # 生成测试信号并显示结果
        import numpy as np
        
        test_results = []
        for device_id, processor in self.noise_processors.items():
            if processor:
                # 生成测试信号
                test_main = np.random.randn(100) * 0.1 + 1.0  # 主信号
                test_ref = np.random.randn(100) * 0.05  # 参考信号（噪声）
                
                # 测试滤波
                filtered_results = []
                for main, ref in zip(test_main, test_ref):
                    filtered, _ = processor.process_sample(main, ref)
                    filtered_results.append(filtered)
                
                # 计算改善
                original_std = np.std(test_main)
                filtered_std = np.std(filtered_results)
                improvement = 20 * np.log10(original_std / filtered_std) if filtered_std > 0 else 0
                
                test_results.append(f"{device_id}: {improvement:.1f}dB")
        
        from PySide6.QtWidgets import QMessageBox
        result_text = "滤波器测试结果:\n" + "\n".join(test_results)
        QMessageBox.information(self, "滤波器测试", result_text)
    
    def update_filter_performance(self):
        """更新滤波性能显示"""
        if not self.filter_enabled or not self.noise_processors:
            return
        
        try:
            # 收集所有处理器的性能数据
            total_snr = 0.0
            total_noise_reduction = 0.0
            converged_count = 0
            total_processors = 0
            
            stats_lines = []
            
            for device_id, processor in self.noise_processors.items():
                if processor:
                    summary = processor.get_performance_summary()
                    
                    snr = summary.get('snr_improvement', 0.0)
                    noise_reduction = summary.get('noise_reduction_ratio', 0.0)
                    
                    total_snr += snr
                    total_noise_reduction += noise_reduction
                    total_processors += 1
                    
                    # 检查LMS收敛状态
                    if 'lms_metrics' in summary and summary['lms_metrics'].get('is_converged', False):
                        converged_count += 1
                    
                    # 添加统计信息
                    stats_lines.append(
                        f"{device_id}: SNR+{snr:.1f}dB, "
                        f"降噪{noise_reduction*100:.1f}%, "
                        f"样本{summary.get('sample_count', 0)}"
                    )
            
            if total_processors > 0:
                # 更新平均指标
                avg_snr = total_snr / total_processors
                avg_noise_reduction = total_noise_reduction / total_processors
                
                self.snr_value_label.setText(f"{avg_snr:.1f} dB")
                self.noise_reduction_label.setText(f"{avg_noise_reduction*100:.1f}%")
                
                # 更新收敛状态
                if converged_count == total_processors:
                    self.convergence_label.setText("已收敛")
                    self.convergence_label.setStyleSheet("color: #2E7D32; font-weight: bold;")
                elif converged_count > 0:
                    self.convergence_label.setText(f"部分收敛 ({converged_count}/{total_processors})")
                    self.convergence_label.setStyleSheet("color: #FF9800; font-weight: bold;")
                else:
                    self.convergence_label.setText("收敛中")
                    self.convergence_label.setStyleSheet("color: #2196F3; font-style: italic;")
                
                # 更新统计文本
                self.processing_stats_text.setText("\n".join(stats_lines))
            
        except Exception as e:
            print(f"更新滤波性能失败: {e}")
    
    def export_filter_data(self):
        """导出滤波数据"""
        from PySide6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出滤波数据", "PM100D_滤波数据.csv",
            "CSV files (*.csv);;All files (*.*)"
        )
        
        if file_path and self.plot_widget:
            success = self.plot_widget.export_data(file_path)
            if success:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, "导出成功", f"滤波数据已导出到:\n{file_path}")
    
    def export_performance_report(self):
        """导出性能报告"""
        from PySide6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出性能报告", "PM100D_滤波性能报告.txt",
            "Text files (*.txt);;All files (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("PM100D 噪声滤波性能报告\n")
                    f.write("=" * 50 + "\n\n")
                    
                    # 系统配置信息
                    f.write("系统配置:\n")
                    f.write(f"  滤波模式: {self.suppression_mode_combo.currentText()}\n")
                    f.write(f"  LMS学习率: {self.step_size_label.text()}\n")
                    f.write(f"  泄漏因子: {self.leakage_label.text()}\n")
                    f.write(f"  滤波器长度: {self.filter_length_spinbox.value()}\n\n")
                    
                    # 设备配对信息
                    f.write("设备配对:\n")
                    for main_dev, ref_dev in self.main_reference_mapping.items():
                        f.write(f"  {main_dev} -> {ref_dev}\n")
                    f.write("\n")
                    
                    # 性能指标
                    f.write("性能指标:\n")
                    f.write(f"  平均SNR改善: {self.snr_value_label.text()}\n")
                    f.write(f"  平均噪声抑制率: {self.noise_reduction_label.text()}\n")
                    f.write(f"  收敛状态: {self.convergence_label.text()}\n\n")
                    
                    # 详细统计
                    f.write("详细统计:\n")
                    f.write(self.processing_stats_text.toPlainText())
                
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, "导出成功", f"性能报告已导出到:\n{file_path}")
                
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "导出失败", f"导出性能报告失败:\n{str(e)}")

