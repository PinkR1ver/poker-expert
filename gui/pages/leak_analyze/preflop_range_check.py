"""
Preflop Range Check - 检查用户 preflop 行动是否符合 GTO
"""
import os
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QProgressBar, QScrollArea, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QBrush


# 位置映射：6-max 座位号到位置名称
# 按钮位为基准：BTN -> SB -> BB -> UTG -> HJ -> CO -> BTN
POSITIONS_6MAX = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]


class AnalyzeWorker(QThread):
    """后台分析线程"""
    progress = Signal(int, int)  # current, total
    result = Signal(list)  # 分析结果列表
    error = Signal(str)
    
    def __init__(self, db_path, gto_base_path, stack_depth):
        super().__init__()
        self.db_path = db_path  # 存储数据库路径，而不是连接
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
        """分析所有手牌的 preflop 行动"""
        import sqlite3
        
        results = []
        
        # 在工作线程中创建独立的数据库连接
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
            if i % 10 == 0:
                self.progress.emit(i, total)
            
            hand_id, hero_cards, blinds, profit, payload_str = hand
            if not payload_str:
                continue
            
            try:
                payload = json.loads(payload_str)
            except:
                continue
            
            # 分析这手牌
            analysis = self._analyze_single_hand(hand_id, hero_cards, blinds, profit, payload)
            if analysis:
                results.append(analysis)
        
        # 关闭工作线程的数据库连接
        conn.close()
        
        self.progress.emit(total, total)
        return results
    
    def _analyze_single_hand(self, hand_id, hero_cards, blinds, profit, payload):
        """分析单手牌"""
        hero_name = payload.get("hero_name", "Hero")
        hero_seat = payload.get("hero_seat", 0)
        button_seat = payload.get("button_seat", 0)
        actions = payload.get("actions", [])
        players = payload.get("players", [])
        
        # 计算 Hero 位置
        hero_position = self._get_position(hero_seat, button_seat, len(players))
        if not hero_position:
            return None
        
        # 获取 preflop 行动
        preflop_actions = [a for a in actions if a.get("street") == "Preflop"]
        
        # 构建行动序列并获取 Hero 的行动
        action_sequence, hero_action = self._build_action_sequence(preflop_actions, hero_name, button_seat, players)
        
        if not hero_action:
            return None
        
        # 标准化手牌格式
        normalized_cards = self._normalize_hand(hero_cards)
        if not normalized_cards:
            return None
        
        # 查找 GTO 数据并比对
        gto_freq, gto_action_type = self._check_gto(action_sequence, hero_position, hero_action, normalized_cards)
        
        # 判断是否符合 GTO
        is_correct = gto_freq is not None and gto_freq > 0.01  # 频率 > 1% 算正确
        
        return {
            "hand_id": hand_id,
            "cards": hero_cards,
            "normalized_cards": normalized_cards,
            "position": hero_position,
            "hero_action": hero_action,
            "action_sequence": action_sequence,
            "gto_freq": gto_freq,
            "gto_action_type": gto_action_type,
            "is_correct": is_correct,
            "profit": profit,
        }
    
    def _get_position(self, hero_seat, button_seat, num_players):
        """计算 Hero 位置"""
        if num_players != 6:
            return None  # 暂时只支持 6-max
        
        # 计算相对于 BTN 的位置
        relative = (hero_seat - button_seat) % 6
        
        # 6-max 位置映射：BTN=0, SB=1, BB=2, UTG=3, HJ=4, CO=5
        position_map = {0: "BTN", 1: "SB", 2: "BB", 3: "UTG", 4: "HJ", 5: "CO"}
        return position_map.get(relative)
    
    def _build_action_sequence(self, preflop_actions, hero_name, button_seat, players):
        """构建行动序列，返回 (action_sequence, hero_action)
        
        action_sequence: [(position, action_type), ...]
        hero_action: Hero 的行动类型 (raise/call/fold/allin)
        """
        sequence = []
        hero_action = None
        
        # 建立座位号到位置的映射
        seat_to_position = {}
        for p in players:
            seat = p.get("seat", 0)
            pos = self._get_position(seat, button_seat, len(players))
            if pos:
                seat_to_position[p.get("name")] = pos
        
        # 跟踪已经 raise 过的次数
        raise_count = 0
        
        for action in preflop_actions:
            player = action.get("player", "")
            action_type = action.get("action_type", "")
            is_all_in = action.get("is_all_in", False)
            
            position = seat_to_position.get(player)
            if not position:
                continue
            
            # 跳过盲注投入
            if action_type in ["posts_sb", "posts_bb", "posts"]:
                continue
            
            # 转换行动类型
            abstract_action = None
            if action_type == "raises" or action_type == "bets":
                raise_count += 1
                if is_all_in:
                    abstract_action = "allin"
                else:
                    # 简化：不区分具体尺寸，只记录 raise
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
        """标准化手牌格式 (e.g., "Ah Kd" -> "AKo")"""
        if not cards or len(cards) < 4:
            return None
        
        # 分割两张牌
        parts = cards.replace(",", " ").split()
        if len(parts) != 2:
            return None
        
        c1, c2 = parts[0], parts[1]
        
        # 提取点数和花色
        rank1, suit1 = c1[:-1], c1[-1]
        rank2, suit2 = c2[:-1], c2[-1]
        
        # 标准化点数
        rank_order = "AKQJT98765432"
        
        # 确保大牌在前
        if rank_order.index(rank1) > rank_order.index(rank2):
            rank1, rank2 = rank2, rank1
            suit1, suit2 = suit2, suit1
        
        # 判断同花/非同花/对子
        if rank1 == rank2:
            return f"{rank1}{rank2}"  # 对子
        elif suit1 == suit2:
            return f"{rank1}{rank2}s"  # 同花
        else:
            return f"{rank1}{rank2}o"  # 非同花
    
    def _check_gto(self, action_sequence, hero_position, hero_action, normalized_cards):
        """检查 GTO range"""
        # 根据 stack_depth 选择 GTO 数据目录
        stack_map = {
            "50bb": "cash6m_50bb_nl50_gto_gto",
            "100bb": "cash6m_100bb_nl50_gto_gto",
            "200bb": "cash6m_200bb_nl50_gto_gto",
        }
        folder = stack_map.get(self.stack_depth, stack_map["100bb"])
        base_path = os.path.join(self.gto_base_path, folder, "ranges")
        
        if not os.path.exists(base_path):
            return None, None
        
        # 简化场景：分析常见的 preflop 情况
        # 1. Hero 是第一个 raise（open）
        # 2. Hero 面对 open raise
        
        # 找到 Hero 之前的行动
        hero_action_index = None
        for i, (pos, act) in enumerate(action_sequence):
            if pos == hero_position:
                hero_action_index = i
                break
        
        if hero_action_index is None:
            return None, None
        
        actions_before_hero = action_sequence[:hero_action_index]
        
        # 场景 1: Hero Open Raise (没有人在 Hero 之前 raise)
        if hero_action == "raise" and not any(act == "raise" for _, act in actions_before_hero):
            # 查找 hero_position 的 open range
            return self._check_open_range(base_path, hero_position, normalized_cards)
        
        # 场景 2: Hero 面对 open raise
        if len(actions_before_hero) > 0:
            # 找到 opener
            opener = None
            opener_action = None
            for pos, act in actions_before_hero:
                if act == "raise":
                    opener = pos
                    opener_action = act
                    break
            
            if opener:
                # Hero 面对 open raise 的行动
                return self._check_vs_open(base_path, opener, hero_position, hero_action, normalized_cards)
        
        return None, None
    
    def _check_open_range(self, base_path, position, hand):
        """检查 open raise range"""
        # 构建路径: ranges/{position}
        pos_path = os.path.join(base_path, position)
        if not os.path.exists(pos_path):
            return None, None
        
        # 获取可用的 open size
        open_sizes = [d for d in os.listdir(pos_path) if os.path.isdir(os.path.join(pos_path, d)) and not d.startswith('.')]
        if not open_sizes:
            return None, None
        
        # 使用第一个 open size（简化：不区分尺寸）
        open_size = sorted(open_sizes, key=lambda x: self._sort_action_key(x))[0]
        
        # 查找 range 文件
        range_file = self._find_range_file(os.path.join(pos_path, open_size), position)
        if not range_file:
            return None, None
        
        # 解析 range 文件
        range_data = self._parse_range_file(range_file)
        freq = range_data.get(hand, 0)
        
        return freq, f"open {open_size}"
    
    def _check_vs_open(self, base_path, opener, hero_position, hero_action, hand):
        """检查面对 open raise 的行动"""
        # 构建路径: ranges/{opener}/{open_size}/{hero_position}
        opener_path = os.path.join(base_path, opener)
        if not os.path.exists(opener_path):
            return None, None
        
        # 获取 opener 的 open size
        open_sizes = [d for d in os.listdir(opener_path) if os.path.isdir(os.path.join(opener_path, d)) and not d.startswith('.')]
        if not open_sizes:
            return None, None
        
        open_size = sorted(open_sizes, key=lambda x: self._sort_action_key(x))[0]
        hero_path = os.path.join(opener_path, open_size, hero_position)
        
        if not os.path.exists(hero_path):
            return None, None
        
        # 获取 Hero 的可用行动
        available_actions = [d for d in os.listdir(hero_path) if os.path.isdir(os.path.join(hero_path, d)) and not d.startswith('.')]
        
        # 映射 hero_action 到 GTO 行动
        gto_action = None
        for act in available_actions:
            act_lower = act.lower()
            if hero_action == "call" and act_lower == "call":
                gto_action = act
                break
            elif hero_action == "raise" and act_lower not in ["call", "fold", "allin"]:
                gto_action = act  # 任意 raise size
                break
            elif hero_action == "allin" and act_lower == "allin":
                gto_action = act
                break
        
        if not gto_action:
            # 如果没找到对应行动，可能是 fold（GTO 中 fold 是剩余部分）
            if hero_action == "fold":
                # Fold 的频率 = 1 - sum(其他行动)
                total_freq = 0
                for act in available_actions:
                    action_path = os.path.join(hero_path, act)
                    range_file = self._find_range_file(action_path, hero_position)
                    if range_file:
                        range_data = self._parse_range_file(range_file)
                        total_freq += range_data.get(hand, 0)
                
                fold_freq = 1.0 - total_freq
                return max(0, fold_freq), "fold"
            return None, None
        
        # 查找对应行动的 range 文件
        action_path = os.path.join(hero_path, gto_action)
        range_file = self._find_range_file(action_path, hero_position)
        if not range_file:
            return None, None
        
        range_data = self._parse_range_file(range_file)
        freq = range_data.get(hand, 0)
        
        return freq, gto_action
    
    def _find_range_file(self, base_path, position):
        """递归查找最近的 range 文件"""
        target_file = f"{position}.txt"
        
        direct_path = os.path.join(base_path, target_file)
        if os.path.exists(direct_path):
            return direct_path
        
        # 优先搜索 call 子目录
        try:
            items = os.listdir(base_path)
            # 优先 call, fold, 然后其他
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
        except Exception as e:
            print(f"Error parsing range file {path}: {e}")
        return range_data
    
    def _sort_action_key(self, action):
        """排序行动"""
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


