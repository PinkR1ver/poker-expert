"""
Solver 核心数据结构
"""
from dataclasses import dataclass
from typing import Optional, Dict, List


@dataclass
class Card:
    """单张牌"""
    rank: int  # 0-12 (2-A)
    suit: int  # 0-3 (c,d,h,s)
    
    def __str__(self):
        ranks = "23456789TJQKA"
        suits = "cdhs"
        # rank 已经是 0-12 索引
        if 0 <= self.rank < 13:
            return f"{ranks[self.rank]}{suits[self.suit]}"
        return f"?{self.rank}{suits[self.suit]}"
    
    def __hash__(self):
        return hash((self.rank, self.suit))
    
    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return self.rank == other.rank and self.suit == other.suit


@dataclass
class HandRange:
    """13x13 矩阵表示的 range，每个 combo 有权重 0-1"""
    weights: Dict[str, float]  # {"AA": 1.0, "AKs": 0.5, ...}
    
    def get_weight(self, combo: str) -> float:
        """获取 combo 的权重"""
        return self.weights.get(combo, 0.0)
    
    def normalize(self):
        """归一化权重到 [0, 1]"""
        max_weight = max(self.weights.values()) if self.weights else 1.0
        if max_weight > 0:
            self.weights = {k: v / max_weight for k, v in self.weights.items()}


@dataclass
class GameState:
    """游戏状态"""
    pot: float
    stacks: List[float]  # [OOP_stack, IP_stack]
    board: List[Card]
    street: str  # "flop", "turn", "river"
    to_call: float = 0.0  # 当前需要 call 的金额
    last_bet: float = 0.0  # 最后一次 bet 的金额
    last_action: Optional[str] = None  # 上一个 action 类型（用于检测连续 check/call）
    
    def copy(self):
        """深拷贝"""
        return GameState(
            pot=self.pot,
            stacks=self.stacks.copy(),
            board=self.board.copy(),
            street=self.street,
            to_call=self.to_call,
            last_bet=self.last_bet,
            last_action=self.last_action
        )


@dataclass
class Action:
    """行动"""
    type: str  # "fold", "check", "call", "bet", "raise"
    size: float  # pot 百分比（对于 bet/raise）或绝对金额
    
    def __str__(self):
        if self.type in ["bet", "raise"]:
            return f"{self.type} {self.size:.0%}"
        return self.type
    
    def __hash__(self):
        return hash((self.type, self.size))
    
    def __eq__(self, other):
        if not isinstance(other, Action):
            return False
        return self.type == other.type and abs(self.size - other.size) < 1e-6


@dataclass
class Node:
    """Game tree 节点"""
    state: GameState
    player: int  # 0=OOP, 1=IP, -1=chance
    actions: List[Action]
    children: Dict[Action, 'Node']
    is_terminal: bool = False
    ev: Optional[float] = None  # 该节点的 EV（对于 terminal node）
    node_type: str = "player"  # "player", "chance", "terminal"
    
    # Chance node 专用字段
    chance_cards: Optional[List[Card]] = None  # 可能的牌
    chance_children: Optional[Dict[Card, 'Node']] = None  # card -> child node
    
    # 用于 Card Abstraction 的桶 ID
    # 前期迭代中，相同 bucket_id 的节点共享策略
    bucket_id: int = -1
    
    def __hash__(self):
        # 使用 state 的关键信息作为 hash
        board_str = "".join(str(c) for c in self.state.board)
        return hash((
            self.player,
            self.state.pot,
            tuple(self.state.stacks),
            self.state.street,
            self.state.to_call,
            board_str,
            self.node_type
        ))



