"""
Game Tree 构建器 - 根据 bet sizing 配置生成完整的游戏树
"""
from solver.data_types import GameState, Action, Node, Card
from typing import List, Dict, Set
from collections import defaultdict


class GameTreeBuilder:
    """构建 postflop game tree"""
    
    def __init__(
        self,
        pot: float,
        stacks: List[float],  # [OOP, IP]
        board: List[Card],
        bet_sizes: List[float],  # pot 百分比列表，如 [0.25, 0.5, 0.75, 1.0]
        raise_sizes: List[float],  # pot 百分比列表
        max_raises: int = 3,  # 最大 raise 次数
        street: str = "flop"
    ):
        self.pot = pot
        self.stacks = stacks.copy()
        self.board = board.copy()
        self.bet_sizes = sorted(bet_sizes)
        self.raise_sizes = sorted(raise_sizes)
        self.max_raises = max_raises
        self.street = street
        
        # 跟踪每个节点的 raise 次数
        self.raise_counts: Dict[Node, int] = {}
    
    def build_tree(self) -> Node:
        """构建完整的 game tree，返回根节点"""
        initial_state = GameState(
            pot=self.pot,
            stacks=self.stacks.copy(),
            board=self.board.copy(),
            street=self.street,
            to_call=0.0,
            last_bet=0.0
        )
        
        root = Node(
            state=initial_state,
            player=0,  # OOP 先行动
            actions=[],
            children={},
            is_terminal=False
        )
        
        self.raise_counts[root] = 0
        self._build_node(root)
        
        return root
    
    def _build_node(self, node: Node):
        """递归构建节点"""
        state = node.state
        player = node.player
        raise_count = self.raise_counts.get(node, 0)
        
        # 检查是否 terminal
        if self._is_terminal(state, raise_count):
            node.is_terminal = True
            return
        
        # 生成可用 actions
        actions = self._get_available_actions(state, player, raise_count)
        node.actions = actions
        
        # 如果没有可用 actions，标记为 terminal
        if not actions:
            node.is_terminal = True
            return
        
        # 为每个 action 创建子节点
        for action in actions:
            child_state = self._apply_action(state, action, player)
            child_player = 1 - player  # 切换玩家
            
            child = Node(
                state=child_state,
                player=child_player,
                actions=[],
                children={},
                is_terminal=False
            )
            
            # 更新 raise count
            if action.type in ["bet", "raise"]:
                child_raise_count = raise_count + 1
            else:
                child_raise_count = raise_count
            
            self.raise_counts[child] = child_raise_count
            node.children[action] = child
            
            # 检查 check-check 情况：如果当前 action 是 check 且上一个 action 也是 check
            # 那么子节点是 terminal (showdown)
            if action.type == "check" and state.last_action == "check":
                child.is_terminal = True
                continue
            
            # 递归构建子节点
            self._build_node(child)
    
    def _is_terminal(self, state: GameState, raise_count: int) -> bool:
        """判断节点是否 terminal"""
        # Fold 后是 terminal
        if state.last_action == "fold":
            return True
        
        # Call 后是 terminal（showdown）
        if state.last_action == "call":
            return True
        
        return False
    
    def _get_available_actions(self, state: GameState, player: int, raise_count: int) -> List[Action]:
        """获取当前节点的可用 actions"""
        actions = []
        player_stack = state.stacks[player]
        
        # 检查是否可以 check
        if state.to_call == 0:
            actions.append(Action(type="check", size=0.0))
        
        # 检查是否可以 fold/call
        if state.to_call > 0:
            actions.append(Action(type="fold", size=0.0))
            call_amount = min(state.to_call, player_stack)
            actions.append(Action(type="call", size=call_amount))
        
        # 检查是否可以 bet/raise（受 max_raises 限制）
        if raise_count >= self.max_raises:
            # 达到最大 raise 次数，不能再 bet/raise
            return actions
        
        current_pot = state.pot
        
        if state.to_call == 0:
            # 可以 bet
            for bet_size_pct in self.bet_sizes:
                bet_amount = current_pot * bet_size_pct
                if bet_amount <= player_stack:
                    actions.append(Action(type="bet", size=bet_size_pct))
        else:
            # 可以 raise
            for raise_size_pct in self.raise_sizes:
                # raise 的金额是相对于当前 pot + to_call 的
                raise_pot = current_pot + state.to_call
                raise_amount = raise_pot * raise_size_pct
                total_cost = state.to_call + raise_amount
                
                if total_cost <= player_stack:
                    actions.append(Action(type="raise", size=raise_size_pct))
        
        return actions
    
    def _apply_action(self, state: GameState, action: Action, player: int) -> GameState:
        """应用 action，返回新的 state"""
        new_state = state.copy()
        new_state.last_action = action.type  # 记录当前 action
        
        if action.type == "fold":
            # Fold - 对手赢得 pot
            new_state.stacks[1 - player] += new_state.pot
            new_state.pot = 0
            new_state.to_call = 0
            new_state.last_bet = 0
        
        elif action.type == "check":
            # Check - 如果双方都 check，进入下一街（MVP 中这是 terminal）
            new_state.to_call = 0
            new_state.last_bet = 0
        
        elif action.type == "call":
            # Call - 投入 to_call 的金额
            call_amount = min(new_state.to_call, new_state.stacks[player])
            new_state.stacks[player] -= call_amount
            new_state.pot += call_amount
            new_state.to_call = 0
            new_state.last_bet = 0
        
        elif action.type == "bet":
            # Bet - 投入 bet 金额
            bet_amount = new_state.pot * action.size
            bet_amount = min(bet_amount, new_state.stacks[player])
            new_state.stacks[player] -= bet_amount
            new_state.pot += bet_amount
            new_state.to_call = bet_amount
            new_state.last_bet = bet_amount
        
        elif action.type == "raise":
            # Raise - 先 call，再 raise
            call_amount = min(new_state.to_call, new_state.stacks[player])
            new_state.stacks[player] -= call_amount
            new_state.pot += call_amount
            
            raise_pot = new_state.pot
            raise_amount = raise_pot * action.size
            raise_amount = min(raise_amount, new_state.stacks[player])
            new_state.stacks[player] -= raise_amount
            new_state.pot += raise_amount
            new_state.to_call = raise_amount
            new_state.last_bet = raise_amount
        
        return new_state

