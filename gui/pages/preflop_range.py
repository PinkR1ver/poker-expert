"""
Preflop Range 页面 - GTO Range 查表功能
支持 Range 视图和 Strategy 视图
"""
import os
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QFrame, QGridLayout, QScrollArea, QSplitter,
    QTreeWidget, QTreeWidgetItem, QSizePolicy, QButtonGroup
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QFont

from gui.styles import PROFIT_GREEN, PROFIT_RED


# 169 种起手牌，按矩阵顺序排列
HAND_MATRIX = [
    ["AA", "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s"],
    ["AKo", "KK", "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s"],
    ["AQo", "KQo", "QQ", "QJs", "QTs", "Q9s", "Q8s", "Q7s", "Q6s", "Q5s", "Q4s", "Q3s", "Q2s"],
    ["AJo", "KJo", "QJo", "JJ", "JTs", "J9s", "J8s", "J7s", "J6s", "J5s", "J4s", "J3s", "J2s"],
    ["ATo", "KTo", "QTo", "JTo", "TT", "T9s", "T8s", "T7s", "T6s", "T5s", "T4s", "T3s", "T2s"],
    ["A9o", "K9o", "Q9o", "J9o", "T9o", "99", "98s", "97s", "96s", "95s", "94s", "93s", "92s"],
    ["A8o", "K8o", "Q8o", "J8o", "T8o", "98o", "88", "87s", "86s", "85s", "84s", "83s", "82s"],
    ["A7o", "K7o", "Q7o", "J7o", "T7o", "97o", "87o", "77", "76s", "75s", "74s", "73s", "72s"],
    ["A6o", "K6o", "Q6o", "J6o", "T6o", "96o", "86o", "76o", "66", "65s", "64s", "63s", "62s"],
    ["A5o", "K5o", "Q5o", "J5o", "T5o", "95o", "85o", "75o", "65o", "55", "54s", "53s", "52s"],
    ["A4o", "K4o", "Q4o", "J4o", "T4o", "94o", "84o", "74o", "64o", "54o", "44", "43s", "42s"],
    ["A3o", "K3o", "Q3o", "J3o", "T3o", "93o", "83o", "73o", "63o", "53o", "43o", "33", "32s"],
    ["A2o", "K2o", "Q2o", "J2o", "T2o", "92o", "82o", "72o", "62o", "52o", "42o", "32o", "22"],
]

# 位置顺序
POSITIONS = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]

# 基础行动颜色
ACTION_COLORS = {
    "fold": QColor("#5d6d7e"),     # 蓝灰色 - fold
    "check": QColor("#16a085"),    # 青色 - check
    "call": QColor("#27ae60"),     # 绿色 - call
    "allin": QColor("#e67e22"),    # 橙色 - all-in
}

# Raise 颜色渐变参数（从浅红到深红）
RAISE_COLOR_MIN = (255, 120, 100)   # 浅红 (小 raise, ~2bb)
RAISE_COLOR_MAX = (120, 30, 30)     # 深红 (大 raise, ~20bb+)
RAISE_SIZE_MIN = 2.0   # 最小 raise 大小
RAISE_SIZE_MAX = 20.0  # 最大 raise 大小（超过此值使用最深色）

# 行动显示优先级（从下到上：fold -> check -> call -> raise -> allin）
ACTION_PRIORITY = {
    "fold": 0,
    "check": 1,
    "call": 2,
    "raise": 3,
    "allin": 4,
}


def get_action_type(action_name):
    """获取行动类型"""
    action_lower = action_name.lower()
    if action_lower == "call":
        return "call"
    elif action_lower == "fold":
        return "fold"
    elif action_lower == "allin":
        return "allin"
    elif action_lower == "check":
        return "check"
    else:
        return "raise"


def get_raise_size(action_name):
    """从行动名称中提取 raise 大小（bb）"""
    match = re.match(r'(\d+\.?\d*)bb', action_name.lower())
    if match:
        return float(match.group(1))
    return 5.0  # 默认中等大小


def lerp_color(color1, color2, t):
    """线性插值两个颜色，t 在 0-1 之间"""
    t = max(0.0, min(1.0, t))  # clamp to [0, 1]
    r = int(color1[0] + (color2[0] - color1[0]) * t)
    g = int(color1[1] + (color2[1] - color1[1]) * t)
    b = int(color1[2] + (color2[2] - color1[2]) * t)
    return QColor(r, g, b)


def get_raise_color(size):
    """根据 raise 大小获取颜色（连续渐变）"""
    # 将 size 映射到 0-1 范围
    t = (size - RAISE_SIZE_MIN) / (RAISE_SIZE_MAX - RAISE_SIZE_MIN)
    return lerp_color(RAISE_COLOR_MIN, RAISE_COLOR_MAX, t)


def get_action_color(action_name):
    """根据行动名称返回颜色"""
    action_type = get_action_type(action_name)
    
    if action_type == "raise":
        # 根据 raise 大小连续渐变颜色
        size = get_raise_size(action_name)
        return get_raise_color(size)
    
    return ACTION_COLORS.get(action_type, ACTION_COLORS["call"])


