#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
仪器读控一体化GUI应用程序主入口
"""

import sys
import os
from PySide6.QtWidgets import QApplication

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# 设置matplotlib后端和中文字体
import matplotlib
matplotlib.use('Qt5Agg')  # 设置Qt后端
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import platform
import warnings

def setup_matplotlib_font():
    """配置matplotlib中文字体"""
    system = platform.system()
    
    if system == "Windows":
        # Windows系统常见中文字体
        fonts = ['SimHei', 'Microsoft YaHei', 'SimSun', 'KaiTi']
    elif system == "Darwin":  # macOS
        fonts = ['Hiragino Sans GB', 'STHeiti', 'Arial Unicode MS']
    else:  # Linux
        fonts = ['WenQuanYi Micro Hei', 'DejaVu Sans', 'Liberation Sans']
    
    # 尝试设置第一个可用的字体
    font_found = False
    for font in fonts:
        try:
            if any(font in f.name for f in fm.fontManager.ttflist):
                plt.rcParams['font.sans-serif'] = [font]
                plt.rcParams['axes.unicode_minus'] = False  # 正确显示负号
                print(f"已设置matplotlib字体为: {font}")
                font_found = True
                break
        except Exception:
            continue
    
    # 如果都不可用，屏蔽字体警告
    if not font_found:
        warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib.font_manager')
        warnings.filterwarnings('ignore', message='.*Glyph.*missing from font.*')
        print("未找到合适的中文字体，已屏蔽字体警告")

# 初始化字体设置
setup_matplotlib_font()

from gui.main_window import MainWindow


def main():
    """主函数"""
    # 创建应用程序实例
    app = QApplication(sys.argv)
    
    # 创建主窗口
    main_window = MainWindow()
    main_window.show()
    
    # 运行应用程序
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
