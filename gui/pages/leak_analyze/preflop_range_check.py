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
    QGridLayout, QSizePolicy, QButtonGroup
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


class NumericTableWidgetItem(QTableWidgetItem):
    """支持数值排序的 TableWidgetItem"""
    def __init__(self, text, value=None):
        super().__init__(text)
        self._value = value if value is not None else 0
    
    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self._value < other._value
        return super().__lt__(other)


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
        """分析所有手牌，按 Position + Scenario + Card 分组"""
        # 结果结构: {position: {scenario: {hand: {...}}}}
        def make_stats():
            return {
                "total": 0, 
                "correct": 0, 
                "incorrect": 0, 
                "profit": 0.0, 
                "hands": [],
                "action_dist": defaultdict(int),  # 用户实际行动分布
                "gto_dist": {},  # GTO 建议分布
            }
        
        # 三层嵌套: position -> scenario -> hand
        results = {pos: defaultdict(lambda: defaultdict(make_stats)) for pos in POSITIONS}
        
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
                scenario = analysis.get("scenario_key", "Other")  # 场景 key
                
                if pos in results and normalized:
                    stats = results[pos][scenario][normalized]
                    stats["total"] += 1
                    stats["profit"] += profit
                    if analysis["is_correct"]:
                        stats["correct"] += 1
                    else:
                        stats["incorrect"] += 1
                    stats["hands"].append(analysis)
                    
                    # 记录用户行动分布
                    hero_action = analysis.get("hero_action", "unknown")
                    stats["action_dist"][hero_action] += 1
                    
                    # 记录 GTO 建议
                    if not stats["gto_dist"] and analysis.get("gto_suggested"):
                        import re
                        for suggestion in analysis.get("gto_suggested", []):
                            match = re.match(r"(\w+).*\((\d+)%\)", suggestion)
                            if match:
                                action_name = match.group(1).lower()
                                freq = int(match.group(2)) / 100
                                if action_name not in ["fold", "call", "allin", "check"]:
                                    action_name = "raise"
                                stats["gto_dist"][action_name] = stats["gto_dist"].get(action_name, 0) + freq
        
        conn.close()
        self.progress.emit(total, total)
        
        # 计算频率偏移
        for pos in results:
            for scenario in results[pos]:
                for hand, stats in results[pos][scenario].items():
                    if stats["total"] > 0 and stats["gto_dist"]:
                        user_dist = {}
                        for action, count in stats["action_dist"].items():
                            user_dist[action] = count / stats["total"]
                        
                        deviation = 0.0
                        for action, gto_freq in stats["gto_dist"].items():
                            user_freq = user_dist.get(action, 0.0)
                            deviation += abs(user_freq - gto_freq)
                        
                        stats["freq_deviation"] = deviation / 2
                        stats["user_freq"] = {k: f"{v*100:.0f}%" for k, v in user_dist.items()}
                        stats["gto_freq"] = {k: f"{v*100:.0f}%" for k, v in stats["gto_dist"].items()}
        
        # 转换为普通 dict
        final = {}
        for pos in POSITIONS:
            final[pos] = {}
            for scenario, hands in results[pos].items():
                final[pos][scenario] = dict(hands)
        return final
    
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
        action_sequence, hero_action, hero_actions = self._build_action_sequence(preflop_actions, hero_name, button_seat, players)
        
        if not hero_action:
            return None
        
        normalized_cards = self._normalize_hand(hero_cards)
        if not normalized_cards:
            return None
        
        # 生成 Hero 行动描述 (e.g., "raise → call")
        hero_action_str = " → ".join(hero_actions) if hero_actions else hero_action
        
        gto_result = self._check_gto_detailed(action_sequence, hero_position, hero_action, normalized_cards)
        gto_freq = gto_result.get("freq")
        
        # 判断是否正确：
        # - GTO 频率 >= 50%: 正确（这是 GTO 主要推荐的行动）
        # - GTO 频率 > 0% 但 < 50%: 可接受但非最优（混合策略中的低频行动）
        # - GTO 频率 = 0% 或 None: 错误
        if gto_freq is None:
            is_correct = False
            is_acceptable = False
        elif gto_freq >= 0.50:
            is_correct = True
            is_acceptable = True
        elif gto_freq > 0.01:
            is_correct = False  # 不是最优，但可以接受
            is_acceptable = True
        else:
            is_correct = False
            is_acceptable = False
        
        # 生成场景 key
        scenario_key = self._get_scenario_key(action_sequence, hero_position, gto_result)
        
        return {
            "hand_id": hand_id,
            "cards": hero_cards,
            "normalized_cards": normalized_cards,
            "position": hero_position,
            "hero_action": hero_action,  # 最后一个行动（用于 GTO 检查）
            "hero_action_str": hero_action_str,  # 完整行动序列 (e.g., "raise → call")
            "action_sequence": action_sequence,
            "gto_freq": gto_freq,
            "gto_action_type": gto_result.get("action_type"),
            "is_correct": is_correct,
            "is_acceptable": is_acceptable,
            "profit": profit,
            "vs_position": gto_result.get("vs_position"),
            "scenario": gto_result.get("scenario"),
            "scenario_key": scenario_key,  # 场景分类 key
            "gto_suggested": gto_result.get("suggested_actions"),
        }
    
    def _get_scenario_key(self, action_sequence, hero_position, gto_result):
        """生成场景分类 key"""
        # 分析 action_sequence 确定场景类型
        # action_sequence: [(pos, action), ...]
        
        # 找到 Hero 第一次行动的位置
        hero_action_index = None
        for i, (pos, act) in enumerate(action_sequence):
            if pos == hero_position:
                hero_action_index = i
                break
        
        if hero_action_index is None:
            return "Other"
        
        actions_before = action_sequence[:hero_action_index]
        
        # 统计 Hero 之前的 raise 数量和位置
        raises_before = [(pos, act) for pos, act in actions_before if act in ["raise", "allin"]]
        
        if len(raises_before) == 0:
            # Hero 是第一个 raise 的机会 -> RFI 场景
            return "RFI"
        elif len(raises_before) == 1:
            # 有一个人 raise -> vs X Open
            opener_pos = raises_before[0][0]
            return f"vs {opener_pos} Open"
        elif len(raises_before) == 2:
            # 有人 open，有人 3bet -> vs X Open, Y 3bet
            opener_pos = raises_before[0][0]
            threebetter_pos = raises_before[1][0]
            return f"vs {opener_pos}/{threebetter_pos} 3bet"
        else:
            # 更复杂的场景
            return "Other"
    
    def _get_position(self, hero_seat, button_seat, num_players):
        """计算 Hero 位置"""
        if num_players != 6:
            return None
        relative = (hero_seat - button_seat) % 6
        position_map = {0: "BTN", 1: "SB", 2: "BB", 3: "UTG", 4: "HJ", 5: "CO"}
        return position_map.get(relative)
    
    def _build_action_sequence(self, preflop_actions, hero_name, button_seat, players):
        """构建行动序列，返回所有 Hero 行动（使用 poker 术语）"""
        sequence = []
        hero_actions = []  # 记录所有 Hero 行动
        raise_count = 0  # 计算 raise 次数来确定是 open/3bet/4bet
        
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
            display_action = None  # 用于显示的 poker 术语
            
            if action_type == "raises" or action_type == "bets":
                raise_count += 1
                if is_all_in:
                    abstract_action = "allin"
                    display_action = "allin"
                else:
                    abstract_action = "raise"
                    # 使用 poker 术语
                    if raise_count == 1:
                        display_action = "open"
                    elif raise_count == 2:
                        display_action = "3bet"
                    elif raise_count == 3:
                        display_action = "4bet"
                    else:
                        display_action = f"{raise_count+1}bet"
            elif action_type == "calls":
                abstract_action = "call"
                display_action = "call"
            elif action_type == "folds":
                abstract_action = "fold"
                display_action = "fold"
            elif action_type == "checks":
                abstract_action = "check"
                display_action = "check"
            
            if abstract_action:
                sequence.append((position, abstract_action))
                if player == hero_name:
                    hero_actions.append(display_action)  # 使用 poker 术语
        
        # 返回最后一个 hero_action 用于兼容性，同时返回完整列表
        hero_action = hero_actions[-1] if hero_actions else None
        # 对于 GTO 检查，需要用 abstract_action（raise/call/fold）
        abstract_hero_action = None
        if hero_actions:
            last = hero_actions[-1]
            if last in ["open", "3bet", "4bet"] or last.endswith("bet"):
                abstract_hero_action = "raise"
            else:
                abstract_hero_action = last
        return sequence, abstract_hero_action, hero_actions
    
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
        
        # 检查是否有人在 hero 之前 raise（open）
        has_opener_before = any(act == "raise" for _, act in actions_before_hero)
        
        if not has_opener_before:
            # Hero 是第一个 raise 的机会（open 场景）
            if hero_action == "raise":
                return self._check_open_range_detailed(base_path, hero_position, normalized_cards)
            elif hero_action == "fold":
                # Hero fold 了（open fold）- 检查是否应该 fold
                return self._check_open_fold_detailed(base_path, hero_position, normalized_cards)
        
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
            "scenario": f"RFI ({position})",  # RFI = Raise First In (第一个 raise 的机会)
            "suggested_actions": suggested
        }
    
    def _check_open_fold_detailed(self, base_path, position, hand):
        """检查 open fold 是否正确（不在 open range 内的牌应该 fold）"""
        pos_path = os.path.join(base_path, position)
        if not os.path.exists(pos_path):
            return {"freq": None, "action_type": None}
        
        open_sizes = [d for d in os.listdir(pos_path) if os.path.isdir(os.path.join(pos_path, d)) and not d.startswith('.')]
        if not open_sizes:
            return {"freq": None, "action_type": None}
        
        # 计算所有 open sizes 的总频率
        total_open_freq = 0
        open_actions = []
        
        for open_size in open_sizes:
            range_file = self._find_range_file(os.path.join(pos_path, open_size), position)
            if range_file:
                range_data = self._parse_range_file(range_file)
                freq = range_data.get(hand, 0)
                if freq > 0.01:
                    total_open_freq += freq
                    open_actions.append(f"Open {open_size} ({freq*100:.0f}%)")
        
        # fold 频率 = 1 - 总 open 频率
        fold_freq = max(0, 1.0 - total_open_freq)
        
        # 构建 GTO 建议
        suggested = []
        if fold_freq > 0.01:
            suggested.append(f"Fold ({fold_freq*100:.0f}%)")
        suggested.extend(open_actions)
        
        return {
            "freq": fold_freq,  # fold 的 GTO 频率
            "action_type": "fold",
            "vs_position": None,
            "scenario": f"RFI ({position})",  # RFI = Raise First In (第一个 raise 的机会)
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
        """查找 range 文件 - 使用广度优先搜索找最短路径"""
        from collections import deque
        
        target_file = f"{position}.txt"
        
        # BFS 广度优先搜索
        queue = deque([base_path])
        
        while queue:
            current_path = queue.popleft()
            
            # 检查当前目录是否有目标文件
            direct_path = os.path.join(current_path, target_file)
            if os.path.exists(direct_path):
                return direct_path
            
            # 将子目录加入队列
            try:
                items = os.listdir(current_path)
                
                def sort_key(item):
                    if item == "call":
                        return (0, 0)
                    if item == "fold":
                        return (0, 1)
                    return (1, item)
                
                items = sorted(items, key=sort_key)
                
                for item in items:
                    item_path = os.path.join(current_path, item)
                    if os.path.isdir(item_path) and not item.startswith('.'):
                        queue.append(item_path)
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
        freq_deviation = stats.get("freq_deviation", 0)
        
        # 计算颜色：基于正确率
        if total == 0:
            bg_color = QColor("#2a2a2a")  # 无数据
        else:
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
        
        # 统计文字：显示正确率
        if total > 0:
            accuracy = correct / total * 100
            stat_font = QFont("Arial", max(6, int(min(cell_w, cell_h) / 5)))
            painter.setFont(stat_font)
            
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
                freq_deviation = stats.get("freq_deviation", 0)
                tooltip = f"{hand}\n"
                tooltip += f"Hands: {total}"
                tooltip += f"\nCorrect: {correct} ({accuracy:.1f}%)"
                if freq_deviation > 0:
                    tooltip += f"\n频率偏移: {freq_deviation*100:.0f}%"
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
        self.results = {}  # {position: {scenario: {hand: stats}}}
        self.current_position = "all"  # "all" 或具体位置
        self.current_scenario = "all"  # "all" 或具体场景 key
        self.worker = None
        self.current_hand_data = []
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
        
        # "All" 按钮
        all_btn = QPushButton("All")
        all_btn.setCheckable(True)
        all_btn.setChecked(self.current_position == "all")
        all_btn.setStyleSheet("""
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
        all_btn.clicked.connect(lambda checked: self._on_position_selected("all"))
        pos_btn_layout.addWidget(all_btn, 0, 0, 1, 3)  # 第一行占满
        self.position_buttons["all"] = all_btn
        
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
            pos_btn_layout.addWidget(btn, 1 + i // 3, i % 3)  # 从第二行开始
            self.position_buttons[pos] = btn
        
        pos_layout.addLayout(pos_btn_layout)
        left_layout.addWidget(pos_frame)
        
        # Scenario 选择
        scenario_frame = QFrame()
        scenario_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 8px;")
        scenario_layout = QVBoxLayout(scenario_frame)
        scenario_layout.setContentsMargins(12, 12, 12, 12)
        
        scenario_title = QLabel("Scenario")
        scenario_title.setStyleSheet("color: white; font-weight: bold;")
        scenario_layout.addWidget(scenario_title)
        
        self.scenario_combo = QComboBox()
        self.scenario_combo.addItem("All Scenarios", "all")
        self.scenario_combo.setStyleSheet("""
            QComboBox {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QComboBox:hover { background-color: #4a4a4a; }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { image: none; border: none; }
            QComboBox QAbstractItemView {
                background-color: #3a3a3a;
                color: white;
                selection-background-color: #4a9eff;
            }
        """)
        self.scenario_combo.currentIndexChanged.connect(self._on_scenario_changed)
        scenario_layout.addWidget(self.scenario_combo)
        
        left_layout.addWidget(scenario_frame)
        
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
        
        # 右侧区域 - 使用 QSplitter 分割矩阵和详情
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(24, 24, 24, 24)
        right_layout.setSpacing(12)
        
        self.matrix_title = QLabel("UTG - Leak Analysis")
        self.matrix_title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        right_layout.addWidget(self.matrix_title)
        
        # 矩阵区域（固定大小）
        self.leak_matrix = LeakMatrixWidget()
        self.leak_matrix.hand_clicked.connect(self._on_hand_clicked)
        self.leak_matrix.setFixedHeight(500)  # 固定矩阵高度（放大）
        right_layout.addWidget(self.leak_matrix)
        
        # 下方区域 - 使用水平 QSplitter 分割 Summary 和 Table
        detail_splitter = QSplitter(Qt.Horizontal)
        detail_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3a3a3a;
                width: 4px;
            }
            QSplitter::handle:hover {
                background-color: #4a9eff;
            }
        """)
        
        # 左边: Summary 统计
        summary_frame = QFrame()
        summary_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 8px;")
        summary_frame.setMinimumWidth(200)
        summary_layout = QVBoxLayout(summary_frame)
        summary_layout.setContentsMargins(12, 12, 12, 12)
        summary_layout.setSpacing(8)
        
        self.detail_title = QLabel("点击格子查看详情")
        self.detail_title.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        summary_layout.addWidget(self.detail_title)
        
        # 统计信息（可滚动）
        stats_scroll = QScrollArea()
        stats_scroll.setWidgetResizable(True)
        stats_scroll.setStyleSheet("""
            QScrollArea { background-color: transparent; border: none; }
            QScrollBar:vertical {
                background-color: #2a2a2a;
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #4a4a4a;
                border-radius: 3px;
            }
        """)
        
        self.detail_stats = QLabel("")
        self.detail_stats.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        self.detail_stats.setWordWrap(True)
        self.detail_stats.setAlignment(Qt.AlignTop)
        stats_scroll.setWidget(self.detail_stats)
        summary_layout.addWidget(stats_scroll, 1)
        
        detail_splitter.addWidget(summary_frame)
        
        # 右边: 手牌表格
        table_frame = QFrame()
        table_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 8px;")
        table_frame.setMinimumWidth(400)
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.setSpacing(8)
        
        # 手牌列表标题
        hands_header = QHBoxLayout()
        hands_label = QLabel("手牌列表 (双击 Replay)")
        hands_label.setStyleSheet("color: #888888; font-size: 11px;")
        hands_header.addWidget(hands_label)
        
        self.filter_label = QLabel("全部")
        self.filter_label.setStyleSheet("color: #4a9eff; font-size: 11px;")
        hands_header.addWidget(self.filter_label)
        hands_header.addStretch()
        table_layout.addLayout(hands_header)
        
        # 手牌表格
        self.hand_table = QTableWidget()
        self.hand_table.setColumnCount(7)
        self.hand_table.setHorizontalHeaderLabels(["", "手牌", "位置", "你的行动", "场景", "GTO建议", "盈亏"])
        self.hand_table.horizontalHeader().setStretchLastSection(True)
        self.hand_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.hand_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.hand_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.hand_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.hand_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.hand_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.hand_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.hand_table.verticalHeader().setVisible(False)
        self.hand_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.hand_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.hand_table.setSortingEnabled(True)  # 启用排序
        self.hand_table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                border: none;
                border-radius: 4px;
                gridline-color: #2a2a2a;
                font-size: 11px;
            }
            QTableWidget::item {
                color: white;
                padding: 4px;
            }
            QTableWidget::item:hover {
                background-color: #3a3a3a;
            }
            QTableWidget::item:selected {
                background-color: #4a9eff;
            }
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #888888;
                padding: 4px;
                border: none;
                font-size: 10px;
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
        self.hand_table.cellDoubleClicked.connect(self._on_hand_table_clicked)
        self.hand_table.setCursor(QCursor(Qt.PointingHandCursor))
        table_layout.addWidget(self.hand_table, 1)
        
        detail_splitter.addWidget(table_frame)
        
        # 设置初始比例 (Summary: Table = 1:2)
        detail_splitter.setSizes([300, 600])
        
        right_layout.addWidget(detail_splitter, 1)  # Splitter 占用剩余空间
        
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
        self._update_scenario_combo()  # 更新场景下拉框
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
        
        # 更新 scenario combo
        self._update_scenario_combo()
        self._update_position_view()
    
    def _on_scenario_changed(self, index):
        """选择场景"""
        self.current_scenario = self.scenario_combo.itemData(index) or "all"
        self._update_position_view()
    
    def _update_scenario_combo(self):
        """更新场景下拉框"""
        self.scenario_combo.blockSignals(True)
        self.scenario_combo.clear()
        self.scenario_combo.addItem("All Scenarios", "all")
        
        # 收集所有场景
        all_scenarios = {}
        positions_to_check = POSITIONS if self.current_position == "all" else [self.current_position]
        
        for pos in positions_to_check:
            if pos in self.results:
                for scenario, hands in self.results[pos].items():
                    if scenario not in all_scenarios:
                        all_scenarios[scenario] = 0
                    all_scenarios[scenario] += sum(stats["total"] for stats in hands.values())
        
        # 排序：Open 优先，然后 vs X Open，然后 Other
        def scenario_order(s):
            if s == "Open":
                return (0, s)
            elif s.startswith("vs ") and "3bet" not in s:
                return (1, s)
            elif "3bet" in s:
                return (2, s)
            else:
                return (3, s)
        
        sorted_scenarios = sorted(all_scenarios.keys(), key=scenario_order)
        
        for s in sorted_scenarios:
            count = all_scenarios[s]
            self.scenario_combo.addItem(f"{s} ({count}手)", s)
        
        self.scenario_combo.blockSignals(False)
        self.current_scenario = "all"
    
    def _update_position_view(self):
        """更新当前位置的视图"""
        pos = self.current_position
        scenario = self.current_scenario
        
        # 标题
        pos_text = "All Positions" if pos == "all" else pos
        scenario_text = "All Scenarios" if scenario == "all" else scenario
        self.matrix_title.setText(f"{pos_text} - {scenario_text}")
        
        if not self.results:
            self.leak_matrix.clear()
            self.summary_label.setText("无数据")
            return
        
        # 根据位置和场景筛选/合并数据
        hand_stats = self._get_merged_hand_stats(pos, scenario)
        self.leak_matrix.set_data(hand_stats)
        
        # 计算统计
        total_hands = sum(s.get("total", 0) for s in hand_stats.values())
        total_correct = sum(s.get("correct", 0) for s in hand_stats.values())
        total_profit = sum(s.get("profit", 0) for s in hand_stats.values())
        
        accuracy = (total_correct / total_hands * 100) if total_hands > 0 else 0
        
        # 找出最大 leak（按频率偏移）
        leaks = []
        for hand, stats in hand_stats.items():
            total = stats.get("total", 0)
            if total > 0:
                freq_dev = stats.get("freq_deviation", 0)
                if freq_dev > 0.1:  # 频率偏移 > 10%
                    leaks.append((hand, total, freq_dev, stats.get("profit", 0), stats.get("user_freq", {}), stats.get("gto_freq", {})))
        
        leaks.sort(key=lambda x: -x[2])  # 按偏移程度排序
        
        summary_text = f"总手数: {total_hands}\n"
        summary_text += f"正确率: {accuracy:.1f}%\n"
        summary_text += f"盈亏: ${total_profit:.2f}\n"
        
        if leaks:
            summary_text += f"\n🚨 频率偏移最大:\n"
            for hand, cnt, dev, pft, user_f, gto_f in leaks[:3]:
                user_str = "/".join(f"{k}:{v}" for k, v in user_f.items())
                gto_str = "/".join(f"{k}:{v}" for k, v in gto_f.items())
                summary_text += f"  {hand}: 偏移{dev*100:.0f}%\n"
                summary_text += f"    你: {user_str}\n"
                summary_text += f"    GTO: {gto_str}\n"
        
        self.summary_label.setText(summary_text)
        self.summary_label.setStyleSheet("color: white; font-size: 12px;")
    
    def _group_by_scenario(self, hands_data):
        """将手牌数据按场景分组，计算每个场景的频率分布"""
        scenario_stats = {}
        
        for h in hands_data:
            scen = h.get("scenario_key", "Other")
            if scen not in scenario_stats:
                scenario_stats[scen] = {
                    "total": 0,
                    "action_dist": defaultdict(int),
                    "gto_dist": {},
                }
            
            scenario_stats[scen]["total"] += 1
            hero_action = h.get("hero_action", "unknown")
            scenario_stats[scen]["action_dist"][hero_action] += 1
            
            # 记录 GTO（第一次）
            if not scenario_stats[scen]["gto_dist"] and h.get("gto_suggested"):
                import re
                for suggestion in h.get("gto_suggested", []):
                    match = re.match(r"(\w+).*\((\d+)%\)", suggestion)
                    if match:
                        action_name = match.group(1).lower()
                        freq = int(match.group(2)) / 100
                        if action_name not in ["fold", "call", "allin", "check"]:
                            action_name = "raise"
                        scenario_stats[scen]["gto_dist"][action_name] = scenario_stats[scen]["gto_dist"].get(action_name, 0) + freq
        
        # 计算用户频率分布
        for scen, data in scenario_stats.items():
            total = data["total"]
            if total > 0:
                data["user_dist"] = {k: v / total for k, v in data["action_dist"].items()}
            else:
                data["user_dist"] = {}
        
        return scenario_stats
    
    def _get_merged_hand_stats(self, position, scenario):
        """获取合并后的手牌统计（用于矩阵显示）"""
        # 确定要遍历的位置
        positions_to_check = POSITIONS if position == "all" else [position]
        
        merged = {}
        
        for pos in positions_to_check:
            if pos not in self.results:
                continue
            
            # 确定要遍历的场景
            if scenario != "all":
                scenarios_to_check = [scenario] if scenario in self.results[pos] else []
            else:
                scenarios_to_check = list(self.results[pos].keys())
            
            for scen in scenarios_to_check:
                if scen not in self.results[pos]:
                    continue
                for hand, stats in self.results[pos][scen].items():
                    if hand not in merged:
                        merged[hand] = {
                            "total": 0, "correct": 0, "incorrect": 0, "profit": 0.0,
                            "hands": [], "action_dist": defaultdict(int), "gto_dist": {},
                        }
                    merged[hand]["total"] += stats.get("total", 0)
                    merged[hand]["correct"] += stats.get("correct", 0)
                    merged[hand]["incorrect"] += stats.get("incorrect", 0)
                    merged[hand]["profit"] += stats.get("profit", 0)
                    merged[hand]["hands"].extend(stats.get("hands", []))
                    for act, cnt in stats.get("action_dist", {}).items():
                        merged[hand]["action_dist"][act] += cnt
        
        # 重新计算频率偏移（合并后）
        for hand, stats in merged.items():
            total = stats["total"]
            if total > 0:
                user_dist = {}
                for action, count in stats["action_dist"].items():
                    user_dist[action] = count / total
                stats["user_freq"] = {k: f"{v*100:.0f}%" for k, v in user_dist.items()}
        
        return merged
    
    def _on_hand_clicked(self, hand, stats):
        """点击手牌显示详情"""
        total = stats.get("total", 0)
        
        # 禁用排序，清空表格
        self.hand_table.setSortingEnabled(False)
        self.hand_table.setRowCount(0)
        self.current_hand_data = []
        
        if total == 0:
            self.detail_title.setText(f"{hand} - 无数据")
            self.detail_stats.setText("")
            self.filter_label.setText("无数据")
            self.hand_table.setSortingEnabled(True)
            return
        
        correct = stats.get("correct", 0)
        incorrect = stats.get("incorrect", 0)
        profit = stats.get("profit", 0)
        accuracy = correct / total * 100
        
        pos_text = "All Positions" if self.current_position == "all" else self.current_position
        self.detail_title.setText(f"{hand} @ {pos_text}")
        
        # 获取手牌数据
        hands_data = stats.get("hands", [])
        
        # 按场景分组统计
        scenario_stats = self._group_by_scenario(hands_data)
        
        # 构建统计文本
        stats_text = f"总手数: {total}  |  正确: {correct} ({accuracy:.1f}%)  |  盈亏: ${profit:.2f}\n"
        
        # 显示每个场景的频率对比
        for scen, scen_data in scenario_stats.items():
            scen_total = scen_data["total"]
            user_dist = scen_data["user_dist"]
            gto_dist = scen_data["gto_dist"]
            
            user_str = " / ".join(f"{k}: {v*100:.0f}%" for k, v in sorted(user_dist.items()))
            gto_str = " / ".join(f"{k}: {v*100:.0f}%" for k, v in sorted(gto_dist.items())) if gto_dist else "N/A"
            
            # 计算偏移
            deviation = 0.0
            if gto_dist:
                for action, gto_freq in gto_dist.items():
                    user_freq = user_dist.get(action, 0.0)
                    deviation += abs(user_freq - gto_freq)
                deviation /= 2
            
            icon = "🚨" if deviation > 0.1 else "✅"
            stats_text += f"\n{icon} {scen} ({scen_total}手):\n"
            stats_text += f"   你: {user_str}\n"
            stats_text += f"   GTO: {gto_str}"
        
        self.detail_stats.setText(stats_text)
        
        self.current_hand_data = hands_data
        
        # 分类：错误 -> 可接受但非最优 -> 正确
        error_hands = [h for h in hands_data if not h.get("is_acceptable", False)]
        suboptimal_hands = [h for h in hands_data if h.get("is_acceptable") and not h.get("is_correct")]
        correct_hands = [h for h in hands_data if h.get("is_correct")]
        
        self.filter_label.setText(f"全部 {len(hands_data)} 手 (❌{len(error_hands)} ⚠️{len(suboptimal_hands)} ✅{len(correct_hands)})")
        
        # 按优先级显示：错误 -> 可接受但非最优 -> 正确
        for h in error_hands:
            self._add_hand_to_table(h)
        for h in suboptimal_hands:
            self._add_hand_to_table(h)
        for h in correct_hands:
            self._add_hand_to_table(h)
        
        # 重新启用排序
        self.hand_table.setSortingEnabled(True)
    
    def _add_hand_to_table(self, hand_data):
        """添加手牌到表格"""
        cards = hand_data.get("cards", "?")
        # 使用完整行动序列，如 "raise → call"
        hero_action = hand_data.get("hero_action_str", hand_data.get("hero_action", "?"))
        scenario = hand_data.get("scenario", "")
        vs_position = hand_data.get("vs_position", "")
        gto_suggested = hand_data.get("gto_suggested", [])
        gto_freq = hand_data.get("gto_freq")
        profit = hand_data.get("profit", 0)
        is_correct = hand_data.get("is_correct", False)
        is_acceptable = hand_data.get("is_acceptable", False)
        hand_id = hand_data.get("hand_id")
        
        # 图标和颜色
        if is_correct:
            icon = "✅"
            color = QColor("#4CAF50")
        elif is_acceptable:
            icon = "⚠️"
            color = QColor("#FF9800")
        else:
            icon = "❌"
            color = QColor("#f44336")
        
        # 场景描述
        if scenario:
            scenario_text = scenario
        elif vs_position:
            scenario_text = f"vs {vs_position}"
        else:
            scenario_text = "Open"
        
        # GTO 建议（简化显示）
        gto_text = " / ".join(gto_suggested[:2]) if gto_suggested else "N/A"
        
        # 你的行动（不显示百分比，百分比在 summary 里显示）
        action_text = hero_action
        
        # 盈亏
        profit_text = f"${profit:.2f}" if profit >= 0 else f"-${abs(profit):.2f}"
        profit_color = QColor("#4CAF50") if profit >= 0 else QColor("#f44336")
        
        # 添加行
        row = self.hand_table.rowCount()
        self.hand_table.insertRow(row)
        
        # 图标列 (0)
        icon_item = QTableWidgetItem(icon)
        icon_item.setTextAlignment(Qt.AlignCenter)
        icon_item.setData(Qt.UserRole, hand_id)
        self.hand_table.setItem(row, 0, icon_item)
        
        # 手牌列 (1)
        cards_item = QTableWidgetItem(cards)
        cards_item.setForeground(color)
        self.hand_table.setItem(row, 1, cards_item)
        
        # 位置列 (2)
        position = hand_data.get("position", "?")
        pos_item = QTableWidgetItem(position)
        pos_item.setForeground(QColor("#4a9eff"))
        self.hand_table.setItem(row, 2, pos_item)
        
        # 你的行动列 (3)
        action_item = QTableWidgetItem(action_text)
        action_item.setForeground(color)
        self.hand_table.setItem(row, 3, action_item)
        
        # 场景列 (4)
        scenario_item = QTableWidgetItem(scenario_text)
        scenario_item.setForeground(QColor("#888888"))
        self.hand_table.setItem(row, 4, scenario_item)
        
        # GTO 建议列 (5)
        gto_item = QTableWidgetItem(gto_text)
        gto_item.setForeground(QColor("#aaaaaa"))
        self.hand_table.setItem(row, 5, gto_item)
        
        # 盈亏列 (6) - 使用 NumericTableWidgetItem 支持数值排序
        profit_item = NumericTableWidgetItem(profit_text, profit)
        profit_item.setForeground(profit_color)
        profit_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.hand_table.setItem(row, 6, profit_item)
    
    def _on_hand_table_clicked(self, row, col):
        """双击手牌打开 replay"""
        # 从第 0 列获取 hand_id
        icon_item = self.hand_table.item(row, 0)
        if icon_item:
            hand_id = icon_item.data(Qt.UserRole)
            if hand_id:
                self.replay_requested.emit(hand_id)
    
    def refresh_data(self):
        pass


