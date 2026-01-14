"""
C++ CFR Engine 的 Python Wrapper

提供与 DCFREngine 兼容的接口，自动使用 C++ 加速。
如果 C++ 扩展不可用，自动回退到 Python 实现。
"""
from solver.core.data_types import Node, Action, HandRange, Card
from solver.core.card_utils import get_all_combos, cards_conflict
from typing import Dict, List, Callable, Optional, Tuple
import os
import sys
import importlib.util
import traceback

# --- 核心修复：强制路径检测与加载 ---
_USE_CPP = False
_cpp = None

def _try_load_cpp():
    global _USE_CPP, _cpp
    
    # 1. 尝试标准导入
    try:
        from . import poker_solver_cpp as m
        _cpp = m
        _USE_CPP = True
        print("[CFR] Using C++ CFR Engine (Standard Import)")
        return
    except ImportError:
        pass

    # 2. 强制路径探测加载
    try:
        # 获取当前文件所在目录 (bridge 目录)，其父目录包含 .so 文件
        bridge_dir = os.path.dirname(os.path.abspath(__file__))
        target_dir = os.path.dirname(bridge_dir)
        
        # 寻找匹配当前 Python 版本的 .so 文件
        suffix = f"cpython-{sys.version_info.major}{sys.version_info.minor}"
        target_name = None
        for f in os.listdir(target_dir):
            if f.startswith("poker_solver_cpp") and suffix in f and f.endswith(".so"):
                target_name = f
                break
        
        if target_name:
            so_path = os.path.join(target_dir, target_name)
            # 动态加载模块
            spec = importlib.util.spec_from_file_location("poker_solver_cpp", so_path)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            _cpp = m
            _USE_CPP = True
            print(f"[CFR] Using C++ CFR Engine (Forced Load: {target_name})")
        else:
            print("[CFR] C++ extension file not found in solver directory.")
    except Exception as e:
        print(f"[CFR] C++ extension loading failed: {e}")

# 执行加载
_try_load_cpp()
# --------------------------------

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

class NodeProxy:
    """C++ 节点的 Python 代理对象，模拟 solver.data_types.Node 的行为"""
    def __init__(self, engine, node_id):
        self._engine = engine
        self._node_id = node_id
        self._data = None  # 延迟加载
        self._children_cache = None
        self._chance_children_cache = None
        self._state_cache = None

    def _ensure_data(self):
        if self._data is None:
            try:
                # 获取数据时确保 GIL
                self._data = self._engine._engine.get_node_data(self._node_id)
            except Exception as e:
                print(f"[NodeProxy] CRITICAL: Error fetching node data for {self._node_id}: {e}")
                self._data = {}

    @property
    def node_id(self): return self._node_id
    
    @property
    def player(self):
        self._ensure_data()
        return self._data.get('player', 0)
    
    @property
    def node_type(self):
        self._ensure_data()
        return self._data.get('type', 'player')
    
    @property
    def is_terminal(self): return self.node_type == "terminal"
    
    @property
    def actions(self):
        self._ensure_data()
        return self._data.get('actions', [])
    
    @property
    def children(self):
        if self._children_cache is None:
            self._ensure_data()
            ids = self._data.get('child_ids', [])
            actions = self.actions
            self._children_cache = {}
            for i in range(min(len(ids), len(actions))):
                self._children_cache[actions[i]] = NodeProxy(self._engine, ids[i])
        return self._children_cache
    
    @property
    def state(self):
        if self._state_cache is None:
            self._ensure_data()
            class StateProxy:
                def __init__(self, data):
                    self.pot = data.get('pot', 0.0)
                    self.stacks = data.get('stacks', [0.0, 0.0])
                    # 使用内部缓存，避免重复创建 Card 对象
                    board_cards = [Card(c[0], c[1]) for c in data.get('board', [])]
                    self.board = board_cards
                    # 修正：根据 Board 长度强制判定街道
                    blen = len(board_cards)
                    if blen == 3: self.street = "flop"
                    elif blen == 4: self.street = "turn"
                    else: self.street = "river"
                    self.to_call = data.get('to_call', 0.0)
            self._state_cache = StateProxy(self._data)
        return self._state_cache

    @property
    def chance_children(self):
        if self._chance_children_cache is None:
            self._ensure_data()
            if self.node_type != "chance": return None
            
            card_data = self._data.get('chance_cards', [])
            ids = self._data.get('chance_child_ids', [])
            
            self._chance_children_cache = {}
            for i in range(min(len(card_data), len(ids))):
                card = Card(card_data[i][0], card_data[i][1])
                self._chance_children_cache[card] = NodeProxy(self._engine, ids[i])
        return self._chance_children_cache

    def __hash__(self): return hash(self._node_id)
    def __eq__(self, other):
        if isinstance(other, int): return self._node_id == other
        if hasattr(other, 'node_id'): return self._node_id == other.node_id
        return False

