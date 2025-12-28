"""
Game Tree 构建器 - 支持完整多街（Flop → Turn → River）
"""
from solver.data_types import GameState, Action, Node, Card
from typing import List, Dict, Set, Optional
from collections import defaultdict


class GameTreeBuilder:
    """构建完整多街 postflop game tree"""
    
    # 所有可能的牌
    ALL_CARDS = [Card(rank=r, suit=s) for r in range(2, 15) for s in range(4)]
    
    # Street progression
    STREET_ORDER = ["flop", "turn", "river"]
    
    def __init__(
        self,
        pot: float,
        stacks: List[float],  # [OOP, IP]
        board: List[Card],
        bet_sizes: List[float],  # pot 百分比列表，如 [0.25, 0.5, 0.75, 1.0]
        raise_sizes: List[float],  # pot 百分比列表
        max_raises: int = 2,  # 最大 raise 次数（每条街）
        street: str = "flop",
        # Card abstraction options
        use_card_abstraction: bool = True,
        abstraction_buckets: int = 4  # 减少 bucket 数量以加速
    ):
        self.pot = pot
        self.stacks = stacks.copy()
        self.board = board.copy()
        # 不限制 bet/raise sizes
        self.bet_sizes = sorted(bet_sizes)
        self.raise_sizes = sorted(raise_sizes)
        self.max_raises = max_raises
        self.start_street = street
        
        # Card abstraction
        self.use_card_abstraction = use_card_abstraction
        self.abstraction_buckets = abstraction_buckets
        
        # 跟踪树的统计信息
        self.node_count = 0
        self.chance_node_count = 0
        self.terminal_node_count = 0
        
        print(f"[GameTree] Building tree: pot={pot}, street={street}, bet_sizes={self.bet_sizes}, raise_sizes={self.raise_sizes}")
    
    def build_tree(self) -> Node:
        """构建完整的多街 game tree，返回根节点"""
        print(f"[GameTree] Starting tree construction...")
        
        initial_state = GameState(
            pot=self.pot,
            stacks=self.stacks.copy(),
            board=self.board.copy(),
            street=self.start_street,
            to_call=0.0,
            last_bet=0.0
        )
        
        root = Node(
            state=initial_state,
            player=0,  # OOP 先行动
            actions=[],
            children={},
            is_terminal=False,
            node_type="player"
        )
        
        self._build_node(root, raise_count=0)
        
        print(f"[GameTree] Tree built: {self.node_count} nodes, {self.chance_node_count} chance nodes, {self.terminal_node_count} terminals")
        
        return root
    
    def _build_node(self, node: Node, raise_count: int):
        """递归构建节点"""
        self.node_count += 1
        state = node.state
        player = node.player
        
        # 检查是否 terminal（fold 或 River showdown）
        if self._is_final_terminal(state):
            node.is_terminal = True
            node.node_type = "terminal"
            self.terminal_node_count += 1
            return
        
        # 检查是否需要创建 Chance Node（街结束，进入下一街）
        if self._should_create_chance_node(state):
            self._create_chance_node(node, state)
            return
        
        # 普通决策节点
        actions = self._get_available_actions(state, player, raise_count)
        node.actions = actions
        
        if not actions:
            node.is_terminal = True
            node.node_type = "terminal"
            self.terminal_node_count += 1
            return
        
        for action in actions:
            child_state = self._apply_action(state, action, player)
            child_player = 1 - player
            
            child = Node(
                state=child_state,
                player=child_player,
                actions=[],
                children={},
                is_terminal=False,
                node_type="player"
            )
            
            # 更新 raise count（每条街独立计数）
            new_raise_count = raise_count + 1 if action.type in ["bet", "raise"] else raise_count
            
            node.children[action] = child
            
            # Check-check 情况特殊处理
            if action.type == "check" and state.last_action == "check":
                # 双方 check，进入下一街或 showdown
                if child_state.street != "river":
                    # 不是 River，创建 Chance Node 进入下一街
                    self._create_chance_node(child, child_state)
                else:
                    # River showdown
                    child.is_terminal = True
                    child.node_type = "terminal"
                    self.terminal_node_count += 1
                continue
            
            self._build_node(child, new_raise_count)
    
    def _is_final_terminal(self, state: GameState) -> bool:
        """判断是否最终 terminal（fold 或 River showdown）"""
        if state.last_action == "fold":
            return True
        
        # River 上 call 是 showdown
        if state.last_action == "call" and state.street == "river":
            return True
        
        return False
    
    def _should_create_chance_node(self, state: GameState) -> bool:
        """判断是否需要创建 Chance Node（街结束）"""
        # 已经是 River，不需要
        if state.street == "river":
            return False
        
        # Call 后进入下一街
        if state.last_action == "call":
            return True
        
        # Check-check 后进入下一街（在 _build_node 中处理）
        return False
    
    def _create_chance_node(self, node: Node, state: GameState):
        """创建 Chance Node，包含所有可能的下一张牌"""
        self.chance_node_count += 1
        node.node_type = "chance"
        node.player = -1  # Chance node
        
        # 确定下一条街
        current_idx = self.STREET_ORDER.index(state.street)
        next_street = self.STREET_ORDER[current_idx + 1]
        
        # 获取可用的牌（排除 board 已有的）
        used_cards = set(state.board)
        available_cards = [c for c in self.ALL_CARDS if c not in used_cards]
        
        # Card Abstraction：将牌分组
        if self.use_card_abstraction:
            card_buckets = self._create_card_buckets(available_cards, state.board)
            node.chance_cards = list(card_buckets.keys())  # 代表牌
            node.chance_children = {}
            
            for representative, cards in card_buckets.items():
                # 为每个 bucket 创建一个子节点
                child_state = self._create_next_street_state(state, representative, next_street)
                
                child = Node(
                    state=child_state,
                    player=0,  # 下一街 OOP 先行动
                    actions=[],
                    children={},
                    is_terminal=False,
                    node_type="player"
                )
                
                node.chance_children[representative] = child
                
                # 递归构建子树（新的街，raise count 重置）
                self._build_node(child, raise_count=0)
        else:
            # 完整展开所有牌（非常慢）
            node.chance_cards = available_cards
            node.chance_children = {}
            
            for card in available_cards:
                child_state = self._create_next_street_state(state, card, next_street)
                
                child = Node(
                    state=child_state,
                    player=0,
                    actions=[],
                    children={},
                    is_terminal=False,
                    node_type="player"
                )
                
                node.chance_children[card] = child
                self._build_node(child, raise_count=0)
    
    def _create_card_buckets(self, available_cards: List[Card], board: List[Card]) -> Dict[Card, List[Card]]:
        """
        Card Abstraction：将牌分组
        
        策略：按 rank 分组，每个 rank 一个 bucket（最多 13 个）
        同一 rank 的不同花色卡映射到同一个 bucket
        
        这样可以在保持合理计算量的同时，区分不同 rank 的影响
        """
        buckets = defaultdict(list)
        
        for card in available_cards:
            # 按 rank 分组
            rank_key = card.rank
            buckets[rank_key].append(card)
        
        # 转换为 {representative_card: [cards]}
        result = {}
        for rank_key, cards in buckets.items():
            if cards:
                # 选择第一张卡作为代表
                representative = cards[0]
                result[representative] = cards
        
        return result
    
    def _create_next_street_state(self, state: GameState, new_card: Card, next_street: str) -> GameState:
        """创建进入下一街的状态"""
        new_state = state.copy()
        new_state.board = state.board.copy() + [new_card]
        new_state.street = next_street
        new_state.to_call = 0.0
        new_state.last_bet = 0.0
        new_state.last_action = None
        return new_state
    
    def _get_available_actions(self, state: GameState, player: int, raise_count: int) -> List[Action]:
        """获取当前节点的可用 actions
        
        考虑 effective stack（双方中较小的筹码）来限制 bet/raise 尺度
        """
        actions = []
        player_stack = state.stacks[player]
        opponent_stack = state.stacks[1 - player]
        
        # Effective stack: 双方中较小的筹码（决定了最大可能的 action）
        effective_stack = min(player_stack, opponent_stack)
        
        # 检查是否可以 check
        if state.to_call == 0:
            actions.append(Action(type="check", size=0.0))
        
        # 检查是否可以 fold/call
        if state.to_call > 0:
            actions.append(Action(type="fold", size=0.0))
            call_amount = min(state.to_call, player_stack)
            actions.append(Action(type="call", size=call_amount))
            
            # 如果 call 就 all-in 了，不需要其他 raise 选项
            if call_amount >= player_stack:
                return actions
        
        # 检查是否可以 bet/raise
        if raise_count >= self.max_raises:
            return actions
        
        # 如果 effective stack 很小，直接只提供 all-in
        current_pot = state.pot
        min_bet = current_pot * 0.2  # 最小 bet 大约 20% pot
        
        if effective_stack <= min_bet:
            # 筹码太少，只能 all-in
            if player_stack > state.to_call:
                actions.append(Action(type="allin", size=player_stack))
            return actions
        
        added_sizes = set()  # 避免重复尺度
        
        if state.to_call == 0:
            # Bet 场景
            for bet_size_pct in self.bet_sizes:
                bet_amount = current_pot * bet_size_pct
                
                # 用 effective stack 限制
                if bet_amount <= effective_stack:
                    actions.append(Action(type="bet", size=bet_size_pct))
                    added_sizes.add(bet_size_pct)
            
            # 如果没有任何 bet 能放下，或者最大 bet 小于 effective stack，添加 all-in
            max_bet_added = max(added_sizes) if added_sizes else 0
            if effective_stack > current_pot * max_bet_added * 1.2:  # 留有余地才添加 all-in
                if player_stack > 0:
                    allin_pct = player_stack / current_pot if current_pot > 0 else 1.0
                    actions.append(Action(type="allin", size=allin_pct))
        else:
            # Raise 场景
            for raise_size_pct in self.raise_sizes:
                raise_pot = current_pot + state.to_call
                raise_amount = raise_pot * raise_size_pct
                total_cost = state.to_call + raise_amount
                
                # 用 effective stack 限制
                if total_cost <= effective_stack:
                    actions.append(Action(type="raise", size=raise_size_pct))
                    added_sizes.add(raise_size_pct)
            
            # 如果有足够筹码但没有合适的 raise size，添加 all-in
            if player_stack > state.to_call:
                max_raise_cost = max((current_pot + state.to_call) * s + state.to_call 
                                     for s in added_sizes) if added_sizes else 0
                if effective_stack > max_raise_cost * 1.2:
                    allin_pct = (player_stack - state.to_call) / (current_pot + state.to_call)
                    actions.append(Action(type="allin", size=allin_pct))
        
        return actions
    
    def _apply_action(self, state: GameState, action: Action, player: int) -> GameState:
        """应用 action，返回新的 state"""
        new_state = state.copy()
        new_state.last_action = action.type
        
        if action.type == "fold":
            new_state.stacks[1 - player] += new_state.pot
            new_state.pot = 0
            new_state.to_call = 0
            new_state.last_bet = 0
        
        elif action.type == "check":
            new_state.to_call = 0
            new_state.last_bet = 0
        
        elif action.type == "call":
            call_amount = min(new_state.to_call, new_state.stacks[player])
            new_state.stacks[player] -= call_amount
            new_state.pot += call_amount
            new_state.to_call = 0
            new_state.last_bet = 0
        
        elif action.type == "bet":
            bet_amount = new_state.pot * action.size
            bet_amount = min(bet_amount, new_state.stacks[player])
            new_state.stacks[player] -= bet_amount
            new_state.pot += bet_amount
            new_state.to_call = bet_amount
            new_state.last_bet = bet_amount
        
        elif action.type == "raise":
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
        
        elif action.type == "allin":
            # All-in: 投入所有剩余筹码
            # 先 call（如果有 to_call）
            call_amount = min(new_state.to_call, new_state.stacks[player])
            new_state.stacks[player] -= call_amount
            new_state.pot += call_amount
            
            # 剩余筹码全部投入
            remaining = new_state.stacks[player]
            new_state.stacks[player] = 0
            new_state.pot += remaining
            new_state.to_call = remaining  # 对手需要 call 的金额
            new_state.last_bet = remaining
        
        return new_state
    
    def get_stats(self) -> Dict:
        """获取树的统计信息"""
        return {
            "total_nodes": self.node_count,
            "chance_nodes": self.chance_node_count,
            "terminal_nodes": self.terminal_node_count,
            "player_nodes": self.node_count - self.chance_node_count - self.terminal_node_count
        }

