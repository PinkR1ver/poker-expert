"""
Solver Results 页面
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QSizePolicy, QPushButton, QScrollArea, QGridLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QBrush

import random
from collections import defaultdict
from copy import deepcopy

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

ACTION_COLORS = {"fold": QColor("#5d6d7e"), "check": QColor("#16a085"), "call": QColor("#27ae60")}


def get_action_color(action_str: str) -> QColor:
    action_lower = action_str.lower()
    if "fold" in action_lower:
        return QColor("#5d6d7e")
    elif "check" in action_lower:
        return QColor("#16a085")
    elif "call" in action_lower:
        return QColor("#27ae60")
    elif "bet" in action_lower or "raise" in action_lower:
        import re
        match = re.search(r'(\d+)', action_str)
        if match:
            size = int(match.group(1))
            t = min(1.0, size / 150)
            return QColor(int(255 - t * 80), int(100 - t * 70), int(100 - t * 70))
        return QColor("#e74c3c")
    return QColor("#3498db")


def get_action_priority(action_str: str) -> float:
    action_lower = action_str.lower()
    if "fold" in action_lower:
        return 0
    elif "check" in action_lower:
        return 1
    elif "call" in action_lower:
        return 2
    else:
        import re
        match = re.search(r'(\d+)', action_str)
        if match:
            return 3 + int(match.group(1)) / 1000
        return 3


class EquityPieChart(QWidget):
    """Equity 饼图"""
    def __init__(self):
        super().__init__()
        self.oop_equity = 50.0
        self.oop_label = "OOP"
        self.ip_label = "IP"
        self.setFixedSize(120, 110)
    
    def set_equity(self, oop_eq: float, oop_label: str = "OOP", ip_label: str = "IP"):
        self.oop_equity = oop_eq
        self.oop_label = oop_label
        self.ip_label = ip_label
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        size = 70
        x = (self.width() - size) // 2
        y = 5
        
        oop_angle = int(self.oop_equity / 100 * 360 * 16)
        painter.setBrush(QBrush(QColor("#3498db")))
        painter.setPen(Qt.NoPen)
        painter.drawPie(x, y, size, size, 90 * 16, -oop_angle)
        
        ip_angle = int((100 - self.oop_equity) / 100 * 360 * 16)
        painter.setBrush(QBrush(QColor("#27ae60")))
        painter.drawPie(x, y, size, size, 90 * 16 - oop_angle, -ip_angle)
        
        painter.setPen(QColor("white"))
        font = QFont()
        font.setPixelSize(9)
        painter.setFont(font)
        painter.drawText(0, y + size + 2, self.width(), 14, Qt.AlignCenter,
                        f"{self.oop_label}: {self.oop_equity:.1f}%")
        painter.drawText(0, y + size + 14, self.width(), 14, Qt.AlignCenter,
                        f"{self.ip_label}: {100-self.oop_equity:.1f}%")
        painter.end()


class EquityLineChart(QWidget):
    """Equity 变化折线图 - 显示 OOP 和 IP 两条线"""
    def __init__(self):
        super().__init__()
        self.equity_history = []  # [(action_label, oop_eq, ip_eq), ...]
        self.oop_label = "OOP"
        self.ip_label = "IP"
        self.setFixedSize(160, 110)
    
    def set_history(self, history: list, oop_label: str = "OOP", ip_label: str = "IP"):
        self.equity_history = history
        self.oop_label = oop_label
        self.ip_label = ip_label
        self.update()
    
    def clear(self):
        self.equity_history = []
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.fillRect(0, 0, self.width(), self.height(), QColor("#252525"))
        
        if len(self.equity_history) < 1:
            painter.setPen(QColor("#666666"))
            font = QFont()
            font.setPixelSize(10)
            painter.setFont(font)
            painter.drawText(0, 0, self.width(), self.height(), Qt.AlignCenter, "Navigate to see changes")
            painter.end()
            return
        
        margin_left = 25
        margin_right = 10
        margin_top = 10
        margin_bottom = 30
        
        w = self.width() - margin_left - margin_right
        h = self.height() - margin_top - margin_bottom
        
        # 坐标轴
        painter.setPen(QPen(QColor("#4a4a4a"), 1))
        painter.drawLine(margin_left, margin_top, margin_left, margin_top + h)
        painter.drawLine(margin_left, margin_top + h, margin_left + w, margin_top + h)
        
        # Y 轴标签
        painter.setPen(QColor("#888888"))
        font = QFont()
        font.setPixelSize(8)
        painter.setFont(font)
        painter.drawText(2, margin_top - 2, 20, 12, Qt.AlignRight, "100")
        painter.drawText(2, margin_top + h // 2 - 6, 20, 12, Qt.AlignRight, "50")
        painter.drawText(2, margin_top + h - 6, 20, 12, Qt.AlignRight, "0")
        
        # 50% 参考线
        painter.setPen(QPen(QColor("#333333"), 1, Qt.DotLine))
        y_50 = margin_top + h // 2
        painter.drawLine(margin_left, y_50, margin_left + w, y_50)
        
        n = len(self.equity_history)
        
        # 绘制 OOP 折线（蓝色）
        painter.setPen(QPen(QColor("#3498db"), 2))
        oop_points = []
        for i, (label, oop_eq, ip_eq) in enumerate(self.equity_history):
            x = margin_left + int(i / max(1, n - 1) * w) if n > 1 else margin_left + w // 2
            y = margin_top + int((100 - oop_eq) / 100 * h)
            oop_points.append((x, y))
        
        for i in range(len(oop_points) - 1):
            painter.drawLine(oop_points[i][0], oop_points[i][1], oop_points[i+1][0], oop_points[i+1][1])
        
        # 绘制 IP 折线（绿色）
        painter.setPen(QPen(QColor("#27ae60"), 2))
        ip_points = []
        for i, (label, oop_eq, ip_eq) in enumerate(self.equity_history):
            x = margin_left + int(i / max(1, n - 1) * w) if n > 1 else margin_left + w // 2
            y = margin_top + int((100 - ip_eq) / 100 * h)
            ip_points.append((x, y))
        
        for i in range(len(ip_points) - 1):
            painter.drawLine(ip_points[i][0], ip_points[i][1], ip_points[i+1][0], ip_points[i+1][1])
        
        # 绘制点
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#3498db")))
        for x, y in oop_points:
            painter.drawEllipse(x - 3, y - 3, 6, 6)
        
        painter.setBrush(QBrush(QColor("#27ae60")))
        for x, y in ip_points:
            painter.drawEllipse(x - 3, y - 3, 6, 6)
        
        # 图例
        painter.setPen(QColor("#3498db"))
        font.setPixelSize(8)
        painter.setFont(font)
        painter.drawText(margin_left, margin_top + h + 8, 50, 12, Qt.AlignLeft, f"● {self.oop_label}")
        
        painter.setPen(QColor("#27ae60"))
        painter.drawText(margin_left + 55, margin_top + h + 8, 50, 12, Qt.AlignLeft, f"● {self.ip_label}")
        
        painter.end()


class HandEquityBar(QWidget):
    """手牌 Equity 条形图"""
    def __init__(self):
        super().__init__()
        self.hand = ""
        self.equity = 0.0
        self.player = "OOP"
        self.setFixedSize(140, 55)
    
    def set_data(self, hand: str, equity: float, player: str):
        self.hand = hand
        self.equity = equity
        self.player = player
        self.update()
    
    def clear(self):
        self.hand = ""
        self.equity = 0.0
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.fillRect(0, 0, self.width(), self.height(), QColor("#252525"))
        
        if not self.hand:
            painter.setPen(QColor("#666666"))
            font = QFont()
            font.setPixelSize(10)
            painter.setFont(font)
            painter.drawText(0, 0, self.width(), self.height(), Qt.AlignCenter, "Click a hand")
            painter.end()
            return
        
        painter.setPen(QColor("#4a9eff"))
        font = QFont()
        font.setPixelSize(13)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(0, 2, self.width(), 16, Qt.AlignCenter, self.hand)
        
        bar_w = self.width() - 20
        bar_h = 12
        bar_x = 10
        bar_y = 22
        
        painter.setBrush(QBrush(QColor("#2a2a2a")))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 4, 4)
        
        eq_w = int(bar_w * self.equity / 100)
        painter.setBrush(QBrush(QColor("#27ae60")))
        painter.drawRoundedRect(bar_x, bar_y, eq_w, bar_h, 4, 4)
        
        painter.setPen(QColor("white"))
        font.setPixelSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(0, bar_y + bar_h + 4, self.width(), 14, Qt.AlignCenter,
                        f"Equity: {self.equity:.1f}%")
        
        painter.end()


class HandStrategyBar(QWidget):
    """手牌策略分布图"""
    def __init__(self):
        super().__init__()
        self.hand = ""
        self.strategy = {}
        self.setMinimumSize(140, 70)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
    
    def set_data(self, hand: str, strategy: dict):
        self.hand = hand
        self.strategy = strategy
        num_actions = len([a for a, f in strategy.items() if f > 0.01])
        self.setFixedHeight(max(70, 40 + num_actions * 12))
        self.update()
    
    def clear(self):
        self.hand = ""
        self.strategy = {}
        self.setFixedHeight(70)
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.fillRect(0, 0, self.width(), self.height(), QColor("#252525"))
        
        if not self.hand or not self.strategy:
            painter.setPen(QColor("#666666"))
            font = QFont()
            font.setPixelSize(10)
            painter.setFont(font)
            painter.drawText(0, 0, self.width(), self.height(), Qt.AlignCenter, "Click a hand")
            painter.end()
            return
        
        painter.setPen(QColor("#4a9eff"))
        font = QFont()
        font.setPixelSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(0, 2, self.width(), 14, Qt.AlignCenter, f"{self.hand} Strategy")
        
        bar_w = self.width() - 20
        bar_h = 14
        bar_x = 10
        bar_y = 18
        
        painter.setBrush(QBrush(QColor("#2a2a2a")))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 4, 4)
        
        sorted_actions = sorted(self.strategy.items(), key=lambda x: get_action_priority(x[0]))
        current_x = float(bar_x)
        
        for action, freq in sorted_actions:
            if freq > 0:
                w = bar_w * freq
                if w > 0.5:
                    color = get_action_color(action)
                    painter.setBrush(QBrush(color))
                    painter.drawRoundedRect(int(current_x), bar_y, int(w) + 1, bar_h, 2, 2)
                    current_x += w
        
        font.setPixelSize(8)
        font.setBold(False)
        painter.setFont(font)
        
        y_offset = bar_y + bar_h + 4
        for action, freq in sorted_actions:
            if freq > 0.005:
                color = get_action_color(action)
                painter.setPen(color)
                text = f"{action}: {freq*100:.0f}%"
                painter.drawText(bar_x, y_offset, bar_w, 11, Qt.AlignLeft, text)
                y_offset += 11
        
        painter.end()


class ConvergenceLineChart(QWidget):
    """Convergence 折线图"""
    def __init__(self):
        super().__init__()
        self.iterations = 0
        self.avg_regret = 1.0
        self.setFixedSize(160, 130)
    
    def set_data(self, iterations: int, avg_regret: float):
        self.iterations = iterations
        self.avg_regret = avg_regret
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.fillRect(0, 0, self.width(), self.height(), QColor("#252525"))
        
        margin_left = 30
        margin_right = 10
        margin_top = 15
        margin_bottom = 35
        
        w = self.width() - margin_left - margin_right
        h = self.height() - margin_top - margin_bottom
        
        painter.setPen(QColor("#888888"))
        font = QFont()
        font.setPixelSize(8)
        painter.setFont(font)
        painter.save()
        painter.translate(8, margin_top + h // 2 + 15)
        painter.rotate(-90)
        painter.drawText(0, 0, "Regret")
        painter.restore()
        
        painter.setPen(QPen(QColor("#4a4a4a"), 1))
        painter.drawLine(margin_left, margin_top, margin_left, margin_top + h)
        painter.drawLine(margin_left, margin_top + h, margin_left + w, margin_top + h)
        
        max_regret = max(1.0, self.avg_regret * 1.2)
        painter.setPen(QColor("#888888"))
        painter.drawText(10, margin_top - 2, 18, 12, Qt.AlignRight, f"{max_regret:.1f}")
        painter.drawText(10, margin_top + h // 2 - 6, 18, 12, Qt.AlignRight, f"{max_regret/2:.1f}")
        painter.drawText(10, margin_top + h - 6, 18, 12, Qt.AlignRight, "0")
        
        painter.drawText(margin_left - 5, margin_top + h + 3, 20, 12, Qt.AlignCenter, "0")
        iter_str = str(self.iterations) if self.iterations < 1000 else f"{self.iterations//1000}k"
        painter.drawText(margin_left + w - 15, margin_top + h + 3, 30, 12, Qt.AlignCenter, iter_str)
        
        painter.drawText(margin_left, margin_top + h + 13, w, 12, Qt.AlignCenter, "Iterations")
        
        painter.setPen(QPen(QColor("#333333"), 1, Qt.DotLine))
        painter.drawLine(margin_left, margin_top + h // 2, margin_left + w, margin_top + h // 2)
        
        painter.setPen(QPen(QColor("#4a9eff"), 2))
        points = []
        for i in range(25):
            x = margin_left + int(i / 24 * w)
            progress = i / 24
            regret = max_regret * (1 - progress) ** 1.5 + self.avg_regret * progress
            y = margin_top + int((1 - min(1, regret / max_regret)) * h)
            points.append((x, y))
        
        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1], points[i+1][0], points[i+1][1])
        
        painter.setBrush(QBrush(QColor("#e74c3c")))
        painter.setPen(Qt.NoPen)
        if points:
            painter.drawEllipse(points[-1][0] - 3, points[-1][1] - 3, 6, 6)
        
        painter.setPen(QColor("white"))
        font.setPixelSize(9)
        painter.setFont(font)
        painter.drawText(0, self.height() - 24, self.width(), 12, Qt.AlignCenter,
                        f"Iters: {self.iterations} | Regret: {self.avg_regret:.2f}")
        
        painter.end()


class StrategyMatrixWidget(QWidget):
    """策略矩阵"""
    hand_clicked = Signal(str, dict)
    
    def __init__(self):
        super().__init__()
        self.strategy_data = {}
        self.action_order = []
        self.view_mode = "strategy"
        self.selected_action = None
        self.player_range = {}
        self.setMinimumSize(350, 350)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
    
    def set_player_range(self, range_weights: dict):
        self.player_range = range_weights
    
    def set_strategy(self, strategy_data: dict, action_order: list):
        self.strategy_data = strategy_data
        self.action_order = action_order
        self.view_mode = "strategy"
        self.selected_action = None
        self.update()
    
    def set_range(self, range_data: dict, action_name: str = None):
        self.strategy_data = {hand: {action_name or "range": freq} for hand, freq in range_data.items()}
        self.action_order = [action_name or "range"]
        self.view_mode = "range"
        self.selected_action = action_name
        self.update()
    
    def clear(self):
        self.strategy_data = {}
        self.action_order = []
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        cell_w = w / 13
        cell_h = h / 13
        
        font = QFont("Arial", max(7, int(min(cell_w, cell_h) / 4)))
        painter.setFont(font)
        
        for row in range(13):
            for col in range(13):
                hand = HAND_MATRIX[row][col]
                x = col * cell_w
                y = row * cell_h
                hand_strategy = self.strategy_data.get(hand, {})
                
                in_range = self.player_range.get(hand, 0) > 0 if self.player_range else True
                has_strategy = bool(hand_strategy) and sum(hand_strategy.values()) > 0
                
                if self.view_mode == "strategy":
                    if in_range and has_strategy:
                        self._draw_strategy_cell(painter, x, y, cell_w, cell_h, hand, hand_strategy)
                    else:
                        self._draw_empty_cell(painter, x, y, cell_w, cell_h, hand)
                else:
                    self._draw_range_cell(painter, x, y, cell_w, cell_h, hand, sum(hand_strategy.values()))
        
        painter.end()
    
    def _draw_empty_cell(self, painter, x, y, cell_w, cell_h, hand):
        painter.fillRect(int(x), int(y), int(cell_w), int(cell_h), QColor("#1a1a1a"))
        painter.setPen(QPen(QColor("#2a2a2a"), 1))
        painter.drawRect(int(x), int(y), int(cell_w), int(cell_h))
        painter.setPen(QColor("#444444"))
        painter.drawText(int(x), int(y), int(cell_w), int(cell_h), Qt.AlignCenter, hand)
    
    def _draw_strategy_cell(self, painter, x, y, cell_w, cell_h, hand, hand_strategy):
        total_non_fold = sum(f for a, f in hand_strategy.items() if "fold" not in a.lower())
        fold_freq = 1.0 - total_non_fold
        
        if fold_freq > 0.01:
            painter.fillRect(int(x), int(y), int(cell_w), int(cell_h), ACTION_COLORS["fold"])
        else:
            painter.fillRect(int(x), int(y), int(cell_w), int(cell_h), QColor("#2a2a2a"))
        
        sorted_actions = sorted(
            [(a, f) for a, f in hand_strategy.items() if "fold" not in a.lower() and f > 0],
            key=lambda x: get_action_priority(x[0])
        )
        
        current_y = y + cell_h
        for action, freq in sorted_actions:
            bar_height = freq * cell_h
            current_y -= bar_height
            color = get_action_color(action)
            painter.fillRect(int(x), int(current_y), int(cell_w), int(bar_height) + 1, color)
        
        painter.setPen(QPen(QColor("#1a1a1a"), 1))
        painter.drawRect(int(x), int(y), int(cell_w), int(cell_h))
        
        painter.setPen(QColor("#000000"))
        painter.drawText(int(x) + 1, int(y) + 1, int(cell_w), int(cell_h), Qt.AlignCenter, hand)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(int(x), int(y), int(cell_w), int(cell_h), Qt.AlignCenter, hand)
    
    def _draw_range_cell(self, painter, x, y, cell_w, cell_h, hand, freq):
        if self.selected_action and freq > 0:
            bg_color = get_action_color(self.selected_action)
            if freq < 1.0:
                bg_color = QColor(int(bg_color.red() * freq + 42 * (1 - freq)),
                                 int(bg_color.green() * freq + 42 * (1 - freq)),
                                 int(bg_color.blue() * freq + 42 * (1 - freq)))
        else:
            if freq <= 0:
                bg_color = QColor("#2a2a2a")
            elif freq < 0.5:
                bg_color = QColor("#5a6a4a")
            else:
                bg_color = QColor("#3a9a3a")
        
        painter.fillRect(int(x), int(y), int(cell_w), int(cell_h), bg_color)
        painter.setPen(QPen(QColor("#3a3a3a"), 1))
        painter.drawRect(int(x), int(y), int(cell_w), int(cell_h))
        
        painter.setPen(QColor("#ffffff") if freq > 0 else QColor("#666666"))
        painter.drawText(int(x), int(y), int(cell_w), int(cell_h), Qt.AlignCenter, hand)
    
    def mouseMoveEvent(self, event):
        cell_w = self.width() / 13
        cell_h = self.height() / 13
        col = int(event.position().x() / cell_w)
        row = int(event.position().y() / cell_h)
        
        if 0 <= row < 13 and 0 <= col < 13:
            hand = HAND_MATRIX[row][col]
            hand_strategy = self.strategy_data.get(hand, {})
            
            if self.view_mode == "strategy" and hand_strategy:
                parts = [f"{a}: {f*100:.0f}%" for a, f in hand_strategy.items() if f > 0.005]
                total = sum(f for f in hand_strategy.values())
                if total < 0.99:
                    parts.append(f"fold: {(1-total)*100:.0f}%")
                tooltip = f"{hand}\n" + "\n".join(sorted(parts)) if parts else f"{hand}: not in range"
            else:
                tooltip = f"{hand}: {sum(hand_strategy.values())*100:.1f}%"
            self.setToolTip(tooltip)
    
    def mousePressEvent(self, event):
        cell_w = self.width() / 13
        cell_h = self.height() / 13
        col = int(event.position().x() / cell_w)
        row = int(event.position().y() / cell_h)
        
        if 0 <= row < 13 and 0 <= col < 13:
            hand = HAND_MATRIX[row][col]
            self.hand_clicked.emit(hand, self.strategy_data.get(hand, {}))


class ResultsPage(QWidget):
    """Solver Results 页面"""
    continue_solving = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = None
        self.game_tree = None
        self.current_node = None
        self.board = []
        self.original_oop_range = None
        self.original_ip_range = None
        self.current_oop_range = None  # 根据 action 更新的 range
        self.current_ip_range = None
        self.oop_position = "OOP"
        self.ip_position = "IP"
        self.action_sequence = []
        self.node_history = []  # 存储节点历史用于回退
        self.selected_action_filter = None
        self.current_view = "strategy"
        self.current_view_player = None
        self.iterations = 0
        self.equity_history = []  # [(action_label, oop_eq, ip_eq), ...]
        self._hand_equity_cache = {}
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # ===== 左侧面板（可滚动） =====
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setFixedWidth(260)
        left_scroll.setStyleSheet("QScrollArea { border: none; background-color: #252525; }")
        
        left_panel = QFrame()
        left_panel.setStyleSheet("background-color: #252525;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)
        
        title = QLabel("Solver Results")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        left_layout.addWidget(title)
        
        self.board_display = QLabel("Board: - - -")
        self.board_display.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        left_layout.addWidget(self.board_display)
        
        line_frame = QFrame()
        line_frame.setStyleSheet("background-color: #1e1e1e; border-radius: 6px;")
        line_layout = QVBoxLayout(line_frame)
        line_layout.setContentsMargins(10, 8, 10, 8)
        line_layout.setSpacing(4)
        
        line_title = QLabel("📍 Action Line")
        line_title.setStyleSheet("color: #888888; font-size: 11px;")
        line_layout.addWidget(line_title)
        
        self.line_display = QLabel("(Root)")
        self.line_display.setStyleSheet("color: white; font-size: 11px;")
        self.line_display.setWordWrap(True)
        line_layout.addWidget(self.line_display)
        
        left_layout.addWidget(line_frame)
        
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(8)
        
        self.back_btn = QPushButton("← Back")
        self.back_btn.setStyleSheet("""
            QPushButton { background-color: #3a3a4a; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 11px; }
            QPushButton:hover { background-color: #4a4a5a; }
            QPushButton:disabled { background-color: #2a2a2a; color: #555555; }
        """)
        self.back_btn.clicked.connect(self._go_back)
        self.back_btn.setEnabled(False)
        nav_layout.addWidget(self.back_btn)
        
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setStyleSheet("""
            QPushButton { background-color: #4a3a3a; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 11px; }
            QPushButton:hover { background-color: #5a4a4a; }
        """)
        self.reset_btn.clicked.connect(self._reset_to_root)
        nav_layout.addWidget(self.reset_btn)
        
        left_layout.addLayout(nav_layout)
        
        self.range_section = QFrame()
        range_layout = QVBoxLayout(self.range_section)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(6)
        
        self.range_label = QLabel("📊 View Range (Acted)")
        self.range_label.setStyleSheet("color: #3498db; font-size: 11px; font-weight: bold;")
        range_layout.addWidget(self.range_label)
        
        self.range_buttons_frame = QFrame()
        self.range_buttons_layout = QVBoxLayout(self.range_buttons_frame)
        self.range_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.range_buttons_layout.setSpacing(4)
        range_layout.addWidget(self.range_buttons_frame)
        
        left_layout.addWidget(self.range_section)
        
        self.strategy_section = QFrame()
        strategy_layout = QVBoxLayout(self.strategy_section)
        strategy_layout.setContentsMargins(0, 0, 0, 0)
        strategy_layout.setSpacing(6)
        
        self.strategy_label = QLabel("🎯 View Strategy (Next)")
        self.strategy_label.setStyleSheet("color: #27ae60; font-size: 11px; font-weight: bold;")
        strategy_layout.addWidget(self.strategy_label)
        
        self.strategy_buttons_frame = QFrame()
        self.strategy_buttons_layout = QVBoxLayout(self.strategy_buttons_frame)
        self.strategy_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.strategy_buttons_layout.setSpacing(4)
        strategy_layout.addWidget(self.strategy_buttons_frame)
        
        left_layout.addWidget(self.strategy_section)
        
        self.filter_section = QFrame()
        filter_layout = QVBoxLayout(self.filter_section)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(6)
        
        self.filter_label = QLabel("🔍 Filter Action")
        self.filter_label.setStyleSheet("color: #888888; font-size: 11px; font-weight: bold;")
        filter_layout.addWidget(self.filter_label)
        
        self.filter_buttons_frame = QFrame()
        self.filter_buttons_layout = QVBoxLayout(self.filter_buttons_frame)
        self.filter_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_buttons_layout.setSpacing(4)
        filter_layout.addWidget(self.filter_buttons_frame)
        
        left_layout.addWidget(self.filter_section)
        
        self.action_section = QFrame()
        action_section_layout = QVBoxLayout(self.action_section)
        action_section_layout.setContentsMargins(0, 0, 0, 0)
        action_section_layout.setSpacing(6)
        
        self.action_label = QLabel("➡️ Select Action")
        self.action_label.setStyleSheet("color: #888888; font-size: 11px; font-weight: bold;")
        action_section_layout.addWidget(self.action_label)
        
        self.action_buttons_frame = QFrame()
        self.action_buttons_layout = QVBoxLayout(self.action_buttons_frame)
        self.action_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.action_buttons_layout.setSpacing(4)
        action_section_layout.addWidget(self.action_buttons_frame)
        
        left_layout.addWidget(self.action_section)
        
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #aaaaaa; font-size: 9px;")
        self.stats_label.setWordWrap(True)
        left_layout.addWidget(self.stats_label)
        
        left_layout.addStretch()
        
        left_scroll.setWidget(left_panel)
        layout.addWidget(left_scroll)
        
        # ===== 中间：矩阵 =====
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(12, 12, 12, 12)
        center_layout.setSpacing(6)
        
        self.matrix_title = QLabel("Select a view")
        self.matrix_title.setStyleSheet("font-size: 13px; font-weight: bold; color: white;")
        center_layout.addWidget(self.matrix_title)
        
        self.strategy_matrix = StrategyMatrixWidget()
        self.strategy_matrix.hand_clicked.connect(self._on_hand_clicked)
        center_layout.addWidget(self.strategy_matrix, 1)
        
        self.legend_layout = QHBoxLayout()
        self.legend_layout.setSpacing(8)
        center_layout.addLayout(self.legend_layout)
        
        layout.addWidget(center_panel, 1)
        
        # ===== 右侧：图表（可滚动） =====
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setFixedWidth(190)
        right_scroll.setStyleSheet("QScrollArea { border: none; background-color: #1e1e1e; }")
        
        right_panel = QFrame()
        right_panel.setStyleSheet("background-color: #1e1e1e;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 12, 10, 12)
        right_layout.setSpacing(12)
        
        equity_frame = QFrame()
        equity_frame.setStyleSheet("background-color: #252525; border-radius: 6px;")
        equity_layout = QVBoxLayout(equity_frame)
        equity_layout.setContentsMargins(6, 6, 6, 6)
        equity_layout.setSpacing(2)
        
        equity_title = QLabel("📊 Equity")
        equity_title.setStyleSheet("color: #27ae60; font-size: 10px; font-weight: bold;")
        equity_title.setAlignment(Qt.AlignCenter)
        equity_layout.addWidget(equity_title)
        
        self.equity_chart = EquityPieChart()
        equity_layout.addWidget(self.equity_chart, alignment=Qt.AlignCenter)
        
        right_layout.addWidget(equity_frame)
        
        equity_hist_frame = QFrame()
        equity_hist_frame.setStyleSheet("background-color: #252525; border-radius: 6px;")
        equity_hist_layout = QVBoxLayout(equity_hist_frame)
        equity_hist_layout.setContentsMargins(6, 6, 6, 6)
        equity_hist_layout.setSpacing(2)
        
        equity_hist_title = QLabel("📈 Equity Change")
        equity_hist_title.setStyleSheet("color: #3498db; font-size: 10px; font-weight: bold;")
        equity_hist_title.setAlignment(Qt.AlignCenter)
        equity_hist_layout.addWidget(equity_hist_title)
        
        self.equity_line_chart = EquityLineChart()
        equity_hist_layout.addWidget(self.equity_line_chart, alignment=Qt.AlignCenter)
        
        right_layout.addWidget(equity_hist_frame)
        
        hand_eq_frame = QFrame()
        hand_eq_frame.setStyleSheet("background-color: #252525; border-radius: 6px;")
        hand_eq_layout = QVBoxLayout(hand_eq_frame)
        hand_eq_layout.setContentsMargins(6, 6, 6, 6)
        hand_eq_layout.setSpacing(2)
        
        hand_eq_title = QLabel("🃏 Hand Equity")
        hand_eq_title.setStyleSheet("color: #4a9eff; font-size: 10px; font-weight: bold;")
        hand_eq_title.setAlignment(Qt.AlignCenter)
        hand_eq_layout.addWidget(hand_eq_title)
        
        self.hand_equity_chart = HandEquityBar()
        hand_eq_layout.addWidget(self.hand_equity_chart, alignment=Qt.AlignCenter)
        
        right_layout.addWidget(hand_eq_frame)
        
        # Hand Strategy Frame - 可以隐藏
        self.hand_strat_frame = QFrame()
        self.hand_strat_frame.setStyleSheet("background-color: #252525; border-radius: 6px;")
        hand_strat_layout = QVBoxLayout(self.hand_strat_frame)
        hand_strat_layout.setContentsMargins(6, 6, 6, 6)
        hand_strat_layout.setSpacing(2)
        
        hand_strat_title = QLabel("🎯 Hand Strategy")
        hand_strat_title.setStyleSheet("color: #e74c3c; font-size: 10px; font-weight: bold;")
        hand_strat_title.setAlignment(Qt.AlignCenter)
        hand_strat_layout.addWidget(hand_strat_title)
        
        self.hand_strategy_chart = HandStrategyBar()
        hand_strat_layout.addWidget(self.hand_strategy_chart, alignment=Qt.AlignCenter)
        
        right_layout.addWidget(self.hand_strat_frame)
        
        conv_frame = QFrame()
        conv_frame.setStyleSheet("background-color: #252525; border-radius: 6px;")
        conv_layout = QVBoxLayout(conv_frame)
        conv_layout.setContentsMargins(6, 6, 6, 6)
        conv_layout.setSpacing(2)
        
        conv_title = QLabel("📉 Convergence")
        conv_title.setStyleSheet("color: #4a9eff; font-size: 10px; font-weight: bold;")
        conv_title.setAlignment(Qt.AlignCenter)
        conv_layout.addWidget(conv_title)
        
        self.conv_chart = ConvergenceLineChart()
        conv_layout.addWidget(self.conv_chart, alignment=Qt.AlignCenter)
        
        self.conv_hint = QLabel("")
        self.conv_hint.setStyleSheet("color: #888888; font-size: 9px;")
        self.conv_hint.setAlignment(Qt.AlignCenter)
        conv_layout.addWidget(self.conv_hint)
        
        right_layout.addWidget(conv_frame)
        
        right_layout.addStretch()
        
        right_scroll.setWidget(right_panel)
        layout.addWidget(right_scroll)
    
    def set_data(self, engine, game_tree, board, oop_range, ip_range, iterations: int,
                 oop_position: str = "OOP", ip_position: str = "IP"):
        self.engine = engine
        self.game_tree = game_tree
        self.current_node = game_tree
        self.board = board
        self.original_oop_range = oop_range
        self.original_ip_range = ip_range
        self.current_oop_range = deepcopy(oop_range)
        self.current_ip_range = deepcopy(ip_range)
        self.oop_position = oop_position
        self.ip_position = ip_position
        self.iterations = iterations
        self.action_sequence = []
        self.node_history = []
        self.selected_action_filter = None
        self.current_view = "strategy"
        self.current_view_player = "OOP" if game_tree.player == 0 else "IP"
        
        self._hand_equity_cache = {}
        
        self.board_display.setText(f"Board: {' '.join(str(c) for c in board)}")
        
        avg_regret = self._calculate_avg_regret()
        self.conv_chart.set_data(iterations, avg_regret)
        
        if avg_regret < 0.01:
            self.conv_hint.setText("✓ Well converged")
            self.conv_hint.setStyleSheet("color: #27ae60; font-size: 9px;")
        elif avg_regret < 0.1:
            self.conv_hint.setText("~ Good")
            self.conv_hint.setStyleSheet("color: #f39c12; font-size: 9px;")
        else:
            self.conv_hint.setText("! Need more iterations")
            self.conv_hint.setStyleSheet("color: #e74c3c; font-size: 9px;")
        
        oop_eq = self._calculate_equity()
        self.equity_history = [("Root", oop_eq, 100 - oop_eq)]
        self.equity_line_chart.set_history(self.equity_history, self.oop_position, self.ip_position)
        
        self._update_ui()
    
    def _calculate_avg_regret(self) -> float:
        if not self.engine or not self.engine.regrets:
            return 1.0
        total, count = 0.0, 0
        for node in self.engine.regrets:
            for hand_str in self.engine.regrets[node]:
                for action, regret in self.engine.regrets[node][hand_str].items():
                    total += abs(regret)
                    count += 1
        return total / count if count > 0 else 1.0
    
    def _calculate_equity(self) -> float:
        try:
            from solver.hand_evaluator import calculate_equity
            from solver.card_utils import get_all_combos, cards_conflict
            
            all_combos = get_all_combos()
            oop_total, total_weight = 0.0, 0.0
            
            oop_hands = [(h, w) for h, w in self.current_oop_range.weights.items() if w > 0]
            ip_hands = [(h, w) for h, w in self.current_ip_range.weights.items() if w > 0]
            
            if not oop_hands or not ip_hands:
                return 50.0
            
            oop_sample = random.sample(oop_hands, min(15, len(oop_hands)))
            ip_sample = random.sample(ip_hands, min(15, len(ip_hands)))
            
            for oop_hand, oop_weight in oop_sample:
                oop_combos = all_combos.get(oop_hand, [])
                if not oop_combos or cards_conflict(list(oop_combos[0]), self.board):
                    continue
                oop_combo = oop_combos[0]
                
                for ip_hand, ip_weight in ip_sample:
                    ip_combos = all_combos.get(ip_hand, [])
                    if not ip_combos:
                        continue
                    ip_combo = ip_combos[0]
                    
                    if cards_conflict(list(ip_combo), self.board) or cards_conflict(list(oop_combo), list(ip_combo)):
                        continue
                    
                    weight = oop_weight * ip_weight
                    eq = calculate_equity(list(oop_combo), list(ip_combo), self.board, num_simulations=10)
                    oop_total += eq * weight
                    total_weight += weight
            
            if total_weight > 0:
                oop_eq = oop_total / total_weight * 100
                self.equity_chart.set_equity(oop_eq, self.oop_position, self.ip_position)
                return oop_eq
        except Exception as e:
            print(f"Error calculating equity: {e}")
        return 50.0
    
    def _update_range_for_action(self, player: str, action_str: str, prev_node):
        """根据选择的 action 更新 range"""
        hand_strategy = self.engine.get_hand_strategy(prev_node)
        
        if "fold" in action_str.lower():
            # Fold: range 变空
            if player == "OOP":
                self.current_oop_range.weights = {h: 0.0 for h in self.current_oop_range.weights}
            else:
                self.current_ip_range.weights = {h: 0.0 for h in self.current_ip_range.weights}
        else:
            # 其他 action: range 变成选择该 action 的部分
            range_obj = self.current_oop_range if player == "OOP" else self.current_ip_range
            new_weights = {}
            for hand, weight in range_obj.weights.items():
                if weight > 0 and hand in hand_strategy:
                    action_freq = hand_strategy[hand].get(action_str, 0)
                    new_weights[hand] = weight * action_freq
                else:
                    new_weights[hand] = 0.0
            range_obj.weights = new_weights
    
    def _update_ui(self):
        if not self.action_sequence:
            self.line_display.setText("(Root) - OOP to act first")
        else:
            lines = []
            for i, (player, action) in enumerate(self.action_sequence):
                pos = self.oop_position if player == "OOP" else self.ip_position
                lines.append(f"{i+1}. {pos} {action}")
            self.line_display.setText("\n".join(lines))
        
        self.back_btn.setEnabled(len(self.action_sequence) > 0)
        
        is_terminal = self.current_node.is_terminal
        
        # Terminal 节点时隐藏 Hand Strategy
        self.hand_strat_frame.setVisible(not is_terminal)
        
        if is_terminal:
            self._update_terminal_view()
        else:
            self._update_non_terminal_view()
    
    def _update_terminal_view(self):
        self.strategy_section.setVisible(False)
        self.filter_section.setVisible(False)
        self.action_section.setVisible(False)
        self.range_label.setText("📊 View Range (Final)")
        self.range_section.setVisible(True)
        
        self._clear_layout(self.range_buttons_layout)
        
        # 检查哪个 range 有内容
        oop_has_range = sum(self.current_oop_range.weights.values()) > 0
        ip_has_range = sum(self.current_ip_range.weights.values()) > 0
        
        if oop_has_range:
            oop_btn = QPushButton(f"OOP ({self.oop_position})")
            oop_btn.setCheckable(True)
            oop_btn.setChecked(self.current_view_player == "OOP")
            oop_btn.setStyleSheet(self._get_btn_style("#2c3e50", "#3498db"))
            oop_btn.clicked.connect(lambda: self._show_terminal_range("OOP"))
            self.range_buttons_layout.addWidget(oop_btn)
        
        if ip_has_range:
            ip_btn = QPushButton(f"IP ({self.ip_position})")
            ip_btn.setCheckable(True)
            ip_btn.setChecked(self.current_view_player == "IP")
            ip_btn.setStyleSheet(self._get_btn_style("#1e3a2f", "#27ae60"))
            ip_btn.clicked.connect(lambda: self._show_terminal_range("IP"))
            self.range_buttons_layout.addWidget(ip_btn)
        
        self._range_btns = {}
        if oop_has_range:
            self._range_btns["OOP"] = self.range_buttons_layout.itemAt(0).widget() if self.range_buttons_layout.count() > 0 else None
        if ip_has_range:
            idx = 1 if oop_has_range else 0
            self._range_btns["IP"] = self.range_buttons_layout.itemAt(idx).widget() if self.range_buttons_layout.count() > idx else None
        
        # 默认显示有内容的一方
        if oop_has_range:
            self._show_terminal_range("OOP")
        elif ip_has_range:
            self._show_terminal_range("IP")
        else:
            # 双方都 fold 了
            self.strategy_matrix.clear()
            self.matrix_title.setText("Both players folded")
            self.stats_label.setText("")
    
    def _show_terminal_range(self, player):
        self.current_view_player = player
        self.current_view = "range"
        
        for p, btn in self._range_btns.items():
            if btn:
                btn.setChecked(p == player)
        
        position = self.oop_position if player == "OOP" else self.ip_position
        range_obj = self.current_oop_range if player == "OOP" else self.current_ip_range
        range_data = {h: w for h, w in range_obj.weights.items() if w > 0}
        
        self.strategy_matrix.set_player_range(range_data)
        self.strategy_matrix.set_range(range_data)
        self.matrix_title.setText(f"{player} ({position}) Range [Terminal]")
        
        self._clear_layout(self.legend_layout)
        total = sum(self._get_hand_combos(h) * w for h, w in range_data.items())
        self.stats_label.setText(f"Total: {total:.0f} combos ({total/1326*100:.1f}%)")
    
    def _update_non_terminal_view(self):
        current_player = "OOP" if self.current_node.player == 0 else "IP"
        current_pos = self.oop_position if current_player == "OOP" else self.ip_position
        acted_player = "IP" if current_player == "OOP" else "OOP"
        acted_pos = self.ip_position if acted_player == "IP" else self.oop_position
        
        player_range = self.current_oop_range if current_player == "OOP" else self.current_ip_range
        self.strategy_matrix.set_player_range(player_range.weights)
        
        if self.action_sequence:
            self.range_section.setVisible(True)
            self.range_label.setText("📊 View Range (Acted)")
            self._clear_layout(self.range_buttons_layout)
            
            btn = QPushButton(f"{acted_player} ({acted_pos})")
            btn.setCheckable(True)
            btn.setChecked(self.current_view == "range")
            btn.setStyleSheet(self._get_btn_style("#2c3e50", "#3498db"))
            btn.clicked.connect(lambda: self._on_view_range(acted_player))
            self.range_buttons_layout.addWidget(btn)
            self._range_btn = btn
        else:
            self.range_section.setVisible(False)
        
        self.strategy_section.setVisible(True)
        self._clear_layout(self.strategy_buttons_layout)
        
        btn = QPushButton(f"{current_player} ({current_pos})")
        btn.setCheckable(True)
        btn.setChecked(self.current_view == "strategy")
        btn.setStyleSheet(self._get_btn_style("#1e3a2f", "#27ae60"))
        btn.clicked.connect(lambda: self._on_view_strategy(current_player))
        self.strategy_buttons_layout.addWidget(btn)
        self._strategy_btn = btn
        
        actions = self._get_available_actions()
        if actions and self.current_view == "strategy":
            self.filter_section.setVisible(True)
            self._update_filter_buttons(actions)
        else:
            self.filter_section.setVisible(False)
        
        if self.current_node.children and self.current_view == "strategy":
            self.action_section.setVisible(True)
            self._update_action_buttons(actions)
        else:
            self.action_section.setVisible(False)
        
        if self.current_view == "strategy":
            self._show_strategy(current_player)
        else:
            self._show_range(acted_player)
    
    def _get_btn_style(self, normal_color, checked_color):
        return f"""
            QPushButton {{
                background-color: {normal_color};
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
                text-align: left;
            }}
            QPushButton:hover {{ background-color: {checked_color}80; }}
            QPushButton:checked {{ background-color: {checked_color}; }}
        """
    
    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
    
    def _on_view_range(self, player):
        self.current_view = "range"
        self.current_view_player = player
        self.selected_action_filter = None
        self._update_ui()
    
    def _on_view_strategy(self, player):
        self.current_view = "strategy"
        self.current_view_player = player
        self.selected_action_filter = None
        self._update_ui()
    
    def _get_available_actions(self) -> list:
        if not self.engine:
            return []
        hand_strategy = self.engine.get_hand_strategy(self.current_node)
        if hand_strategy:
            all_actions = set()
            for strat in hand_strategy.values():
                all_actions.update(strat.keys())
            return sorted(all_actions, key=get_action_priority)
        return []
    
    def _find_action_by_str(self, action_str: str):
        for action in self.current_node.children.keys():
            if str(action) == action_str:
                return action
        return None
    
    def _update_filter_buttons(self, actions):
        self._clear_layout(self.filter_buttons_layout)
        
        self._filter_btn_map = {}
        buttons_per_row = 3
        
        all_btn = QPushButton("All")
        all_btn.setCheckable(True)
        all_btn.setChecked(self.selected_action_filter is None)
        all_btn.setStyleSheet(self._get_small_btn_style("#3a3a3a", "#6a6a6a"))
        all_btn.clicked.connect(lambda: self._on_filter_action(None))
        self._filter_btn_map[None] = all_btn
        
        all_actions = [None] + actions
        current_row = None
        for i, action in enumerate(all_actions):
            if i % buttons_per_row == 0:
                current_row = QHBoxLayout()
                current_row.setSpacing(4)
                self.filter_buttons_layout.addLayout(current_row)
            
            if action is None:
                current_row.addWidget(all_btn)
            else:
                color = get_action_color(action)
                btn = QPushButton(action)
                btn.setCheckable(True)
                btn.setChecked(self.selected_action_filter == action)
                btn.setStyleSheet(self._get_small_btn_style("#3a3a3a", color.name()))
                btn.clicked.connect(lambda checked, a=action: self._on_filter_action(a))
                current_row.addWidget(btn)
                self._filter_btn_map[action] = btn
        
        if current_row:
            remaining = buttons_per_row - (len(all_actions) % buttons_per_row)
            if remaining < buttons_per_row:
                for _ in range(remaining):
                    current_row.addStretch()
    
    def _update_action_buttons(self, actions):
        self._clear_layout(self.action_buttons_layout)
        
        buttons_per_row = 3
        current_row = None
        btn_count = 0
        
        for action_str in actions:
            action_obj = self._find_action_by_str(action_str)
            if action_obj and action_obj in self.current_node.children:
                if btn_count % buttons_per_row == 0:
                    current_row = QHBoxLayout()
                    current_row.setSpacing(4)
                    self.action_buttons_layout.addLayout(current_row)
                
                child = self.current_node.children[action_obj]
                color = get_action_color(action_str)
                btn = QPushButton(action_str)
                
                if child.is_terminal:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {color.darker(180).name()};
                            color: #aaaaaa;
                            border: 1px dashed #666666;
                            padding: 5px 8px;
                            border-radius: 4px;
                            font-size: 10px;
                        }}
                        QPushButton:hover {{ background-color: {color.darker(150).name()}; color: white; }}
                    """)
                    btn.setToolTip(f"{action_str} → Terminal (Line ends)")
                else:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {color.darker(150).name()};
                            color: white;
                            border: none;
                            padding: 5px 8px;
                            border-radius: 4px;
                            font-size: 10px;
                        }}
                        QPushButton:hover {{ background-color: {color.name()}; }}
                    """)
                
                btn.clicked.connect(lambda checked, a=action_str: self._select_action(a))
                current_row.addWidget(btn)
                btn_count += 1
        
        if current_row and btn_count % buttons_per_row != 0:
            remaining = buttons_per_row - (btn_count % buttons_per_row)
            for _ in range(remaining):
                current_row.addStretch()
    
    def _get_small_btn_style(self, normal_color, checked_color):
        return f"""
            QPushButton {{
                background-color: {normal_color};
                color: white;
                border: none;
                padding: 5px 8px;
                border-radius: 4px;
                font-size: 10px;
            }}
            QPushButton:hover {{ background-color: #4a4a4a; }}
            QPushButton:checked {{ background-color: {checked_color}; }}
        """
    
    def _show_strategy(self, player):
        if not self.engine:
            return
        
        hand_strategy = self.engine.get_hand_strategy(self.current_node)
        
        all_actions = set()
        for strat in hand_strategy.values():
            all_actions.update(strat.keys())
        actions = sorted(all_actions, key=get_action_priority)
        
        position = self.oop_position if player == "OOP" else self.ip_position
        
        if self.selected_action_filter is None:
            self.strategy_matrix.set_strategy(hand_strategy, actions)
            self.matrix_title.setText(f"{player} ({position}) Strategy")
        else:
            range_data = {h: strat.get(self.selected_action_filter, 0) for h, strat in hand_strategy.items()}
            range_data = {h: f for h, f in range_data.items() if f > 0}
            self.strategy_matrix.set_range(range_data, self.selected_action_filter)
            self.matrix_title.setText(f"{player} ({position}) {self.selected_action_filter} Range")
        
        self._update_legend(actions, hand_strategy)
        self._update_stats(hand_strategy, actions)
    
    def _show_range(self, player):
        position = self.oop_position if player == "OOP" else self.ip_position
        range_obj = self.current_oop_range if player == "OOP" else self.current_ip_range
        range_data = {h: w for h, w in range_obj.weights.items() if w > 0}
        
        self.strategy_matrix.set_player_range(range_data)
        self.strategy_matrix.set_range(range_data)
        self.matrix_title.setText(f"{player} ({position}) Range")
        
        self._clear_layout(self.legend_layout)
        total = sum(self._get_hand_combos(h) * w for h, w in range_data.items())
        self.stats_label.setText(f"Total: {total:.0f} combos ({total/1326*100:.1f}%)")
    
    def _on_filter_action(self, action):
        self.selected_action_filter = action
        for a, btn in self._filter_btn_map.items():
            btn.setChecked(a == action)
        current_player = "OOP" if self.current_node.player == 0 else "IP"
        self._show_strategy(current_player)
    
    def _select_action(self, action_str):
        action_obj = self._find_action_by_str(action_str)
        if action_obj and action_obj in self.current_node.children:
            player = "OOP" if self.current_node.player == 0 else "IP"
            
            # 保存当前状态用于回退
            self.node_history.append({
                'node': self.current_node,
                'oop_range': deepcopy(self.current_oop_range),
                'ip_range': deepcopy(self.current_ip_range),
            })
            
            # 更新 range
            self._update_range_for_action(player, action_str, self.current_node)
            
            self.action_sequence.append((player, action_str))
            self.current_node = self.current_node.children[action_obj]
            self.selected_action_filter = None
            self.current_view = "strategy"
            
            oop_eq = self._calculate_equity()
            self.equity_history.append((action_str[:6], oop_eq, 100 - oop_eq))
            self.equity_line_chart.set_history(self.equity_history, self.oop_position, self.ip_position)
            
            self._update_ui()
    
    def _go_back(self):
        if self.action_sequence and self.node_history:
            self.action_sequence.pop()
            if self.equity_history:
                self.equity_history.pop()
            
            # 恢复状态
            prev_state = self.node_history.pop()
            self.current_node = prev_state['node']
            self.current_oop_range = prev_state['oop_range']
            self.current_ip_range = prev_state['ip_range']
            
            self.selected_action_filter = None
            self.current_view = "strategy"
            
            self._calculate_equity()
            self.equity_line_chart.set_history(self.equity_history, self.oop_position, self.ip_position)
            self._update_ui()
    
    def _reset_to_root(self):
        self.action_sequence = []
        self.node_history = []
        self.current_node = self.game_tree
        self.current_oop_range = deepcopy(self.original_oop_range)
        self.current_ip_range = deepcopy(self.original_ip_range)
        self.selected_action_filter = None
        self.current_view = "strategy"
        
        oop_eq = self._calculate_equity()
        self.equity_history = [("Root", oop_eq, 100 - oop_eq)]
        self.equity_line_chart.set_history(self.equity_history, self.oop_position, self.ip_position)
        
        self._update_ui()
    
    def _update_legend(self, actions, hand_strategy):
        self._clear_layout(self.legend_layout)
        
        action_combos = defaultdict(float)
        total_combos = 0.0
        for hand, strat in hand_strategy.items():
            combos = self._get_hand_combos(hand)
            hand_total = sum(strat.values())
            for action, freq in strat.items():
                action_combos[action] += combos * freq
            if hand_total < 1.0:
                action_combos["fold"] += combos * (1.0 - hand_total)
            total_combos += combos
        
        for action in ["fold"] + [a for a in actions if "fold" not in a.lower()]:
            combos = action_combos.get(action, 0)
            if combos > 0.1:
                pct = combos / total_combos * 100 if total_combos > 0 else 0
                self._add_legend_item(action, get_action_color(action), pct)
        
        self.legend_layout.addStretch()
    
    def _add_legend_item(self, label, color, pct):
        item = QWidget()
        layout = QHBoxLayout(item)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        
        box = QFrame()
        box.setFixedSize(10, 10)
        box.setStyleSheet(f"background-color: {color.name()}; border-radius: 2px;")
        layout.addWidget(box)
        
        text = QLabel(f"{label} ({pct:.0f}%)")
        text.setStyleSheet("color: #aaaaaa; font-size: 9px;")
        layout.addWidget(text)
        
        self.legend_layout.addWidget(item)
    
    def _update_stats(self, hand_strategy, actions):
        action_combos = defaultdict(float)
        total_combos = 0.0
        for hand, strat in hand_strategy.items():
            combos = self._get_hand_combos(hand)
            hand_total = sum(strat.values())
            for action, freq in strat.items():
                action_combos[action] += combos * freq
            if hand_total < 1.0:
                action_combos["fold"] += combos * (1.0 - hand_total)
            total_combos += combos
        
        parts = []
        for action in ["fold"] + [a for a in actions if "fold" not in a.lower()]:
            c = action_combos.get(action, 0)
            if c > 0.01:
                pct = c / total_combos * 100 if total_combos > 0 else 0
                parts.append(f"{action}: {c:.0f} ({pct:.1f}%)")
        
        self.stats_label.setText("\n".join(parts))
    
    def _on_hand_clicked(self, hand, strategy):
        player = self.current_view_player or ("OOP" if self.current_node.player == 0 else "IP")
        self._calculate_hand_equity(hand, player)
        
        # Terminal 节点时只显示 equity，不显示 strategy
        if not self.current_node.is_terminal and strategy:
            total = sum(strategy.values())
            display_strategy = dict(strategy)
            if total < 0.99:
                display_strategy["fold"] = 1.0 - total
            self.hand_strategy_chart.set_data(hand, display_strategy)
        else:
            self.hand_strategy_chart.clear()
    
    def _calculate_hand_equity(self, hand, player):
        cache_key = (hand, player, tuple(self.action_sequence) if self.action_sequence else ())
        
        if cache_key in self._hand_equity_cache:
            hand_eq = self._hand_equity_cache[cache_key]
            self.hand_equity_chart.set_data(hand, hand_eq, player)
            return
        
        try:
            from solver.hand_evaluator import calculate_equity
            from solver.card_utils import get_all_combos, cards_conflict
            
            all_combos = get_all_combos()
            hand_combos = all_combos.get(hand, [])
            
            if hand_combos:
                valid_combo = None
                for combo in hand_combos:
                    if not cards_conflict(list(combo), self.board):
                        valid_combo = combo
                        break
                
                if valid_combo:
                    opp_range = self.current_ip_range if player == "OOP" else self.current_oop_range
                    opp_hands = [(h, w) for h, w in opp_range.weights.items() if w > 0]
                    
                    if not opp_hands:
                        self.hand_equity_chart.set_data(hand, 100.0, player)
                        return
                    
                    total_eq, total_weight = 0.0, 0.0
                    
                    for opp_hand, opp_weight in opp_hands:
                        opp_combos = all_combos.get(opp_hand, [])
                        if opp_combos:
                            opp_combo = opp_combos[0]
                            if not cards_conflict(list(opp_combo), self.board) and not cards_conflict(list(valid_combo), list(opp_combo)):
                                eq = calculate_equity(list(valid_combo), list(opp_combo), self.board, num_simulations=20)
                                total_eq += eq * opp_weight
                                total_weight += opp_weight
                    
                    if total_weight > 0:
                        hand_eq = total_eq / total_weight * 100
                        self._hand_equity_cache[cache_key] = hand_eq
                        self.hand_equity_chart.set_data(hand, hand_eq, player)
                        return
        except Exception:
            pass
        
        self.hand_equity_chart.clear()
    
    def _get_hand_combos(self, hand):
        if len(hand) == 2:
            return 6
        elif hand.endswith('s'):
            return 4
        return 12
