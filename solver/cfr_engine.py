"""
Discounted CFR 算法核心实现 - 手牌级别策略
"""
from solver.data_types import Node, Action, HandRange, Card
from solver.hand_evaluator import calculate_equity, clear_equity_cache
from solver.card_utils import get_all_combos, cards_conflict
from typing import Dict, List, Callable, Optional, Tuple
from collections import defaultdict
import math
import random


class DCFREngine:
    """Discounted CFR 引擎 - 手牌级别策略"""
    
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
        
        # 过滤有效的 combos（不与 board 冲突）
        # 格式: [(combo, weight, hand_str), ...]
        self.oop_combos = self._filter_combos(oop_range)
        self.ip_combos = self._filter_combos(ip_range)
        
        # **手牌级别**的 CFR 数据结构
        # regrets[node][hand_str][action] = float
        self.regrets: Dict[Node, Dict[str, Dict[Action, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        # cumulative_strategies[node][hand_str][action] = float
        self.cumulative_strategies: Dict[Node, Dict[str, Dict[Action, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        
        # 建立 hand_str -> combos 映射
        self.oop_hand_combos: Dict[str, List[Tuple]] = defaultdict(list)
        self.ip_hand_combos: Dict[str, List[Tuple]] = defaultdict(list)
        for combo, weight, hand_str in self.oop_combos:
            self.oop_hand_combos[hand_str].append((combo, weight))
        for combo, weight, hand_str in self.ip_combos:
            self.ip_hand_combos[hand_str].append((combo, weight))
    
    def _filter_combos(self, range_obj: HandRange) -> List[Tuple]:
        """过滤出与 board 不冲突的 combos，返回 (combo, weight, hand_str)"""
        valid_combos = []
        for hand_str, weight in range_obj.weights.items():
            if weight <= 0:
                continue
            combos = self.all_combos.get(hand_str, [])
            for combo in combos:
                if not cards_conflict(list(combo), self.board):
                    valid_combos.append((combo, weight, hand_str))
        return valid_combos
    
    def solve(self, iterations: int = 1000, callback: Optional[Callable] = None):
        """运行 DCFR 迭代"""
        clear_equity_cache()
        update_interval = max(1, iterations // 100)
        
        for t in range(1, iterations + 1):
            # 为每个手牌分别运行 CFR
            for player in [0, 1]:
                combos = self.oop_combos if player == 0 else self.ip_combos
                # MVP: 采样部分手牌以加速
                sample_size = min(20, len(combos))
                sampled = random.sample(combos, sample_size) if len(combos) > sample_size else combos
                
                for combo, weight, hand_str in sampled:
                    self._cfr_traversal_hand(
                        self.tree, player, hand_str, combo, weight, 1.0, t
                    )
            
            # 应用 discount
            self._apply_discount(t)
            
            if callback and (t % update_interval == 0 or t == iterations):
                callback(t, None)
    
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
        if node.is_terminal:
            return self._terminal_ev_hand(node, player, combo, weight)
        
        if node.player == player:
            return self._player_node_cfr_hand(
                node, player, hand_str, combo, weight, reach_prob, iteration
            )
        else:
            return self._opponent_node_cfr_hand(
                node, player, hand_str, combo, weight, reach_prob, iteration
            )
    
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
        """当前玩家决策节点的 CFR（手牌级别）"""
        strategy = self._get_current_strategy_hand(node, hand_str)
        node_util = 0.0
        action_utils = {}
        
        for action in node.actions:
            child = node.children[action]
            new_reach = reach_prob * strategy[action]
            
            action_util = self._cfr_traversal_hand(
                child, player, hand_str, combo, weight, new_reach, iteration
            )
            action_utils[action] = action_util
            node_util += strategy[action] * action_util
        
        # 更新该手牌的 regrets
        for action in node.actions:
            regret = action_utils[action] - node_util
            self.regrets[node][hand_str][action] += regret * reach_prob
        
        # 更新累计策略
        for action in strategy:
            self.cumulative_strategies[node][hand_str][action] += strategy[action] * reach_prob
        
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
        """对手决策节点的 CFR（手牌级别）"""
        # 对手使用平均策略
        strategy = self._get_average_opponent_strategy(node)
        node_util = 0.0
        
        for action in node.actions:
            child = node.children[action]
            action_util = self._cfr_traversal_hand(
                child, player, hand_str, combo, weight, reach_prob, iteration
            )
            node_util += strategy[action] * action_util
        
        return node_util
    
    def _get_current_strategy_hand(self, node: Node, hand_str: str) -> Dict[Action, float]:
        """获取特定手牌的当前策略（基于 regrets）"""
        strategy = {}
        normalizing_sum = 0.0
        
        for action in node.actions:
            regret = self.regrets[node][hand_str][action]
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
    
    def _get_average_opponent_strategy(self, node: Node) -> Dict[Action, float]:
        """获取对手的平均策略（聚合所有手牌）"""
        # 聚合所有手牌的累计策略
        total_strategy = defaultdict(float)
        
        hand_combos = self.ip_hand_combos if node.player == 1 else self.oop_hand_combos
        
        for hand_str in hand_combos.keys():
            if node in self.cumulative_strategies and hand_str in self.cumulative_strategies[node]:
                for action, count in self.cumulative_strategies[node][hand_str].items():
                    total_strategy[action] += count
        
        total = sum(total_strategy.values())
        if total > 0:
            return {action: count / total for action, count in total_strategy.items()}
        else:
            # 均匀随机
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
            ev = state.stacks[player] - initial_stack
            return ev
        
        # Showdown: 计算 equity
        opponent_combos = self.ip_combos if player == 0 else self.oop_combos
        
        total_ev = 0.0
        total_weight = 0.0
        
        # 采样对手手牌计算 EV
        max_samples = 8
        sampled = random.sample(opponent_combos, min(max_samples, len(opponent_combos)))
        
        for opp_combo, opp_weight, _ in sampled:
            if cards_conflict(list(combo), list(opp_combo)):
                continue
            
            equity = calculate_equity(
                list(combo),
                list(opp_combo),
                state.board,
                num_simulations=5
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
        
        for node in list(self.regrets.keys()):
            for hand_str in list(self.regrets[node].keys()):
                for action in list(self.regrets[node][hand_str].keys()):
                    self.regrets[node][hand_str][action] *= discount
    
    def get_strategy(self) -> Dict[Node, Dict[Action, float]]:
        """获取节点级别的平均策略（兼容旧接口）"""
        avg_strategy = {}
        self._collect_node_strategy(self.tree, avg_strategy)
        return avg_strategy
    
    def _collect_node_strategy(self, node: Node, avg_strategy: Dict):
        """递归收集节点级别策略"""
        if node.is_terminal:
            return
        
        # 聚合所有手牌的策略
        total_strategy = defaultdict(float)
        hand_combos = self.oop_hand_combos if node.player == 0 else self.ip_hand_combos
        
        for hand_str in hand_combos.keys():
            if node in self.cumulative_strategies and hand_str in self.cumulative_strategies[node]:
                for action, count in self.cumulative_strategies[node][hand_str].items():
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
        """获取手牌级别的策略
        返回: {hand_str: {action_str: freq}}
        """
        if node is None:
            node = self.tree
        
        hand_strategy = {}
        hand_combos = self.oop_hand_combos if node.player == 0 else self.ip_hand_combos
        
        for hand_str in hand_combos.keys():
            if node in self.cumulative_strategies and hand_str in self.cumulative_strategies[node]:
                cum = self.cumulative_strategies[node][hand_str]
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
                # 没有累计策略，使用均匀分布
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

