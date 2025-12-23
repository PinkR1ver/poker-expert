"""
Position Analysis Report - 位置分析报告
包含 PositionTableWidget（扑克桌样式可视化）和 PositionAnalysisReport（报告页面）
"""
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSplitter, QTreeWidget, QTreeWidgetItem
)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QBrush, QPainter, QPen, QFont

from gui.styles import PROFIT_GREEN, PROFIT_RED


class PositionTableWidget(QWidget):
    """
    扑克桌样式的 Position 分析可视化组件。
    绘制椭圆桌子、6个圆形位置卡片、中心统计框。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.position_data = {}
        self.overall_stats = {"winloss": 0.0, "flop_pct": 0.0, "showdown_pct": 0.0, "winloss_bb": 0.0, "bb_per_100": 0.0, "won_rake": 0.0, "total_hands": 0}
        self.show_big_blinds = True
        self.show_bb100 = True
        self.big_blind = 0.02
        self.winloss_min = 0.0
        self.winloss_max = 0.0
        self.setMinimumHeight(300)
        self.setMaximumHeight(350)
        self.setMinimumWidth(700)
    
    def set_data(self, position_stats, big_blind=0.02):
        """设置 position 统计数据"""
        self.big_blind = big_blind
        
        self.position_data = {}
        total_hands = 0
        total_flop_hands = 0
        total_showdown_hands = 0
        total_winloss = 0.0
        total_winloss_bb = 0.0
        total_won_rake = 0.0
        total_rake_bb = 0.0
        
        all_winloss = []
        
        for pos_name in ["BB", "UTG", "MP", "CO", "BTN", "SB"]:
            if pos_name not in position_stats:
                continue
            stats = position_stats[pos_name]
            if stats["total_hands"] == 0:
                continue
            
            flop_count = stats.get("flop_count", 0)
            flop_pct = (flop_count / stats["total_hands"] * 100) if stats["total_hands"] > 0 else 0.0
            showdown_count = stats.get("showdown_count", 0)
            
            winloss = stats["net_profit"]
            winloss_bb = (winloss / big_blind) if big_blind > 0 else 0.0
            bb_per_100 = (winloss_bb / stats["total_hands"] * 100) if stats["total_hands"] > 0 else 0.0
            won_rake = stats.get("won_rake", 0.0)
            
            # Rake 的 BB 和 bb/100 计算
            rake_bb = (won_rake / big_blind) if big_blind > 0 else 0.0
            rake_bb_per_100 = (rake_bb / stats["total_hands"] * 100) if stats["total_hands"] > 0 else 0.0
            
            all_winloss.append(winloss)
            
            self.position_data[pos_name] = {
                "winloss": winloss,
                "winloss_bb": winloss_bb,
                "bb_per_100": bb_per_100,
                "flop_pct": flop_pct,
                "showdown_count": showdown_count,
                "total_hands": stats["total_hands"],
                "won_rake": won_rake,
                "rake_bb": rake_bb,
                "rake_bb_per_100": rake_bb_per_100,
            }
            
            total_hands += stats["total_hands"]
            total_flop_hands += flop_count
            total_showdown_hands += showdown_count
            total_winloss += winloss
            total_winloss_bb += winloss_bb
            total_won_rake += won_rake
            total_rake_bb += rake_bb
        
        if all_winloss:
            self.winloss_min = min(all_winloss)
            self.winloss_max = max(all_winloss)
        else:
            self.winloss_min = 0.0
            self.winloss_max = 0.0
        
        total_bb_per_100 = (total_winloss_bb / total_hands * 100) if total_hands > 0 else 0.0
        total_rake_bb_per_100 = (total_rake_bb / total_hands * 100) if total_hands > 0 else 0.0
        
        if total_hands > 0:
            self.overall_stats = {
                "winloss": total_winloss,
                "winloss_bb": total_winloss_bb,
                "bb_per_100": total_bb_per_100,
                "flop_pct": (total_flop_hands / total_hands * 100) if total_hands > 0 else 0.0,
                "showdown_pct": (total_showdown_hands / total_hands * 100) if total_hands > 0 else 0.0,
                "won_rake": total_won_rake,
                "rake_bb": total_rake_bb,
                "rake_bb_per_100": total_rake_bb_per_100,
                "total_hands": total_hands,
            }
        
        self.update()
    
    def set_view_mode(self, show_big_blinds):
        self.show_big_blinds = show_big_blinds
        self.update()
    
    def set_bb100_mode(self, show_bb100):
        self.show_bb100 = show_bb100
        self.update()
    
    def _get_color_for_value(self, value):
        """根据输赢值计算圆圈背景色"""
        if self.winloss_max == self.winloss_min:
            return QColor(80, 80, 80)
        
        if value > 0:
            if self.winloss_max > 0:
                ratio = min(value / self.winloss_max, 1.0)
            else:
                ratio = 0.5
            r = int(61 - 15 * ratio)
            g = int(107 + 18 * ratio)
            b = int(61 - 11 * ratio)
            return QColor(r, g, b)
        
        if value < 0:
            if self.winloss_min < 0:
                ratio = min(abs(value) / abs(self.winloss_min), 1.0)
            else:
                ratio = 0.5
            r = int(107 + 32 * ratio)
            g = int(91 - 33 * ratio)
            b = int(79 - 21 * ratio)
            return QColor(r, g, b)
        
        return QColor(80, 80, 80)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        painter.fillRect(0, 0, width, height, QColor("#2a2a2a"))
        
        # Ellipse table
        table_margin = 40
        table_rect = QRectF(table_margin, table_margin, width - 2 * table_margin, height - 2 * table_margin)
        painter.setPen(QPen(QColor("#3a3a3a"), 2))
        painter.setBrush(QBrush(QColor("#1e1e1e")))
        painter.drawEllipse(table_rect)
        
        # Position coordinates
        center_x = width / 2
        center_y = height / 2
        radius_x = (width - 2 * table_margin) / 2 - 60
        radius_y = (height - 2 * table_margin) / 2 - 60
        
        positions = [
            ("BB", center_x - radius_x * 0.75, center_y - radius_y * 0.85),
            ("UTG", center_x, center_y - radius_y * 1.05),
            ("MP", center_x + radius_x * 0.75, center_y - radius_y * 0.85),
            ("CO", center_x + radius_x * 0.75, center_y + radius_y * 0.85),
            ("BTN", center_x, center_y + radius_y * 1.05),
            ("SB", center_x - radius_x * 0.75, center_y + radius_y * 0.85),
        ]
        
        # Draw position circles
        circle_radius = 48
        for pos_name, x, y in positions:
            if pos_name not in self.position_data:
                continue
            
            data = self.position_data[pos_name]
            winloss = data["winloss"]
            
            base_color = self._get_color_for_value(winloss)
            circle_color = QColor(base_color.red(), base_color.green(), base_color.blue(), 200)
            
            painter.setPen(QPen(QColor(base_color.red(), base_color.green(), base_color.blue(), 230), 2))
            painter.setBrush(QBrush(circle_color))
            painter.drawEllipse(QRectF(x - circle_radius, y - circle_radius, circle_radius * 2, circle_radius * 2))
            
            # Position name
            painter.setPen(Qt.white)
            font = QFont()
            font.setBold(True)
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(QRectF(x - circle_radius, y - circle_radius + 8, circle_radius * 2, 18), Qt.AlignCenter, pos_name)
            
            # Main value
            winloss_bb = data.get("winloss_bb", 0.0)
            bb_per_100 = data.get("bb_per_100", 0.0)
            
            if self.show_bb100:
                display_value = bb_per_100
                value_color = QColor(PROFIT_GREEN) if bb_per_100 >= 0 else QColor(PROFIT_RED)
                value_num = f"{bb_per_100:.1f}"
                unit_text = " bb/100"
            else:
                display_value = winloss if not self.show_big_blinds else winloss_bb
                value_color = QColor(PROFIT_GREEN) if winloss >= 0 else QColor(PROFIT_RED)
                if self.show_big_blinds:
                    value_num = f"{winloss_bb:.1f}"
                    unit_text = " BB"
                else:
                    value_num = f"${winloss:.2f}"
                    unit_text = ""
            
            # Calculate text width for centering
            font.setBold(True)
            font.setPointSize(11)
            painter.setFont(font)
            num_width = painter.fontMetrics().horizontalAdvance(value_num)
            
            font.setPointSize(8)
            font.setBold(False)
            painter.setFont(font)
            unit_width = painter.fontMetrics().horizontalAdvance(unit_text) if unit_text else 0
            
            total_width = num_width + unit_width
            start_x = x - total_width / 2
            
            # Draw value
            font.setBold(True)
            font.setPointSize(11)
            painter.setFont(font)
            painter.setPen(value_color)
            painter.drawText(QRectF(start_x, y - circle_radius + 24, num_width + 2, 16), Qt.AlignLeft | Qt.AlignVCenter, value_num)
            
            # Draw unit
            if unit_text:
                font.setPointSize(8)
                font.setBold(False)
                painter.setFont(font)
                painter.setPen(QColor("#888888"))
                painter.drawText(QRectF(start_x + num_width, y - circle_radius + 26, unit_width + 2, 14), Qt.AlignLeft | Qt.AlignVCenter, unit_text)
            
            # Hands count
            font.setPointSize(9)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QColor("#aaaaaa"))
            painter.drawText(QRectF(x - circle_radius, y - circle_radius + 40, circle_radius * 2, 14), Qt.AlignCenter, f"{data['total_hands']} hands")
            
            # Flop %
            painter.setPen(Qt.white)
            painter.drawText(QRectF(x - circle_radius, y - circle_radius + 54, circle_radius * 2, 14), Qt.AlignCenter, f"Flop %: {data['flop_pct']:.1f}%")
            
            # Showdown
            painter.drawText(QRectF(x - circle_radius, y - circle_radius + 68, circle_radius * 2, 14), Qt.AlignCenter, f"Showdown: {data['showdown_count']}")
        
        # Center stats box
        center_box_width = 200
        center_box_height = 110
        center_box_x = center_x - center_box_width / 2
        center_box_y = center_y - center_box_height / 2
        
        painter.setPen(QPen(QColor(120, 120, 120), 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(center_box_x, center_box_y, center_box_width, center_box_height))
        
        stats = self.overall_stats
        bb_per_100 = stats.get("bb_per_100", 0)
        winloss = stats["winloss"]
        winloss_bb = stats["winloss_bb"]
        
        if self.show_bb100:
            main_value = bb_per_100
            main_label = "bb/100:"
            main_text = f"{bb_per_100:.2f}"
        else:
            main_label = "Winloss:"
            if self.show_big_blinds:
                main_value = winloss_bb
                main_text = f"{winloss_bb:.1f} BB"
            else:
                main_value = winloss
                main_text = f"${winloss:.2f}"
        
        main_color = QColor(PROFIT_GREEN) if main_value >= 0 else QColor(PROFIT_RED)
        
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        
        y_offset = 16
        painter.setPen(Qt.white)
        painter.drawText(QRectF(center_box_x, center_box_y + y_offset, center_box_width / 2 + 10, 18), Qt.AlignRight, main_label)
        painter.setPen(main_color)
        painter.drawText(QRectF(center_box_x + center_box_width / 2 + 14, center_box_y + y_offset, center_box_width / 2 - 20, 18), Qt.AlignLeft, main_text)
        
        # Rake（根据显示模式切换）
        y_offset += 22
        font.setBold(False)
        font.setPointSize(10)
        painter.setFont(font)
        painter.setPen(Qt.white)
        painter.drawText(QRectF(center_box_x, center_box_y + y_offset, center_box_width / 2 + 10, 16), Qt.AlignRight, "Rake:")
        painter.setPen(QColor("#ff9800"))
        
        # Rake 显示模式：bb/100 模式显示 rake bb/100，Total 模式根据 BB/$ 切换
        if self.show_bb100:
            rake_text = f"{stats.get('rake_bb_per_100', 0):.2f} bb/100"
        else:
            if self.show_big_blinds:
                rake_text = f"{stats.get('rake_bb', 0):.1f} BB"
            else:
                rake_text = f"${stats.get('won_rake', 0):.2f}"
        painter.drawText(QRectF(center_box_x + center_box_width / 2 + 14, center_box_y + y_offset, center_box_width / 2 - 20, 16), Qt.AlignLeft, rake_text)
        
        # Flop % / Showdown %
        y_offset += 20
        painter.setPen(Qt.white)
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(QRectF(center_box_x, center_box_y + y_offset, center_box_width, 14), Qt.AlignCenter, f"Flop: {stats['flop_pct']:.1f}%  |  SD: {stats['showdown_pct']:.1f}%")
        
        # Hands count
        y_offset += 16
        painter.setPen(QColor("#888888"))
        painter.drawText(QRectF(center_box_x, center_box_y + y_offset, center_box_width, 14), Qt.AlignCenter, f"({stats.get('total_hands', 0)} hands)")


class PositionAnalysisReport(QWidget):
    """Position 分析报告页面"""
    
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Title and controls
        title_layout = QHBoxLayout()
        title = QLabel("Position Analysis")
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        self.btn_bb100_mode = QPushButton("bb/100")
        self.btn_bb100_mode.setCheckable(True)
        self.btn_bb100_mode.setChecked(True)
        self.btn_bb100_mode.setFixedWidth(70)
        self.btn_bb100_mode.setStyleSheet("""
            QPushButton { background-color: #3a3a3a; color: white; border: 1px solid #555; padding: 4px; border-radius: 4px; }
            QPushButton:checked { background-color: #4caf50; }
        """)
        self.btn_bb100_mode.clicked.connect(self.toggle_bb100_mode)
        title_layout.addWidget(self.btn_bb100_mode)
        
        self.btn_view_mode = QPushButton("BB")
        self.btn_view_mode.setCheckable(True)
        self.btn_view_mode.setChecked(True)
        self.btn_view_mode.setFixedWidth(50)
        self.btn_view_mode.setStyleSheet("""
            QPushButton { background-color: #3a3a3a; color: white; border: 1px solid #555; padding: 4px; border-radius: 4px; }
            QPushButton:checked { background-color: #4caf50; }
        """)
        self.btn_view_mode.clicked.connect(self.toggle_view_mode)
        title_layout.addWidget(self.btn_view_mode)
        layout.addLayout(title_layout)
        
        # Splitter
        splitter = QSplitter(Qt.Vertical)
        
        self.position_table = PositionTableWidget()
        self.position_table.setMaximumHeight(350)
        self.position_table.set_view_mode(True)
        self.position_table.set_bb100_mode(True)
        splitter.addWidget(self.position_table)
        
        # Stats table
        hands_container = QWidget()
        hands_layout = QVBoxLayout(hands_container)
        hands_layout.setContentsMargins(0, 0, 0, 0)
        hands_layout.setSpacing(4)
        
        hands_label = QLabel("Statistics by Position")
        hands_label.setStyleSheet("color: #b0b0b0; font-size: 12px; font-weight: bold;")
        hands_layout.addWidget(hands_label)
        
        self.hands_tree = QTreeWidget()
        self.hands_tree.setHeaderLabels(["Position", "Hands", "Rake", "Net Profit", "bb/100"])
        self.hands_tree.setStyleSheet("""
            QTreeWidget { background-color: #252525; border: 1px solid #3a3a3a; color: #e0e0e0; }
            QTreeWidget::item { padding: 6px; }
            QTreeWidget::item:selected { background-color: #3a3a3a; }
            QHeaderView::section { background-color: #2a2a2a; color: #e0e0e0; padding: 8px; border: none; }
        """)
        self.hands_tree.setAlternatingRowColors(True)
        self.hands_tree.setRootIsDecorated(False)
        hands_layout.addWidget(self.hands_tree)
        
        splitter.addWidget(hands_container)
        splitter.setSizes([1, 4])
        layout.addWidget(splitter, 1)
    
    def toggle_view_mode(self):
        show_bb = self.btn_view_mode.isChecked()
        self.position_table.set_view_mode(show_bb)
        self.btn_view_mode.setText("BB" if show_bb else "$")
    
    def toggle_bb100_mode(self):
        show_bb100 = self.btn_bb100_mode.isChecked()
        self.position_table.set_bb100_mode(show_bb100)
        self.btn_bb100_mode.setText("bb/100" if show_bb100 else "Total")

    def refresh_data(self, start_date=None, end_date=None):
        """刷新数据"""
        hands = self.db.get_hands_in_range(start_date, end_date) if hasattr(self.db, "get_hands_in_range") else self.db.get_all_hands()
        
        position_stats = {}
        position_names = ["BTN", "SB", "BB", "UTG", "MP", "CO"]
        
        for pos in position_names:
            position_stats[pos] = {
                "hands": [], "net_profit": 0.0, "won_rake": 0.0,
                "vpip_count": 0, "three_bet_count": 0, "faced_open_count": 0,
                "total_hands": 0, "total_bb": 0.0, "flop_count": 0, "showdown_count": 0,
            }
        
        big_blinds = []
        
        for row in hands:
            hand_id = row[0]
            profit = float(row[5] or 0.0)
            rake = float(row[6] or 0.0)
            
            payload = self.db.get_replay_payload(hand_id, min_version=2)
            if not payload:
                continue
            
            hero_seat = payload.get("hero_seat", 0)
            button_seat = payload.get("button_seat", 0)
            
            if hero_seat and button_seat:
                relative_pos = (hero_seat - button_seat + 6) % 6
                pos_map = {0: "BTN", 1: "SB", 2: "BB", 3: "UTG", 4: "MP", 5: "CO"}
                position = pos_map.get(relative_pos, "Unknown")
            else:
                position = "Unknown"
            
            if position not in position_stats:
                position_stats[position] = {
                    "hands": [], "net_profit": 0.0, "won_rake": 0.0,
                    "vpip_count": 0, "three_bet_count": 0, "faced_open_count": 0,
                    "total_hands": 0, "total_bb": 0.0, "flop_count": 0, "showdown_count": 0,
                }
            
            stats = position_stats[position]
            stats["total_hands"] += 1
            stats["net_profit"] += profit
            
            if profit > 0 and rake > 0:
                stats["won_rake"] += rake
            
            # Parse big blind
            blinds_str = row[2] or ""
            big_blind = 0.0
            try:
                m = re.search(r'\$?([\d\.]+)\s*/\s*\$?([\d\.]+)', blinds_str)
                if m:
                    big_blind = float(m.group(2))
                else:
                    m = re.search(r'\$?([\d\.]+)\s*-\s*\$?([\d\.]+)', blinds_str)
                    if m:
                        big_blind = float(m.group(2))
                    else:
                        numbers = re.findall(r'[\d\.]+', blinds_str)
                        if len(numbers) >= 2:
                            big_blind = float(numbers[1])
                        elif len(numbers) == 1:
                            big_blind = float(numbers[0])
            except:
                pass
            
            if big_blind > 0:
                stats["total_bb"] += profit / big_blind
                big_blinds.append(big_blind)
            
            # Check showdown
            went_to_showdown = bool(row[12] if len(row) > 12 else False)
            if went_to_showdown:
                stats["showdown_count"] += 1
            
            # Check flop
            actions = payload.get("actions", [])
            hero_name = payload.get("hero_name", "Hero")
            saw_flop = False
            for act in actions:
                if not isinstance(act, dict):
                    continue
                street = act.get("street", "")
                player = act.get("player")
                if street in ["Flop", "Turn", "River"] and player == hero_name:
                    saw_flop = True
                    break
            if saw_flop:
                stats["flop_count"] += 1
        
        avg_big_blind = sum(big_blinds) / len(big_blinds) if big_blinds else 0.02
        
        self.position_table.set_data(position_stats, avg_big_blind)
        self._update_hands_tree(position_stats)

    def _update_hands_tree(self, position_stats):
        """更新手牌表格"""
        self.hands_tree.clear()
        
        for pos_name in ["BTN", "SB", "BB", "UTG", "MP", "CO"]:
            if pos_name not in position_stats:
                continue
            
            stats = position_stats[pos_name]
            if stats["total_hands"] == 0:
                continue
            
            total_bb = stats.get("total_bb", 0.0)
            bb_per_100 = (total_bb / stats["total_hands"] * 100) if stats["total_hands"] > 0 else 0.0
            won_rake = stats.get("won_rake", 0.0)
            
            pos_item = QTreeWidgetItem(self.hands_tree)
            pos_item.setText(0, pos_name)
            pos_item.setText(1, f"{stats['total_hands']}")
            pos_item.setText(2, f"${won_rake:.2f}")
            pos_item.setText(3, f"${stats['net_profit']:.2f}")
            pos_item.setText(4, f"{bb_per_100:.2f}")
            
            pos_item.setForeground(2, QBrush(QColor("#ff9800")))
            
            if stats['net_profit'] > 0:
                pos_item.setForeground(3, QBrush(QColor(PROFIT_GREEN)))
            elif stats['net_profit'] < 0:
                pos_item.setForeground(3, QBrush(QColor(PROFIT_RED)))
            
            if bb_per_100 > 0:
                pos_item.setForeground(4, QBrush(QColor(PROFIT_GREEN)))
            elif bb_per_100 < 0:
                pos_item.setForeground(4, QBrush(QColor(PROFIT_RED)))
        
        self.hands_tree.setColumnWidth(0, 80)
        self.hands_tree.setColumnWidth(1, 80)
        self.hands_tree.setColumnWidth(2, 100)
        self.hands_tree.setColumnWidth(3, 100)
        self.hands_tree.setColumnWidth(4, 80)
