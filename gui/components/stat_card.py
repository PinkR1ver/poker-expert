"""
统计卡片组件
"""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel


class StatCard(QFrame):
    """统计卡片，显示标题和数值"""
    
    def __init__(self, title, value, parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("CardTitle")
        
        self.lbl_value = QLabel(value)
        self.lbl_value.setObjectName("CardValue")
        
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)
        self.setFixedHeight(100)

    def set_value(self, value, color=None):
        self.lbl_value.setText(value)
        if color:
            self.lbl_value.setStyleSheet(f"color: {color};")
        else:
            self.lbl_value.setStyleSheet("")