class PreflopRangeCheck(QWidget):
    """Preflop Range Check 功能界面"""
    
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.results = []
        self.worker = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Header
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("Preflop Range Check")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Stack Depth 选择
        stack_label = QLabel("Stack Depth:")
        stack_label.setStyleSheet("color: #888888;")
        header_layout.addWidget(stack_label)
        
        self.stack_combo = QComboBox()
        self.stack_combo.addItems(["50bb", "100bb", "200bb"])
        self.stack_combo.setCurrentText("100bb")
        self.stack_combo.setStyleSheet("""
            QComboBox {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
        """)
        header_layout.addWidget(self.stack_combo)
        
        # Analyze Button
        self.analyze_btn = QPushButton("🔍 Analyze")
        self.analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                border: none;
                padding: 8px 24px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #5aafff; }
            QPushButton:disabled { background-color: #3a3a3a; color: #666666; }
        """)
        self.analyze_btn.clicked.connect(self.start_analyze)
        header_layout.addWidget(self.analyze_btn)
        
        layout.addWidget(header)
        
        # Description
        desc = QLabel(
            "分析数据库中的手牌，检查 Preflop 行动是否符合 GTO 策略。\n"
            "注意：分析基于抽象行动（raise/call/fold），不区分具体下注尺度。"
        )
        desc.setStyleSheet("color: #888888; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Progress
        self.progress_frame = QFrame()
        self.progress_frame.setVisible(False)
        progress_layout = QVBoxLayout(self.progress_frame)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        
        self.progress_label = QLabel("Analyzing...")
        self.progress_label.setStyleSheet("color: #888888;")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #2a2a2a;
                border: none;
                border-radius: 4px;
                height: 8px;
            }
            QProgressBar::chunk {
                background-color: #4a9eff;
                border-radius: 4px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addWidget(self.progress_frame)
        
        # Summary
        self.summary_frame = QFrame()
        self.summary_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 8px;")
        summary_layout = QHBoxLayout(self.summary_frame)
        summary_layout.setContentsMargins(16, 12, 16, 12)
        
        self.summary_label = QLabel("点击 Analyze 开始分析")
        self.summary_label.setStyleSheet("color: #888888;")
        summary_layout.addWidget(self.summary_label)
        
        layout.addWidget(self.summary_frame)
        
        # Results Table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(8)
        self.results_table.setHorizontalHeaderLabels([
            "Hand ID", "Cards", "Position", "Action", "GTO Freq", "Status", "Profit", "Action Seq"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: none;
                gridline-color: #2a2a2a;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #3a3a3a;
            }
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #888888;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        self.results_table.setSortingEnabled(True)
        layout.addWidget(self.results_table, 1)
    
    def start_analyze(self):
        """开始分析"""
        if self.worker and self.worker.isRunning():
            return
        
        self.analyze_btn.setEnabled(False)
        self.progress_frame.setVisible(True)
        self.progress_bar.setValue(0)
        self.results_table.setRowCount(0)
        
        # 获取 GTO 数据路径
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        gto_base_path = os.path.join(project_root, "assets", "range")
        
        # 创建工作线程（传递数据库路径，而不是连接对象）
        db_path = "poker_tracker.db"  # 默认数据库路径
        self.worker = AnalyzeWorker(db_path, gto_base_path, self.stack_combo.currentText())
        self.worker.progress.connect(self.on_progress)
        self.worker.result.connect(self.on_result)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
    
    def on_progress(self, current, total):
        """更新进度"""
        self.progress_label.setText(f"Analyzing... {current}/{total}")
        if total > 0:
            self.progress_bar.setValue(int(current / total * 100))
    
    def on_result(self, results):
        """显示结果"""
        self.results = results
        
        # 统计
        total = len(results)
        correct = sum(1 for r in results if r["is_correct"])
        incorrect = total - correct
        correct_pct = (correct / total * 100) if total > 0 else 0
        
        # 计算 EV 损失
        incorrect_hands = [r for r in results if not r["is_correct"]]
        incorrect_profit = sum(r["profit"] for r in incorrect_hands)
        
        self.summary_label.setText(
            f"分析完成: {total} 手 | "
            f"✅ 正确: {correct} ({correct_pct:.1f}%) | "
            f"❌ 错误: {incorrect} ({100-correct_pct:.1f}%) | "
            f"错误手牌盈亏: ${incorrect_profit:.2f}"
        )
        self.summary_label.setStyleSheet("color: white;")
        
        # 填充表格
        self.results_table.setRowCount(len(results))
        for i, r in enumerate(results):
            self.results_table.setItem(i, 0, QTableWidgetItem(r["hand_id"]))
            self.results_table.setItem(i, 1, QTableWidgetItem(r["cards"]))
            self.results_table.setItem(i, 2, QTableWidgetItem(r["position"]))
            self.results_table.setItem(i, 3, QTableWidgetItem(r["hero_action"]))
            
            # GTO Freq
            freq_item = QTableWidgetItem(f"{r['gto_freq']*100:.1f}%" if r["gto_freq"] is not None else "N/A")
            self.results_table.setItem(i, 4, freq_item)
            
            # Status
            status_item = QTableWidgetItem("✅ OK" if r["is_correct"] else "❌ Leak")
            status_item.setForeground(QBrush(QColor("#4caf50" if r["is_correct"] else "#f44336")))
            self.results_table.setItem(i, 5, status_item)
            
            # Profit
            profit_item = QTableWidgetItem(f"${r['profit']:.2f}")
            profit_item.setForeground(QBrush(QColor("#4caf50" if r["profit"] >= 0 else "#f44336")))
            self.results_table.setItem(i, 6, profit_item)
            
            # Action Sequence
            seq_str = " → ".join([f"{pos} {act}" for pos, act in r["action_sequence"][:4]])
            if len(r["action_sequence"]) > 4:
                seq_str += " ..."
            self.results_table.setItem(i, 7, QTableWidgetItem(seq_str))
    
    def on_error(self, error_msg):
        """处理错误"""
        self.summary_label.setText(f"分析失败: {error_msg}")
        self.summary_label.setStyleSheet("color: #f44336;")
    
    def on_finished(self):
        """分析完成"""
        self.analyze_btn.setEnabled(True)
        self.progress_frame.setVisible(False)
    
    def refresh_data(self):
        """刷新数据"""
        pass  # 手动触发分析
