#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
左侧面板 - 设备管理界面
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem, QGroupBox, QComboBox,
    QMessageBox, QProgressBar, QFrame, QCheckBox, QTabWidget
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QIcon

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from instrument.pm100d import PM100D, rm
from utils.device_cache import DeviceCache
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


class QuickConnectThread(QThread):
    """快速连接线程"""
    connection_result = Signal(str, bool, object, str)  # 资源地址, 成功/失败, 设备对象, 错误信息
    connection_finished = Signal()
    
    def __init__(self, cached_devices):
        super().__init__()
        self.cached_devices = cached_devices
        self.connected_devices = []
        
    def run(self):
        """尝试快速连接缓存的设备"""
        print(f"开始快速连接 {len(self.cached_devices)} 个缓存设备")
        
        for device_info in self.cached_devices:
            resource = device_info['resource']
            try:
                print(f"尝试连接缓存设备: {resource}")
                
                # 创建PM100D实例
                pm100d = PM100D(resource)
                
                # 验证设备响应
                idn_response = pm100d.write("*IDN?", q=True).strip()
                
                self.connection_result.emit(resource, True, pm100d, "")
                self.connected_devices.append((resource, pm100d))
                print(f"成功连接到缓存设备: {resource}")
                
            except Exception as e:
                error_msg = str(e)
                print(f"连接缓存设备失败 {resource}: {error_msg}")
                self.connection_result.emit(resource, False, None, error_msg)
        
        self.connection_finished.emit()


