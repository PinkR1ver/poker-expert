"""
Leak Analyze 页面 - 包含多种 Leak 分析功能
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QStackedWidget, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QColor, QBrush

from .preflop_range_check import PreflopRangeCheck


class LeakAnalyzePage(QWidget):
    """
    Leak Analyze 页面，包含功能选择器和内容区域
    """
    # 转发 replay 请求信号
    replay_requested = Signal(str)  # hand_id
    
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.init_ui()
    
    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Left: Function Selector (二级侧边栏)
        function_selector = QFrame()
        function_selector.setFixedWidth(200)
        function_selector.setStyleSheet("""
            QFrame { background-color: #252525; border-right: 1px solid #3a3a3a; }
        """)
        selector_layout = QVBoxLayout(function_selector)
        selector_layout.setContentsMargins(0, 0, 0, 0)
        selector_layout.setSpacing(0)
        
        # Title
        title_frame = QFrame()
        title_frame.setStyleSheet("background-color: #2a2a2a; border-bottom: 1px solid #3a3a3a;")
        title_layout = QVBoxLayout(title_frame)
        title_layout.setContentsMargins(16, 16, 16, 16)
        
        title_label = QLabel("Leak Analyze")
        title_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        subtitle_label = QLabel("发现并修复你的漏洞")
        subtitle_label.setStyleSheet("color: #888888; font-size: 11px;")
        title_layout.addWidget(subtitle_label)
        
        selector_layout.addWidget(title_frame)
        
        # Function List
        self.function_list = QListWidget()
        self.function_list.setStyleSheet("""
            QListWidget {
                background-color: #252525;
                border: none;
                color: #e0e0e0;
                outline: none;
            }
            QListWidget::item {
                padding: 12px 16px;
                border-bottom: 1px solid #2f2f2f;
            }
            QListWidget::item:selected {
                background-color: #3a3a3a;
                border-left: 3px solid #4a9eff;
            }
            QListWidget::item:hover {
                background-color: #2f2f2f;
            }
        """)
        self.function_list.currentRowChanged.connect(self.on_function_selected)
        
        # Add function items
        functions = [
            ("🎯 Preflop Range Check", "preflop_range_check", "检查翻前行动是否符合 GTO"),
            # 未来功能占位
            # ("📊 Postflop Analysis", "postflop_analysis", "翻后行动分析"),
            # ("💰 Bet Sizing Check", "bet_sizing", "下注尺度检查"),
        ]
        
        for name, func_id, description in functions:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, func_id)
            item.setData(Qt.UserRole + 1, description)
            item.setSizeHint(QSize(0, 48))
            self.function_list.addItem(item)
        
        selector_layout.addWidget(self.function_list)
        selector_layout.addStretch()
        
        main_layout.addWidget(function_selector)
        
        # Right: Content Area
        self.content_area = QStackedWidget()
        self.content_area.setStyleSheet("background-color: #1e1e1e;")
        main_layout.addWidget(self.content_area, 1)
        
        # Register function widgets
        self.function_widgets = {}
        
        # Preflop Range Check
        self.preflop_check = PreflopRangeCheck(self.db)
        self.preflop_check.replay_requested.connect(self.replay_requested.emit)  # 转发 replay 信号
        self.content_area.addWidget(self.preflop_check)
        self.function_widgets["preflop_range_check"] = self.preflop_check
        
        # Default selection
        self.function_list.setCurrentRow(0)
    
    def on_function_selected(self, index):
        """处理功能选择"""
        item = self.function_list.item(index)
        if not item:
            return
        
        func_id = item.data(Qt.UserRole)
        
        if func_id in self.function_widgets:
            widget = self.function_widgets[func_id]
            self.content_area.setCurrentWidget(widget)
        else:
            # Placeholder for unimplemented functions
            if "placeholder" not in self.function_widgets:
                placeholder = QLabel("This feature is coming soon...")
                placeholder.setStyleSheet("color: #888888; font-size: 14px;")
                placeholder.setAlignment(Qt.AlignCenter)
                self.content_area.addWidget(placeholder)
                self.function_widgets["placeholder"] = placeholder
            self.content_area.setCurrentWidget(self.function_widgets["placeholder"])
    
    def refresh_data(self):
        """刷新当前功能的数据"""
        current_widget = self.content_area.currentWidget()
        if hasattr(current_widget, "refresh_data"):
            current_widget.refresh_data()