class CppDCFREngine:
    """C++ 加速的 DCFR 引擎
    
    与 DCFREngine 兼容的接口，内部使用 C++ 实现加速。
    """
    
    def __init__(
        self,
        game_tree: Optional[Node],
        oop_range: HandRange,
        ip_range: HandRange,
        board: List[Card],
        alpha: float = 1.5,
        beta: float = 0.0,
        gamma: float = 2.0,
        betting_config: Optional[Dict] = None
    ):
        if not _USE_CPP:
            raise RuntimeError("C++ extension not loaded")
        
        try:
            self.tree = game_tree
            self.oop_range = oop_range
            self.ip_range = ip_range
            self.board = board
            
            # 创建 C++ 引擎
            self._engine = _cpp.CFREngine()
            
            # 如果提供了 betting_config，直接在 C++ 中建树
            if betting_config:
                print("[CFR] Building tree in C++ (Using disk-backed buffer)...")
                
                # 安全获取 sizing
                bet_cfg = betting_config.get('bet_sizes', {})
                raise_cfg = betting_config.get('raise_sizes', {})
                
                self._engine.build_tree_cpp(
                    pot=float(betting_config['pot']),
                    oop_stack=float(betting_config['stacks'][0]),
                    ip_stack=float(betting_config['stacks'][1]),
                    flop_bet_sizes=[float(s) for s in bet_cfg.get('flop', [0.33, 0.67])],
                    flop_raise_sizes=[float(s) for s in raise_cfg.get('flop', [0.5, 1.0])],
                    turn_bet_sizes=[float(s) for s in bet_cfg.get('turn', [0.33, 0.67])],
                    turn_raise_sizes=[float(s) for s in raise_cfg.get('turn', [0.5, 1.0])],
                    river_bet_sizes=[float(s) for s in bet_cfg.get('river', [0.33, 0.67])],
                    river_raise_sizes=[float(s) for s in raise_cfg.get('river', [0.5, 1.0])],
                    initial_board=[(c.rank, c.suit) for c in board],
                    max_raises=int(betting_config.get('max_raises', 2))
                )
                # 使用 Proxy 对象作为根节点
                self.tree = NodeProxy(self, 0)
                print(f"[CFR] C++ Tree built with {self._engine.node_count} nodes.")
            elif game_tree:
                print("[CFR] Converting Python tree to C++ (Warning: legacy path)...")
                self._engine.build_tree_from_python(game_tree)
            else:
                raise ValueError("Either betting_config or game_tree must be provided")
            
            # 存储所有 combos
            self.all_combos = get_all_combos()
            
            # 过滤有效的 combos
            self.oop_combos = self._filter_combos(oop_range)
            self.ip_combos = self._filter_combos(ip_range)
            
            # 设置 ranges
            oop_cpp = self._range_to_cpp(self.oop_combos)
            ip_cpp = self._range_to_cpp(self.ip_combos)
            self._engine.set_oop_range(oop_cpp)
            self._engine.set_ip_range(ip_cpp)
            
            # 设置 board
            board_cpp = [(c.rank, c.suit) for c in board]
            self._engine.set_board(board_cpp)
            
            # 迭代统计
            self._iteration_regrets = []
        except Exception as e:
            print(f"[CFR] CppDCFREngine initialization error: {e}")
            traceback.print_exc()
            raise
    
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
    
    def _range_to_cpp(self, combos: List[Tuple]) -> List[Tuple]:
        """转换 combos 到 C++ 格式"""
        result = []
        for combo, weight, hand_str in combos:
            c1, c2 = combo
            result.append((c1.rank, c1.suit, c2.rank, c2.suit, weight, hand_str))
        return result
    
    def solve(
        self, 
        iterations: int = 1000, 
        callback: Optional[Callable] = None,
        parallel: bool = True
    ):
        """运行 DCFR 迭代"""
        def cpp_callback(current: int, total: int):
            if callback:
                callback(current, total)
        
        self._engine.solve(iterations, cpp_callback if callback else None)
        
        # 获取 regret 历史
        self._iteration_regrets = self._engine.get_regret_history()
    
    def get_strategy(self) -> Dict:
        return {"status": "computed_in_cpp"}
    
    def get_node_data(self, node_id: int) -> Dict:
        log_debug("H1", "engine.get_node_data start", "cpp_cfr_wrapper.py:258", {"node_id": node_id})
        try:
            res = self._engine.get_node_data(node_id)
            log_debug("H1", "engine.get_node_data end", "cpp_cfr_wrapper.py:261")
            return res
        except Exception as e:
            log_debug("H1", "engine.get_node_data crash", "cpp_cfr_wrapper.py:264", {"error": str(e)})
            raise

    def get_hand_strategy(self, node) -> Dict[str, Dict[str, float]]:
        """获取特定节点的手牌策略"""
        node_id = -1
        if isinstance(node, int):
            node_id = node
        elif hasattr(node, 'node_id'):
            node_id = node.node_id
        else:
            return {}
            
        if node_id < 0:
            return {}
        
        # 获取动作名称
        action_names = []
        if hasattr(node, 'actions'):
            action_names = node.actions
        else:
            try:
                data = self._engine.get_node_data(node_id)
                action_names = data.get('actions', [])
            except: pass
        
        if not action_names:
            return {}

        # 获取原始策略 (Dict[str, List[float]])
        # 现在 C++ 端返回的是未归一化的累加值，且已按 shorthand 合并
        raw_strategies = self._engine.get_node_hand_strategies(node_id)
        
        # 转换为 UI 期望的 Dict[str, Dict[str, float]] 格式，并进行归一化
        result = {}
        for hand, counts in raw_strategies.items():
            total = sum(counts)
            hand_strat = {}
            if total > 0:
                for i, c in enumerate(counts):
                    if i < len(action_names):
                        hand_strat[action_names[i]] = c / total
            else:
                # 理论上不会发生，作为兜底
                avg = 1.0 / len(action_names)
                hand_strat = {a: avg for a in action_names}
            result[hand] = hand_strat
            
        # 核心修复：如果某手牌完全没被采样，提供均匀分布作为 Fallback
        # 这样可以防止 UI 层的 Range 更新逻辑因为找不到手牌而将其权重设为 0
        current_player = "OOP" if (getattr(node, 'player', 0) == 0) else "IP"
        full_range = self.oop_range if current_player == "OOP" else self.ip_range
        
        avg_strat = {a: 1.0 / len(action_names) for a in action_names}
        for hand_str in full_range.weights.keys():
            if hand_str not in result:
                result[hand_str] = avg_strat
                
        return result
    
    def get_average_regret(self) -> float:
        return self._engine.get_average_regret()

    def dump_all(self, filepath: str):
        self._engine.dump_all_data(filepath)


def create_cfr_engine(
    game_tree: Optional[Node],
    oop_range: HandRange,
    ip_range: HandRange,
    board: List[Card],
    use_cpp: bool = True,
    betting_config: Optional[Dict] = None,
    **kwargs
):
    """创建 CFR 引擎的工厂函数"""
    if use_cpp and _USE_CPP:
        try:
            return CppDCFREngine(game_tree, oop_range, ip_range, board, betting_config=betting_config, **kwargs)
        except Exception as e:
            print(f"[CFR] C++ engine failed: {e}, falling back to Python")
            # traceback already printed in CppDCFREngine.__init__
    
    # Fallback to Python
    print("[CFR] Falling back to Python engine...")
    from solver.core.cfr_engine import DCFREngine
    # Note: If game_tree is None, this will likely crash later in solve()
    return DCFREngine(game_tree, oop_range, ip_range, board, **kwargs)
