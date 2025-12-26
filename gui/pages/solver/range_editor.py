"""
Range 编辑器组件 - 13x13 矩阵编辑
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QSizePolicy, QDialog, QComboBox, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QMouseEvent
from solver.card_utils import HAND_MATRIX
from solver.data_types import HandRange
import os


class RangeMatrixWidget(QWidget):
    """13x13 Range 矩阵绘制组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.weights = {}  # {hand: weight (0-1)}
        self.hovered_cell = None
        self.setMinimumSize(400, 400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
    
    def set_weights(self, weights: dict):
        """设置权重"""
        self.weights = weights
        self.update()
    
    def set_hovered_cell(self, hand: str):
        """设置悬停的单元格"""
        self.hovered_cell = hand
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        cell_w = width / 13
        cell_h = height / 13
        
        font = QFont("Arial", max(8, int(min(cell_w, cell_h) / 4)))
        painter.setFont(font)
        
        for row in range(13):
            for col in range(13):
                hand = HAND_MATRIX[row][col]
                x = col * cell_w
                y = row * cell_h
                
                weight = self.weights.get(hand, 0.0)
                self._draw_cell(painter, x, y, cell_w, cell_h, hand, weight, font)
        
        painter.end()
    
    def _draw_cell(self, painter, x, y, cell_w, cell_h, hand, weight, base_font):
        """绘制单元格"""
        # 背景颜色基于权重
        if weight <= 0:
            bg_color = QColor("#2a2a2a")  # 无权重
        elif weight < 0.5:
            bg_color = QColor("#3a4a3a")  # 低权重
        elif weight < 1.0:
            bg_color = QColor("#4a6a4a")  # 中权重
        else:
            bg_color = QColor("#5a8a5a")  # 高权重
        
        # 悬停高亮
        if self.hovered_cell == hand:
            bg_color = bg_color.lighter(120)
        
        painter.fillRect(int(x), int(y), int(cell_w), int(cell_h), bg_color)
        
        # 边框
        painter.setPen(QPen(QColor("#1a1a1a"), 1))
        painter.drawRect(int(x), int(y), int(cell_w), int(cell_h))
        
        # 手牌文字
        text_color = QColor("#ffffff") if weight > 0 else QColor("#666666")
        painter.setFont(base_font)
        painter.setPen(QColor("#000000"))
        painter.drawText(int(x) + 1, int(y) + 1, int(cell_w), int(cell_h * 0.6), Qt.AlignCenter, hand)
        painter.setPen(text_color)
        painter.drawText(int(x), int(y), int(cell_w), int(cell_h * 0.6), Qt.AlignCenter, hand)
        
        # 权重文字
        if weight > 0:
            weight_text = f"{weight*100:.0f}%"
            weight_font = QFont("Arial", max(6, int(min(cell_w, cell_h) / 6)))
            painter.setFont(weight_font)
            painter.setPen(QColor("#cccccc"))
            painter.drawText(int(x), int(y + cell_h * 0.5), int(cell_w), int(cell_h * 0.4),
                           Qt.AlignCenter, weight_text)
            # 恢复基础字体
            painter.setFont(base_font)
    
    def get_cell_at_pos(self, x: float, y: float) -> str:
        """根据坐标获取单元格"""
        cell_w = self.width() / 13
        cell_h = self.height() / 13
        col = int(x / cell_w)
        row = int(y / cell_h)
        
        if 0 <= row < 13 and 0 <= col < 13:
            return HAND_MATRIX[row][col]
        return None


class RangeEditorWidget(QWidget):
    """13x13 Range 编辑器"""
    
    range_changed = Signal(HandRange)  # Range 变化时发出信号
    
    def __init__(self, title="Range Editor"):
        super().__init__()
        self.title = title
        self.weights = {}  # {hand: weight (0-1)}
        self.hovered_cell = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 标题和按钮行
        header_layout = QHBoxLayout()
        title_label = QLabel(self.title)
        title_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # 快速选择按钮
        btn_clear = QPushButton("Clear")
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 4px 12px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        btn_clear.clicked.connect(self.clear)
        header_layout.addWidget(btn_clear)
        
        btn_tight = QPushButton("Tight")
        btn_tight.setStyleSheet(btn_clear.styleSheet())
        btn_tight.clicked.connect(self._load_tight_range)
        header_layout.addWidget(btn_tight)
        
        btn_medium = QPushButton("Medium")
        btn_medium.setStyleSheet(btn_clear.styleSheet())
        btn_medium.clicked.connect(self._load_medium_range)
        header_layout.addWidget(btn_medium)
        
        btn_loose = QPushButton("Loose")
        btn_loose.setStyleSheet(btn_clear.styleSheet())
        btn_loose.clicked.connect(self._load_loose_range)
        header_layout.addWidget(btn_loose)
        
        # GTO 预设按钮
        btn_gto = QPushButton("Load GTO")
        btn_gto.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                border: none;
                padding: 4px 12px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5aaeff;
            }
        """)
        btn_gto.clicked.connect(self._show_gto_dialog)
        header_layout.addWidget(btn_gto)
        
        layout.addLayout(header_layout)
        
        # 说明文字
        hint_label = QLabel("💡 点击格子选择手牌 (左键: 25%→50%→75%→100%→0%, 右键: 清除)")
        hint_label.setStyleSheet("color: #888888; font-size: 10px;")
        layout.addWidget(hint_label)
        
        # 矩阵区域（使用固定大小的 widget）
        self.matrix_widget = RangeMatrixWidget()
        self.matrix_widget.setMinimumHeight(350)
        self.matrix_widget.setMaximumHeight(400)
        # 安装事件过滤器以处理鼠标事件
        self.matrix_widget.installEventFilter(self)
        layout.addWidget(self.matrix_widget, 1)
        
        # 更新矩阵显示
        self.matrix_widget.set_weights(self.weights)
    
    def set_range(self, range_obj: HandRange):
        """设置 range"""
        self.weights = range_obj.weights.copy()
        self.matrix_widget.set_weights(self.weights)
    
    def get_range(self) -> HandRange:
        """获取当前 range"""
        return HandRange(weights=self.weights.copy())
    
    def clear(self):
        """清空 range"""
        self.weights = {}
        self.matrix_widget.set_weights(self.weights)
        self.range_changed.emit(HandRange(weights={}))
    
    def _load_tight_range(self):
        """加载 Tight range (约 15% 的手牌)"""
        tight_hands = [
            "AA", "AKs", "AQs", "AJs", "AKo",
            "KK", "KQs", "KJs", "KQo",
            "QQ", "QJs", "QJo",
            "JJ", "JTs", "JTo",
            "TT", "T9s",
            "99", "98s",
            "88", "87s",
            "77", "76s",
            "66", "65s",
            "55", "54s",
            "44", "33", "22"
        ]
        self.weights = {hand: 1.0 for hand in tight_hands}
        self.matrix_widget.set_weights(self.weights)
        self.range_changed.emit(HandRange(weights=self.weights.copy()))
    
    def _load_medium_range(self):
        """加载 Medium range (约 25% 的手牌)"""
        medium_hands = [
            "AA", "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
            "AKo", "KK", "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s",
            "AQo", "KQo", "QQ", "QJs", "QTs", "Q9s", "Q8s", "Q7s", "Q6s", "Q5s", "Q4s", "Q3s", "Q2s",
            "AJo", "KJo", "QJo", "JJ", "JTs", "J9s", "J8s", "J7s", "J6s", "J5s", "J4s", "J3s", "J2s",
            "ATo", "KTo", "QTo", "JTo", "TT", "T9s", "T8s", "T7s", "T6s", "T5s", "T4s", "T3s", "T2s",
            "A9o", "K9o", "Q9o", "J9o", "T9o", "99", "98s", "97s", "96s", "95s", "94s", "93s", "92s",
            "A8o", "K8o", "Q8o", "J8o", "T8o", "98o", "88", "87s", "86s", "85s", "84s", "83s", "82s",
            "A7o", "K7o", "Q7o", "J7o", "T7o", "97o", "87o", "77", "76s", "75s", "74s", "73s", "72s",
            "A6o", "K6o", "Q6o", "J6o", "T6o", "96o", "86o", "76o", "66", "65s", "64s", "63s", "62s",
            "A5o", "K5o", "Q5o", "J5o", "T5o", "95o", "85o", "75o", "65o", "55", "54s", "53s", "52s",
            "A4o", "K4o", "Q4o", "J4o", "T4o", "94o", "84o", "74o", "64o", "54o", "44", "43s", "42s",
            "A3o", "K3o", "Q3o", "J3o", "T3o", "93o", "83o", "73o", "63o", "53o", "43o", "33", "32s",
            "A2o", "K2o", "Q2o", "J2o", "T2o", "92o", "82o", "72o", "62o", "52o", "42o", "32o", "22"
        ]
        # 只选择部分手牌作为 medium range
        selected = [
            "AA", "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
            "AKo", "KK", "KQs", "KJs", "KTs", "K9s", "K8s",
            "AQo", "KQo", "QQ", "QJs", "QTs", "Q9s",
            "AJo", "KJo", "QJo", "JJ", "JTs", "J9s",
            "ATo", "KTo", "QTo", "JTo", "TT", "T9s", "T8s",
            "A9o", "K9o", "Q9o", "J9o", "T9o", "99", "98s", "97s",
            "A8o", "K8o", "Q8o", "J8o", "T8o", "98o", "88", "87s", "86s",
            "A7o", "K7o", "Q7o", "J7o", "T7o", "97o", "87o", "77", "76s", "75s",
            "A6o", "K6o", "Q6o", "J6o", "T6o", "96o", "86o", "76o", "66", "65s", "64s",
            "A5o", "K5o", "Q5o", "J5o", "T5o", "95o", "85o", "75o", "65o", "55", "54s",
            "A4o", "K4o", "Q4o", "J4o", "T4o", "94o", "84o", "74o", "64o", "54o", "44", "43s",
            "A3o", "K3o", "Q3o", "J3o", "T3o", "93o", "83o", "73o", "63o", "53o", "43o", "33", "32s",
            "A2o", "K2o", "Q2o", "J2o", "T2o", "92o", "82o", "72o", "62o", "52o", "42o", "32o", "22"
        ]
        self.weights = {hand: 1.0 for hand in selected}
        self.matrix_widget.set_weights(self.weights)
        self.range_changed.emit(HandRange(weights=self.weights.copy()))
    
    def _load_loose_range(self):
        """加载 Loose range (约 40% 的手牌)"""
        # 选择大部分手牌
        all_hands = []
        for row in HAND_MATRIX:
            all_hands.extend(row)
        self.weights = {hand: 1.0 for hand in all_hands[:70]}  # 前 70 个手牌
        self.matrix_widget.set_weights(self.weights)
        self.range_changed.emit(HandRange(weights=self.weights.copy()))
    
    def _show_gto_dialog(self):
        """显示 GTO range 加载对话框"""
        dialog = GTORangeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            range_data = dialog.get_range_data()
            if range_data:
                self.weights = range_data
                self.matrix_widget.set_weights(self.weights)
                self.range_changed.emit(HandRange(weights=self.weights.copy()))


class GTORangeDialog(QDialog):
    """GTO Range 加载对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load GTO Range")
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
            }
            QLabel {
                color: white;
            }
            QComboBox {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 6px;
                border-radius: 4px;
            }
        """)
        self.range_data = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Stack Depth
        stack_layout = QHBoxLayout()
        stack_layout.addWidget(QLabel("Stack Depth:"))
        self.stack_combo = QComboBox()
        self.stack_combo.addItems(["50bb", "100bb", "200bb"])
        self.stack_combo.setCurrentText("100bb")
        stack_layout.addWidget(self.stack_combo)
        layout.addLayout(stack_layout)
        
        # Position
        pos_layout = QHBoxLayout()
        pos_layout.addWidget(QLabel("Position:"))
        self.position_combo = QComboBox()
        self.position_combo.addItems(["UTG", "HJ", "CO", "BTN", "SB", "BB"])
        pos_layout.addWidget(self.position_combo)
        layout.addLayout(pos_layout)
        
        # Action (简化：只支持 Open Raise)
        action_layout = QHBoxLayout()
        action_layout.addWidget(QLabel("Action:"))
        self.action_combo = QComboBox()
        self.action_combo.addItems(["2bb (Open)", "2.5bb (Open)", "3bb (Open)"])
        action_layout.addWidget(self.action_combo)
        layout.addLayout(action_layout)
        
        # 说明
        hint = QLabel("💡 当前仅支持 Open Raise 场景")
        hint.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(hint)
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._load_range)
        buttons.rejected.connect(self.reject)
        buttons.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5aaeff;
            }
        """)
        layout.addWidget(buttons)
    
    def _load_range(self):
        """加载 GTO range"""
        stack = self.stack_combo.currentText()
        position = self.position_combo.currentText()
        action_str = self.action_combo.currentText()
        
        # 解析 action
        if "2bb" in action_str:
            action_size = "2bb"
        elif "2.5bb" in action_str:
            action_size = "2.5bb"
        else:
            action_size = "3bb"
        
        # 构建路径
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        stack_map = {
            "50bb": "cash6m_50bb_nl50_gto_gto",
            "100bb": "cash6m_100bb_nl50_gto_gto",
            "200bb": "cash6m_200bb_nl50_gto_gto",
        }
        folder = stack_map.get(stack, stack_map["100bb"])
        base_path = os.path.join(project_root, "assets", "range", folder, "ranges", position, action_size)
        
        # 查找 range 文件（简化：查找该目录下的第一个 .txt 文件）
        range_file = None
        if os.path.exists(base_path):
            for root, dirs, files in os.walk(base_path):
                for file in files:
                    if file.endswith('.txt') and file in ["UTG.txt", "HJ.txt", "CO.txt", "BTN.txt", "SB.txt", "BB.txt"]:
                        range_file = os.path.join(root, file)
                        break
                if range_file:
                    break
        
        if not range_file or not os.path.exists(range_file):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Not Found", f"GTO range file not found for {position} {action_size}")
            return
        
        # 解析 range 文件
        self.range_data = self._parse_range_file(range_file)
        if self.range_data:
            self.accept()
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", "Failed to parse range file")
    
    def _parse_range_file(self, path):
        """解析 range 文件"""
        range_data = {}
        try:
            with open(path, 'r') as f:
                content = f.read().strip()
                for item in content.split(','):
                    if ':' in item:
                        hand, freq = item.split(':')
                        range_data[hand.strip()] = float(freq.strip())
        except Exception as e:
            print(f"Error loading range: {e}")
        return range_data
    
    def get_range_data(self):
        """获取加载的 range 数据"""
        return self.range_data
    
    def eventFilter(self, obj, event):
        """事件过滤器 - 处理 matrix widget 的鼠标事件"""
        if obj == self.matrix_widget:
            if event.type() == QEvent.Type.MouseMove:
                hand = self.matrix_widget.get_cell_at_pos(event.position().x(), event.position().y())
                if hand:
                    self.hovered_cell = hand
                    self.matrix_widget.set_hovered_cell(hand)
                else:
                    if self.hovered_cell:
                        self.hovered_cell = None
                        self.matrix_widget.set_hovered_cell(None)
                return True
            elif event.type() == QEvent.Type.MouseButtonPress:
                hand = self.matrix_widget.get_cell_at_pos(event.position().x(), event.position().y())
                if hand:
                    current_weight = self.weights.get(hand, 0.0)
                    
                    # 点击循环切换：0% -> 25% -> 50% -> 75% -> 100% -> 0%
                    if event.button() == Qt.LeftButton:
                        if current_weight <= 0:
                            new_weight = 0.25
                        elif current_weight <= 0.25:
                            new_weight = 0.5
                        elif current_weight <= 0.5:
                            new_weight = 0.75
                        elif current_weight <= 0.75:
                            new_weight = 1.0
                        else:
                            new_weight = 0.0
                        
                        self.weights[hand] = new_weight
                        self.matrix_widget.set_weights(self.weights)
                        self.range_changed.emit(HandRange(weights=self.weights.copy()))
                    
                    elif event.button() == Qt.RightButton:
                        # 右键清除
                        if hand in self.weights:
                            del self.weights[hand]
                        self.matrix_widget.set_weights(self.weights)
                        self.range_changed.emit(HandRange(weights=self.weights.copy()))
                    return True
        return super().eventFilter(obj, event)

