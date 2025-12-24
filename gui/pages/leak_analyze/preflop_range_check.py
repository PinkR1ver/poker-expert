"""
Preflop Range Check - 检查用户 preflop 行动是否符合 GTO
按 Position + Card 组合分组显示
"""
import os
import json
import sqlite3
from collections import defaultdict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QProgressBar, QScrollArea, QSplitter,
    QGridLayout, QSizePolicy, QButtonGroup, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QCursor


# 169 种起手牌矩阵
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

# 最小样本量阈值
MIN_SAMPLE_SIZE = 5  # 少于这个数量显示 Warning


class AnalyzeWorker(QThread):
    """后台分析线程"""
    progress = Signal(int, int)
    result = Signal(dict)  # 分析结果: {position: {hand: {stats}}}
    error = Signal(str)
    
    def __init__(self, db_path, gto_base_path, stack_depth):
        super().__init__()
        self.db_path = db_path
        self.gto_base_path = gto_base_path
        self.stack_depth = stack_depth
    
    def run(self):
        try:
            results = self._analyze_hands()
            self.result.emit(results)
        except Exception as e:
            import traceback
            self.error.emit(f"{str(e)}\n{traceback.format_exc()}")
    
    def _analyze_hands(self):
        """分析所有手牌，按 Position + Card 分组"""
        # 结果结构: {position: {hand: {"total": n, "correct": n, "incorrect": n, "hands": [...]}}}
        results = {pos: defaultdict(lambda: {"total": 0, "correct": 0, "incorrect": 0, "profit": 0.0, "hands": []}) 
                   for pos in POSITIONS}
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT h.hand_id, h.hero_hole_cards, h.blinds, h.profit, r.payload
            FROM hands h
            LEFT JOIN hand_replay r ON h.hand_id = r.hand_id
            WHERE h.hero_hole_cards IS NOT NULL 
            AND h.hero_hole_cards != ''
            ORDER BY h.date_time DESC
        """)
        hands = cursor.fetchall()
        
        total = len(hands)
        for i, hand in enumerate(hands):
            if i % 50 == 0:
                self.progress.emit(i, total)
            
            hand_id, hero_cards, blinds, profit, payload_str = hand
            if not payload_str:
                continue
            
            try:
                payload = json.loads(payload_str)
            except:
                continue
            
            analysis = self._analyze_single_hand(hand_id, hero_cards, blinds, profit, payload)
            if analysis:
                pos = analysis["position"]
                normalized = analysis["normalized_cards"]
                
                if pos in results and normalized:
                    stats = results[pos][normalized]
                    stats["total"] += 1
                    stats["profit"] += profit
                    if analysis["is_correct"]:
                        stats["correct"] += 1
                    else:
                        stats["incorrect"] += 1
                    stats["hands"].append(analysis)
        
        conn.close()
        self.progress.emit(total, total)
        
        # 转换为普通 dict
        return {pos: dict(hands) for pos, hands in results.items()}
    
    def _analyze_single_hand(self, hand_id, hero_cards, blinds, profit, payload):
        """分析单手牌"""
        hero_name = payload.get("hero_name", "Hero")
        hero_seat = payload.get("hero_seat", 0)
        button_seat = payload.get("button_seat", 0)
        actions = payload.get("actions", [])
        players = payload.get("players", [])
        
        hero_position = self._get_position(hero_seat, button_seat, len(players))
        if not hero_position:
            return None
        
        preflop_actions = [a for a in actions if a.get("street") == "Preflop"]
        action_sequence, hero_action = self._build_action_sequence(preflop_actions, hero_name, button_seat, players)
        
        if not hero_action:
            return None
        
        normalized_cards = self._normalize_hand(hero_cards)
        if not normalized_cards:
            return None
        
        gto_result = self._check_gto_detailed(action_sequence, hero_position, hero_action, normalized_cards)
        gto_freq = gto_result.get("freq")
        is_correct = gto_freq is not None and gto_freq > 0.01
        
        return {
            "hand_id": hand_id,
            "cards": hero_cards,
            "normalized_cards": normalized_cards,
            "position": hero_position,
            "hero_action": hero_action,
            "action_sequence": action_sequence,
            "gto_freq": gto_freq,
            "gto_action_type": gto_result.get("action_type"),
            "is_correct": is_correct,
            "profit": profit,
            # 新增详细信息
            "vs_position": gto_result.get("vs_position"),  # 对手位置 (e.g. "UTG")
            "scenario": gto_result.get("scenario"),  # 场景描述 (e.g. "vs UTG open 2bb")
            "gto_suggested": gto_result.get("suggested_actions"),  # GTO 建议 (e.g. ["fold 85%", "3bet 15%"])
        }
    
    def _get_position(self, hero_seat, button_seat, num_players):
        """计算 Hero 位置"""
        if num_players != 6:
            return None
        relative = (hero_seat - button_seat) % 6
        position_map = {0: "BTN", 1: "SB", 2: "BB", 3: "UTG", 4: "HJ", 5: "CO"}
        return position_map.get(relative)
    
    def _build_action_sequence(self, preflop_actions, hero_name, button_seat, players):
        """构建行动序列"""
        sequence = []
        hero_action = None
        
        seat_to_position = {}
        for p in players:
            seat = p.get("seat", 0)
            pos = self._get_position(seat, button_seat, len(players))
            if pos:
                seat_to_position[p.get("name")] = pos
        
        for action in preflop_actions:
            player = action.get("player", "")
            action_type = action.get("action_type", "")
            is_all_in = action.get("is_all_in", False)
            
            position = seat_to_position.get(player)
            if not position:
                continue
            
            if action_type in ["posts_sb", "posts_bb", "posts"]:
                continue
            
            abstract_action = None
            if action_type == "raises" or action_type == "bets":
                if is_all_in:
                    abstract_action = "allin"
                else:
                    abstract_action = "raise"
            elif action_type == "calls":
                abstract_action = "call"
            elif action_type == "folds":
                abstract_action = "fold"
            elif action_type == "checks":
                abstract_action = "check"
            
            if abstract_action:
                sequence.append((position, abstract_action))
                if player == hero_name:
                    hero_action = abstract_action
        
        return sequence, hero_action
    
    def _normalize_hand(self, cards):
        """标准化手牌格式"""
        if not cards or len(cards) < 4:
            return None
        
        parts = cards.replace(",", " ").split()
        if len(parts) != 2:
            return None
        
        c1, c2 = parts[0], parts[1]
        rank1, suit1 = c1[:-1], c1[-1]
        rank2, suit2 = c2[:-1], c2[-1]
        
        rank_order = "AKQJT98765432"
        if rank_order.index(rank1) > rank_order.index(rank2):
            rank1, rank2 = rank2, rank1
            suit1, suit2 = suit2, suit1
        
        if rank1 == rank2:
            return f"{rank1}{rank2}"
        elif suit1 == suit2:
            return f"{rank1}{rank2}s"
        else:
            return f"{rank1}{rank2}o"
    
    def _check_gto(self, action_sequence, hero_position, hero_action, normalized_cards):
        """检查 GTO range (兼容旧接口)"""
        result = self._check_gto_detailed(action_sequence, hero_position, hero_action, normalized_cards)
        return result.get("freq"), result.get("action_type")
    
    def _check_gto_detailed(self, action_sequence, hero_position, hero_action, normalized_cards):
        """检查 GTO range，返回详细信息"""
        stack_map = {
            "50bb": "cash6m_50bb_nl50_gto_gto",
            "100bb": "cash6m_100bb_nl50_gto_gto",
            "200bb": "cash6m_200bb_nl50_gto_gto",
        }
        folder = stack_map.get(self.stack_depth, stack_map["100bb"])
        base_path = os.path.join(self.gto_base_path, folder, "ranges")
        
        if not os.path.exists(base_path):
            return {"freq": None, "action_type": None}
        
        hero_action_index = None
        for i, (pos, act) in enumerate(action_sequence):
            if pos == hero_position:
                hero_action_index = i
                break
        
        if hero_action_index is None:
            return {"freq": None, "action_type": None}
        
        actions_before_hero = action_sequence[:hero_action_index]
        
        if hero_action == "raise" and not any(act == "raise" for _, act in actions_before_hero):
            return self._check_open_range_detailed(base_path, hero_position, normalized_cards)
        
        if len(actions_before_hero) > 0:
            opener = None
            for pos, act in actions_before_hero:
                if act == "raise":
                    opener = pos
                    break
            
            if opener:
                return self._check_vs_open_detailed(base_path, opener, hero_position, hero_action, normalized_cards)
        
        return {"freq": None, "action_type": None}
    
    def _check_open_range_detailed(self, base_path, position, hand):
        """检查 open raise range，返回详细信息"""
        pos_path = os.path.join(base_path, position)
        if not os.path.exists(pos_path):
            return {"freq": None, "action_type": None}
        
        open_sizes = [d for d in os.listdir(pos_path) if os.path.isdir(os.path.join(pos_path, d)) and not d.startswith('.')]
        if not open_sizes:
            return {"freq": None, "action_type": None}
        
        open_size = sorted(open_sizes, key=lambda x: self._sort_action_key(x))[0]
        range_file = self._find_range_file(os.path.join(pos_path, open_size), position)
        if not range_file:
            return {"freq": None, "action_type": None}
        
        range_data = self._parse_range_file(range_file)
        freq = range_data.get(hand, 0)
        
        # 计算 GTO 建议
        suggested = []
        if freq > 0.01:
            suggested.append(f"Open {open_size} ({freq*100:.0f}%)")
        fold_freq = 1.0 - freq
        if fold_freq > 0.01:
            suggested.append(f"Fold ({fold_freq*100:.0f}%)")
        
        return {
            "freq": freq,
            "action_type": f"open {open_size}",
            "vs_position": None,  # Open 没有对手
            "scenario": f"{position} Open",
            "suggested_actions": suggested
        }
    
    def _check_vs_open_detailed(self, base_path, opener, hero_position, hero_action, hand):
        """检查面对 open raise 的行动，返回详细信息"""
        opener_path = os.path.join(base_path, opener)
        if not os.path.exists(opener_path):
            return {"freq": None, "action_type": None}
        
        open_sizes = [d for d in os.listdir(opener_path) if os.path.isdir(os.path.join(opener_path, d)) and not d.startswith('.')]
        if not open_sizes:
            return {"freq": None, "action_type": None}
        
        open_size = sorted(open_sizes, key=lambda x: self._sort_action_key(x))[0]
        hero_path = os.path.join(opener_path, open_size, hero_position)
        
        if not os.path.exists(hero_path):
            return {"freq": None, "action_type": None}
        
        available_actions = [d for d in os.listdir(hero_path) if os.path.isdir(os.path.join(hero_path, d)) and not d.startswith('.')]
        
        # 收集所有可能行动的频率用于显示 GTO 建议
        action_freqs = {}
        for act in available_actions:
            action_path = os.path.join(hero_path, act)
            range_file = self._find_range_file(action_path, hero_position)
            if range_file:
                range_data = self._parse_range_file(range_file)
                action_freqs[act] = range_data.get(hand, 0)
        
        # 计算 fold 频率
        total_freq = sum(action_freqs.values())
        fold_freq = max(0, 1.0 - total_freq)
        if fold_freq > 0.01:
            action_freqs["Fold"] = fold_freq
        
        # 构建 GTO 建议列表
        suggested = []
        for act, freq in sorted(action_freqs.items(), key=lambda x: -x[1]):
            if freq > 0.01:
                suggested.append(f"{act} ({freq*100:.0f}%)")
        
        # 找到 hero 行动对应的 GTO 频率
        gto_action = None
        hero_freq = None
        
        for act in available_actions:
            act_lower = act.lower()
            if hero_action == "call" and act_lower == "call":
                gto_action = act
                hero_freq = action_freqs.get(act, 0)
                break
            elif hero_action == "raise" and act_lower not in ["call", "fold", "allin"]:
                gto_action = act
                hero_freq = action_freqs.get(act, 0)
                break
            elif hero_action == "allin" and act_lower == "allin":
                gto_action = act
                hero_freq = action_freqs.get(act, 0)
                break
        
        if not gto_action and hero_action == "fold":
            gto_action = "fold"
            hero_freq = fold_freq
        
        scenario = f"vs {opener} open {open_size}"
        
        return {
            "freq": hero_freq,
            "action_type": gto_action,
            "vs_position": opener,
            "scenario": scenario,
            "suggested_actions": suggested
        }
    
    def _find_range_file(self, base_path, position):
        """递归查找 range 文件"""
        target_file = f"{position}.txt"
        direct_path = os.path.join(base_path, target_file)
        if os.path.exists(direct_path):
            return direct_path
        
        try:
            items = os.listdir(base_path)
            def sort_key(item):
                if item == "call":
                    return (0, item)
                if item == "fold":
                    return (1, item)
                return (2, item)
            items = sorted(items, key=sort_key)
            
            for item in items:
                item_path = os.path.join(base_path, item)
                if os.path.isdir(item_path) and not item.startswith('.'):
                    result = self._find_range_file(item_path, position)
                    if result:
                        return result
        except:
            pass
        return None
    
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
        except:
            pass
        return range_data
    
    def _sort_action_key(self, action):
        import re
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


class LeakMatrixWidget(QWidget):
    """Leak 分析矩阵组件 - 显示每手牌的正确率"""
    
    hand_clicked = Signal(str, dict)  # hand, stats
    
    def __init__(self):
        super().__init__()
        self.hand_stats = {}  # {hand: {"total": n, "correct": n, ...}}
        self.setMinimumSize(400, 400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.hovered_cell = None
        self.setMouseTracking(True)
    
    def set_data(self, hand_stats):
        """设置数据"""
        self.hand_stats = hand_stats
        self.update()
    
    def clear(self):
        self.hand_stats = {}
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
                
                stats = self.hand_stats.get(hand, {})
                self._draw_cell(painter, x, y, cell_w, cell_h, hand, stats)
        
        painter.end()
    
    def _draw_cell(self, painter, x, y, cell_w, cell_h, hand, stats):
        """绘制单元格"""
        total = stats.get("total", 0)
        correct = stats.get("correct", 0)
        incorrect = stats.get("incorrect", 0)
        
        # 计算颜色
        if total == 0:
            bg_color = QColor("#2a2a2a")  # 无数据
        elif total < MIN_SAMPLE_SIZE:
            # 样本量不足 - 黄色警告
            accuracy = correct / total if total > 0 else 0
            if accuracy >= 0.8:
                bg_color = QColor("#4a4a2a")  # 黄绿
            elif accuracy >= 0.5:
                bg_color = QColor("#5a5a2a")  # 黄色
            else:
                bg_color = QColor("#5a4a2a")  # 黄红
        else:
            # 正常样本量
            accuracy = correct / total
            if accuracy >= 0.9:
                bg_color = QColor("#2a5a2a")  # 深绿 - 很好
            elif accuracy >= 0.7:
                bg_color = QColor("#3a6a3a")  # 绿色 - 良好
            elif accuracy >= 0.5:
                bg_color = QColor("#5a5a3a")  # 黄色 - 一般
            elif accuracy >= 0.3:
                bg_color = QColor("#6a4a3a")  # 橙色 - 差
            else:
                bg_color = QColor("#6a3a3a")  # 红色 - 很差
        
        painter.fillRect(int(x), int(y), int(cell_w), int(cell_h), bg_color)
        
        # 边框
        painter.setPen(QPen(QColor("#1a1a1a"), 1))
        painter.drawRect(int(x), int(y), int(cell_w), int(cell_h))
        
        # 手牌文字
        text_color = QColor("#ffffff") if total > 0 else QColor("#666666")
        painter.setPen(QColor("#000000"))
        painter.drawText(int(x) + 1, int(y) + 1, int(cell_w), int(cell_h * 0.6), Qt.AlignCenter, hand)
        painter.setPen(text_color)
        painter.drawText(int(x), int(y), int(cell_w), int(cell_h * 0.6), Qt.AlignCenter, hand)
        
        # 统计文字
        if total > 0:
            accuracy = correct / total * 100
            stat_font = QFont("Arial", max(6, int(min(cell_w, cell_h) / 5)))
            painter.setFont(stat_font)
            
            # 样本量不足时显示警告符号
            if total < MIN_SAMPLE_SIZE:
                stat_text = f"⚠{total}"
                painter.setPen(QColor("#ffcc00"))
            else:
                stat_text = f"{accuracy:.0f}%"
                painter.setPen(QColor("#cccccc"))
            
            painter.drawText(int(x), int(y + cell_h * 0.5), int(cell_w), int(cell_h * 0.4),
                           Qt.AlignCenter, stat_text)
    
    def mouseMoveEvent(self, event):
        cell_w = self.width() / 13
        cell_h = self.height() / 13
        col = int(event.position().x() / cell_w)
        row = int(event.position().y() / cell_h)
        
        if 0 <= row < 13 and 0 <= col < 13:
            self.hovered_cell = (row, col)
            hand = HAND_MATRIX[row][col]
            stats = self.hand_stats.get(hand, {})
            
            total = stats.get("total", 0)
            correct = stats.get("correct", 0)
            profit = stats.get("profit", 0)
            
            if total > 0:
                accuracy = correct / total * 100
                tooltip = f"{hand}\n"
                tooltip += f"Hands: {total}"
                if total < MIN_SAMPLE_SIZE:
                    tooltip += " ⚠️ 样本量不足"
                tooltip += f"\nCorrect: {correct} ({accuracy:.1f}%)"
                tooltip += f"\nProfit: ${profit:.2f}"
            else:
                tooltip = f"{hand}\n无数据"
            
            self.setToolTip(tooltip)
        else:
            self.hovered_cell = None
            self.setToolTip("")
    
    def mousePressEvent(self, event):
        cell_w = self.width() / 13
        cell_h = self.height() / 13
        col = int(event.position().x() / cell_w)
        row = int(event.position().y() / cell_h)
        
        if 0 <= row < 13 and 0 <= col < 13:
            hand = HAND_MATRIX[row][col]
            stats = self.hand_stats.get(hand, {})
            self.hand_clicked.emit(hand, stats)


class PreflopRangeCheck(QWidget):
    """Preflop Range Check 功能界面"""
    
    # 发送 replay 请求信号
    replay_requested = Signal(str)  # hand_id
    
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.results = {}  # {position: {hand: stats}}
        self.current_position = "UTG"
        self.worker = None
        self.current_hand_data = []  # 当前选中手牌的所有手牌数据
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 左侧控制面板
        left_panel = QFrame()
        left_panel.setFixedWidth(280)
        left_panel.setStyleSheet("background-color: #252525; border-right: 1px solid #3a3a3a;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)
        
        # Title
        title = QLabel("Preflop Range Check")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        left_layout.addWidget(title)
        
        desc = QLabel("检查 Preflop 行动是否符合 GTO")
        desc.setStyleSheet("color: #888888; font-size: 11px;")
        desc.setWordWrap(True)
        left_layout.addWidget(desc)
        
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
        self.stack_combo.setCurrentText("100bb")
        self.stack_combo.setStyleSheet("""
            QComboBox {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
        """)
        stack_layout.addWidget(self.stack_combo)
        left_layout.addWidget(stack_frame)
        
        # Analyze Button
        self.analyze_btn = QPushButton("🔍 Analyze All Hands")
        self.analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #5aafff; }
            QPushButton:disabled { background-color: #3a3a3a; color: #666666; }
        """)
        self.analyze_btn.clicked.connect(self.start_analyze)
        left_layout.addWidget(self.analyze_btn)
        
        # Progress
        self.progress_frame = QFrame()
        self.progress_frame.setVisible(False)
        progress_layout = QVBoxLayout(self.progress_frame)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        
        self.progress_label = QLabel("Analyzing...")
        self.progress_label.setStyleSheet("color: #888888; font-size: 11px;")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #2a2a2a;
                border: none;
                border-radius: 4px;
                height: 6px;
            }
            QProgressBar::chunk {
                background-color: #4a9eff;
                border-radius: 4px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        left_layout.addWidget(self.progress_frame)
        
        # Position 选择
        pos_frame = QFrame()
        pos_layout = QVBoxLayout(pos_frame)
        pos_layout.setContentsMargins(0, 0, 0, 0)
        pos_layout.setSpacing(4)
        
        pos_label = QLabel("Position")
        pos_label.setStyleSheet("color: #888888; font-size: 11px;")
        pos_layout.addWidget(pos_label)
        
        pos_btn_layout = QGridLayout()
        pos_btn_layout.setSpacing(4)
        self.position_buttons = {}
        
        for i, pos in enumerate(POSITIONS):
            btn = QPushButton(pos)
            btn.setCheckable(True)
            btn.setChecked(pos == self.current_position)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    color: white;
                    border: none;
                    padding: 8px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #4a4a4a; }
                QPushButton:checked { background-color: #4a9eff; }
            """)
            btn.clicked.connect(lambda checked, p=pos: self._on_position_selected(p))
            pos_btn_layout.addWidget(btn, i // 3, i % 3)
            self.position_buttons[pos] = btn
        
        pos_layout.addLayout(pos_btn_layout)
        left_layout.addWidget(pos_frame)
        
        # Summary 统计
        self.summary_frame = QFrame()
        self.summary_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 8px;")
        summary_layout = QVBoxLayout(self.summary_frame)
        summary_layout.setContentsMargins(12, 12, 12, 12)
        
        self.summary_title = QLabel("Position Summary")
        self.summary_title.setStyleSheet("color: white; font-weight: bold;")
        summary_layout.addWidget(self.summary_title)
        
        self.summary_label = QLabel("点击 Analyze 开始分析")
        self.summary_label.setStyleSheet("color: #888888; font-size: 12px;")
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)
        
        left_layout.addWidget(self.summary_frame)
        
        # Legend
        legend_frame = QFrame()
        legend_layout = QVBoxLayout(legend_frame)
        legend_layout.setContentsMargins(0, 0, 0, 0)
        legend_layout.setSpacing(4)
        
        legend_title = QLabel("Legend")
        legend_title.setStyleSheet("color: #888888; font-size: 11px;")
        legend_layout.addWidget(legend_title)
        
        legends = [
            ("#2a5a2a", "≥90% 正确"),
            ("#3a6a3a", "70-90% 正确"),
            ("#5a5a3a", "50-70% 正确"),
            ("#6a4a3a", "30-50% 正确"),
            ("#6a3a3a", "<30% 正确"),
            ("#5a5a2a", "⚠ 样本不足"),
        ]
        
        for color, text in legends:
            item = QWidget()
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(6)
            
            color_box = QFrame()
            color_box.setFixedSize(12, 12)
            color_box.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
            item_layout.addWidget(color_box)
            
            label = QLabel(text)
            label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
            item_layout.addWidget(label)
            item_layout.addStretch()
            
            legend_layout.addWidget(item)
        
        left_layout.addWidget(legend_frame)
        left_layout.addStretch()
        
        layout.addWidget(left_panel)
        
        # 右侧矩阵
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(24, 24, 24, 24)
        
        self.matrix_title = QLabel("UTG - Leak Analysis")
        self.matrix_title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        right_layout.addWidget(self.matrix_title)
        
        self.leak_matrix = LeakMatrixWidget()
        self.leak_matrix.hand_clicked.connect(self._on_hand_clicked)
        right_layout.addWidget(self.leak_matrix, 1)
        
        # 手牌详情（可滚动）
        self.detail_frame = QFrame()
        self.detail_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 8px;")
        self.detail_frame.setFixedHeight(220)
        detail_outer_layout = QVBoxLayout(self.detail_frame)
        detail_outer_layout.setContentsMargins(12, 12, 12, 12)
        detail_outer_layout.setSpacing(8)
        
        self.detail_title = QLabel("点击格子查看详情")
        self.detail_title.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        detail_outer_layout.addWidget(self.detail_title)
        
        # 统计信息
        self.detail_stats = QLabel("")
        self.detail_stats.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        self.detail_stats.setWordWrap(True)
        detail_outer_layout.addWidget(self.detail_stats)
        
        # 手牌列表标题
        hands_header = QHBoxLayout()
        hands_label = QLabel("手牌列表 (点击 Replay)")
        hands_label.setStyleSheet("color: #888888; font-size: 11px;")
        hands_header.addWidget(hands_label)
        
        self.filter_label = QLabel("全部")
        self.filter_label.setStyleSheet("color: #4a9eff; font-size: 11px;")
        hands_header.addWidget(self.filter_label)
        hands_header.addStretch()
        detail_outer_layout.addLayout(hands_header)
        
        # 手牌列表
        self.hand_list = QListWidget()
        self.hand_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: none;
                border-radius: 4px;
            }
            QListWidget::item {
                color: white;
                padding: 6px 8px;
                border-bottom: 1px solid #2a2a2a;
            }
            QListWidget::item:hover {
                background-color: #3a3a3a;
            }
            QListWidget::item:selected {
                background-color: #4a9eff;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background-color: #4a4a4a;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        self.hand_list.itemDoubleClicked.connect(self._on_hand_list_clicked)
        self.hand_list.setCursor(QCursor(Qt.PointingHandCursor))
        detail_outer_layout.addWidget(self.hand_list, 1)
        
        right_layout.addWidget(self.detail_frame)
        
        layout.addWidget(right_panel, 1)
    
    def start_analyze(self):
        """开始分析"""
        if self.worker and self.worker.isRunning():
            return
        
        self.analyze_btn.setEnabled(False)
        self.progress_frame.setVisible(True)
        self.progress_bar.setValue(0)
        self.leak_matrix.clear()
        
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        gto_base_path = os.path.join(project_root, "assets", "range")
        
        db_path = "poker_tracker.db"
        self.worker = AnalyzeWorker(db_path, gto_base_path, self.stack_combo.currentText())
        self.worker.progress.connect(self.on_progress)
        self.worker.result.connect(self.on_result)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
    
    def on_progress(self, current, total):
        self.progress_label.setText(f"Analyzing... {current}/{total}")
        if total > 0:
            self.progress_bar.setValue(int(current / total * 100))
    
    def on_result(self, results):
        """显示结果"""
        self.results = results
        self._update_position_view()
    
    def on_error(self, error_msg):
        self.summary_label.setText(f"分析失败: {error_msg[:100]}...")
        self.summary_label.setStyleSheet("color: #f44336; font-size: 12px;")
    
    def on_finished(self):
        self.analyze_btn.setEnabled(True)
        self.progress_frame.setVisible(False)
    
    def _on_position_selected(self, position):
        """选择位置"""
        self.current_position = position
        for pos, btn in self.position_buttons.items():
            btn.setChecked(pos == position)
        self._update_position_view()
    
    def _update_position_view(self):
        """更新当前位置的视图"""
        pos = self.current_position
        self.matrix_title.setText(f"{pos} - Leak Analysis")
        
        if pos not in self.results:
            self.leak_matrix.clear()
            self.summary_label.setText("无数据")
            return
        
        hand_stats = self.results[pos]
        self.leak_matrix.set_data(hand_stats)
        
        # 计算统计
        total_hands = sum(s.get("total", 0) for s in hand_stats.values())
        total_correct = sum(s.get("correct", 0) for s in hand_stats.values())
        total_profit = sum(s.get("profit", 0) for s in hand_stats.values())
        
        accuracy = (total_correct / total_hands * 100) if total_hands > 0 else 0
        
        # 找出最大 leak
        leaks = []
        for hand, stats in hand_stats.items():
            total = stats.get("total", 0)
            if total >= MIN_SAMPLE_SIZE:
                correct = stats.get("correct", 0)
                acc = correct / total
                if acc < 0.5:  # 正确率 < 50%
                    leaks.append((hand, total, acc, stats.get("profit", 0)))
        
        leaks.sort(key=lambda x: x[2])  # 按正确率排序
        
        summary_text = f"总手数: {total_hands}\n"
        summary_text += f"正确率: {accuracy:.1f}%\n"
        summary_text += f"盈亏: ${total_profit:.2f}\n"
        
        if leaks:
            summary_text += f"\n🚨 Top Leaks:\n"
            for hand, cnt, acc, pft in leaks[:3]:
                summary_text += f"  {hand}: {acc*100:.0f}% ({cnt}手, ${pft:.2f})\n"
        
        self.summary_label.setText(summary_text)
        self.summary_label.setStyleSheet("color: white; font-size: 12px;")
    
    def _on_hand_clicked(self, hand, stats):
        """点击手牌显示详情"""
        total = stats.get("total", 0)
        self.hand_list.clear()
        self.current_hand_data = []
        
        if total == 0:
            self.detail_title.setText(f"{hand} - 无数据")
            self.detail_stats.setText("")
            self.filter_label.setText("无数据")
            return
        
        correct = stats.get("correct", 0)
        incorrect = stats.get("incorrect", 0)
        profit = stats.get("profit", 0)
        accuracy = correct / total * 100
        
        self.detail_title.setText(f"{hand} @ {self.current_position}")
        
        # 统计信息
        stats_text = f"总手数: {total}"
        if total < MIN_SAMPLE_SIZE:
            stats_text += " ⚠️ 样本量不足"
        stats_text += f"  |  正确: {correct} ({accuracy:.1f}%)  |  错误: {incorrect}"
        stats_text += f"  |  盈亏: ${profit:.2f}"
        self.detail_stats.setText(stats_text)
        
        # 获取手牌数据
        hands_data = stats.get("hands", [])
        self.current_hand_data = hands_data
        
        # 显示所有手牌（错误的优先）
        incorrect_hands = [h for h in hands_data if not h.get("is_correct")]
        correct_hands = [h for h in hands_data if h.get("is_correct")]
        
        self.filter_label.setText(f"全部 {len(hands_data)} 手 (❌{len(incorrect_hands)} ✅{len(correct_hands)})")
        
        # 先显示错误的
        for h in incorrect_hands:
            self._add_hand_to_list(h, is_correct=False)
        
        # 再显示正确的
        for h in correct_hands:
            self._add_hand_to_list(h, is_correct=True)
    
    def _add_hand_to_list(self, hand_data, is_correct):
        """添加手牌到列表"""
        cards = hand_data.get("cards", "?")
        hero_action = hand_data.get("hero_action", "?")
        scenario = hand_data.get("scenario", "")
        vs_position = hand_data.get("vs_position", "")
        gto_suggested = hand_data.get("gto_suggested", [])
        profit = hand_data.get("profit", 0)
        
        # 构建显示文本
        icon = "✅" if is_correct else "❌"
        
        # 场景描述
        if scenario:
            scenario_text = scenario
        elif vs_position:
            scenario_text = f"vs {vs_position}"
        else:
            scenario_text = "Open"
        
        # GTO 建议
        if gto_suggested:
            gto_text = " / ".join(gto_suggested[:2])  # 最多显示2个
        else:
            gto_text = "N/A"
        
        # 盈亏颜色提示
        profit_text = f"${profit:.2f}" if profit >= 0 else f"-${abs(profit):.2f}"
        
        display_text = f"{icon} {cards}  |  你: {hero_action}  |  {scenario_text}  |  GTO: {gto_text}  |  {profit_text}"
        
        item = QListWidgetItem(display_text)
        item.setData(Qt.UserRole, hand_data.get("hand_id"))
        
        # 根据正确与否设置颜色
        if is_correct:
            item.setForeground(QColor("#4CAF50"))  # 绿色
        else:
            item.setForeground(QColor("#f44336"))  # 红色
        
        self.hand_list.addItem(item)
    
    def _on_hand_list_clicked(self, item):
        """双击手牌打开 replay"""
        hand_id = item.data(Qt.UserRole)
        if hand_id:
            self.replay_requested.emit(hand_id)
    
    def refresh_data(self):
        pass