class LeftPanel(QWidget):
    """左侧面板类 - 设备管理"""
    
    # 信号定义
    device_connected = Signal(str, object)  # 设备ID, PM100D对象
    device_disconnected = Signal(str)       # 设备ID
    
    def __init__(self):
        super().__init__()
        self.connected_devices = {}  # 存储已连接的设备
        self.search_thread = None
        self.quick_connect_thread = None
        
        # 初始化设备缓存管理器
        self.device_cache = DeviceCache()
        
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
        
        # 创建选项卡界面
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 快速连接选项卡
        self.create_quick_connect_tab()
        
        # 设备搜索选项卡
        self.create_device_search_tab()
        
        # 设备列表区域
        self.create_device_list_section(layout)
        
        # 设备信息区域
        self.create_device_info_section(layout)
        
        layout.addStretch()  # 添加弹性空间
    
    def create_quick_connect_tab(self):
        """创建快速连接选项卡"""
        quick_tab = QWidget()
        layout = QVBoxLayout(quick_tab)
        
        # 快速连接说明
        info_label = QLabel("快速连接会尝试连接之前成功连接过的设备")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(info_label)
        
        # 缓存设备列表
        self.cached_device_combo = QComboBox()
        self.cached_device_combo.setMinimumWidth(250)
        layout.addWidget(QLabel("缓存设备:"))
        layout.addWidget(self.cached_device_combo)
        
        # 快速连接按钮
        quick_connect_layout = QHBoxLayout()
        
        self.quick_connect_button = QPushButton("快速连接选中")
        self.quick_connect_button.clicked.connect(self.quick_connect_selected)
        quick_connect_layout.addWidget(self.quick_connect_button)
        
        self.quick_connect_all_button = QPushButton("连接所有缓存")
        self.quick_connect_all_button.clicked.connect(self.quick_connect_all)
        quick_connect_layout.addWidget(self.quick_connect_all_button)
        
        layout.addLayout(quick_connect_layout)
        
        # 快速连接进度条
        self.quick_progress = QProgressBar()
        self.quick_progress.setVisible(False)
        layout.addWidget(self.quick_progress)
        
        # 缓存管理按钮
        cache_layout = QHBoxLayout()
        
        self.refresh_cache_button = QPushButton("刷新缓存")
        self.refresh_cache_button.clicked.connect(self.refresh_cached_devices)
        cache_layout.addWidget(self.refresh_cache_button)
        
        self.clear_cache_button = QPushButton("清空缓存")
        self.clear_cache_button.clicked.connect(self.clear_device_cache)
        cache_layout.addWidget(self.clear_cache_button)
        
        layout.addLayout(cache_layout)
        
        # 缓存统计信息
        self.cache_stats_label = QLabel("缓存统计：")
        self.cache_stats_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.cache_stats_label)
        
        layout.addStretch()
        
        self.tab_widget.addTab(quick_tab, "快速连接")
        
        # 初始化缓存设备列表
        self.refresh_cached_devices()
    
    def create_device_search_tab(self):
        """创建设备搜索选项卡"""
        search_tab = QWidget()
        layout = QVBoxLayout(search_tab)
        
        # 搜索说明
        info_label = QLabel("搜索会扫描所有VISA设备并识别PM100D设备")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(info_label)
        
        # 搜索按钮和进度条
        search_control_layout = QHBoxLayout()
        
        self.search_button = QPushButton("搜索PM100D设备")
        self.search_button.clicked.connect(self.search_devices)
        search_control_layout.addWidget(self.search_button)
        
        self.search_progress = QProgressBar()
        self.search_progress.setVisible(False)
        search_control_layout.addWidget(self.search_progress)
        
        layout.addLayout(search_control_layout)
        
        # 可用设备下拉框
        layout.addWidget(QLabel("搜索到的设备:"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(250)
        layout.addWidget(self.device_combo)
        
        # 连接按钮
        self.connect_button = QPushButton("连接设备")
        self.connect_button.clicked.connect(self.connect_device)
        self.connect_button.setEnabled(False)
        layout.addWidget(self.connect_button)
        
        layout.addStretch()
        
        self.tab_widget.addTab(search_tab, "设备搜索")
        
    def refresh_cached_devices(self):
        """刷新缓存设备列表"""
        self.cached_device_combo.clear()
        cached_devices = self.device_cache.get_priority_devices(10)  # 获取前10个优先设备
        
        if not cached_devices:
            self.cached_device_combo.addItem("没有缓存设备")
            self.quick_connect_button.setEnabled(False)
            self.quick_connect_all_button.setEnabled(False)
        else:
            for device in cached_devices:
                display_name = f"{device['resource']} (连接{device['connection_count']}次)"
                self.cached_device_combo.addItem(display_name)
                self.cached_device_combo.setItemData(self.cached_device_combo.count() - 1, device)
            
            self.quick_connect_button.setEnabled(True)
            self.quick_connect_all_button.setEnabled(True)
        
        # 更新缓存统计
        stats = self.device_cache.get_cache_stats()
        stats_text = f"缓存统计：{stats['total_devices']}个设备，平均成功率{stats['avg_success_rate']:.1%}"
        self.cache_stats_label.setText(stats_text)
    
    def quick_connect_selected(self):
        """快速连接选中的缓存设备"""
        if self.cached_device_combo.count() == 0:
            return
        
        current_index = self.cached_device_combo.currentIndex()
        device_data = self.cached_device_combo.itemData(current_index)
        
        if not device_data:
            QMessageBox.warning(self, "快速连接失败", "请选择一个有效的缓存设备")
            return
        
        self.start_quick_connect([device_data])
    
    def quick_connect_all(self):
        """快速连接所有缓存设备"""
        cached_devices = self.device_cache.get_priority_devices(10)
        if not cached_devices:
            QMessageBox.information(self, "快速连接", "没有可连接的缓存设备")
            return
        
        self.start_quick_connect(cached_devices)
    
    def start_quick_connect(self, devices_to_connect):
        """开始快速连接过程"""
        if self.quick_connect_thread and self.quick_connect_thread.isRunning():
            return
        
        print(f"开始快速连接 {len(devices_to_connect)} 个设备")
        
        # 禁用相关按钮
        self.quick_connect_button.setEnabled(False)
        self.quick_connect_all_button.setEnabled(False)
        
        # 显示进度条
        self.quick_progress.setVisible(True)
        self.quick_progress.setRange(0, len(devices_to_connect))
        self.quick_progress.setValue(0)
        
        # 启动快速连接线程
        self.quick_connect_thread = QuickConnectThread(devices_to_connect)
        self.quick_connect_thread.connection_result.connect(self.on_quick_connect_result)
        self.quick_connect_thread.connection_finished.connect(self.on_quick_connect_finished)
        self.quick_connect_thread.start()
    
    def on_quick_connect_result(self, resource, success, device, error_msg):
        """处理快速连接结果"""
        # 更新进度条
        self.quick_progress.setValue(self.quick_progress.value() + 1)
        
        # 更新设备缓存的连接统计
        self.device_cache.update_connection_result(resource, success)
        
        if success:
            try:
                # 生成设备ID
                device_id = f"PM100D_{len(self.connected_devices) + 1}"
                
                # 获取设备信息
                idn_response = device.write("*IDN?", q=True).strip()
                
                # 存储设备
                self.connected_devices[device_id] = {
                    'device': device,
                    'resource': resource,
                    'idn': idn_response
                }
                
                # 添加到设备列表
                list_item = QListWidgetItem(f"{device_id} ({resource}) [缓存]")
                list_item.setData(Qt.UserRole, device_id)
                self.device_list.addItem(list_item)
                
                # 发送连接信号
                self.device_connected.emit(device_id, device)
                
                # 更新多设备状态概览
                self.update_device_overview()
                
                print(f"快速连接成功: {device_id} ({resource})")
                
            except Exception as e:
                print(f"快速连接后处理失败: {e}")
                if hasattr(device, 'close'):
                    device.close()
        else:
            print(f"快速连接失败: {resource} - {error_msg}")
    
    def on_quick_connect_finished(self):
        """快速连接完成处理"""
        # 隐藏进度条
        self.quick_progress.setVisible(False)
        
        # 重新启用按钮
        self.quick_connect_button.setEnabled(True)
        self.quick_connect_all_button.setEnabled(True)
        
        # 显示连接结果
        connected_count = len([item for item in self.quick_connect_thread.connected_devices])
        total_count = len(self.quick_connect_thread.cached_devices)
        
        if connected_count > 0:
            QMessageBox.information(
                self, "快速连接完成", 
                f"成功连接 {connected_count}/{total_count} 个缓存设备"
            )
        else:
            QMessageBox.warning(
                self, "快速连接完成", 
                "没有成功连接任何缓存设备\n建议使用设备搜索功能"
            )
        
        # 刷新缓存列表（更新连接统计）
        self.refresh_cached_devices()
    
    def clear_device_cache(self):
        """清空设备缓存"""
        reply = QMessageBox.question(
            self, '确认操作', 
            '确定要清空所有设备缓存吗？\n这将删除所有已保存的设备连接信息。',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.device_cache.clear_cache():
                self.refresh_cached_devices()
                QMessageBox.information(self, "操作完成", "设备缓存已清空")
            else:
                QMessageBox.warning(self, "操作失败", "清空设备缓存失败")
        
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
        
        # 选中设备的详细信息
        self.info_label = QLabel("未选择设备")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("QLabel { padding: 10px; background-color: #f0f0f0; border: 1px solid #ccc; }")
        info_layout.addWidget(self.info_label)
        
        # 多设备状态概览
        overview_frame = QFrame()
        overview_frame.setFrameStyle(QFrame.Box)
        overview_layout = QVBoxLayout(overview_frame)
        
        overview_title = QLabel("多设备状态概览")
        overview_title.setStyleSheet("font-weight: bold; color: #333;")
        overview_layout.addWidget(overview_title)
        
        self.device_overview_label = QLabel("暂无连接设备")
        self.device_overview_label.setWordWrap(True)
        self.device_overview_label.setStyleSheet("QLabel { padding: 5px; font-size: 11px; color: #666; }")
        overview_layout.addWidget(self.device_overview_label)
        
        # 快速操作按钮
        quick_ops_layout = QHBoxLayout()
        
        self.test_all_button = QPushButton("测试所有连接")
        self.test_all_button.clicked.connect(self.test_all_connections)
        self.test_all_button.setEnabled(False)
        self.test_all_button.setToolTip("测试所有连接设备的通信状态")
        quick_ops_layout.addWidget(self.test_all_button)
        
        self.refresh_all_button = QPushButton("刷新所有状态")
        self.refresh_all_button.clicked.connect(self.refresh_all_devices)
        self.refresh_all_button.setEnabled(False)
        self.refresh_all_button.setToolTip("刷新所有设备的状态信息")
        quick_ops_layout.addWidget(self.refresh_all_button)
        
        overview_layout.addLayout(quick_ops_layout)
        info_layout.addWidget(overview_frame)
        
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
        
        print(f"尝试连接设备: {device_data['resource']}")
        print(f"设备IDN: {device_data['idn']}")
            
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
            
            # 更新多设备状态概览
            self.update_device_overview()
            
            # 将设备信息添加到缓存
            try:
                sensor_info = pm100d.getSensorInfo()
                additional_info = {
                    'sensor_name': sensor_info.get('name', ''),
                    'sensor_serial': sensor_info.get('serial_number', ''),
                    'sensor_type': sensor_info.get('type', ''),
                    'connection_method': 'manual_search'  # 标记为手动搜索连接
                }
                
                self.device_cache.add_device(
                    device_data['resource'], 
                    device_data['idn'], 
                    additional_info
                )
                
                # 更新连接成功状态
                self.device_cache.update_connection_result(device_data['resource'], True)
                
                print(f"设备已添加到缓存: {device_data['resource']}")
                
                # 刷新缓存列表
                self.refresh_cached_devices()
                
            except Exception as cache_error:
                print(f"添加设备到缓存失败: {cache_error}")
                # 缓存失败不影响设备连接
            
            print(f"设备 {device_id} 连接成功完成")
            QMessageBox.information(self, "连接成功", f"已成功连接到设备: {device_id}\n设备信息已保存到缓存")
            
        except Exception as e:
            # 更新连接失败状态到缓存
            try:
                self.device_cache.update_connection_result(device_data['resource'], False)
            except:
                pass
            
            error_msg = f"连接设备失败:\n\n错误详情: {str(e)}\n\n可能原因:\n"
            error_msg += "1. 设备正在被其他程序使用\n"
            error_msg += "2. 设备响应超时\n"
            error_msg += "3. VISA驱动问题\n"
            error_msg += "4. 设备硬件故障\n\n"
            error_msg += "建议:\n"
            error_msg += "• 关闭其他可能使用该设备的程序\n"
            error_msg += "• 重新连接USB线缆\n"
            error_msg += "• 检查设备电源状态"
            
            print(f"设备连接失败: {e}")
            QMessageBox.critical(self, "设备连接失败", error_msg)
            
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
            
            # 更新多设备状态概览
            self.update_device_overview()
            
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
        
    def update_device_overview(self):
        """更新多设备状态概览"""
        if not self.connected_devices:
            self.device_overview_label.setText("暂无连接设备")
            self.test_all_button.setEnabled(False)
            self.refresh_all_button.setEnabled(False)
            return
        
        device_count = len(self.connected_devices)
        overview_text = f"已连接 {device_count} 个设备:\n"
        
        for device_id, device_info in self.connected_devices.items():
            try:
                # 尝试获取基本状态信息
                device = device_info['device']
                wavelength = device.getWavelength()
                bandwidth = device.getBandwidth()
                overview_text += f"• {device_id}: λ={wavelength:.0f}nm, BW={bandwidth}\n"
            except Exception:
                overview_text += f"• {device_id}: 通信异常\n"
        
        self.device_overview_label.setText(overview_text.strip())
        self.test_all_button.setEnabled(True)
        self.refresh_all_button.setEnabled(True)
        
    def test_all_connections(self):
        """测试所有设备的连接状态"""
        if not self.connected_devices:
            return
            
        healthy_devices = []
        failed_devices = []
        
        for device_id, device_info in self.connected_devices.items():
            try:
                device = device_info['device']
                # 简单的通信测试
                idn = device.write("*IDN?", q=True)
                if idn:
                    healthy_devices.append(device_id)
                else:
                    failed_devices.append(device_id)
            except Exception as e:
                failed_devices.append(device_id)
                print(f"设备 {device_id} 连接测试失败: {e}")
        
        # 显示测试结果
        from PySide6.QtWidgets import QMessageBox
        if failed_devices:
            msg = f"连接测试完成！\n\n正常: {len(healthy_devices)} 个设备\n异常: {len(failed_devices)} 个设备\n\n异常设备: {', '.join(failed_devices)}"
            QMessageBox.warning(self, "连接测试", msg)
        else:
            QMessageBox.information(self, "连接测试", f"所有 {len(healthy_devices)} 个设备连接正常！")
            
        # 更新状态概览
        self.update_device_overview()
    
    def refresh_all_devices(self):
        """刷新所有设备状态"""
        for device_id in self.connected_devices.keys():
            self.update_device_info(device_id)
        
        # 更新状态概览
        self.update_device_overview()
        
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "状态刷新", f"已刷新所有 {len(self.connected_devices)} 个设备的状态信息")
        
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
