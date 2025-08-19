#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
左侧面板 - 设备管理界面
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem, QGroupBox, QComboBox,
    QMessageBox, QProgressBar, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from instrument.pm100d import PM100D, rm
import pyvisa


class DeviceSearchThread(QThread):
    """设备搜索线程"""
    devices_found = Signal(list)
    search_finished = Signal()
    
    def run(self):
        """搜索可用的PM100D设备"""
        try:
            # 获取所有可用的VISA资源
            resources = rm.list_resources()
            pm100d_devices = []
            
            for resource in resources:
                try:
                    # 尝试连接并检查是否为PM100D
                    temp_inst = rm.open_resource(resource)
                    temp_inst.timeout = 1000  # 短超时用于快速检测
                    
                    idn = temp_inst.query("*IDN?").strip()
                    if "PM100D" in idn.upper():
                        pm100d_devices.append({
                            'resource': resource,
                            'idn': idn
                        })
                    
                    temp_inst.close()
                    
                except Exception:
                    # 连接失败或不是目标设备，继续下一个
                    continue
            
            self.devices_found.emit(pm100d_devices)
            
        except Exception as e:
            print(f"搜索设备时出错: {e}")
        finally:
            self.search_finished.emit()


class LeftPanel(QWidget):
    """左侧面板类 - 设备管理"""
    
    # 信号定义
    device_connected = Signal(str, object)  # 设备ID, PM100D对象
    device_disconnected = Signal(str)       # 设备ID
    
    def __init__(self):
        super().__init__()
        self.connected_devices = {}  # 存储已连接的设备
        self.search_thread = None
        
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 标题
        title_label = QLabel("设备管理")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # 设备搜索区域
        self.create_search_section(layout)
        
        # 设备列表区域
        self.create_device_list_section(layout)
        
        # 设备信息区域
        self.create_device_info_section(layout)
        
        layout.addStretch()  # 添加弹性空间
        
    def create_search_section(self, parent_layout):
        """创建设备搜索区域"""
        search_group = QGroupBox("设备搜索")
        search_layout = QVBoxLayout(search_group)
        
        # 搜索按钮和进度条布局
        search_control_layout = QHBoxLayout()
        
        self.search_button = QPushButton("搜索PM100D设备")
        self.search_button.clicked.connect(self.search_devices)
        search_control_layout.addWidget(self.search_button)
        
        self.search_progress = QProgressBar()
        self.search_progress.setVisible(False)
        search_control_layout.addWidget(self.search_progress)
        
        search_layout.addLayout(search_control_layout)
        
        # 可用设备下拉框
        device_select_layout = QHBoxLayout()
        device_select_layout.addWidget(QLabel("可用设备:"))
        
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(200)
        device_select_layout.addWidget(self.device_combo)
        
        search_layout.addLayout(device_select_layout)
        
        # 连接按钮
        self.connect_button = QPushButton("连接设备")
        self.connect_button.clicked.connect(self.connect_device)
        self.connect_button.setEnabled(False)
        search_layout.addWidget(self.connect_button)
        
        parent_layout.addWidget(search_group)
        
    def create_device_list_section(self, parent_layout):
        """创建已连接设备列表区域"""
        device_list_group = QGroupBox("已连接设备")
        device_list_layout = QVBoxLayout(device_list_group)
        
        self.device_list = QListWidget()
        self.device_list.setMaximumHeight(150)
        self.device_list.itemSelectionChanged.connect(self.on_device_selection_changed)
        device_list_layout.addWidget(self.device_list)
        
        # 设备操作按钮
        device_buttons_layout = QHBoxLayout()
        
        self.disconnect_button = QPushButton("断开连接")
        self.disconnect_button.clicked.connect(self.disconnect_device)
        self.disconnect_button.setEnabled(False)
        device_buttons_layout.addWidget(self.disconnect_button)
        
        self.refresh_button = QPushButton("刷新状态")
        self.refresh_button.clicked.connect(self.refresh_device_status)
        self.refresh_button.setEnabled(False)
        device_buttons_layout.addWidget(self.refresh_button)
        
        device_list_layout.addLayout(device_buttons_layout)
        
        parent_layout.addWidget(device_list_group)
        
    def create_device_info_section(self, parent_layout):
        """创建设备信息显示区域"""
        info_group = QGroupBox("设备信息")
        info_layout = QVBoxLayout(info_group)
        
        self.info_label = QLabel("未选择设备")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("QLabel { padding: 10px; background-color: #f0f0f0; border: 1px solid #ccc; }")
        info_layout.addWidget(self.info_label)
        
        parent_layout.addWidget(info_group)
        
    def search_devices(self):
        """搜索PM100D设备"""
        if self.search_thread and self.search_thread.isRunning():
            return
            
        self.search_button.setEnabled(False)
        self.search_progress.setVisible(True)
        self.search_progress.setRange(0, 0)  # 不确定进度
        self.device_combo.clear()
        
        # 启动搜索线程
        self.search_thread = DeviceSearchThread()
        self.search_thread.devices_found.connect(self.on_devices_found)
        self.search_thread.search_finished.connect(self.on_search_finished)
        self.search_thread.start()
        
    def on_devices_found(self, devices):
        """处理找到的设备"""
        self.device_combo.clear()
        
        if not devices:
            self.device_combo.addItem("未找到PM100D设备")
            self.connect_button.setEnabled(False)
        else:
            for device in devices:
                display_name = f"{device['resource']} ({device['idn'].split(',')[0]})"
                self.device_combo.addItem(display_name)
                self.device_combo.setItemData(self.device_combo.count() - 1, device)
            self.connect_button.setEnabled(True)
            
    def on_search_finished(self):
        """搜索完成处理"""
        self.search_button.setEnabled(True)
        self.search_progress.setVisible(False)
        
    def connect_device(self):
        """连接选中的设备"""
        if self.device_combo.count() == 0:
            return
            
        current_index = self.device_combo.currentIndex()
        device_data = self.device_combo.itemData(current_index)
        
        if not device_data:
            QMessageBox.warning(self, "连接失败", "请先搜索设备")
            return
            
        try:
            # 创建PM100D实例
            pm100d = PM100D(device_data['resource'])
            
            # 生成设备ID
            device_id = f"PM100D_{len(self.connected_devices) + 1}"
            
            # 存储设备
            self.connected_devices[device_id] = {
                'device': pm100d,
                'resource': device_data['resource'],
                'idn': device_data['idn']
            }
            
            # 添加到设备列表
            list_item = QListWidgetItem(f"{device_id} ({device_data['resource']})")
            list_item.setData(Qt.UserRole, device_id)
            self.device_list.addItem(list_item)
            
            # 发送连接信号
            self.device_connected.emit(device_id, pm100d)
            
            QMessageBox.information(self, "连接成功", f"已成功连接到设备: {device_id}")
            
        except Exception as e:
            QMessageBox.critical(self, "连接失败", f"连接设备失败: {str(e)}")
            
    def disconnect_device(self):
        """断开选中的设备"""
        current_item = self.device_list.currentItem()
        if not current_item:
            return
            
        device_id = current_item.data(Qt.UserRole)
        
        try:
            # 关闭设备连接
            if device_id in self.connected_devices:
                self.connected_devices[device_id]['device'].close()
                del self.connected_devices[device_id]
                
            # 从列表中移除
            row = self.device_list.row(current_item)
            self.device_list.takeItem(row)
            
            # 发送断开连接信号
            self.device_disconnected.emit(device_id)
            
            # 清空信息显示
            self.info_label.setText("未选择设备")
            self.disconnect_button.setEnabled(False)
            self.refresh_button.setEnabled(False)
            
            QMessageBox.information(self, "断开连接", f"已断开设备: {device_id}")
            
        except Exception as e:
            QMessageBox.critical(self, "断开失败", f"断开设备失败: {str(e)}")
            
    def on_device_selection_changed(self):
        """设备选择改变处理"""
        current_item = self.device_list.currentItem()
        
        if current_item:
            device_id = current_item.data(Qt.UserRole)
            self.update_device_info(device_id)
            self.disconnect_button.setEnabled(True)
            self.refresh_button.setEnabled(True)
        else:
            self.info_label.setText("未选择设备")
            self.disconnect_button.setEnabled(False)
            self.refresh_button.setEnabled(False)
            
    def update_device_info(self, device_id):
        """更新设备信息显示"""
        if device_id not in self.connected_devices:
            self.info_label.setText("设备信息不可用")
            return
            
        try:
            device_info = self.connected_devices[device_id]
            pm100d = device_info['device']
            
            # 获取设备详细信息
            sensor_info = pm100d.getSensorInfo()
            wavelength = pm100d.getWavelength()
            bandwidth = pm100d.getBandwidth()
            avg_count = pm100d.getAvgCount()
            range_auto = pm100d.getRangeAuto()
            
            info_text = f"""
设备ID: {device_id}
资源地址: {device_info['resource']}
设备标识: {device_info['idn']}

传感器信息:
  型号: {sensor_info['name']}
  序列号: {sensor_info['serial_number']}
  类型: {sensor_info['type']} / {sensor_info['subtype']}

当前配置:
  波长: {wavelength:.0f} nm
  带宽: {bandwidth}
  平均次数: {avg_count}
  自动量程: {'开启' if range_auto else '关闭'}
            """.strip()
            
            self.info_label.setText(info_text)
            
        except Exception as e:
            self.info_label.setText(f"获取设备信息失败: {str(e)}")
            
    def refresh_device_status(self):
        """刷新当前选中设备的状态"""
        current_item = self.device_list.currentItem()
        if current_item:
            device_id = current_item.data(Qt.UserRole)
            self.update_device_info(device_id)
            
    def get_connected_devices(self):
        """获取所有已连接的设备"""
        return self.connected_devices.copy()
        
    def closeEvent(self, event):
        """窗口关闭时清理资源"""
        # 断开所有设备连接
        for device_id in list(self.connected_devices.keys()):
            try:
                self.connected_devices[device_id]['device'].close()
            except:
                pass
        
        # 停止搜索线程
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.quit()
            self.search_thread.wait()
            
        event.accept()
