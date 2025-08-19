from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QSplitter, QMenuBar, QMenu, QStatusBar, QMessageBox,
    QFileDialog, QProgressBar, QLabel
)
from PySide6.QtGui import QAction, QIcon, QDragEnterEvent, QDropEvent, QCloseEvent
from PySide6.QtCore import Qt, QTimer

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from instrument.pm100d import PM100D
from .left_panel import LeftPanel
from .plot_widget import PlotWidget
from .right_panel import RightPanel


class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        self.current_file_path = None
        
        # 存储设备连接
        self.pm100ds = {}

        self.init_ui()
        self.connect_data_signals()
        
        # 延迟启动自动连接（给界面一些时间完成初始化）
        QTimer.singleShot(1000, self.auto_connect_cached_devices)
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("PM100D 仪器读控一体化GUI")
        self.setGeometry(100, 100, 1400, 900)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # 创建左侧面板
        self.left_panel = LeftPanel()
        self.left_panel.setMinimumWidth(300)
        self.left_panel.setMaximumWidth(400)
        splitter.addWidget(self.left_panel)
        
        # 创建中间绘图区域
        self.plot_widget = PlotWidget()
        self.plot_widget.setMinimumWidth(500)
        splitter.addWidget(self.plot_widget)
        
        # 创建右侧面板
        self.right_panel = RightPanel()
        self.right_panel.setMinimumWidth(300)
        self.right_panel.setMaximumWidth(400)
        
        # 将绘图组件引用和主窗口引用传递给右侧面板
        self.right_panel.set_plot_widget(self.plot_widget)
        self.right_panel.set_main_window(self)
        
        splitter.addWidget(self.right_panel)
        
        # 设置分割器比例
        splitter.setSizes([300, 800, 300])
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 创建状态栏
        self.create_status_bar()
        
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件')
        
        # 导出数据动作
        export_action = QAction('导出数据', self)
        export_action.setShortcut('Ctrl+E')
        export_action.triggered.connect(self.export_data)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        # 退出动作
        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 设备菜单
        device_menu = menubar.addMenu('设备')
        
        # 搜索设备动作
        search_action = QAction('搜索设备', self)
        search_action.setShortcut('Ctrl+F')
        search_action.triggered.connect(self.search_devices)
        device_menu.addAction(search_action)
        
        # 断开所有设备动作
        disconnect_all_action = QAction('断开所有设备', self)
        disconnect_all_action.triggered.connect(self.disconnect_all_devices)
        device_menu.addAction(disconnect_all_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu('帮助')
        
        # 关于动作
        about_action = QAction('关于', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = self.statusBar()
        
        # 设备数量标签
        self.device_count_label = QLabel("已连接设备: 0")
        self.status_bar.addPermanentWidget(self.device_count_label)
        
        # 采集状态标签
        self.acquisition_status_label = QLabel("数据采集: 停止")
        self.status_bar.addPermanentWidget(self.acquisition_status_label)
        
        self.status_bar.showMessage("就绪")
        
    def connect_data_signals(self):
        """连接信号槽"""
        # 连接左侧面板的设备管理信号
        self.left_panel.device_connected.connect(self.on_device_connected)
        self.left_panel.device_disconnected.connect(self.on_device_disconnected)
        
        # 连接右侧面板的数据采集信号
        self.right_panel.acquisition_stopped.connect(self.auto_save_data)
        
        # 验证信号连接
        print(f"信号连接验证: acquisition_stopped信号已连接到auto_save_data方法")
        
    def on_device_connected(self, device_id, pm100d_device):
        """处理设备连接事件"""
        # 存储设备连接
        self.pm100ds[device_id] = pm100d_device
        
        # 更新右侧面板的设备列表
        self.right_panel.update_device_list(self.left_panel.get_connected_devices())
        
        # 更新状态栏
        self.update_device_count()
        
        # 状态栏消息
        self.status_bar.showMessage(f"设备 {device_id} 已连接", 3000)
        
    def on_device_disconnected(self, device_id):
        """处理设备断开事件"""
        # 从存储中移除设备
        if device_id in self.pm100ds:
            del self.pm100ds[device_id]
        
        # 更新右侧面板的设备列表
        self.right_panel.update_device_list(self.left_panel.get_connected_devices())
        
        # 清除该设备的绘图数据
        self.plot_widget.clear_device_data(device_id)
        
        # 更新状态栏
        self.update_device_count()
        
        # 状态栏消息
        self.status_bar.showMessage(f"设备 {device_id} 已断开", 3000)
        
    def update_device_count(self):
        """更新设备数量显示"""
        count = len(self.pm100ds)
        self.device_count_label.setText(f"已连接设备: {count}")
        
    def search_devices(self):
        """触发设备搜索"""
        self.left_panel.search_devices()
        
    def disconnect_all_devices(self):
        """断开所有设备"""
        reply = QMessageBox.question(
            self, '确认操作', 
            '确定要断开所有设备连接吗？',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 获取所有连接的设备ID
            device_ids = list(self.pm100ds.keys())
            
            # 逐个断开设备
            for device_id in device_ids:
                try:
                    if device_id in self.left_panel.connected_devices:
                        self.left_panel.connected_devices[device_id]['device'].close()
                        del self.left_panel.connected_devices[device_id]
                    
                    # 从主窗口移除
                    if device_id in self.pm100ds:
                        del self.pm100ds[device_id]
                        
                except Exception as e:
                    print(f"断开设备 {device_id} 失败: {e}")
            
            # 清空设备列表显示
            self.left_panel.device_list.clear()
            
            # 更新界面
            self.right_panel.update_device_list({})
            self.plot_widget.clear_all_data()
            self.update_device_count()
            
            self.status_bar.showMessage("所有设备已断开", 3000)
            
    def export_data(self):
        """导出数据"""
        if not self.pm100ds:
            QMessageBox.information(self, "导出数据", "没有连接的设备或数据可导出")
            return
        
        # 检查是否有数据可导出
        if not hasattr(self.plot_widget, 'power_data') or not self.plot_widget.power_data:
            QMessageBox.information(self, "导出数据", "没有采集到的数据可导出\n请先开始数据采集")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出数据", "", "CSV files (*.csv);;All files (*.*)"
        )
        
        if file_path:
            try:
                import csv
                import time
                
                # 从plot_widget获取所有数据
                time_data = self.plot_widget.time_data
                power_data = self.plot_widget.power_data
                
                if not time_data or not power_data:
                    QMessageBox.warning(self, "导出失败", "没有数据可导出")
                    return
                
                # 写入CSV文件
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # 写入表头
                    headers = ['时间戳', '格式化时间']
                    device_ids = list(power_data.keys())
                    headers.extend([f'{device_id}_功率(W)' for device_id in device_ids])
                    writer.writerow(headers)
                    
                    # 写入数据行
                    max_rows = len(time_data)
                    for i in range(max_rows):
                        row = []
                        
                        # 添加时间信息
                        timestamp = time_data[i]
                        row.append(timestamp)
                        row.append(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp)))
                        
                        # 添加每个设备的功率数据
                        for device_id in device_ids:
                            if i < len(power_data[device_id]):
                                row.append(f"{power_data[device_id][i]:.6e}")
                            else:
                                row.append("")  # 如果该设备没有这个时间点的数据
                        
                        writer.writerow(row)
                
                # 显示导出统计信息
                total_points = sum(len(data) for data in power_data.values())
                device_count = len(power_data)
                
                success_msg = f"数据导出成功！\n\n"
                success_msg += f"文件路径: {file_path}\n"
                success_msg += f"设备数量: {device_count}\n"
                success_msg += f"总数据点: {total_points}\n"
                success_msg += f"时间范围: {max_rows} 个时间点"
                
                QMessageBox.information(self, "导出成功", success_msg)
                self.status_bar.showMessage(f"数据已导出到: {file_path}", 5000)
                
            except Exception as e:
                error_msg = f"导出数据失败: {str(e)}\n\n"
                error_msg += "可能原因:\n"
                error_msg += "• 文件被其他程序占用\n"
                error_msg += "• 磁盘空间不足\n"
                error_msg += "• 没有写入权限\n"
                error_msg += "• 文件路径无效"
                
                QMessageBox.critical(self, "导出失败", error_msg)
    
    def auto_save_data(self):
        """自动保存数据"""
        print("auto_save_data 被调用")
        
        if not self.pm100ds:
            print("没有连接的设备，跳过自动保存")
            return
        
        # 详细的数据检查和调试信息
        print(f"已连接设备数量: {len(self.pm100ds)}")
        print(f"已连接设备列表: {list(self.pm100ds.keys())}")
        
        # 检查plot_widget是否存在
        if not hasattr(self, 'plot_widget'):
            print("ERROR: plot_widget 不存在!")
            return
            
        print(f"plot_widget 存在: {self.plot_widget is not None}")
        
        # 检查power_data属性
        if not hasattr(self.plot_widget, 'power_data'):
            print("ERROR: plot_widget.power_data 属性不存在!")
            return
            
        print(f"power_data 类型: {type(self.plot_widget.power_data)}")
        print(f"power_data 内容: {self.plot_widget.power_data}")
        
        # 检查time_data
        if hasattr(self.plot_widget, 'time_data'):
            print(f"time_data 长度: {len(self.plot_widget.time_data)}")
            print(f"time_data 内容预览: {self.plot_widget.time_data[:5] if len(self.plot_widget.time_data) > 0 else '空'}")
        else:
            print("ERROR: plot_widget.time_data 属性不存在!")
        
        # 检查是否有数据可保存
        if not self.plot_widget.power_data:
            print("没有数据可保存，跳过自动保存")
            print("可能原因:")
            print("1. 数据采集时间太短，还没来得及采集数据")
            print("2. 设备连接有问题，无法读取数据")
            print("3. 数据被清除了")
            print("4. 数据传递过程出现问题")
            QMessageBox.information(self, "自动保存", "没有数据可保存\n\n可能原因:\n• 采集时间太短\n• 设备连接异常\n• 数据已被清除\n\n建议：连接设备后采集几秒钟数据再停止")
            return
        
        print(f"开始自动保存数据，设备数量: {len(self.plot_widget.power_data)}")
        print(f"时间数据点数: {len(self.plot_widget.time_data)}")
        
        try:
            import csv
            import time
            import os
            
            # 生成自动保存文件名（带时间戳）
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"PM100D_数据_{timestamp}.csv"
            
            # 创建保存目录（如果不存在）
            save_dir = os.path.join(os.getcwd(), "数据保存")
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            
            file_path = os.path.join(save_dir, filename)
            
            # 从plot_widget获取所有数据
            time_data = self.plot_widget.time_data
            power_data = self.plot_widget.power_data
            
            if not time_data or not power_data:
                return
            
            # 写入CSV文件
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # 写入表头
                headers = ['时间戳', '格式化时间']
                device_ids = list(power_data.keys())
                headers.extend([f'{device_id}_功率(W)' for device_id in device_ids])
                writer.writerow(headers)
                
                # 写入数据行
                max_rows = len(time_data)
                for i in range(max_rows):
                    row = []
                    
                    # 添加时间信息
                    timestamp_val = time_data[i]
                    row.append(timestamp_val)
                    row.append(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp_val)))
                    
                    # 添加每个设备的功率数据
                    for device_id in device_ids:
                        if i < len(power_data[device_id]):
                            row.append(f"{power_data[device_id][i]:.6e}")
                        else:
                            row.append("")  # 如果该设备没有这个时间点的数据
                    
                    writer.writerow(row)
            
            # 显示保存成功信息
            total_points = sum(len(data) for data in power_data.values())
            device_count = len(power_data)
            
            success_msg = f"数据已自动保存成功！\n\n"
            success_msg += f"文件路径: {file_path}\n"
            success_msg += f"设备数量: {device_count}\n"
            success_msg += f"总数据点: {total_points}\n"
            success_msg += f"时间范围: {max_rows} 个时间点"
            
            QMessageBox.information(self, "自动保存成功", success_msg)
            self.status_bar.showMessage(f"数据已自动保存到: {file_path}", 5000)
            
        except Exception as e:
            error_msg = f"自动保存数据失败: {str(e)}\n\n"
            error_msg += "数据已停留在内存中，您可以通过菜单手动导出。"
            QMessageBox.warning(self, "自动保存失败", error_msg)
            print(f"自动保存失败: {e}")
                
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self, "关于",
            "PM100D 仪器读控一体化GUI\n\n"
            "版本: 1.0\n"
            "作者: 开发团队\n\n"
            "这是一个用于PM100D光强探测器的数据读取和控制GUI应用程序，\n"
            "支持多设备连接、实时数据显示和数据可视化功能。"
        )
        
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 确认是否退出
        reply = QMessageBox.question(
            self, '确认退出', 
            '确定要退出程序吗？\n\n注意：所有设备连接将被断开。',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 停止数据采集
            if hasattr(self.right_panel, 'data_timer'):
                self.right_panel.data_timer.stop()
            
            # 断开所有设备
            for device_id, device in self.pm100ds.items():
                try:
                    if hasattr(device, 'close'):
                        device.close()
                except Exception as e:
                    print(f"关闭设备 {device_id} 时出错: {e}")
            
            # 清理左侧面板资源
            self.left_panel.closeEvent(event)
            
            event.accept()
        else:
            event.ignore()
    
    def auto_connect_cached_devices(self):
        """程序启动时自动连接缓存的设备"""
        try:
            print("开始自动连接缓存设备...")
            
            # 检查是否有缓存设备
            cached_devices = self.left_panel.device_cache.get_priority_devices(3)  # 只尝试连接前3个优先设备
            
            if not cached_devices:
                print("没有缓存设备，跳过自动连接")
                self.status_bar.showMessage("没有缓存设备可连接", 3000)
                return
            
            print(f"发现 {len(cached_devices)} 个缓存设备，开始自动连接...")
            self.status_bar.showMessage(f"正在尝试自动连接 {len(cached_devices)} 个缓存设备...", 5000)
            
            # 使用左侧面板的快速连接功能
            self.left_panel.start_quick_connect(cached_devices)
            
        except Exception as e:
            print(f"自动连接缓存设备时出错: {e}")
            self.status_bar.showMessage("自动连接缓存设备失败", 3000)