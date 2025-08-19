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
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
import time


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
        """采集数据（只采集选中设备的数据）"""
        current_time = time.time()
        selected_devices = self.get_selected_devices()
        
        if not selected_devices:
            print("没有选中设备，停止数据采集")
            self.stop_acquisition()
            return
            
        print(f"开始数据采集 - 时间戳: {current_time}")
        print(f"选中设备数量: {len(selected_devices)}")
        
        # 只采集选中设备的数据
        for device_id in selected_devices:
            if device_id not in self.connected_devices:
                print(f"设备 {device_id} 已断开连接，跳过采集")
                continue
                
            try:
                print(f"正在采集设备 {device_id} 的数据...")
                device_info = self.connected_devices[device_id]
                power = device_info['device'].getPower()
                print(f"设备 {device_id} 功率值: {power:.6e} W")
                
                # 更新实时显示（显示第一个选中设备的功率）
                if device_id == selected_devices[0]:
                    self.power_label.setText(f"{power:.6e} W")
                
                # 添加到数据表格
                self.add_data_to_table(current_time, device_id, power)
                
                # 发送数据到绘图组件
                if self.plot_widget is not None:
                    print(f"向 plot_widget 添加数据: 设备={device_id}, 时间={current_time}, 功率={power:.6e}")
                    self.plot_widget.add_device_data(device_id, current_time, power)
                    
                    # 验证数据是否成功添加
                    if hasattr(self.plot_widget, 'power_data'):
                        device_data_count = len(self.plot_widget.power_data.get(device_id, []))
                        print(f"设备 {device_id} 当前数据点数: {device_data_count}")
                else:
                    print(f"错误: plot_widget 引用为空，无法保存数据到图形组件")
                
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
            

