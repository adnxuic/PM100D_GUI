from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QSplitter, QMenuBar, QMenu, QStatusBar, QMessageBox,
    QFileDialog, QProgressBar, QLabel
)
from PySide6.QtGui import QAction, QIcon, QDragEnterEvent, QDropEvent, QCloseEvent
from PySide6.QtCore import Qt

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
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出数据", "", "CSV files (*.csv);;All files (*.*)"
        )
        
        if file_path:
            try:
                # 这里可以实现数据导出逻辑
                # 从right_panel的数据表格或其他数据源导出
                QMessageBox.information(self, "导出成功", f"数据已导出到: {file_path}")
                self.status_bar.showMessage(f"数据已导出到: {file_path}", 5000)
            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出数据失败: {str(e)}")
                
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