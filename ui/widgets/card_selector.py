"""
可视化卡牌选择器组件
点击选择/取消选择卡牌
"""
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QHBoxLayout, QVBoxLayout, 
    QPushButton, QLabel, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class CardButton(QPushButton):
    """单张卡牌按钮"""
    
    def __init__(self, rank: str, suit: str):
        super().__init__()
        self.rank = rank
        self.suit = suit
        self.card_str = f"{rank}{suit}"
        self._selected = False
        self._disabled = False
        
        # 花色颜色 - 更鲜艳的颜色
        self.suit_colors = {
            'h': '#ff4757',  # 红桃 - 亮红色
            'd': '#70a1ff',  # 方块 - 亮蓝色
            'c': '#2ed573',  # 梅花 - 亮绿色
            's': '#a4b0be',  # 黑桃 - 浅灰色（深色背景上更清晰）
        }
        
        # 花色符号
        self.suit_symbols = {
            'h': '♥',
            'd': '♦', 
            'c': '♣',
            's': '♠',
        }
        
        self.setText(f"{rank}{self.suit_symbols[suit]}")
        self.setFixedSize(52, 60)  # 更大的按钮
        self.setFont(QFont("Arial", 14, QFont.Bold))  # 更大的字体
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()
    
    def _update_style(self):
        """更新按钮样式"""
        color = self.suit_colors[self.suit]
        
        if self._disabled:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: #1a1a1a;
                    color: #333333;
                    border: 1px solid #2a2a2a;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 14px;
                }}
            """)
        elif self._selected:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    border: 3px solid #ffd700;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 14px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: #363636;
                    color: {color};
                    border: 2px solid #4a4a4a;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background-color: #454545;
                    border: 2px solid {color};
                }}
            """)
    
    def set_selected(self, selected: bool):
        """设置选中状态"""
        self._selected = selected
        self._update_style()
    
    def is_selected(self) -> bool:
        return self._selected
    
    def set_card_disabled(self, disabled: bool):
        """设置禁用状态（用于显示已被使用的牌）"""
        self._disabled = disabled
        self.setEnabled(not disabled)
        self._update_style()


class CardSelector(QWidget):
    """卡牌选择器 - 显示 52 张牌的网格，支持点击选择"""
    
    # 信号：选择变化时发出
    selection_changed = Signal(list)  # 发送选中的卡牌列表 [card_str, ...]
    
    def __init__(self, max_selection: int = 3, title: str = "Select Cards"):
        super().__init__()
        self.max_selection = max_selection
        self.title = title
        self.card_buttons = {}  # card_str -> CardButton
        self.selected_cards = []  # 按选择顺序存储
        self.disabled_cards = set()  # 被禁用的牌
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 标题和已选显示
        header = QHBoxLayout()
        
        title_label = QLabel(self.title)
        title_label.setStyleSheet("color: #aaaaaa; font-size: 14px; font-weight: bold;")
        header.addWidget(title_label)
        
        header.addStretch()
        
        # 显示已选择的卡牌
        self.selection_label = QLabel("None selected")
        self.selection_label.setStyleSheet("color: #4a9eff; font-size: 16px; font-weight: bold;")
        header.addWidget(self.selection_label)
        
        layout.addLayout(header)
        
        # 卡牌网格
        grid_frame = QFrame()
        grid_frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        
        grid_layout = QGridLayout(grid_frame)
        grid_layout.setSpacing(4)
        grid_layout.setContentsMargins(12, 12, 12, 12)
        
        ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']  # 黑桃、红桃、方块、梅花
        
        # 添加花色标签列
        for row, suit in enumerate(suits):
            suit_symbols = {'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}
            suit_colors = {'s': '#a4b0be', 'h': '#ff4757', 'd': '#70a1ff', 'c': '#2ed573'}
            
            label = QLabel(suit_symbols[suit])
            label.setStyleSheet(f"color: {suit_colors[suit]}; font-size: 22px; font-weight: bold;")
            label.setAlignment(Qt.AlignCenter)
            label.setFixedWidth(30)
            grid_layout.addWidget(label, row, 0)
        
        # 添加卡牌按钮
        for col, rank in enumerate(ranks):
            for row, suit in enumerate(suits):
                btn = CardButton(rank, suit)
                btn.clicked.connect(lambda checked, b=btn: self._on_card_clicked(b))
                grid_layout.addWidget(btn, row, col + 1)
                self.card_buttons[btn.card_str] = btn
        
        layout.addWidget(grid_frame)
        
        # 清除按钮
        clear_btn = QPushButton("Clear Selection")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #888888;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                color: white;
            }
        """)
        clear_btn.clicked.connect(self.clear_selection)
        clear_btn.setFixedHeight(28)
        layout.addWidget(clear_btn)
    
    def _on_card_clicked(self, btn: CardButton):
        """处理卡牌点击"""
        if btn.is_selected():
            # 取消选择
            btn.set_selected(False)
            if btn.card_str in self.selected_cards:
                self.selected_cards.remove(btn.card_str)
        else:
            # 选择
            if len(self.selected_cards) >= self.max_selection:
                # 已达最大数量，先取消最早选择的
                oldest = self.selected_cards.pop(0)
                self.card_buttons[oldest].set_selected(False)
            
            btn.set_selected(True)
            self.selected_cards.append(btn.card_str)
        
        self._update_selection_label()
        self.selection_changed.emit(self.selected_cards.copy())
    
    def _update_selection_label(self):
        """更新选择标签"""
        if not self.selected_cards:
            self.selection_label.setText("None selected")
            self.selection_label.setStyleSheet("color: #666666; font-size: 16px;")
        else:
            # 显示选中的牌（带花色符号）
            symbols = {'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}
            display = "  ".join(
                f"{c[0]}{symbols.get(c[1], c[1])}" for c in self.selected_cards
            )
            self.selection_label.setText(display)
            
            if len(self.selected_cards) == self.max_selection:
                self.selection_label.setStyleSheet("color: #2ed573; font-size: 18px; font-weight: bold;")
            else:
                self.selection_label.setStyleSheet("color: #ffa502; font-size: 18px; font-weight: bold;")
    
    def clear_selection(self):
        """清除所有选择"""
        for card_str in self.selected_cards:
            if card_str in self.card_buttons:
                self.card_buttons[card_str].set_selected(False)
        self.selected_cards.clear()
        self._update_selection_label()
        self.selection_changed.emit([])
    
    def get_selected_cards(self) -> list:
        """获取已选择的卡牌列表"""
        return self.selected_cards.copy()
    
    def set_selected_cards(self, cards: list):
        """设置选中的卡牌"""
        self.clear_selection()
        for card_str in cards[:self.max_selection]:
            card_str = card_str.strip()
            if card_str in self.card_buttons:
                btn = self.card_buttons[card_str]
                btn.set_selected(True)
                self.selected_cards.append(card_str)
        self._update_selection_label()
    
    def set_disabled_cards(self, cards: list):
        """设置禁用的卡牌（例如已在 range 中使用的）"""
        # 先启用所有之前禁用的
        for card_str in self.disabled_cards:
            if card_str in self.card_buttons:
                self.card_buttons[card_str].set_card_disabled(False)
        
        self.disabled_cards = set(cards)
        
        # 禁用新的
        for card_str in self.disabled_cards:
            if card_str in self.card_buttons:
                self.card_buttons[card_str].set_card_disabled(True)
                # 如果之前选中了，取消选中
                if card_str in self.selected_cards:
                    self.selected_cards.remove(card_str)
        
        self._update_selection_label()