def get_action_priority(action_name):
    """获取行动优先级（用于排序）"""
    action_type = get_action_type(action_name)
    base_priority = ACTION_PRIORITY.get(action_type, 3)
    
    # 对于 raise，根据大小调整优先级（小的在下面，大的在上面）
    if action_type == "raise":
        size = get_raise_size(action_name)
        # 在 raise 优先级内部，按大小排序 (3.0 -> 3.01, 6.0 -> 3.02, etc.)
        return base_priority + min(size / 100, 0.99)
    
    return base_priority


class StrategyMatrixWidget(QWidget):
    """策略矩阵显示组件 - 显示每手牌的策略分布"""
    
    hand_clicked = Signal(str, dict)  # 手牌, {action: freq}
    
    def __init__(self):
        super().__init__()
        # {hand: {action: frequency}}
        self.strategy_data = {}
        self.action_order = []  # 行动显示顺序
        self.view_mode = "strategy"  # "strategy" 或 "range"
        self.selected_action = None  # 选中的特定行动（range 模式）
        self.setMinimumSize(400, 400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.hovered_cell = None
        self.setMouseTracking(True)
    
    def set_strategy(self, strategy_data, action_order):
        """设置策略数据
        strategy_data: {hand: {action: freq}}
        action_order: [action1, action2, ...] 按顺序显示
        """
        self.strategy_data = strategy_data
        self.action_order = action_order
        self.view_mode = "strategy"
        self.selected_action = None
        self.update()
    
    def set_range(self, range_data, action_name=None):
        """设置单一 range 数据（兼容旧模式）"""
        self.strategy_data = {hand: {action_name or "range": freq} for hand, freq in range_data.items()}
        self.action_order = [action_name or "range"]
        self.view_mode = "range"
        self.selected_action = action_name
        self.update()
    
    def clear(self):
        """清空数据"""
        self.strategy_data = {}
        self.action_order = []
        self.update()
    
    def _get_color_for_freq(self, freq):
        """根据频率返回颜色（range 模式用）"""
        if freq <= 0:
            return QColor("#2a2a2a")
        elif freq < 0.25:
            return QColor("#4a3a2a")
        elif freq < 0.5:
            return QColor("#6a5a3a")
        elif freq < 0.75:
            return QColor("#5a7a4a")
        elif freq < 1.0:
            return QColor("#4a8a4a")
        else:
            return QColor("#3a9a3a")
    
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
                
                hand_strategy = self.strategy_data.get(hand, {})
                
                if self.view_mode == "strategy" and len(self.action_order) > 1:
                    # 策略模式：绘制多色条形
                    self._draw_strategy_cell(painter, x, y, cell_w, cell_h, hand, hand_strategy)
                else:
                    # Range 模式：单色
                    total_freq = sum(hand_strategy.values())
                    self._draw_range_cell(painter, x, y, cell_w, cell_h, hand, total_freq)
        
        painter.end()
    
    def _draw_strategy_cell(self, painter, x, y, cell_w, cell_h, hand, hand_strategy):
        """绘制策略单元格（垂直堆叠 - 从下到上）"""
        # 背景（fold 颜色作为基底）
        painter.fillRect(int(x), int(y), int(cell_w), int(cell_h), ACTION_COLORS["fold"])
        
        # 按优先级排序行动（从下到上：fold -> call -> raise -> allin）
        sorted_actions = sorted(self.action_order, key=get_action_priority)
        
        # 计算总频率
        total_freq = sum(hand_strategy.get(a, 0) for a in self.action_order)
        
        if total_freq > 0:
            # 从底部开始堆叠（跳过 fold，因为已经是背景色）
            current_y = y + cell_h  # 从底部开始
            
            for action in sorted_actions:
                if get_action_type(action) == "fold":
                    continue  # fold 已经是背景
                
                freq = hand_strategy.get(action, 0)
                if freq > 0:
                    bar_height = freq * cell_h
                    current_y -= bar_height
                    color = get_action_color(action)
                    painter.fillRect(int(x), int(current_y), int(cell_w), int(bar_height) + 1, color)
        
        # 边框
        painter.setPen(QPen(QColor("#1a1a1a"), 1))
        painter.drawRect(int(x), int(y), int(cell_w), int(cell_h))
        
        # 手牌文字（带阴影效果提升可读性）
        text_color = QColor("#ffffff")
        painter.setPen(QColor("#000000"))
        painter.drawText(int(x) + 1, int(y) + 1, int(cell_w), int(cell_h), Qt.AlignCenter, hand)
        painter.setPen(text_color)
        painter.drawText(int(x), int(y), int(cell_w), int(cell_h), Qt.AlignCenter, hand)
    
    def _draw_range_cell(self, painter, x, y, cell_w, cell_h, hand, freq):
        """绘制 range 单元格（单色）"""
        # 背景色
        if self.selected_action:
            bg_color = get_action_color(self.selected_action) if freq > 0 else QColor("#2a2a2a")
            if freq > 0 and freq < 1.0:
                # 调暗颜色表示部分频率
                bg_color = QColor(
                    int(bg_color.red() * freq + 42 * (1 - freq)),
                    int(bg_color.green() * freq + 42 * (1 - freq)),
                    int(bg_color.blue() * freq + 42 * (1 - freq))
                )
        else:
            bg_color = self._get_color_for_freq(freq)
        
        painter.fillRect(int(x), int(y), int(cell_w), int(cell_h), bg_color)
        
        # 边框
        painter.setPen(QPen(QColor("#3a3a3a"), 1))
        painter.drawRect(int(x), int(y), int(cell_w), int(cell_h))
        
        # 手牌文字
        text_color = QColor("#ffffff") if freq > 0 else QColor("#666666")
        painter.setPen(text_color)
        painter.drawText(int(x), int(y), int(cell_w), int(cell_h), Qt.AlignCenter, hand)
        
        # 频率文字
        if 0 < freq < 1.0:
            freq_font = QFont("Arial", max(6, int(min(cell_w, cell_h) / 5)))
            painter.setFont(freq_font)
            painter.setPen(QColor("#cccccc"))
            freq_text = f"{freq*100:.0f}%"
            painter.drawText(int(x), int(y + cell_h * 0.5), int(cell_w), int(cell_h * 0.4),
                            Qt.AlignCenter, freq_text)
    
    def mouseMoveEvent(self, event):
        """鼠标悬停显示详情"""
        cell_w = self.width() / 13
        cell_h = self.height() / 13
        col = int(event.position().x() / cell_w)
        row = int(event.position().y() / cell_h)
        
        if 0 <= row < 13 and 0 <= col < 13:
            self.hovered_cell = (row, col)
            hand = HAND_MATRIX[row][col]
            hand_strategy = self.strategy_data.get(hand, {})
            
            if self.view_mode == "strategy" and len(self.action_order) > 1:
                # 显示策略分布
                parts = []
                for action in self.action_order:
                    freq = hand_strategy.get(action, 0)
                    if freq > 0:
                        parts.append(f"{action}: {freq*100:.0f}%")
                tooltip = f"{hand}\n" + "\n".join(parts) if parts else f"{hand}: fold 100%"
            else:
                total_freq = sum(hand_strategy.values())
                tooltip = f"{hand}: {total_freq*100:.1f}%"
            
            self.setToolTip(tooltip)
        else:
            self.hovered_cell = None
            self.setToolTip("")
    
    def mousePressEvent(self, event):
        """点击手牌"""
        cell_w = self.width() / 13
        cell_h = self.height() / 13
        col = int(event.position().x() / cell_w)
        row = int(event.position().y() / cell_h)
        
        if 0 <= row < 13 and 0 <= col < 13:
            hand = HAND_MATRIX[row][col]
            hand_strategy = self.strategy_data.get(hand, {})
            self.hand_clicked.emit(hand, hand_strategy)


class ActionSequenceBuilder(QWidget):
    """行动序列构建器"""
    
    sequence_changed = Signal(list)  # 行动序列变化信号
    position_selected = Signal(str, list)  # 位置, 可用行动列表
    
    def __init__(self, base_path):
        super().__init__()
        self.base_path = base_path
        self.action_sequence = []
        self.init_ui()
        self._update_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 标题
        title = QLabel("Action Sequence")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: white;")
        layout.addWidget(title)
        
        # 当前序列显示
        self.sequence_label = QLabel("(Empty - Select opener)")
        self.sequence_label.setStyleSheet("color: #888888; font-size: 11px;")
        self.sequence_label.setWordWrap(True)
        layout.addWidget(self.sequence_label)
        
        # 可用行动按钮区域
        self.actions_frame = QFrame()
        self.actions_layout = QVBoxLayout(self.actions_frame)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(4)
        layout.addWidget(self.actions_frame)
        
        # Back / Reset 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.back_btn = QPushButton("← Back")
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a4a;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #4a4a5a; }
            QPushButton:disabled { background-color: #2a2a2a; color: #555555; }
        """)
        self.back_btn.clicked.connect(self.back_sequence)
        self.back_btn.setEnabled(False)
        btn_layout.addWidget(self.back_btn)
        
        reset_btn = QPushButton("Reset")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a3a3a;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #5a4a4a; }
        """)
        reset_btn.clicked.connect(self.reset_sequence)
        btn_layout.addWidget(reset_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
    
    def set_base_path(self, path):
        self.base_path = path
        self.reset_sequence()
    
    def reset_sequence(self):
        self.action_sequence = []
        self._update_ui()
        self.sequence_changed.emit([])
    
    def back_sequence(self):
        if self.action_sequence:
            self.action_sequence.pop()
            self._update_ui()
            self.sequence_changed.emit(self.action_sequence.copy())
    
    def _update_ui(self):
        # 清空现有按钮
        while self.actions_layout.count():
            item = self.actions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.back_btn.setEnabled(len(self.action_sequence) > 0)
        
        if not self.action_sequence:
            self.sequence_label.setText("(Empty - Select opener)")
        else:
            seq_text = " → ".join([f"{pos} {act}" for pos, act in self.action_sequence])
            self.sequence_label.setText(seq_text)
        
        available_actions = self._get_available_actions()
        
        if available_actions:
            # 按位置顺序排列（UTG -> HJ -> CO -> BTN -> SB -> BB）
            sorted_positions = sorted(
                available_actions.keys(),
                key=lambda p: POSITIONS.index(p) if p in POSITIONS else 99
            )
            
            for position in sorted_positions:
                actions = available_actions[position]
                pos_label = QLabel(position)
                pos_label.setStyleSheet("color: #aaaaaa; font-size: 11px; margin-top: 4px;")
                self.actions_layout.addWidget(pos_label)
                
                btn_layout = QHBoxLayout()
                btn_layout.setSpacing(4)
                for action in actions:
                    btn = QPushButton(action)
                    # 根据行动类型设置颜色
                    color = get_action_color(action)
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {color.name()};
                            color: white;
                            border: none;
                            padding: 4px 8px;
                            border-radius: 3px;
                            font-size: 11px;
                        }}
                        QPushButton:hover {{ background-color: {color.lighter(120).name()}; }}
                    """)
                    btn.clicked.connect(lambda checked, p=position, a=action: self._add_action(p, a))
                    btn_layout.addWidget(btn)
                btn_layout.addStretch()
                
                container = QWidget()
                container.setLayout(btn_layout)
                self.actions_layout.addWidget(container)
    
    def _get_current_path(self):
        if not self.base_path:
            return None
        
        path = os.path.join(self.base_path, "ranges")
        for position, action in self.action_sequence:
            path = os.path.join(path, position, action)
        
        return path if os.path.exists(path) else None
    
    def _get_available_actions(self):
        if not self.base_path:
            return {}
        
        if not self.action_sequence:
            ranges_path = os.path.join(self.base_path, "ranges")
            if os.path.exists(ranges_path):
                positions = {}
                for pos in os.listdir(ranges_path):
                    pos_path = os.path.join(ranges_path, pos)
                    if os.path.isdir(pos_path) and not pos.startswith('.'):
                        actions = [a for a in os.listdir(pos_path) 
                                  if os.path.isdir(os.path.join(pos_path, a)) and not a.startswith('.')]
                        if actions:
                            positions[pos] = sorted(actions, key=self._sort_action_key)
                return positions
            return {}
        
        current_path = self._get_current_path()
        if not current_path or not os.path.exists(current_path):
            return {}
        
        positions = {}
        for item in os.listdir(current_path):
            item_path = os.path.join(current_path, item)
            if os.path.isdir(item_path) and not item.startswith('.'):
                if item in POSITIONS or item in ["UTG", "HJ", "CO", "BTN", "SB", "BB"]:
                    actions = [a for a in os.listdir(item_path)
                              if os.path.isdir(os.path.join(item_path, a)) and not a.startswith('.')]
                    if actions:
                        positions[item] = sorted(actions, key=self._sort_action_key)
        
        return positions
    
    def _sort_action_key(self, action):
        match = re.match(r'(\d+\.?\d*)bb', action)
        if match:
            return (0, float(match.group(1)))
        if action == 'call':
            return (1, 0)
        if action == 'fold':
            return (2, 0)
        if action == 'allin':
            return (3, 0)
        return (4, 0)
    
    def _add_action(self, position, action):
        self.action_sequence.append((position, action))
        self._update_ui()
        self.sequence_changed.emit(self.action_sequence)
    
    def get_available_range_positions(self):
        """获取当前节点下可查看 range 的位置"""
        current_path = self._get_current_path()
        if not current_path:
            return []
        
        positions = []
        for item in os.listdir(current_path):
            if item.endswith('.txt') and not item.startswith('.'):
                pos = item.replace('.txt', '')
                positions.append(pos)
        
        return positions
    
    def get_position_actions(self, position):
        """获取某位置在当前节点的所有可用行动"""
        current_path = self._get_current_path()
        if not current_path:
            return []
        
        pos_path = os.path.join(current_path, position)
        if not os.path.exists(pos_path):
            return []
        
        actions = [a for a in os.listdir(pos_path)
                  if os.path.isdir(os.path.join(pos_path, a)) and not a.startswith('.')]
        return sorted(actions, key=self._sort_action_key)


class PreflopRangePage(QWidget):
    """Preflop Range 页面"""
    
    def __init__(self, db_manager=None):
        super().__init__()
        self.db = db_manager
        self.current_stack = "50bb"
        self.range_base_path = self._get_range_base_path()
        self.current_position = None
        self.current_position_type = None  # "acted" or "next"
        self.acted_positions = set()
        self.next_positions = set()
        self.init_ui()
    
    def _get_range_base_path(self):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        stack_map = {
            "50bb": "cash6m_50bb_nl50_gto_gto",
            "100bb": "cash6m_100bb_nl50_gto_gto",
            "200bb": "cash6m_200bb_nl50_gto_gto",
        }
        
        folder = stack_map.get(self.current_stack, stack_map["50bb"])
        return os.path.join(project_root, "assets", "range", folder)
    
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 左侧面板
        left_panel = QFrame()
        left_panel.setFixedWidth(300)
        left_panel.setStyleSheet("background-color: #252525; border-right: 1px solid #3a3a3a;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(16)
        
        title = QLabel("Preflop Range")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        left_layout.addWidget(title)
        
        # Stack Depth
        stack_frame = QFrame()
        stack_layout = QVBoxLayout(stack_frame)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.setSpacing(4)
        
        stack_label = QLabel("Stack Depth")
        stack_label.setStyleSheet("color: #888888; font-size: 11px;")
        stack_layout.addWidget(stack_label)
        
        self.stack_combo = QComboBox()
        self.stack_combo.addItems(["50bb", "100bb", "200bb"])
        self.stack_combo.setStyleSheet("""
            QComboBox {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { image: none; }
        """)
        self.stack_combo.currentTextChanged.connect(self._on_stack_changed)
        stack_layout.addWidget(self.stack_combo)
        left_layout.addWidget(stack_frame)
        
        # 行动序列构建器
        self.action_builder = ActionSequenceBuilder(self.range_base_path)
        self.action_builder.sequence_changed.connect(self._on_sequence_changed)
        left_layout.addWidget(self.action_builder)
        
        # 位置选择
        # 已行动位置 - Range 视图
        range_frame = QFrame()
        range_layout = QVBoxLayout(range_frame)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(4)
        
        self.range_label = QLabel("📊 View Range (Acted)")
        self.range_label.setStyleSheet("color: #3498db; font-size: 11px; font-weight: bold;")
        range_layout.addWidget(self.range_label)
        
        self.range_buttons_layout = QHBoxLayout()
        self.range_buttons_layout.setSpacing(4)
        range_layout.addLayout(self.range_buttons_layout)
        
        left_layout.addWidget(range_frame)
        
        # 待行动位置 - Strategy 视图
        strategy_frame = QFrame()
        strategy_layout = QVBoxLayout(strategy_frame)
        strategy_layout.setContentsMargins(0, 0, 0, 0)
        strategy_layout.setSpacing(4)
        
        self.strategy_label = QLabel("🎯 View Strategy (Next)")
        self.strategy_label.setStyleSheet("color: #27ae60; font-size: 11px; font-weight: bold;")
        strategy_layout.addWidget(self.strategy_label)
        
        self.strategy_buttons_layout = QHBoxLayout()
        self.strategy_buttons_layout.setSpacing(4)
        strategy_layout.addLayout(self.strategy_buttons_layout)
        
        left_layout.addWidget(strategy_frame)
        
        self.position_buttons = {}
        
        # 行动筛选（Strategy 模式）
        action_filter_frame = QFrame()
        action_filter_layout = QVBoxLayout(action_filter_frame)
        action_filter_layout.setContentsMargins(0, 0, 0, 0)
        action_filter_layout.setSpacing(4)
        
        self.action_filter_label = QLabel("Filter Action")
        self.action_filter_label.setStyleSheet("color: #888888; font-size: 11px;")
        action_filter_layout.addWidget(self.action_filter_label)
        
        self.action_buttons_layout = QHBoxLayout()
        self.action_buttons_layout.setSpacing(4)
        self.action_buttons = {}
        action_filter_layout.addLayout(self.action_buttons_layout)
        
        left_layout.addWidget(action_filter_frame)
        
        # 统计
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        self.stats_label.setWordWrap(True)
        left_layout.addWidget(self.stats_label)
        
        left_layout.addStretch()
        layout.addWidget(left_panel)
        
        # 右侧面板 - 矩阵
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(24, 24, 24, 24)
        
        self.range_title = QLabel("Select an action sequence")
        self.range_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        right_layout.addWidget(self.range_title)
        
        self.range_matrix = StrategyMatrixWidget()
        self.range_matrix.hand_clicked.connect(self._on_hand_clicked)
        right_layout.addWidget(self.range_matrix, 1)
        
        # 图例
        self.legend_layout = QHBoxLayout()
        self.legend_layout.setSpacing(16)
        right_layout.addLayout(self.legend_layout)
        
        layout.addWidget(right_panel, 1)
        
        self._update_position_buttons([], [])
    
    def _on_stack_changed(self, stack):
        self.current_stack = stack
        self.range_base_path = self._get_range_base_path()
        self.action_builder.set_base_path(self.range_base_path)
        self.range_matrix.clear()
        self._update_position_buttons([], [])
        self._update_action_buttons([])
        self.range_title.setText("Select an action sequence")
        self.stats_label.setText("")
    
    def _on_sequence_changed(self, sequence):
        current_path = self.action_builder._get_current_path()
        
        # 获取已行动位置（从行动序列中提取，去重但保持顺序）
        seen = set()
        acted_positions = []
        for pos, action in sequence:
            if pos not in seen:
                seen.add(pos)
                acted_positions.append(pos)
        
        # 获取待行动位置（有子目录的位置）
        next_positions = []
        if current_path and os.path.exists(current_path):
            for item in os.listdir(current_path):
                item_path = os.path.join(current_path, item)
                if os.path.isdir(item_path) and not item.startswith('.'):
                    if item in POSITIONS or item in ["UTG", "HJ", "CO", "BTN", "SB", "BB"]:
                        next_positions.append(item)
        
        self._update_position_buttons(acted_positions, next_positions)
        self._update_action_buttons([])
        self.current_position = None
        self.current_position_type = None  # "acted" or "next"
        
        if not acted_positions and not next_positions:
            self.range_matrix.clear()
            self.range_title.setText("Select an opener to start")
            self.stats_label.setText("")
        elif not next_positions and acted_positions:
            self.range_matrix.clear()
            self.range_title.setText("Select a position to view range")
            self.stats_label.setText("")
    
    def _update_position_buttons(self, acted_positions, next_positions):
        """更新位置按钮
        acted_positions: 已行动的位置（显示 Range）
        next_positions: 待行动的位置（显示 Strategy）
        """
        # 清空 Range 按钮
        while self.range_buttons_layout.count():
            item = self.range_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 清空 Strategy 按钮
        while self.strategy_buttons_layout.count():
            item = self.strategy_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.position_buttons = {}
        self.acted_positions = set(acted_positions)
        self.next_positions = set(next_positions)
        
        # 更新 Range 标签可见性
        self.range_label.setVisible(bool(acted_positions))
        
        # 已行动位置（蓝色系 - Range）
        for pos in acted_positions:  # 保持行动顺序
            btn = QPushButton(pos)
            btn.setCheckable(True)
            btn.setToolTip(f"View {pos}'s Range")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2c3e50;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #34495e; }
                QPushButton:checked { background-color: #3498db; }
            """)
            btn.clicked.connect(lambda checked, p=pos: self._on_position_selected(p, "acted"))
            self.range_buttons_layout.addWidget(btn)
            self.position_buttons[f"range_{pos}"] = btn
        
        self.range_buttons_layout.addStretch()
        
        # 更新 Strategy 标签可见性
        self.strategy_label.setVisible(bool(next_positions))
        
        # 待行动位置（绿色系 - Strategy）
        for pos in sorted(next_positions, key=lambda p: POSITIONS.index(p) if p in POSITIONS else 99):
            btn = QPushButton(pos)
            btn.setCheckable(True)
            btn.setToolTip(f"View {pos}'s Strategy")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e3a2f;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #2a5040; }
                QPushButton:checked { background-color: #27ae60; }
            """)
            btn.clicked.connect(lambda checked, p=pos: self._on_position_selected(p, "next"))
            self.strategy_buttons_layout.addWidget(btn)
            self.position_buttons[f"strategy_{pos}"] = btn
        
        self.strategy_buttons_layout.addStretch()
    
    def _update_action_buttons(self, actions):
        """更新行动筛选按钮"""
        while self.action_buttons_layout.count():
            item = self.action_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.action_buttons = {}
        
        if not actions:
            self.action_filter_label.setVisible(False)
            return
        
        self.action_filter_label.setVisible(True)
        
        # "All" 按钮显示策略视图
        all_btn = QPushButton("Strategy")
        all_btn.setCheckable(True)
        all_btn.setChecked(True)
        all_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #4a4a4a; }
            QPushButton:checked { background-color: #6a6a6a; }
        """)
        all_btn.clicked.connect(lambda: self._on_action_filter_selected(None))
        self.action_buttons_layout.addWidget(all_btn)
        self.action_buttons[None] = all_btn
        
        # 各个行动按钮
        for action in actions:
            btn = QPushButton(action)
            btn.setCheckable(True)
            color = get_action_color(action)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #3a3a3a;
                    color: white;
                    border: none;
                    padding: 4px 8px;
                    border-radius: 3px;
                    font-size: 11px;
                }}
                QPushButton:hover {{ background-color: #4a4a4a; }}
                QPushButton:checked {{ background-color: {color.name()}; }}
            """)
            btn.clicked.connect(lambda checked, a=action: self._on_action_filter_selected(a))
            self.action_buttons_layout.addWidget(btn)
            self.action_buttons[action] = btn
        
        self.action_buttons_layout.addStretch()
    
    def _on_position_selected(self, position, position_type="next"):
        """选择位置
        position_type: "acted" (已行动，显示 Range) 或 "next" (待行动，显示 Strategy)
        """
        # 取消所有按钮的选中状态
        for key, btn in self.position_buttons.items():
            if position_type == "acted":
                btn.setChecked(key == f"range_{position}")
            else:
                btn.setChecked(key == f"strategy_{position}")
        
        self.current_position = position
        self.current_position_type = position_type
        
        if position_type == "acted":
            # 已行动位置 - 显示其 Range
            self._update_action_buttons([])  # 清空行动按钮
            self._load_acted_range(position)
        else:
            # 待行动位置 - 显示其 Strategy
            actions = self.action_builder.get_position_actions(position)
            self._update_action_buttons(actions)
            self._load_strategy(position, actions)
    
    def _on_action_filter_selected(self, action):
        """选择特定行动筛选"""
        for act, btn in self.action_buttons.items():
            btn.setChecked(act == action)
        
        if not self.current_position:
            return
        
        actions = self.action_builder.get_position_actions(self.current_position)
        
        if action is None:
            # 显示策略视图
            self._load_strategy(self.current_position, actions)
        else:
            # 显示特定行动的 range
            self._load_single_range(self.current_position, action)
    
    def _load_acted_range(self, position):
        """加载已行动位置的 Range"""
        current_path = self.action_builder._get_current_path()
        if not current_path:
            return
        
        # 递归搜索当前路径下该位置的 range 文件
        range_path = self._find_range_file(current_path, position)
        if not range_path:
            self.range_matrix.clear()
            self.range_title.setText(f"No range data for {position}")
            self.stats_label.setText("")
            return
        
        range_data = self._parse_range_file(range_path)
        
        # 使用单色显示 range
        self.range_matrix.set_range(range_data, None)
        
        # 更新标题 - 显示该位置的行动
        seq = self.action_builder.action_sequence
        pos_action = None
        for pos, action in seq:
            if pos == position:
                pos_action = action
                break
        
        seq_text = " → ".join([f"{pos} {act}" for pos, act in seq])
        if pos_action:
            self.range_title.setText(f"{position}'s {pos_action} Range: {seq_text}")
        else:
            self.range_title.setText(f"{position}'s Range: {seq_text}")
        
        # 更新图例（单色）
        self._update_legend_single()
        
        # 更新统计
        self._update_range_stats(range_data, pos_action or "range")
    
    def _update_legend_single(self):
        """更新单色图例"""
        while self.legend_layout.count():
            item = self.legend_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        legend_items = [
            ("#3a9a3a", "100%"),
            ("#4a8a4a", "75-99%"),
            ("#5a7a4a", "50-74%"),
            ("#6a5a3a", "25-49%"),
            ("#4a3a2a", "1-24%"),
            ("#2a2a2a", "0%"),
        ]
        
        for color, text in legend_items:
            item = QWidget()
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(4)
            
            color_box = QFrame()
            color_box.setFixedSize(16, 16)
            color_box.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
            item_layout.addWidget(color_box)
            
            label = QLabel(text)
            label.setStyleSheet("color: #888888; font-size: 11px;")
            item_layout.addWidget(label)
            
            self.legend_layout.addWidget(item)
        
        self.legend_layout.addStretch()
    
    def _find_range_file(self, base_path, position):
        """查找某位置的 range 文件
        
        优先查找策略：
        1. 当前目录直接的 {position}.txt
        2. 优先查找 opener 位置的子目录（回到 opener 做决定）
        3. 递归搜索其他子目录（按位置顺序）
        """
        target_file = f"{position}.txt"
        
        # 先检查当前目录
        direct_path = os.path.join(base_path, target_file)
        if os.path.exists(direct_path):
            return direct_path
        
        # 获取 opener 位置（优先搜索）
        opener = None
        if self.action_builder.action_sequence:
            opener = self.action_builder.action_sequence[0][0]
        
        try:
            items = os.listdir(base_path)
            # 排序：opener 优先，然后按位置顺序，行动关键词在后
            def sort_key(item):
                if item == opener:
                    return (0, 0)  # opener 最优先
                if item in POSITIONS:
                    return (1, POSITIONS.index(item))
                # call 和 fold 是常见的结束行动
                if item == "call":
                    return (2, 0)
                if item == "fold":
                    return (2, 1)
                return (3, item)
            
            items = sorted(items, key=sort_key)
            
            for item in items:
                item_path = os.path.join(base_path, item)
                if os.path.isdir(item_path) and not item.startswith('.'):
                    result = self._find_range_file(item_path, position)
                    if result:
                        return result
        except Exception:
            pass
        
        return None
    
    def _load_strategy(self, position, actions):
        """加载某位置的完整策略（所有行动的分布）"""
        current_path = self.action_builder._get_current_path()
        if not current_path:
            return
        
        # 读取所有行动的 range
        strategy_data = {}  # {hand: {action: freq}}
        
        for action in actions:
            action_path = os.path.join(current_path, position, action)
            if os.path.exists(action_path):
                # 递归搜索该行动分支下的第一个 range 文件
                range_path = self._find_range_file(action_path, position)
                if range_path:
                    range_data = self._parse_range_file(range_path)
                    for hand, freq in range_data.items():
                        if hand not in strategy_data:
                            strategy_data[hand] = {}
                        strategy_data[hand][action] = freq
        
        # 计算每个行动的 combos
        action_stats = {action: 0 for action in actions}
        for hand, hand_strategy in strategy_data.items():
            combos = self._get_hand_combos(hand)
            for action in actions:
                freq = hand_strategy.get(action, 0)
                action_stats[action] += combos * freq
        
        # 过滤掉 0% 的行动（用于图例和统计）
        non_zero_actions = [a for a in actions if action_stats[a] > 0.01]
        
        # 更新显示
        self.range_matrix.set_strategy(strategy_data, actions)
        
        # 更新标题
        seq_text = " → ".join([f"{pos} {act}" for pos, act in self.action_builder.action_sequence])
        self.range_title.setText(f"{position}'s Strategy: {seq_text}")
        
        # 更新图例（带百分比）
        self._update_legend(non_zero_actions, action_stats)
        
        # 更新统计（只显示非零行动）
        self._update_strategy_stats_with_data(action_stats, non_zero_actions)
    
    def _load_single_range(self, position, action):
        """加载特定行动的 range"""
        current_path = self.action_builder._get_current_path()
        if not current_path:
            return
        
        action_path = os.path.join(current_path, position, action)
        if not os.path.exists(action_path):
            return
        
        # 递归搜索该行动分支下的第一个 range 文件
        range_path = self._find_range_file(action_path, position)
        if not range_path:
            return
        
        range_data = self._parse_range_file(range_path)
        self.range_matrix.set_range(range_data, action)
        
        # 更新标题
        seq_text = " → ".join([f"{pos} {act}" for pos, act in self.action_builder.action_sequence])
        self.range_title.setText(f"{position}'s {action} Range: {seq_text}")
        
        # 更新图例
        self._update_legend([action])
        
        # 更新统计
        self._update_range_stats(range_data, action)
    
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
    
    def _update_legend(self, actions, action_stats=None):
        """更新图例，可选显示百分比"""
        while self.legend_layout.count():
            item = self.legend_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 计算 fold 百分比
        fold_pct = ""
        if action_stats:
            total_action_combos = sum(action_stats.values())
            fold_combos = 1326 - total_action_combos
            fold_pct = f" ({fold_combos / 1326 * 100:.0f}%)"
        
        # 先添加 Fold（背景色）
        fold_item = QWidget()
        fold_layout = QHBoxLayout(fold_item)
        fold_layout.setContentsMargins(0, 0, 0, 0)
        fold_layout.setSpacing(4)
        
        fold_color = ACTION_COLORS["fold"]
        fold_box = QFrame()
        fold_box.setFixedSize(16, 16)
        fold_box.setStyleSheet(f"background-color: {fold_color.name()}; border-radius: 2px;")
        fold_layout.addWidget(fold_box)
        
        fold_label = QLabel(f"Fold{fold_pct}")
        fold_label.setStyleSheet("color: #888888; font-size: 11px;")
        fold_layout.addWidget(fold_label)
        
        self.legend_layout.addWidget(fold_item)
        
        # 添加其他行动（带百分比）
        for action in actions:
            item = QWidget()
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(4)
            
            color = get_action_color(action)
            color_box = QFrame()
            color_box.setFixedSize(16, 16)
            color_box.setStyleSheet(f"background-color: {color.name()}; border-radius: 2px;")
            item_layout.addWidget(color_box)
            
            # 添加百分比显示
            action_pct = ""
            if action_stats and action in action_stats:
                pct = action_stats[action] / 1326 * 100
                action_pct = f" ({pct:.0f}%)"
            
            label = QLabel(f"{action}{action_pct}")
            label.setStyleSheet("color: #888888; font-size: 11px;")
            item_layout.addWidget(label)
            
            self.legend_layout.addWidget(item)
        
        self.legend_layout.addStretch()
    
    def _update_strategy_stats_with_data(self, action_stats, actions):
        """使用预计算的数据更新策略统计"""
        # 计算 Fold（剩余的部分）
        total_action_combos = sum(action_stats.values())
        fold_combos = 1326 - total_action_combos
        fold_pct = fold_combos / 1326 * 100
        
        # Fold 始终显示（作为背景）
        parts = [f"Fold: {fold_combos:.0f} ({fold_pct:.1f}%)"]
        
        # 只显示非零的行动
        for action in actions:
            combos = action_stats.get(action, 0)
            if combos > 0.01:  # 过滤掉接近 0 的
                pct = combos / 1326 * 100
                parts.append(f"{action}: {combos:.0f} ({pct:.1f}%)")
        
        self.stats_label.setText("\n".join(parts))
    
    def _update_range_stats(self, range_data, action):
        """更新单一 range 统计"""
        total_combos = 0
        for hand, freq in range_data.items():
            combos = self._get_hand_combos(hand)
            total_combos += combos * freq
        
        pct = total_combos / 1326 * 100
        self.stats_label.setText(f"{action}: {total_combos:.0f} combos ({pct:.1f}%)")
    
    def _get_hand_combos(self, hand):
        if len(hand) == 2:
            return 6
        elif hand.endswith('s'):
            return 4
        else:
            return 12
    
    def _on_hand_clicked(self, hand, strategy):
        """点击手牌显示详情"""
        if strategy:
            parts = [f"{action}: {freq*100:.0f}%" for action, freq in strategy.items() if freq > 0]
            print(f"{hand}: " + ", ".join(parts))
    
    def refresh_data(self):
        pass

