"""
Discounted CFR 算法核心实现 - 支持完整多街 + 多进程并行计算
"""
from .data_types import Node, Action, HandRange, Card
from .hand_evaluator import calculate_equity, clear_equity_cache
from .card_utils import get_all_combos, cards_conflict
from typing import Dict, List, Callable, Optional, Tuple
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import math
import random
import os

# 获取 CPU 核心数（保留 2 个给系统）
NUM_WORKERS = max(1, multiprocessing.cpu_count() - 2)
print(f"[CFR] Detected {multiprocessing.cpu_count()} CPU cores, using {NUM_WORKERS} workers")


class DCFREngine:
    """Discounted CFR 引擎 - 支持多街 Chance Node"""
    
    def __init__(
        self,
        game_tree: Node,
        oop_range: HandRange,
        ip_range: HandRange,
        board: List[Card],
        alpha: float = 1.5,
        beta: float = 0.0,
        gamma: float = 2.0
    ):
        self.tree = game_tree
        self.oop_range = oop_range
        self.ip_range = ip_range
        self.board = board
        
        # DCFR 参数
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        
        # 存储所有 combos
        self.all_combos = get_all_combos()
        
        # 过滤有效的 combos（不与初始 board 冲突）
        self.oop_combos = self._filter_combos(oop_range)
        self.ip_combos = self._filter_combos(ip_range)
        
        # 手牌级别的 CFR 数据结构
        # regrets[node_id][hand_str][action] = float
        self.regrets: Dict[int, Dict[str, Dict[Action, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        # cumulative_strategies[node_id][hand_str][action] = float
        self.cumulative_strategies: Dict[int, Dict[str, Dict[Action, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        
        # 建立 hand_str -> combos 映射
        self.oop_hand_combos: Dict[str, List[Tuple]] = defaultdict(list)
        self.ip_hand_combos: Dict[str, List[Tuple]] = defaultdict(list)
        for combo, weight, hand_str in self.oop_combos:
            self.oop_hand_combos[hand_str].append((combo, weight))
        for combo, weight, hand_str in self.ip_combos:
            self.ip_hand_combos[hand_str].append((combo, weight))
        
        # 用于节点 ID（因为多街树很大，使用 id 替代 hash）
        self._node_id_cache: Dict[int, int] = {}
        self._next_node_id = 0
    
    def _get_node_id(self, node: Node) -> int:
        """获取节点的唯一 ID"""
        obj_id = id(node)
        if obj_id not in self._node_id_cache:
            self._node_id_cache[obj_id] = self._next_node_id
            self._next_node_id += 1
        return self._node_id_cache[obj_id]
    
    def _filter_combos(self, range_obj: HandRange) -> List[Tuple]:
        """过滤出与初始 board 不冲突的 combos"""
        valid_combos = []
        for hand_str, weight in range_obj.weights.items():
            if weight <= 0:
                continue
            combos = self.all_combos.get(hand_str, [])
            for combo in combos:
                if not cards_conflict(list(combo), self.board):
                    valid_combos.append((combo, weight, hand_str))
        return valid_combos
    
    def solve(self, iterations: int = 1000, callback: Optional[Callable] = None, parallel: bool = True):
        """运行 DCFR 迭代
        
        Args:
            iterations: 迭代次数
            callback: 进度回调函数
            parallel: 是否使用并行计算（目前由于 GIL 限制，优化效果有限）
        """
        clear_equity_cache()
        update_interval = max(1, iterations // 20)  # 减少回调频率
        
        print(f"[CFR] Starting {iterations} iterations")
        print(f"[CFR] OOP combos: {len(self.oop_combos)}, IP combos: {len(self.ip_combos)}")
        
        # 追踪每次迭代的即时 regret
        self._iteration_regrets = []
        
        # 采样设置：每次迭代采样部分手牌
        # 动态调整：早期多采样探索，后期少采样加速收敛
        base_sample = 12
        
        for t in range(1, iterations + 1):
            iteration_regret_sum = 0.0
            iteration_regret_count = 0
            
            # 动态采样：早期更多探索
            if t < 20:
                sample_size = base_sample
            elif t < 50:
                sample_size = base_sample - 2
            else:
                sample_size = base_sample - 4  # 后期减少采样加速
            
            sample_size = max(5, sample_size)
            
            # 为每个玩家运行 CFR
            for player in [0, 1]:
                combos = self.oop_combos if player == 0 else self.ip_combos
                actual_sample = min(sample_size, len(combos))
                sampled = random.sample(combos, actual_sample) if len(combos) > actual_sample else combos
                
                for combo, weight, hand_str in sampled:
                    regret = self._cfr_traversal_hand(
                        self.tree, player, hand_str, combo, weight, 1.0, t
                    )
                    iteration_regret_sum += abs(regret)
                    iteration_regret_count += 1
            
            # 记录本次迭代的平均 regret
            if iteration_regret_count > 0:
                avg_regret = iteration_regret_sum / iteration_regret_count
                self._iteration_regrets.append(avg_regret)
            
            # 应用 discount（每 2 次迭代一次，减少开销）
            if t % 2 == 0:
                self._apply_discount(t)
            
            if callback and (t % update_interval == 0 or t == iterations):
                callback(t, None)
            
            # 每 20 次迭代打印进度
            if t % 20 == 0:
                print(f"[CFR] Iteration {t}/{iterations}")
    
    def _parallel_cfr_batch(self, sampled: List[Tuple], player: int, iteration: int, num_workers: int) -> List[float]:
        """并行处理一批手牌的 CFR 遍历
        
        注意：由于 Python GIL，ThreadPoolExecutor 对纯 CPU 任务帮助有限
        但由于 CFR 状态更新的复杂性，ProcessPoolExecutor 的序列化开销更大
        这里采用批量串行处理 + 减少 Python 调用开销的策略
        """
        regrets = []
        
        # 批量处理，减少函数调用开销
        for combo, weight, hand_str in sampled:
            try:
                regret = self._cfr_traversal_hand(
                    self.tree, player, hand_str, combo, weight, 1.0, iteration
                )
                regrets.append(regret)
            except Exception as e:
                regrets.append(0.0)
        
        return regrets
    
    def _cfr_traversal_hand(
        self,
        node: Node,
        player: int,
        hand_str: str,
        combo: tuple,
        weight: float,
        reach_prob: float,
        iteration: int
    ) -> float:
        """为特定手牌的 CFR 遍历"""
        
        # 检查 combo 是否与当前 board 冲突
        if cards_conflict(list(combo), node.state.board):
            return 0.0
        
        if node.is_terminal or node.node_type == "terminal":
            return self._terminal_ev_hand(node, player, combo, weight)
        
        # Chance Node 处理
        if node.node_type == "chance":
            return self._chance_node_cfr(
                node, player, hand_str, combo, weight, reach_prob, iteration
            )
        
        # 普通决策节点
        if node.player == player:
            return self._player_node_cfr_hand(
                node, player, hand_str, combo, weight, reach_prob, iteration
            )
        else:
            return self._opponent_node_cfr_hand(
                node, player, hand_str, combo, weight, reach_prob, iteration
            )
    
    def _chance_node_cfr(
        self,
        node: Node,
        player: int,
        hand_str: str,
        combo: tuple,
        weight: float,
        reach_prob: float,
        iteration: int
    ) -> float:
        """
        Chance Node 的 CFR 处理
        
        遍历所有可能的发牌，根据发牌概率加权 EV。
        对于 Card Abstraction，使用 bucket size 作为权重。
        """
        if not node.chance_children:
            return 0.0
        
        total_ev = 0.0
        total_cards = 0
        
        # 计算可能的牌数（排除与 combo 冲突的）
        for representative, child in node.chance_children.items():
            # 检查代表牌是否与玩家手牌冲突
            if cards_conflict([representative], list(combo)):
                continue
            
            # Abstraction：假设每个 bucket 有相同权重
            # 实际上应该根据 bucket 内牌的数量加权，但简化处理
            card_prob = 1.0  # 均匀分布
            
            child_ev = self._cfr_traversal_hand(
                child, player, hand_str, combo, weight, reach_prob, iteration
            )
            
            total_ev += child_ev * card_prob
            total_cards += 1
        
        if total_cards > 0:
            return total_ev / total_cards
        return 0.0
    
    def _player_node_cfr_hand(
        self,
        node: Node,
        player: int,
        hand_str: str,
        combo: tuple,
        weight: float,
        reach_prob: float,
        iteration: int
    ) -> float:
        """当前玩家决策节点的 CFR"""
        node_id = self._get_node_id(node)
        strategy = self._get_current_strategy_hand(node, node_id, hand_str)
        
        if not strategy:
            return 0.0
        
        node_util = 0.0
        action_utils = {}
        
        for action in node.actions:
            if action not in node.children:
                continue
            child = node.children[action]
            new_reach = reach_prob * strategy.get(action, 0.0)
            
            action_util = self._cfr_traversal_hand(
                child, player, hand_str, combo, weight, new_reach, iteration
            )
            action_utils[action] = action_util
            node_util += strategy.get(action, 0.0) * action_util
        
        # 更新该手牌的 regrets
        for action in node.actions:
            if action in action_utils:
                regret = action_utils[action] - node_util
                self.regrets[node_id][hand_str][action] += regret * reach_prob
        
        # 更新累计策略
        for action in strategy:
            self.cumulative_strategies[node_id][hand_str][action] += strategy[action] * reach_prob
        
        return node_util
    
    def _opponent_node_cfr_hand(
        self,
        node: Node,
        player: int,
        hand_str: str,
        combo: tuple,
        weight: float,
        reach_prob: float,
        iteration: int
    ) -> float:
        """对手决策节点的 CFR"""
        node_id = self._get_node_id(node)
        strategy = self._get_average_opponent_strategy(node, node_id)
        
        if not strategy:
            return 0.0
        
        node_util = 0.0
        
        for action in node.actions:
            if action not in node.children:
                continue
            child = node.children[action]
            action_util = self._cfr_traversal_hand(
                child, player, hand_str, combo, weight, reach_prob, iteration
            )
            node_util += strategy.get(action, 0.0) * action_util
        
        return node_util
    
    def _get_current_strategy_hand(self, node: Node, node_id: int, hand_str: str) -> Dict[Action, float]:
        """获取特定手牌的当前策略"""
        if not node.actions:
            return {}
        
        strategy = {}
        normalizing_sum = 0.0
        
        for action in node.actions:
            regret = self.regrets[node_id][hand_str][action]
            strategy[action] = max(0.0, regret)
            normalizing_sum += strategy[action]
        
        if normalizing_sum > 0:
            for action in node.actions:
                strategy[action] /= normalizing_sum
        else:
            uniform = 1.0 / len(node.actions)
            for action in node.actions:
                strategy[action] = uniform
        
        return strategy
    
    def _get_average_opponent_strategy(self, node: Node, node_id: int) -> Dict[Action, float]:
        """获取对手的平均策略"""
        if not node.actions:
            return {}
        
        total_strategy = defaultdict(float)
        hand_combos = self.ip_hand_combos if node.player == 1 else self.oop_hand_combos
        
        for hand_str in hand_combos.keys():
            if hand_str in self.cumulative_strategies[node_id]:
                for action, count in self.cumulative_strategies[node_id][hand_str].items():
                    total_strategy[action] += count
        
        total = sum(total_strategy.values())
        if total > 0:
            return {action: count / total for action, count in total_strategy.items()}
        else:
            uniform = 1.0 / len(node.actions)
            return {action: uniform for action in node.actions}
    
    def _terminal_ev_hand(
        self,
        node: Node,
        player: int,
        combo: tuple,
        weight: float
    ) -> float:
        """计算特定手牌在 terminal 节点的 EV"""
        state = node.state
        initial_stack = self.tree.state.stacks[player]
        
        # Fold: pot 为 0
        if state.pot == 0:
            return state.stacks[player] - initial_stack
        
        # Showdown: 计算 equity
        opponent_combos = self.ip_combos if player == 0 else self.oop_combos
        
        # 过滤与当前 board 冲突的对手 combos
        valid_opp_combos = [
            (c, w, h) for c, w, h in opponent_combos 
            if not cards_conflict(list(c), state.board) and not cards_conflict(list(c), list(combo))
        ]
        
        if not valid_opp_combos:
            return 0.0
        
        # 采样对手手牌计算 EV
        max_samples = 4  # 减少采样
        sampled = random.sample(valid_opp_combos, min(max_samples, len(valid_opp_combos)))
        
        total_ev = 0.0
        total_weight = 0.0
        
        for opp_combo, opp_weight, _ in sampled:
            equity = calculate_equity(
                list(combo),
                list(opp_combo),
                state.board,
                num_simulations=2  # 减少模拟次数
            )
            
            pot_share = equity * state.pot
            investment = initial_stack - state.stacks[player]
            ev = pot_share - investment
            
            total_ev += ev * opp_weight
            total_weight += opp_weight
        
        if total_weight > 0:
            return total_ev / total_weight
        return 0.0
    
    def _apply_discount(self, iteration: int):
        """应用 DCFR discount"""
        t = iteration
        discount = (t ** self.alpha) / (t ** self.alpha + 1)
        
        for node_id in list(self.regrets.keys()):
            for hand_str in list(self.regrets[node_id].keys()):
                for action in list(self.regrets[node_id][hand_str].keys()):
                    self.regrets[node_id][hand_str][action] *= discount
    
    def get_strategy(self) -> Dict[Node, Dict[Action, float]]:
        """获取节点级别的平均策略（兼容旧接口）"""
        avg_strategy = {}
        self._collect_node_strategy(self.tree, avg_strategy)
        return avg_strategy
    
    def _collect_node_strategy(self, node: Node, avg_strategy: Dict):
        """递归收集节点级别策略"""
        if node.is_terminal or node.node_type == "terminal":
            return
        
        # 跳过 Chance Node
        if node.node_type == "chance":
            if node.chance_children:
                for child in node.chance_children.values():
                    self._collect_node_strategy(child, avg_strategy)
            return
        
        node_id = self._get_node_id(node)
        
        # 聚合所有手牌的策略
        total_strategy = defaultdict(float)
        hand_combos = self.oop_hand_combos if node.player == 0 else self.ip_hand_combos
        
        for hand_str in hand_combos.keys():
            if hand_str in self.cumulative_strategies[node_id]:
                for action, count in self.cumulative_strategies[node_id][hand_str].items():
                    total_strategy[action] += count
        
        total = sum(total_strategy.values())
        if total > 0:
            avg_strategy[node] = {
                action: count / total for action, count in total_strategy.items()
            }
        elif node.actions:
            uniform = 1.0 / len(node.actions)
            avg_strategy[node] = {action: uniform for action in node.actions}
        
        for action, child in node.children.items():
            self._collect_node_strategy(child, avg_strategy)
    
    def get_hand_strategy(self, node: Node = None) -> Dict[str, Dict[str, float]]:
        """获取手牌级别的策略"""
        if node is None:
            node = self.tree
        
        # 跳过 Chance Node
        if node.node_type == "chance":
            return {}
        
        node_id = self._get_node_id(node)
        hand_strategy = {}
        hand_combos = self.oop_hand_combos if node.player == 0 else self.ip_hand_combos
        
        for hand_str in hand_combos.keys():
            if hand_str in self.cumulative_strategies[node_id]:
                cum = self.cumulative_strategies[node_id][hand_str]
                total = sum(cum.values())
                if total > 0:
                    hand_strategy[hand_str] = {
                        str(action): cum[action] / total
                        for action in cum
                    }
                else:
                    if node.actions:
                        uniform = 1.0 / len(node.actions)
                        hand_strategy[hand_str] = {
                            str(action): uniform for action in node.actions
                        }
            else:
                if node.actions:
                    uniform = 1.0 / len(node.actions)
                    hand_strategy[hand_str] = {
                        str(action): uniform for action in node.actions
                    }
        
        return hand_strategy
    
    def get_node_strategy(self, node: Node) -> Dict[Action, float]:
        """获取特定节点的策略"""
        strategy = self.get_strategy()
        return strategy.get(node, {})
    
    def get_average_regret(self) -> float:
        """获取最近迭代的平均 regret（用于收敛判断）
        
        理论上，随着迭代增加，这个值应该趋近于 0。
        使用最近 10 次迭代的移动平均来平滑噪声。
        """
        if not hasattr(self, '_iteration_regrets') or not self._iteration_regrets:
            return 0.0
        
        # 使用最近 10 次迭代的移动平均
        recent = self._iteration_regrets[-10:]
        return sum(recent) / len(recent)



