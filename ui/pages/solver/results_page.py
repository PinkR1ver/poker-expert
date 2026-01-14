"""
Solver Results 页面
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QSizePolicy, QPushButton, QScrollArea, QGridLayout, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QElapsedTimer
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QBrush

import random
import os
import json
from datetime import datetime
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
    """手牌 Equity 条形图 - 支持 combo 级别显示"""
    
    SUIT_SYMBOLS = {'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}
    SUIT_COLORS = {'s': '#1a1a1a', 'h': '#e74c3c', 'd': '#3498db', 'c': '#27ae60'}
    
    def __init__(self):
        super().__init__()
        self.hand = ""
        self.equity = 0.0
        self.player = "OOP"
        self.combos = []  # [(combo_str, equity, is_valid), ...]
        self.setMinimumSize(200, 55)  # 增加宽度从 140 到 200
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    
    def set_data(self, hand: str, equity: float, player: str):
        """设置单个 equity（旧接口，兼容）"""
        self.hand = hand
        self.equity = equity
        self.player = player
        self.combos = []
        self.setFixedHeight(55)
        self.update()
    
    def set_combo_data(self, hand: str, combos: list, player: str):
        """
        设置 combo 级别的 equity
        combos: [(combo_str, equity, is_valid), ...]
        """
        self.hand = hand
        self.combos = combos
        self.player = player
        
        # 计算平均 equity（只计算有效 combo）
        valid_combos = [c for c in combos if c[2]]
        if valid_combos:
            self.equity = sum(c[1] for c in valid_combos) / len(valid_combos)
        else:
            self.equity = 0.0
        
        # 根据 combo 数量调整高度
        height = 45 + len(combos) * 18
        self.setFixedHeight(height)
        self.update()
    
    def clear(self):
        self.hand = ""
        self.equity = 0.0
        self.combos = []
        self.setFixedHeight(55)
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
        
        # 标题
        painter.setPen(QColor("#4a9eff"))
        font = QFont()
        font.setPixelSize(13)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(0, 2, self.width(), 16, Qt.AlignCenter, self.hand)
        
        y_offset = 20
        
        if self.combos:
            # Combo 级别显示
            font.setPixelSize(9)
            font.setBold(False)
            painter.setFont(font)
            
            valid_count = sum(1 for c in self.combos if c[2])
            invalid_count = len(self.combos) - valid_count
            
            painter.setPen(QColor("#888888"))
            painter.drawText(0, y_offset, self.width(), 14, Qt.AlignCenter,
                           f"({valid_count} valid, {invalid_count} blocked)")
            y_offset += 16
            
            for combo_str, eq, is_valid in self.combos:
                # 解析花色来显示彩色符号
                if len(combo_str) >= 4:
                    c1 = combo_str[:2]
                    c2 = combo_str[2:]
                    display = self._format_combo(c1, c2)
                else:
                    display = combo_str
                
                if is_valid:
                    # 有效 combo：显示 equity bar
                    bar_w = 60
                    bar_h = 10
                    bar_x = 70
                    
                    painter.setPen(QColor("#ffffff"))
                    painter.drawText(5, y_offset, 65, 14, Qt.AlignLeft, display)
                    
                    painter.setBrush(QBrush(QColor("#2a2a2a")))
                    painter.setPen(Qt.NoPen)
                    painter.drawRoundedRect(bar_x, y_offset + 2, bar_w, bar_h, 3, 3)
                    
                    eq_w = int(bar_w * eq / 100)
                    painter.setBrush(QBrush(QColor("#27ae60")))
                    painter.drawRoundedRect(bar_x, y_offset + 2, eq_w, bar_h, 3, 3)
                    
                    painter.setPen(QColor("#ffffff"))
                    painter.drawText(bar_x + bar_w + 3, y_offset, 40, 14, Qt.AlignLeft, f"{eq:.0f}%")
                else:
                    # 无效 combo：划掉
                    painter.setPen(QColor("#555555"))
                    painter.drawText(5, y_offset, 65, 14, Qt.AlignLeft, display)
                    
                    painter.setPen(QPen(QColor("#ff4444"), 1))
                    painter.drawLine(5, y_offset + 7, 60, y_offset + 7)
                    
                    painter.setPen(QColor("#555555"))
                    painter.drawText(70, y_offset, 60, 14, Qt.AlignLeft, "blocked")
                
                y_offset += 16
        else:
            # 旧模式：单个 equity
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
    
    def _format_combo(self, c1: str, c2: str) -> str:
        """格式化 combo 显示，用花色符号"""
        r1, s1 = c1[0], c1[1]
        r2, s2 = c2[0], c2[1]
        sym1 = self.SUIT_SYMBOLS.get(s1, s1)
        sym2 = self.SUIT_SYMBOLS.get(s2, s2)
        return f"{r1}{sym1}{r2}{sym2}"


class HandStrategyBar(QWidget):
    """手牌策略分布图 - 显示绝对频率和到达概率"""
    def __init__(self):
        super().__init__()
        self.hand = ""
        self.strategy = {}
        self.reach_prob = 1.0
        self.setMinimumSize(200, 80)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
    
    def set_data(self, hand: str, strategy: dict, reach_prob: float = 1.0):
        self.hand = hand
        self.strategy = strategy
        self.reach_prob = reach_prob
        num_actions = len([a for a, f in strategy.items() if f > 0.01])
        self.setFixedHeight(max(80, 60 + num_actions * 12))
        self.update()
    
    def clear(self):
        self.hand = ""
        self.strategy = {}
        self.reach_prob = 1.0
        self.setFixedHeight(80)
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
        painter.drawText(0, 2, self.width(), 14, Qt.AlignCenter, f"{self.hand} (Reach: {self.reach_prob*100:.1f}%)")
        
        bar_w = self.width() - 20
        bar_h = 14
        bar_x = 10
        bar_y = 18
        
        # 背景条（代表 reach prob）
        painter.setBrush(QBrush(QColor("#2a2a2a")))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 4, 4)
        
        # 如果 reach prob 小，我们可以缩小 bar 的显示
        actual_bar_w = bar_w * self.reach_prob
        
        sorted_actions = sorted(self.strategy.items(), key=lambda x: get_action_priority(x[0]))
        current_x = float(bar_x)
        
        for action, freq in sorted_actions:
            if freq > 0:
                w = bar_w * freq # 这里显示的是条件概率，填满背景条
                if w > 0.5:
                    color = get_action_color(action)
                    painter.setBrush(QBrush(color))
                    painter.drawRoundedRect(int(current_x), bar_y, int(w) + 1, bar_h, 2, 2)
                    current_x += w
        
        font.setPixelSize(9)
        font.setBold(False)
        painter.setFont(font)
        
        y_offset = bar_y + bar_h + 6
        for action, freq in sorted_actions:
            if freq > 0.005:
                color = get_action_color(action)
                painter.setPen(color)
                # 同时显示条件频率和绝对频率
                abs_freq = freq * self.reach_prob
                text = f"{action}: {freq*100:.0f}% (Abs: {abs_freq*100:.1f}%)"
                painter.drawText(bar_x, y_offset, bar_w, 11, Qt.AlignLeft, text)
                y_offset += 12
        
        painter.end()


class ConvergenceLineChart(QWidget):
    """Convergence 折线图 - 显示真实历史数据"""
    def __init__(self):
        super().__init__()
        self.iterations = 0
        self.avg_regret = 1.0
        self.regret_history = []  # 存储历史 regret 值
        self.setFixedSize(160, 130)
    
    def set_data(self, iterations: int, avg_regret: float):
        self.iterations = iterations
        self.avg_regret = avg_regret
        self.update()
    
    def set_history(self, history: list):
        """设置 regret 历史数据"""
        self.regret_history = history
        if history:
            self.avg_regret = history[-1]
            self.iterations = len(history)
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
        
        # 计算 Y 轴范围
        if self.regret_history:
            max_regret = max(self.regret_history) * 1.2
            max_regret = max(1.0, max_regret)
        else:
            max_regret = max(1.0, self.avg_regret * 1.2)
        
        painter.setPen(QColor("#888888"))
        painter.drawText(10, margin_top - 2, 18, 12, Qt.AlignRight, f"{max_regret:.0f}")
        painter.drawText(10, margin_top + h // 2 - 6, 18, 12, Qt.AlignRight, f"{max_regret/2:.0f}")
        painter.drawText(10, margin_top + h - 6, 18, 12, Qt.AlignRight, "0")
        
        painter.drawText(margin_left - 5, margin_top + h + 3, 20, 12, Qt.AlignCenter, "0")
        iter_str = str(self.iterations) if self.iterations < 1000 else f"{self.iterations//1000}k"
        painter.drawText(margin_left + w - 15, margin_top + h + 3, 30, 12, Qt.AlignCenter, iter_str)
        
        painter.drawText(margin_left, margin_top + h + 13, w, 12, Qt.AlignCenter, "Iterations")
        
        painter.setPen(QPen(QColor("#333333"), 1, Qt.DotLine))
        painter.drawLine(margin_left, margin_top + h // 2, margin_left + w, margin_top + h // 2)
        
        # 绘制真实历史曲线
        painter.setPen(QPen(QColor("#4a9eff"), 2))
        points = []
        
        if self.regret_history and len(self.regret_history) > 1:
            # 采样点（最多 50 个点）
            n = len(self.regret_history)
            step = max(1, n // 50)
            sampled = self.regret_history[::step]
            if self.regret_history[-1] not in sampled:
                sampled.append(self.regret_history[-1])
            
            for i, regret in enumerate(sampled):
                x = margin_left + int(i / (len(sampled) - 1) * w) if len(sampled) > 1 else margin_left
                y = margin_top + int((1 - min(1, regret / max_regret)) * h)
                points.append((x, y))
        else:
            # 没有历史，画单点
            x = margin_left + w
            y = margin_top + int((1 - min(1, self.avg_regret / max_regret)) * h)
            points = [(margin_left, margin_top), (x, y)]
        
        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1], points[i+1][0], points[i+1][1])
        
        # 当前点
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
    """策略矩阵 - 采用延迟加载模式，避免内存爆炸"""
    hand_clicked = Signal(str, dict)
    
    def __init__(self):
        super().__init__()
        self.engine = None
        self.current_node = None
        self.strategy_data = {}  # 仅用于非延迟加载模式 (Fallback)
        self.action_order = []
        self.view_mode = "strategy"
        self.selected_action = None
        self.player_range = {}
        self.setMinimumSize(350, 350)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
    
    def set_player_range(self, range_weights: dict):
        self.player_range = range_weights
    
    def set_engine_data(self, engine, node, action_order):
        """设置 C++ 引擎数据源，实现按需获取"""
        self.engine = engine
        self.current_node = node
        self.action_order = action_order
        self.view_mode = "strategy"
        self.selected_action = None
        self.strategy_data = {} # 清空旧数据
        self.update()

    def set_strategy(self, strategy_data: dict, action_order: list):
        """兼容旧模式"""
        self.engine = None
        self.current_node = None
        self.strategy_data = strategy_data
        self.action_order = action_order
        self.view_mode = "strategy"
        self.selected_action = None
        self.update()
    
    def set_range(self, range_data: dict, action_name: str = None):
        """兼容旧模式"""
        self.engine = None
        self.current_node = None
        self.strategy_data = {hand: {action_name or "range": freq} for hand, freq in range_data.items()}
        self.action_order = [action_name or "range"]
        self.view_mode = "range"
        self.selected_action = action_name
        self.update()
    
    def clear(self):
        self.engine = None
        self.current_node = None
        self.strategy_data = {}
        self.action_order = []
        self.update()
    
    def _get_hand_strategy(self, hand: str) -> dict:
        """从引擎按需获取特定手牌的策略"""
        if self.engine and self.current_node:
            return self.engine.get_hand_strategy(self.current_node).get(hand, {})
        return self.strategy_data.get(hand, {})

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        cell_w = w / 13
        cell_h = h / 13
        
        font = QFont("Arial", max(7, int(min(cell_w, cell_h) / 4)))
        painter.setFont(font)
        
        # 缓存当前节点的所有策略（仅限当前显示这一个节点，极小）
        current_node_strategy = {}
        if self.engine and self.current_node:
            current_node_strategy = self.engine.get_hand_strategy(self.current_node)

        for row in range(13):
            for col in range(13):
                hand = HAND_MATRIX[row][col]
                x = col * cell_w
                y = row * cell_h
                
                hand_strategy = current_node_strategy.get(hand, {}) if self.engine else self.strategy_data.get(hand, {})
                
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
        # 获取该手牌在当前节点的 reach probability
        reach_prob = self.player_range.get(hand, 0.0)
        
        # 背景色（如果是 fold 频率较高的则带一点红色调，否则深灰）
        total_non_fold = sum(f for a, f in hand_strategy.items() if "fold" not in a.lower())
        fold_freq = 1.0 - total_non_fold
        
        # 绘制背景
        painter.fillRect(int(x), int(y), int(cell_w), int(cell_h), QColor("#1a1a1a"))
        
        if fold_freq > 0.01:
            # 如果有策略内的 fold，用半透明红色背景表示
            c = ACTION_COLORS["fold"]
            painter.fillRect(int(x), int(y), int(cell_w), int(cell_h), QColor(c.red(), c.green(), c.blue(), 40))

        sorted_actions = sorted(
            [(a, f) for a, f in hand_strategy.items() if "fold" not in a.lower() and f > 0],
            key=lambda x: get_action_priority(x[0])
        )
        
        # 策略条的总高度 = cell_h * reach_prob
        # 这反映了手牌在当前 range 中的真实权重
        total_bar_h = cell_h * reach_prob
        
        current_y = y + cell_h
        for action, freq in sorted_actions:
            # 这里的 freq 是条件概率，乘以 reach_prob 得到绝对概率
            bar_height = freq * total_bar_h
            current_y -= bar_height
            color = get_action_color(action)
            painter.fillRect(int(x), int(current_y), int(cell_w), int(bar_height) + 1, color)
        
        # 边框
        painter.setPen(QPen(QColor("#1a1a1a"), 1))
        painter.drawRect(int(x), int(y), int(cell_w), int(cell_h))
        
        # 文字
        text_color = QColor("#ffffff") if reach_prob > 0.3 else QColor("#888888")
        painter.setPen(QColor("#000000"))
        painter.drawText(int(x) + 1, int(y) + 1, int(cell_w), int(cell_h), Qt.AlignCenter, hand)
        painter.setPen(text_color)
        painter.setFont(QFont("Arial", max(6, int(min(cell_w, cell_h) / 4.5))))
        painter.drawText(int(x), int(y), int(cell_w), int(cell_h), Qt.AlignCenter, hand)
    
    def _draw_range_cell(self, painter, x, y, cell_w, cell_h, hand, freq):
        """绘制 range 单元格，用颜色深浅表示权重"""
        # 保存当前字体
        normal_font = QFont("Arial", max(7, int(min(cell_w, cell_h) / 4)))
        
        if freq <= 0:
            # 不在 range 内
            bg_color = QColor("#2a2a2a")
            text_color = QColor("#666666")
        else:
            # 在 range 内，用颜色深浅表示权重
            if self.selected_action:
                base_color = get_action_color(self.selected_action)
            else:
                base_color = QColor("#27ae60")  # 绿色
            
            # 根据 freq 调整颜色深浅（freq 越高颜色越深）
            intensity = min(1.0, freq)  # 限制在 0-1
            
            # 混合颜色：freq=0 时是深灰，freq=1 时是基础色
            dark = QColor("#2a2a2a")
            r = int(dark.red() * (1 - intensity) + base_color.red() * intensity)
            g = int(dark.green() * (1 - intensity) + base_color.green() * intensity)
            b = int(dark.blue() * (1 - intensity) + base_color.blue() * intensity)
            bg_color = QColor(r, g, b)
            text_color = QColor("#ffffff")
        
        painter.fillRect(int(x), int(y), int(cell_w), int(cell_h), bg_color)
        painter.setPen(QPen(QColor("#3a3a3a"), 1))
        painter.drawRect(int(x), int(y), int(cell_w), int(cell_h))
        
        # 显示 hand 名称（使用正常字体）
        painter.setFont(normal_font)
        painter.setPen(text_color)
        
        # 如果有显著权重差异，显示 hand + 百分比
        if freq > 0 and freq < 0.99:
            # 上半部分显示 hand
            painter.drawText(int(x), int(y), int(cell_w), int(cell_h * 0.6), Qt.AlignCenter, hand)
            # 下半部分显示百分比（小字体）
            small_font = QFont("Arial", max(5, int(min(cell_w, cell_h) / 5)))
            painter.setFont(small_font)
            painter.setPen(QColor("#cccccc"))
            painter.drawText(int(x), int(y + cell_h * 0.5), int(cell_w), int(cell_h * 0.5), 
                           Qt.AlignCenter, f"{freq*100:.0f}%")
            # 恢复字体
            painter.setFont(normal_font)
        else:
            painter.drawText(int(x), int(y), int(cell_w), int(cell_h), Qt.AlignCenter, hand)
    
    def mouseMoveEvent(self, event):
        cell_w = self.width() / 13
        cell_h = self.height() / 13
        col = int(event.position().x() / cell_w)
        row = int(event.position().y() / cell_h)
        
        if 0 <= row < 13 and 0 <= col < 13:
            hand = HAND_MATRIX[row][col]
            hand_strategy = self._get_hand_strategy(hand)
            
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
            self.hand_clicked.emit(hand, self._get_hand_strategy(hand))


# #region agent log
def log_debug(hypothesis_id, message, location, data=None):
    import json, time
    log_path = "/Volumes/macOSexternal/Documents/proj/poker-expert/.cursor/debug.log"
    try:
        entry = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000)
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except: pass
# #endregion

class ResultsPage(QWidget):
    """Solver Results 页面"""
    continue_solving = Signal()
    # Signal: (new_board, oop_range, ip_range, pot_size, street_name)
    continue_to_next_street = Signal(list, object, object, float, str)
    
    # 扑克牌等级和花色
    RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
    SUITS = ['s', 'h', 'd', 'c']  # spades, hearts, diamonds, clubs
    SUIT_SYMBOLS = {'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}
    SUIT_COLORS = {'s': '#1a1a1a', 'h': '#e74c3c', 'd': '#3498db', 'c': '#27ae60'}
    
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
        self.pot_size = 10.0  # 当前底池大小
        self.selected_next_card = None  # 选择的下一张牌
        self.solve_timer = QElapsedTimer()
        self.init_ui()
    
    def init_ui(self):
        # 使用叠加布局，底层是结果，顶层是进度遮罩
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.content_widget = QWidget()
        content_layout = QHBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        self.main_layout.addWidget(self.content_widget)
        
        # 进度遮罩层
        self.progress_overlay = QFrame(self)
        self.progress_overlay.setStyleSheet("background-color: rgba(30, 30, 30, 230);")
        self.progress_overlay.setVisible(False)
        overlay_layout = QVBoxLayout(self.progress_overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)
        
        overlay_content = QFrame()
        overlay_content.setFixedWidth(400)
        overlay_content.setStyleSheet("background-color: #2a2a2a; border-radius: 12px; padding: 30px;")
        overlay_inner = QVBoxLayout(overlay_content)
        overlay_inner.setSpacing(20)
        
        self.progress_title = QLabel("Solving Game Tree...")
        self.progress_title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        self.progress_title.setAlignment(Qt.AlignCenter)
        overlay_inner.addWidget(self.progress_title)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(15)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1a1a1a;
                border: none;
                border-radius: 7px;
                text-align: center;
                color: transparent;
            }
            QProgressBar::chunk {
                background-color: #4a9eff;
                border-radius: 7px;
            }
        """)
        overlay_inner.addWidget(self.progress_bar)
        
        self.progress_status = QLabel("Initializing...")
        self.progress_status.setStyleSheet("color: #aaaaaa; font-size: 13px;")
        self.progress_status.setAlignment(Qt.AlignCenter)
        overlay_inner.addWidget(self.progress_status)
        
        self.progress_time = QLabel("")
        self.progress_time.setStyleSheet("color: #4a9eff; font-size: 12px; font-weight: bold;")
        self.progress_time.setAlignment(Qt.AlignCenter)
        overlay_inner.addWidget(self.progress_time)
        
        overlay_layout.addWidget(overlay_content)
        
        # 将 content_layout 应用到 content_widget
        layout = content_layout
        
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

        # 数据导出按钮
        self.dump_btn = QPushButton("💾 Dump Range Data")
        self.dump_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1a1a;
                color: #888888;
                border: 1px solid #333333;
                padding: 4px;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #2a2a2a; color: white; }
        """)
        self.dump_btn.clicked.connect(self._dump_data)
        left_layout.addWidget(self.dump_btn)
        
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
        
        # Next Street Section (Turn/River)
        self.next_street_section = QFrame()
        self.next_street_section.setStyleSheet("background-color: #1e3a1e; border-radius: 6px; padding: 8px;")
        next_street_layout = QVBoxLayout(self.next_street_section)
        next_street_layout.setContentsMargins(8, 8, 8, 8)
        next_street_layout.setSpacing(8)
        
        self.next_street_label = QLabel("🃏 Continue to Turn")
        self.next_street_label.setStyleSheet("color: #27ae60; font-size: 11px; font-weight: bold;")
        next_street_layout.addWidget(self.next_street_label)
        
        self.next_street_info = QLabel("Select next card:")
        self.next_street_info.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        next_street_layout.addWidget(self.next_street_info)
        
        # 警告：单街近似
        approx_warning = QLabel("⚠️ Note: Single-street approximation\n(Not full multi-street GTO)")
        approx_warning.setStyleSheet("color: #ffaa00; font-size: 9px;")
        approx_warning.setWordWrap(True)
        next_street_layout.addWidget(approx_warning)
        
        # Card selector grid
        self.card_selector_frame = QFrame()
        self.card_selector_layout = QGridLayout(self.card_selector_frame)
        self.card_selector_layout.setContentsMargins(0, 0, 0, 0)
        self.card_selector_layout.setSpacing(2)
        next_street_layout.addWidget(self.card_selector_frame)
        
        # Selected card display
        self.selected_card_label = QLabel("Selected: -")
        self.selected_card_label.setStyleSheet("color: white; font-size: 11px; font-weight: bold;")
        next_street_layout.addWidget(self.selected_card_label)
        
        # Confirm button
        self.confirm_next_street_btn = QPushButton("▶ Solve Next Street")
        self.confirm_next_street_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:disabled { background-color: #1a3a1a; color: #555555; }
        """)
        self.confirm_next_street_btn.clicked.connect(self._on_confirm_next_street)
        self.confirm_next_street_btn.setEnabled(False)
        next_street_layout.addWidget(self.confirm_next_street_btn)
        
        self.next_street_section.setVisible(False)
        left_layout.addWidget(self.next_street_section)
        
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
        right_scroll.setFixedWidth(240)  # 增加宽度从 190 到 240
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
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'progress_overlay'):
            self.progress_overlay.resize(self.size())
            
    def show_progress(self, current, total):
        self.progress_overlay.setVisible(True)
        self.progress_overlay.raise_()
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        
        if not self.solve_timer.isValid():
            self.solve_timer.start()
            
        percentage = (current / total) * 100 if total > 0 else 0
        self.progress_status.setText(f"Iteration {current} / {total} ({percentage:.1f}%)")
        
        if current > 0:
            elapsed = self.solve_timer.elapsed() / 1000
            rate = current / elapsed
            eta = (total - current) / rate if rate > 0 else 0
            self.progress_time.setText(f"Elapsed: {elapsed:.1f}s | ETA: {eta:.1f}s | Speed: {rate:.1f} it/s")

    def hide_progress(self):
        self.progress_overlay.setVisible(False)
        self.solve_timer.invalidate()

    def set_data(self, engine, game_tree, board, oop_range, ip_range, iterations: int,
                 oop_position: str = "OOP", ip_position: str = "IP", pot_size: float = 10.0):
        print(f"[Results] set_data entry, node_id: {getattr(game_tree, '_node_id', 'N/A')}", flush=True)
        self.engine = engine
        self.game_tree = game_tree
        self.current_node = game_tree
        
        # 允许 game_tree 为 None (虽然不应该发生，但防止崩溃)
        if game_tree is None:
            initial_player = 0
            print("[Results] Warning: game_tree is None in set_data", flush=True)
        else:
            initial_player = getattr(game_tree, 'player', 0)

        self.board = board
        self.original_oop_range = oop_range
        self.original_ip_range = ip_range
        from copy import deepcopy
        self.current_oop_range = deepcopy(oop_range)
        self.current_ip_range = deepcopy(ip_range)
        self.oop_position = oop_position
        self.ip_position = ip_position
        self.iterations = iterations
        self.pot_size = pot_size
        self.action_sequence = []
        self.node_history = []
        self.selected_action_filter = None
        self.current_view = "strategy"
        self.current_view_player = "OOP" if initial_player == 0 else "IP"
        self.selected_next_card = None
        
        self._hand_equity_cache = {}
        
        # 确定当前街道
        board_len = len(board)
        if board_len == 3:
            street = "Flop"
        elif board_len == 4:
            street = "Turn"
        else:
            street = "River"
        
        self.board_display.setText(f"Board ({street}): {' '.join(str(c) for c in board)}")
        
        # 使用真实历史数据
        if hasattr(engine, '_iteration_regrets') and engine._iteration_regrets:
            self.conv_chart.set_history(engine._iteration_regrets)
            avg_regret = engine.get_average_regret()
        else:
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
        
        print("[Results] Starting initial equity calculation...", flush=True)
        oop_eq = self._calculate_equity()
        print(f"[Results] Initial equity: {oop_eq:.2f}", flush=True)
        self.equity_history = [("Root", oop_eq, 100 - oop_eq)]
        self.equity_line_chart.set_history(self.equity_history, self.oop_position, self.ip_position)
        
        print("[Results] Calling _update_ui", flush=True)
        self._update_ui()
        print("[Results] set_data finished", flush=True)
    
    def _calculate_avg_regret(self) -> float:
        if not self.engine:
            return 1.0
        # 直接调用引擎的统计方法，不要在 Python 层遍历
        return self.engine.get_average_regret()
    
    def _calculate_equity(self) -> float:
        log_debug("H2", "_calculate_equity start", "results_page.py:1372")
        try:
            from solver.core.hand_evaluator import calculate_equity
            from solver.core.card_utils import get_all_combos, cards_conflict
            
            all_combos = get_all_combos()
            oop_total, total_weight = 0.0, 0.0
            
            oop_hands = [(h, w) for h, w in self.current_oop_range.weights.items() if w > 0]
            ip_hands = [(h, w) for h, w in self.current_ip_range.weights.items() if w > 0]
            
            if not oop_hands or not ip_hands:
                log_debug("H2", "_calculate_equity early exit (no hands)", "results_page.py:1384")
                return 50.0
            
            import random
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
                    log_debug("H2", "Calling C++ calculate_equity", "results_page.py:1405", {"oop": oop_hand, "ip": ip_hand})
                    eq = calculate_equity(list(oop_combo), list(ip_combo), self.board, num_simulations=10)
                    oop_total += eq * weight
                    total_weight += weight
            
            if total_weight > 0:
                oop_eq = oop_total / total_weight * 100
                self.equity_chart.set_equity(oop_eq, self.oop_position, self.ip_position)
                log_debug("H2", "_calculate_equity finished", "results_page.py:1412", {"equity": oop_eq})
                return oop_eq
        except Exception as e:
            log_debug("H2", "_calculate_equity error", "results_page.py:1414", {"error": str(e)})
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
            
            # 获取当前节点手牌策略（已包含缺失手牌的 Fallback）
            hand_strategy = self.engine.get_hand_strategy(prev_node)
            
            for hand, weight in range_obj.weights.items():
                if weight > 0:
                    # 即使 hand 不在 hand_strategy 中，也不要直接归零 (Wrapper 已处理，这里做双重保险)
                    hand_strat = hand_strategy.get(hand, {})
                    action_freq = hand_strat.get(action_str, 0)
                    
                    # 如果这手牌在此 node 完全没数据，保留原权重（或使用平均分布）
                    if not hand_strat:
                        # 面对 100 次迭代这种极端情况，我们倾向于保留 range 
                        # 获取 node 可选动作数
                        action_count = len(getattr(prev_node, 'actions', [1]))
                        action_freq = 1.0 / max(1, action_count)
                        
                    new_weights[hand] = weight * action_freq
                else:
                    new_weights[hand] = 0.0
            range_obj.weights = new_weights
    
    def _update_ui(self):
        print("[Results] _update_ui: Starting...", flush=True)
        if self.current_node is None:
            self.line_display.setText("Error: No node data available (C++ Build Failed)")
            return

        print("[Results] _update_ui: Updating history text...", flush=True)
        if not self.action_sequence:
            self.line_display.setText("(Root) - OOP to act first")
        else:
            lines = []
            for i, (player, action) in enumerate(self.action_sequence):
                pos = self.oop_position if player == "OOP" else self.ip_position
                lines.append(f"{i+1}. {pos} {action}")
            self.line_display.setText("\n".join(lines))
        
        self.back_btn.setEnabled(len(self.action_sequence) > 0)
        
        print(f"[Results] _update_ui: Accessing node properties for node_id={getattr(self.current_node, '_node_id', 'unknown')}...", flush=True)
        try:
            is_terminal = self.current_node.is_terminal
            print(f"[Results] _update_ui: is_terminal={is_terminal}", flush=True)
            node_type = getattr(self.current_node, 'node_type', 'player')
            print(f"[Results] _update_ui: node_type={node_type}", flush=True)
        except Exception as e:
            print(f"[Results] _update_ui: ERROR accessing node: {e}", flush=True)
            return

        is_terminal = is_terminal or node_type == "terminal"
        is_chance = node_type == "chance"
        
        # Terminal 节点时隐藏 Hand Strategy
        self.hand_strat_frame.setVisible(not is_terminal and not is_chance)
        
        if is_terminal:
            print("[Results] _update_ui: Calling _update_terminal_view", flush=True)
            self._update_terminal_view()
        elif is_chance:
            print("[Results] _update_ui: Calling _update_chance_node_view", flush=True)
            self._update_chance_node_view()
        else:
            print("[Results] _update_ui: Calling _update_non_terminal_view", flush=True)
            self._update_non_terminal_view()
        print("[Results] _update_ui: Finished.", flush=True)
    
    def _update_chance_node_view(self):
        """更新 Chance Node 视图 - 显示牌选择器"""
        # 隐藏普通策略相关区域
        self.strategy_section.setVisible(False)
        self.filter_section.setVisible(False)
        self.action_section.setVisible(False)
        
        # 显示 range 区域用于展示当前 board
        self.range_label.setText("🎲 Chance Node - Select Next Card")
        self.range_section.setVisible(True)
        
        # 清空之前的 range 按钮
        self._clear_layout(self.range_buttons_layout)
        
        # 显示当前 board
        current_street = self.current_node.state.street
        # 修复：始终显示 UI 层的真实 board，而不是 node 里的代表牌 board
        board_str = " ".join(str(c) for c in self.board)
        info_label = QLabel(f"Current Board ({current_street}): {board_str}")
        info_label.setStyleSheet("color: #27ae60; font-size: 11px; font-weight: bold;")
        self.range_buttons_layout.addWidget(info_label)
        
        # 显示下一条街的牌选择
        self.next_street_section.setVisible(True)
        
        # 确定下一条街
        if current_street == "flop":
            next_street = "Turn"
        elif current_street == "turn":
            next_street = "River"
        else:
            next_street = "?"
        
        self.next_street_label.setText(f"🃏 Select {next_street} Card")
        self.confirm_next_street_btn.setText(f"▶ Go to {next_street}")
        
        # 创建牌选择器，使用 Chance Node 的可用牌
        self._create_chance_card_selector()
        
        # Chance Node 没有策略，清空矩阵显示
        self.strategy_matrix.clear()
        self.matrix_title.setText("Select a card to continue")
        self.stats_label.setText("")
    
    def _create_chance_card_selector(self):
        """为 Chance Node 创建牌选择器 - 显示所有 47 张可用牌"""
        self._clear_layout(self.card_selector_layout)
        
        # 获取 Chance Node 的 cluster 信息
        chance_children = getattr(self.current_node, 'chance_children', None)
        if not chance_children:
            return
        
        # 获取已使用的牌（board 上的牌）
        used_cards = set(str(card) for card in self.current_node.state.board)
        
        # 构建 card -> cluster 映射
        self._card_to_cluster = {}
        for representative, child in chance_children.items():
            # 假设每个 cluster 包含相似的牌，我们需要从 game_tree 获取完整映射
            # 这里简化：把代表牌映射到自己
            self._card_to_cluster[str(representative)] = representative
        
        self._card_buttons = {}
        
        # 显示所有 52 张牌（排除已用的）
        idx = 0
        for rank in self.RANKS:
            for suit in self.SUITS:
                card_str = f"{rank}{suit}"
                
                if card_str in used_cards:
                    continue  # 跳过已用的牌
                
                btn = QPushButton(f"{rank}{self.SUIT_SYMBOLS.get(suit, suit)}")
                btn.setFixedSize(32, 26)
                btn.setCheckable(True)
                
                # 找到这张牌属于哪个 cluster
                cluster_key = self._find_cluster_for_card(card_str, chance_children)
                
                suit_color = self.SUIT_COLORS.get(suit, '#ffffff')
                btn.setStyleSheet(f"""
                    QPushButton {{ 
                        background-color: #f0f0f0; 
                        color: {suit_color}; 
                        border: none; 
                        border-radius: 3px; 
                        font-size: 10px; 
                        font-weight: bold; 
                    }}
                    QPushButton:hover {{ 
                        background-color: #ffffff; 
                        border: 2px solid #27ae60; 
                    }}
                    QPushButton:checked {{ 
                        background-color: #27ae60; 
                        color: white; 
                    }}
                """)
                btn.clicked.connect(lambda checked, c=card_str, k=cluster_key: self._on_chance_card_selected_full(c, k))
                
                self._card_buttons[card_str] = btn
                
                # 每行显示 4 张牌（按花色）
                row = self.RANKS.index(rank)
                col = self.SUITS.index(suit)
                self.card_selector_layout.addWidget(btn, row, col)
                idx += 1
        
        # 提示文字
        hint = QLabel(f"({len(chance_children)} clusters, {idx} cards available)")
        hint.setStyleSheet("color: #888888; font-size: 9px;")
        self.card_selector_layout.addWidget(hint, len(self.RANKS), 0, 1, 4)
    
    def _find_cluster_for_card(self, card_str: str, chance_children: dict):
        """找到一张牌属于哪个 cluster
        
        新逻辑：按 rank 分组，每个 rank 一个 bucket
        找到与选择的牌相同 rank 的 representative
        """
        rank_map = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10, 
                    '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2}
        
        # 解析牌的 rank
        rank_char = card_str[0]
        target_rank = rank_map.get(rank_char, 2)
        
        # 找到相同 rank 的 cluster
        for representative in chance_children.keys():
            if representative.rank == target_rank:
                return representative
        
        # 如果没找到（不应该发生），返回第一个
        return list(chance_children.keys())[0] if chance_children else None
    
    def _on_chance_card_selected_full(self, card_str: str, cluster_key):
        """选择具体的牌，映射到对应的 cluster"""
        # 取消其他选择
        for c, btn in self._card_buttons.items():
            if c != card_str:
                btn.setChecked(False)
        
        if self._card_buttons[card_str].isChecked():
            self.selected_next_card = card_str
            self._selected_cluster = cluster_key
            rank = card_str[0]
            suit = card_str[1]
            self.selected_card_label.setText(f"Selected: {rank}{self.SUIT_SYMBOLS.get(suit, suit)}")
            self.confirm_next_street_btn.setEnabled(True)
        else:
            self.selected_next_card = None
            self._selected_cluster = None
            self.selected_card_label.setText("Selected: -")
            self.confirm_next_street_btn.setEnabled(False)
    
    def _on_chance_card_selected(self, card):
        """选择 Chance Node 的牌"""
        # 取消其他选择
        for c, btn in self._card_buttons.items():
            if c != card:
                btn.setChecked(False)
        
        if self._card_buttons[card].isChecked():
            self.selected_next_card = str(card)
            self.selected_card_label.setText(f"Selected: {card}")
            self.confirm_next_street_btn.setEnabled(True)
        else:
            self.selected_next_card = None
            self.selected_card_label.setText("Selected: -")
            self.confirm_next_street_btn.setEnabled(False)
    
    def _on_confirm_chance_card(self):
        """确认 Chance Node 的牌选择，导航到对应子节点"""
        if not self.selected_next_card:
            return
        
        chance_children = getattr(self.current_node, 'chance_children', None)
        if not chance_children:
            return
        
        # 1. 尝试寻找对应的子节点（考虑 Card Abstraction）
        from solver.core.card_utils import parse_card
        actual_card = parse_card(self.selected_next_card)
        
        selected_child_node = None
        
        # 优先直接匹配
        for card_obj, child in chance_children.items():
            if str(card_obj) == self.selected_next_card:
                selected_child_node = child
                break
        
        # 如果没有直接匹配，按 Rank 寻找匹配的 Bucket（处理 Card Abstraction）
        if selected_child_node is None:
            for card_obj, child in chance_children.items():
                if card_obj.rank == actual_card.rank:
                    selected_child_node = child
                    print(f"[Results] Card Abstraction: Mapped {actual_card} to cluster representative {card_obj}")
                    break
        
        # 如果还是没找到，取第一个作为 fallback
        if selected_child_node is None and chance_children:
            selected_child_node = list(chance_children.values())[0]
            print(f"[Results] Warning: No bucket found for {actual_card}, using fallback")

        if selected_child_node:
            # 2. 保存历史
            self.node_history.append({
                'node': self.current_node,
                'oop_range': deepcopy(self.current_oop_range),
                'ip_range': deepcopy(self.current_ip_range),
                'board': list(self.board),
            })
            
            # 3. 导航到子节点
            self.action_sequence.append(("CARD", f"[{self.selected_next_card}]"))
            self.current_node = selected_child_node
            
            # 更新 board：使用用户实际选择的卡（而不是 cluster 代表卡）
            # 注意：即便 current_node.state.board 可能是代表牌，我们也要在 UI 层坚持显示用户选的那张
            previous_board = self.node_history[-1]['board']
            self.board = previous_board + [actual_card]
            
            street = self.current_node.state.street.capitalize()
            # 强制 UI 显示 self.board 而不是 node 里的 board
            self.board_display.setText(f"Board ({street}): {' '.join(str(c) for c in self.board)}")
            
            # 重新计算 equity
            oop_eq = self._calculate_equity()
            self.equity_history.append((f"+{self.selected_next_card}", oop_eq, 100 - oop_eq))
            self.equity_line_chart.set_history(self.equity_history, self.oop_position, self.ip_position)
            
            # 重置选择状态
            self.selected_next_card = None
            self._selected_cluster = None
            
            # 隐藏牌选择界面
            self.next_street_section.setVisible(False)
            
            # 更新 UI
            self._update_ui()
    
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
        
        # 在多街模式下，terminal node 就是最终节点（fold 或 River showdown）
        # 不需要显示"Continue to Turn"（那是 Chance Node 的职责）
        self.next_street_section.setVisible(False)
    
    def _update_next_street_section(self, can_continue: bool):
        """更新下一条街选择区域"""
        board_len = len(self.board)
        
        # 只有双方都有 range 且不是 River 才能继续
        if not can_continue or board_len >= 5:
            self.next_street_section.setVisible(False)
            return
        
        # 确定下一条街
        if board_len == 3:
            next_street = "Turn"
            self.next_street_label.setText("🃏 Continue to Turn")
        elif board_len == 4:
            next_street = "River"
            self.next_street_label.setText("🃏 Continue to River")
        else:
            self.next_street_section.setVisible(False)
            return
        
        self.next_street_section.setVisible(True)
        self.selected_next_card = None
        self.selected_card_label.setText("Selected: -")
        self.confirm_next_street_btn.setEnabled(False)
        self.confirm_next_street_btn.setText(f"▶ Solve {next_street}")
        
        # 生成牌选择器
        self._create_card_selector()
    
    def _create_card_selector(self):
        """创建牌选择器"""
        # 清空现有选择器
        self._clear_layout(self.card_selector_layout)
        
        # 获取已使用的牌
        used_cards = set()
        for card in self.board:
            used_cards.add(str(card))
        
        # 创建按钮
        self._card_buttons = {}
        for row, rank in enumerate(self.RANKS):
            for col, suit in enumerate(self.SUITS):
                card_str = f"{rank}{suit}"
                btn = QPushButton(f"{rank}{self.SUIT_SYMBOLS[suit]}")
                btn.setFixedSize(28, 24)
                
                if card_str in used_cards:
                    # 已使用的牌
                    btn.setEnabled(False)
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #1a1a1a;
                            color: #333333;
                            border: none;
                            border-radius: 3px;
                            font-size: 10px;
                        }
                    """)
                else:
                    suit_color = self.SUIT_COLORS[suit]
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: #f0f0f0;
                            color: {suit_color};
                            border: none;
                            border-radius: 3px;
                            font-size: 10px;
                            font-weight: bold;
                        }}
                        QPushButton:hover {{ background-color: #ffffff; border: 2px solid #27ae60; }}
                        QPushButton:checked {{ background-color: #27ae60; color: white; }}
                    """)
                    btn.setCheckable(True)
                    btn.clicked.connect(lambda checked, c=card_str: self._on_card_selected(c))
                
                self._card_buttons[card_str] = btn
                self.card_selector_layout.addWidget(btn, row, col)
    
    def _on_card_selected(self, card_str: str):
        """选择一张牌"""
        # 取消其他选中的牌
        for c, btn in self._card_buttons.items():
            if c != card_str and btn.isEnabled():
                btn.setChecked(False)
        
        if self._card_buttons[card_str].isChecked():
            self.selected_next_card = card_str
            rank = card_str[0]
            suit = card_str[1]
            self.selected_card_label.setText(f"Selected: {rank}{self.SUIT_SYMBOLS[suit]}")
            self.confirm_next_street_btn.setEnabled(True)
        else:
            self.selected_next_card = None
            self.selected_card_label.setText("Selected: -")
            self.confirm_next_street_btn.setEnabled(False)
    
    def _on_confirm_next_street(self):
        """确认继续到下一条街（或导航 Chance Node）"""
        if not self.selected_next_card:
            return
        
        # 检查当前是否是 Chance Node
        is_chance = getattr(self.current_node, 'node_type', 'player') == "chance"
        
        if is_chance:
            # 多街模式：在已构建的树中导航
            self._on_confirm_chance_card()
        else:
            # 单街模式：发送 signal 让 solver_page 重新构建树
            from solver.core.card_utils import parse_card
            new_card = parse_card(self.selected_next_card)
            new_board = list(self.board) + [new_card]
            
            street_name = "Turn" if len(new_board) == 4 else "River"
            
            self.continue_to_next_street.emit(
                new_board,
                self.current_oop_range,
                self.current_ip_range,
                self.pot_size,
                street_name
            )
    
    def _show_terminal_range(self, player):
        self.current_view_player = player
        self.current_view = "range"
        
        for p, btn in self._range_btns.items():
            if btn:
                btn.setChecked(p == player)
        
        position = self.oop_position if player == "OOP" else self.ip_position
        range_obj = self.current_oop_range if player == "OOP" else self.current_ip_range
        
        # 获取所有权重，并考虑 board blocker
        from solver.core.card_utils import get_all_combos, cards_conflict
        all_combos = get_all_combos()
        
        raw_weights = {}
        for hand, weight in range_obj.weights.items():
            if weight <= 0:
                continue
            
            # 检查这个 hand 有多少 valid combos（不与 board 冲突）
            hand_combos = all_combos.get(hand, [])
            valid_combos = [c for c in hand_combos if not cards_conflict(list(c), self.board)]
            
            if not valid_combos:
                # 所有 combos 都被 block，权重为 0
                raw_weights[hand] = 0.0
            else:
                # 按 valid combo 比例调整权重
                ratio = len(valid_combos) / len(hand_combos) if hand_combos else 0
                raw_weights[hand] = weight * ratio
        
        # 归一化权重（相对于最大值），便于显示
        max_weight = max(raw_weights.values()) if raw_weights else 1.0
        if max_weight > 0:
            range_data = {h: w / max_weight for h, w in raw_weights.items()}
        else:
            range_data = raw_weights
        
        self.strategy_matrix.set_player_range(range_data)
        self.strategy_matrix.set_range(range_data)
        self.matrix_title.setText(f"{player} ({position}) Range [Terminal]")
        
        self._clear_layout(self.legend_layout)
        
        # 统计：计算有效 combos
        total_combos = 0.0
        for hand, weight in raw_weights.items():
            if weight > 0:
                hand_combos = all_combos.get(hand, [])
                valid_combos = [c for c in hand_combos if not cards_conflict(list(c), self.board)]
                total_combos += len(valid_combos) * weight
        
        hands_in_range = sum(1 for w in raw_weights.values() if w > 0)
        self.stats_label.setText(f"Total: {total_combos:.0f} combos ({total_combos/1326*100:.1f}%) | {hands_in_range} hands")
    
    def _update_non_terminal_view(self):
        log_debug("H2", "_update_non_terminal_view start", "results_page.py:1953")
        # 始终更新 Board 显示，确保显示的是 UI 层的真实 board，而不是 node 里的代表牌 board
        street = self.current_node.state.street.capitalize()
        self.board_display.setText(f"Board ({street}): {' '.join(str(c) for c in self.board)}")

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
            log_debug("H2", "Calling _show_strategy", "results_page.py:2006")
            self._show_strategy(current_player)
        else:
            log_debug("H2", "Calling _show_range", "results_page.py:2008")
            self._show_range(acted_player)
        log_debug("H2", "_update_non_terminal_view end", "results_page.py:2009")
    
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
        
        from solver.core.card_utils import get_all_combos, cards_conflict
        all_combos = get_all_combos()
        
        # 1. 直接从引擎获取当前节点的策略（已包含 Fallback）
        raw_hand_strategy = self.engine.get_hand_strategy(self.current_node)
        
        # 2. 获取动作列表
        actions = getattr(self.current_node, 'actions', [])
        if not actions:
            all_actions = set()
            for strat in raw_hand_strategy.values():
                all_actions.update(strat.keys())
            actions = sorted(all_actions, key=get_action_priority)
        
        position = self.oop_position if player == "OOP" else self.ip_position
        range_obj = self.current_oop_range if player == "OOP" else self.current_ip_range
        
        # 考虑 board blockers 更新显示的 range 权重
        visible_range = {}
        for hand, weight in range_obj.weights.items():
            if weight <= 0:
                continue
            hand_combos = all_combos.get(hand, [])
            valid_combos = [c for c in hand_combos if not cards_conflict(list(c), self.board)]
            if valid_combos:
                # 即使只有部分 combo 有效，我们也认为这手牌 "in range"
                # 但权重按有效比例缩减
                visible_range[hand] = weight * (len(valid_combos) / len(hand_combos))
        
        # 同步当前 player 的可见 range 到矩阵，用于 gray out
        self.strategy_matrix.set_player_range(visible_range)
        
        # 3. 设置矩阵数据源
        if self.selected_action_filter is None:
            # 内部会自动根据 hand_strategy 进行渲染
            self.strategy_matrix.set_engine_data(self.engine, self.current_node, actions)
            self.matrix_title.setText(f"{player} ({position}) Strategy")
        else:
            # 过滤模式：显示 Range (weight * freq)
            range_data = {}
            for h, strat in raw_hand_strategy.items():
                weight = visible_range.get(h, 0.0)
                freq = strat.get(self.selected_action_filter, 0.0)
                if weight > 0:
                    range_data[h] = weight * freq
                
            self.strategy_matrix.set_range(range_data, self.selected_action_filter)
            self.matrix_title.setText(f"{player} ({position}) {self.selected_action_filter} Range")
        
        # 4. 更新图例和统计
        self._update_legend(actions, raw_hand_strategy)
        self._update_stats(raw_hand_strategy, actions)
    
    def _show_range(self, player):
        from solver.core.card_utils import get_all_combos, cards_conflict
        all_combos = get_all_combos()
        
        position = self.oop_position if player == "OOP" else self.ip_position
        range_obj = self.current_oop_range if player == "OOP" else self.current_ip_range
        
        # 考虑 board blocker
        range_data = {}
        total_combos = 0.0
        
        for hand, weight in range_obj.weights.items():
            if weight <= 0:
                continue
            
            hand_combos = all_combos.get(hand, [])
            valid_combos = [c for c in hand_combos if not cards_conflict(list(c), self.board)]
            
            if valid_combos:
                ratio = len(valid_combos) / len(hand_combos) if hand_combos else 0
                range_data[hand] = weight * ratio
                total_combos += len(valid_combos) * weight
        
        self.strategy_matrix.set_player_range(range_data)
        self.strategy_matrix.set_range(range_data)
        self.matrix_title.setText(f"{player} ({position}) Range")
        
        self._clear_layout(self.legend_layout)
        self.stats_label.setText(f"Total: {total_combos:.0f} combos ({total_combos/1326*100:.1f}%)")
    
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
            
            # 保存当前状态用于回退（包括 board）
            self.node_history.append({
                'node': self.current_node,
                'oop_range': deepcopy(self.current_oop_range),
                'ip_range': deepcopy(self.current_ip_range),
                'board': list(self.board),
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
            # 获取上一个动作
            last_action_tuple = self.action_sequence.pop()
            if self.equity_history:
                self.equity_history.pop()
            
            # 恢复状态
            prev_state = self.node_history.pop()
            self.current_node = prev_state['node']
            self.current_oop_range = prev_state['oop_range']
            self.current_ip_range = prev_state['ip_range']
            
            # 恢复 board
            if 'board' in prev_state:
                self.board = prev_state['board']
            else:
                self.board = self.current_node.state.board
            
            # 如果回退的是选牌动作，重置选牌界面
            if last_action_tuple[0] == "CARD":
                self.selected_next_card = None
                self.next_street_section.setVisible(True)
            else:
                self.next_street_section.setVisible(False)
            
            street = self.current_node.state.street.capitalize()
            self.board_display.setText(f"Board ({street}): {' '.join(str(c) for c in self.board)}")
            
            self.selected_action_filter = None
            self.current_view = "strategy"
            
            self._calculate_equity()
            self.equity_line_chart.set_history(self.equity_history, self.oop_position, self.ip_position)
            self._update_ui()
        else:
            # 在根节点且无历史，不做操作，由上一层可能处理
            pass
    
    def _reset_to_root(self):
        self.action_sequence = []
        self.node_history = []
        self.current_node = self.game_tree
        self.current_oop_range = deepcopy(self.original_oop_range)
        self.current_ip_range = deepcopy(self.original_ip_range)
        self.selected_action_filter = None
        self.current_view = "strategy"
        
        # 重置 board 为初始 board
        self.board = self.game_tree.state.board
        street = self.game_tree.state.street.capitalize()
        self.board_display.setText(f"Board ({street}): {' '.join(str(c) for c in self.board)}")
        
        oop_eq = self._calculate_equity()
        self.equity_history = [("Root", oop_eq, 100 - oop_eq)]
        self.equity_line_chart.set_history(self.equity_history, self.oop_position, self.ip_position)
        
        self._update_ui()
    
    def _update_legend(self, actions, hand_strategy):
        self._clear_layout(self.legend_layout)
        
        position = "OOP" if self.current_node.player == 0 else "IP"
        range_obj = self.current_oop_range if position == "OOP" else self.current_ip_range
        
        action_combos = defaultdict(float)
        total_combos = 0.0
        
        from solver.core.card_utils import get_all_combos, cards_conflict
        all_combos = get_all_combos()
        
        for hand, weight in range_obj.weights.items():
            if weight <= 0:
                continue
                
            # 获取该手牌在当前 board 下的有效 combo 数
            hand_combos = all_combos.get(hand, [])
            valid_combos_count = len([c for c in hand_combos if not cards_conflict(list(c), self.board)])
            
            if valid_combos_count <= 0:
                continue
                
            strat = hand_strategy.get(hand, {})
            # 该手牌在 range 中的实际权重（考虑权重和 blocker）
            effective_weight = weight * valid_combos_count
            
            hand_total_freq = sum(strat.values())
            for action, freq in strat.items():
                action_combos[action] += effective_weight * freq
                
            if hand_total_freq < 0.999: # 兜底补齐 fold
                action_combos["fold"] += effective_weight * (1.0 - hand_total_freq)
            
            total_combos += effective_weight
        
        for action in ["fold"] + [a for a in actions if "fold" not in a.lower()]:
            combos = action_combos.get(action, 0)
            if combos > 0.01:
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
        """更新统计文本（基于有效 Range）"""
        action_combos = defaultdict(float)
        total_combos = 0.0
        
        # 获取当前位置的 range 权重，用于计算绝对 combo 数
        current_player = "OOP" if self.current_node.player == 0 else "IP"
        player_range = self.current_oop_range if current_player == "OOP" else self.current_ip_range
        
        from solver.core.card_utils import get_all_combos, cards_conflict
        all_combos = get_all_combos()
        
        for hand, strat in hand_strategy.items():
            reach_prob = player_range.weights.get(hand, 0.0)
            if reach_prob <= 0: continue
            
            hand_combos = all_combos.get(hand, [])
            valid_count = len([c for c in hand_combos if not cards_conflict(list(c), self.board)])
            if valid_count <= 0: continue
            
            hand_total = sum(strat.values())
            # 使用 reach_prob 和 blocker 缩放 combo 数
            effective_combos = valid_count * reach_prob
            
            for action, freq in strat.items():
                action_combos[action] += effective_combos * freq
            if hand_total < 0.999:
                action_combos["fold"] += effective_combos * (1.0 - hand_total)
            total_combos += effective_combos
        
        parts = []
        # 按优先级显示动作统计
        sorted_actions = sorted(action_combos.keys(), key=get_action_priority)
        for action in sorted_actions:
            c = action_combos.get(action, 0)
            if c > 0.01:
                pct = c / total_combos * 100 if total_combos > 0 else 0
                parts.append(f"{action}: {c:.1f} ({pct:.0f}%)")
        
        self.stats_label.setText(f"Effective: {total_combos:.1f} combos\n" + "\n".join(parts))
    
    def _dump_data(self):
        """将当前节点的策略和 Range 导出到 tmp/output"""
        try:
            output_dir = "tmp/output"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            board_str = "_".join(str(c) for c in self.board)
            street = self.current_node.state.street
            node_player = "OOP" if self.current_node.player == 0 else "IP"
            
            filename = f"range_{street}_{node_player}_{timestamp}.json"
            filepath = os.path.join(output_dir, filename)
            
            # 准备数据
            hand_strategies = self.engine.get_hand_strategy(self.current_node)
            player_range = self.current_oop_range if self.current_node.player == 0 else self.current_ip_range
            
            dump_data = {
                "timestamp": timestamp,
                "street": street,
                "board": [str(c) for c in self.board],
                "acting_player": node_player,
                "action_history": [f"{p}: {a}" for p, a in self.action_sequence],
                "pot": self.current_node.state.pot,
                "hands": {}
            }
            
            for hand, strat in hand_strategies.items():
                weight = player_range.weights.get(hand, 0.0)
                if weight > 0.0001:
                    dump_data["hands"][hand] = {
                        "reach_prob": weight,
                        "strategy": strat
                    }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(dump_data, f, indent=2, ensure_ascii=False)
            
            print(f"[Dump] Data saved to {filepath}")
            from PySide6.QtWidgets import QMessageBox
            # QMessageBox.information(self, "Dump Success", f"Data exported to:\n{filepath}")
            self.stats_label.setText(f"✅ Last Dump: {filename}\n" + self.stats_label.text())
            
        except Exception as e:
            print(f"[Dump] Error: {e}")

    def _on_hand_clicked(self, hand, strategy):
        player = self.current_view_player or ("OOP" if self.current_node.player == 0 else "IP")
        self._calculate_combo_equities(hand, player)
        
        # 获取该手牌的 reach probability
        player_range = self.current_oop_range if player == "OOP" else self.current_ip_range
        reach_prob = player_range.weights.get(hand, 0.0)
        
        # Terminal 节点时只显示 equity，不显示 strategy
        is_terminal = self.current_node.is_terminal or getattr(self.current_node, 'node_type', 'player') == "terminal"
        if not is_terminal and strategy:
            total = sum(strategy.values())
            display_strategy = dict(strategy)
            if total < 0.99:
                display_strategy["fold"] = 1.0 - total
            # 传递 reach_prob 给 strategy chart
            self.hand_strategy_chart.set_data(hand, display_strategy, reach_prob)
        else:
            self.hand_strategy_chart.clear()
    
    def _calculate_combo_equities(self, hand, player):
        """计算每个 combo 的 equity"""
        try:
            from solver.core.hand_evaluator import calculate_equity
            from solver.core.card_utils import get_all_combos, cards_conflict
            
            all_combos = get_all_combos()
            hand_combos = all_combos.get(hand, [])
            
            if not hand_combos:
                self.hand_equity_chart.clear()
                return
            
            # 获取对手 range
            opp_range = self.current_ip_range if player == "OOP" else self.current_oop_range
            opp_hands = [(h, w) for h, w in opp_range.weights.items() if w > 0]
            
            combo_results = []  # [(combo_str, equity, is_valid), ...]
            
            for combo in hand_combos:
                combo_str = "".join(str(c) for c in combo)
                
                # 检查是否与 board 冲突
                if cards_conflict(list(combo), self.board):
                    combo_results.append((combo_str, 0.0, False))
                    continue
                
                # 计算 equity
                if not opp_hands:
                    combo_results.append((combo_str, 100.0, True))
                    continue
                
                total_eq, total_weight = 0.0, 0.0
                
                # 采样对手手牌计算
                sample_opps = opp_hands[:10]  # 限制采样数量
                
                for opp_hand, opp_weight in sample_opps:
                    opp_combos = all_combos.get(opp_hand, [])
                    if opp_combos:
                        for opp_combo in opp_combos[:2]:  # 每个 hand 最多采样 2 个 combo
                            if not cards_conflict(list(opp_combo), self.board) and not cards_conflict(list(combo), list(opp_combo)):
                                eq = calculate_equity(list(combo), list(opp_combo), self.board, num_simulations=10)
                                total_eq += eq * opp_weight
                                total_weight += opp_weight
                                break
                
                if total_weight > 0:
                    combo_eq = total_eq / total_weight * 100
                else:
                    combo_eq = 50.0
                
                combo_results.append((combo_str, combo_eq, True))
            
            # 更新显示
            self.hand_equity_chart.set_combo_data(hand, combo_results, player)
            
        except Exception as e:
            print(f"[Equity] Error calculating combo equities: {e}")
            self.hand_equity_chart.clear()
    
    def _calculate_hand_equity(self, hand, player):
        """旧接口，兼容"""
        self._calculate_combo_equities(hand, player)
    
    def _get_hand_combos(self, hand):
        if len(hand) == 2:
            return 6
        elif hand.endswith('s'):
            return 4
        return 12


