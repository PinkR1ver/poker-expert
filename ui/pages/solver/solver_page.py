"""
Postflop Solver 主页面 - 多步骤向导界面
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QStackedWidget, QMessageBox, QComboBox, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal
from ui.pages.solver.range_editor import RangeEditorWidget
from ui.pages.solver.settings_panel import SettingsPanel
from ui.widgets.card_selector import CardSelector
from solver.core.data_types import HandRange
from solver.core.card_utils import parse_cards
from solver.core.game_tree import GameTreeBuilder
from solver.bridge.cpp_cfr_wrapper import create_cfr_engine, _USE_CPP
import os
import json
import time

# #region agent log
def write_debug_log(hypothesis_id, message, data=None):
    log_path = "/Volumes/macOSexternal/Documents/proj/poker-expert/.cursor/debug.log"
    now = int(time.time() * 1000)
    entry = {
        "timestamp": now,
        "location": "solver_page.py",
        "hypothesisId": hypothesis_id,
        "message": message,
        "data": data or {}
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
# #endregion

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

class SolverWorker(QThread):
    """后台 Solver 计算线程"""
    progress = Signal(int, int)  # iteration, total
    finished = Signal()  # 完成信号
    error = Signal(str)
    
    def __init__(self, oop_range, ip_range, board, iterations=1000, parallel=True, betting_config=None, game_tree=None):
        super().__init__()
        self.oop_range = oop_range
        self.ip_range = ip_range
        self.board = board
        self.iterations = iterations
        self.parallel = parallel
        self.betting_config = betting_config
        self.game_tree = game_tree
        self.engine = None
    
    def run(self):
        try:
            # 自动使用 C++ 加速（包含建树）
            self.engine = create_cfr_engine(
                self.game_tree,
                self.oop_range,
                self.ip_range,
                self.board,
                use_cpp=True,
                betting_config=self.betting_config
            )
            
            def callback(iteration, total):
                self.progress.emit(iteration, self.iterations)
            
            print(f"[SolverWorker] Solving with {self.iterations} iterations...")
            self.engine.solve(self.iterations, callback, parallel=self.parallel)
            
            # 自动全量导出
            try:
                import os
                from datetime import datetime
                output_dir = "tmp/output"
                if not os.path.exists(output_dir): os.makedirs(output_dir)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                board_str = "".join(str(c) for c in self.board)
                filepath = os.path.abspath(os.path.join(output_dir, f"full_tree_{board_str}_{timestamp}.json"))
                self.engine.dump_all(filepath)
            except Exception as e:
                print(f"[Solver] Warning: Auto-dump failed: {e}")

            self.finished.emit()
        except Exception as e:
            import traceback
            self.error.emit(f"{str(e)}\n{traceback.format_exc()}")


class RangePage(QWidget):
    """第一步：Range 设置页面（包含两个子步骤：Load from Line 和 Manual Adjust）"""
    
    # Postflop 位置顺序（从 OOP 到 IP）
    POSTFLOP_ORDER = ["SB", "BB", "UTG", "HJ", "CO", "BTN"]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_substep = 0  # 0: Load from Line, 1: Manual Adjust
        # 先创建 range editors（在两个子步骤间共享）
        self.oop_range_editor = RangeEditorWidget("OOP Range")
        self.ip_range_editor = RangeEditorWidget("IP Range")
        self.oop_position = None  # 自动识别的 OOP 位置
        self.ip_position = None   # 自动识别的 IP 位置
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("Step 1: Set Ranges")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        
        # 子步骤指示器
        substep_frame = QFrame()
        substep_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 4px; padding: 8px;")
        substep_layout = QHBoxLayout(substep_frame)
        substep_layout.setContentsMargins(12, 8, 12, 8)
        
        self.substep_label = QLabel("1a. Load from Preflop Line (Optional)")
        self.substep_label.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
        substep_layout.addWidget(self.substep_label)
        
        substep_layout.addStretch()
        
        # 返回按钮（默认隐藏）
        self.back_substep_btn = QPushButton("← Back to Line Builder")
        self.back_substep_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        self.back_substep_btn.clicked.connect(self._back_to_line_builder)
        self.back_substep_btn.hide()
        substep_layout.addWidget(self.back_substep_btn)
        
        # Skip 按钮
        self.skip_btn = QPushButton("Skip → Manual Adjust")
        self.skip_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        self.skip_btn.clicked.connect(self._skip_to_adjust)
        substep_layout.addWidget(self.skip_btn)
        
        layout.addWidget(substep_frame)
        
        # 内容区域（Stacked Widget）
        self.substep_stacked = QStackedWidget()
        
        # 子步骤 1: 从 Preflop Line 加载
        self.load_from_line_widget = self._create_load_from_line_widget()
        self.substep_stacked.addWidget(self.load_from_line_widget)
        
        # 子步骤 2: 手动微调
        self.manual_adjust_widget = self._create_manual_adjust_widget()
        self.substep_stacked.addWidget(self.manual_adjust_widget)
        
        layout.addWidget(self.substep_stacked, 1)
    
    def _create_load_from_line_widget(self):
        """创建从 Preflop Line 加载的组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # 说明
        desc = QLabel("构建 Preflop 行动序列，系统自动识别 OOP/IP 位置并加载对应 GTO Range。")
        desc.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(desc)
        
        # 主内容区域（水平分割）
        main_splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：行动序列构建器
        left_panel = QFrame()
        left_panel.setFixedWidth(350)
        left_panel.setStyleSheet("background-color: #252525; border-radius: 8px;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(16)
        
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
        self.stack_combo.currentTextChanged.connect(self._on_stack_changed)
        stack_layout.addWidget(self.stack_combo)
        left_layout.addWidget(stack_frame)
        
        # 行动序列构建器（延迟初始化）
        self.action_builder = None
        self._on_stack_changed()  # 初始化
        
        left_layout.addWidget(self.action_builder)
        left_layout.addStretch()
        
        main_splitter.addWidget(left_panel)
        
        # 右侧：自动识别的位置显示 + 加载按钮
        right_panel = QFrame()
        right_panel.setStyleSheet("background-color: #252525; border-radius: 8px;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(16)
        
        # 位置显示标题
        pos_title = QLabel("Detected Positions")
        pos_title.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        right_layout.addWidget(pos_title)
        
        # OOP 位置显示
        oop_frame = QFrame()
        oop_frame.setStyleSheet("background-color: #3a3a3a; border-radius: 6px; padding: 8px;")
        oop_inner = QHBoxLayout(oop_frame)
        oop_inner.setContentsMargins(12, 8, 12, 8)
        
        self.oop_pos_label = QLabel("OOP: --")
        self.oop_pos_label.setStyleSheet("color: #ff9999; font-size: 13px; font-weight: bold;")
        oop_inner.addWidget(self.oop_pos_label)
        oop_inner.addStretch()
        
        self.oop_status_label = QLabel("")
        self.oop_status_label.setStyleSheet("color: #888888; font-size: 11px;")
        oop_inner.addWidget(self.oop_status_label)
        
        right_layout.addWidget(oop_frame)
        
        # IP 位置显示
        ip_frame = QFrame()
        ip_frame.setStyleSheet("background-color: #3a3a3a; border-radius: 6px; padding: 8px;")
        ip_inner = QHBoxLayout(ip_frame)
        ip_inner.setContentsMargins(12, 8, 12, 8)
        
        self.ip_pos_label = QLabel("IP: --")
        self.ip_pos_label.setStyleSheet("color: #99ff99; font-size: 13px; font-weight: bold;")
        ip_inner.addWidget(self.ip_pos_label)
        ip_inner.addStretch()
        
        self.ip_status_label = QLabel("")
        self.ip_status_label.setStyleSheet("color: #888888; font-size: 11px;")
        ip_inner.addWidget(self.ip_status_label)
        
        right_layout.addWidget(ip_frame)
        
        # 提示信息
        self.hint_label = QLabel("请先构建行动序列（至少选择 opener 和一个 caller/3bettor）")
        self.hint_label.setStyleSheet("color: #ffaa00; font-size: 11px;")
        self.hint_label.setWordWrap(True)
        right_layout.addWidget(self.hint_label)
        
        right_layout.addStretch()
        
        # 一键加载按钮
        self.load_ranges_btn = QPushButton("Load GTO Ranges")
        self.load_ranges_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #5aaeff;
            }
            QPushButton:disabled {
                background-color: #3a3a3a;
                color: #666666;
            }
        """)
        self.load_ranges_btn.clicked.connect(self._load_both_ranges)
        self.load_ranges_btn.setEnabled(False)
        right_layout.addWidget(self.load_ranges_btn)
        
        # 继续按钮
        done_btn = QPushButton("Continue to Manual Adjust →")
        done_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        done_btn.clicked.connect(self._continue_to_adjust)
        right_layout.addWidget(done_btn)
        
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([350, 300])
        
        layout.addWidget(main_splitter, 1)
        
        return widget
    
    def _create_manual_adjust_widget(self):
        """创建手动微调组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # 说明
        desc = QLabel("手动微调 Range。可以点击格子选择手牌，或使用预设按钮。")
        desc.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(desc)
        
        # Range 编辑器（水平布局）- 使用已创建的共享实例
        range_layout = QHBoxLayout()
        range_layout.setSpacing(16)
        
        range_layout.addWidget(self.oop_range_editor, 1)
        range_layout.addWidget(self.ip_range_editor, 1)
        
        layout.addLayout(range_layout, 1)
        
        return widget
    
    def _on_stack_changed(self):
        """Stack depth 变化时重新初始化 ActionSequenceBuilder"""
        from ui.pages.preflop_range import ActionSequenceBuilder
        stack = self.stack_combo.currentText()
        base_path = self._get_range_base_path(stack)
        
        if self.action_builder and hasattr(self, 'load_from_line_widget') and self.load_from_line_widget:
            left_layout = self.load_from_line_widget.findChild(QVBoxLayout)
            if left_layout:
                left_layout.removeWidget(self.action_builder)
                self.action_builder.deleteLater()
        
        self.action_builder = ActionSequenceBuilder(base_path)
        self.action_builder.sequence_changed.connect(self._on_sequence_changed)
        
        if hasattr(self, 'load_from_line_widget') and self.load_from_line_widget:
            left_panel = self.load_from_line_widget.findChild(QFrame)
            if left_panel:
                left_layout = left_panel.layout()
                stack_frame = self.stack_combo.parent().parent()
                stack_index = left_layout.indexOf(stack_frame)
                left_layout.insertWidget(stack_index + 1, self.action_builder)
    
    def _get_range_base_path(self, stack=None):
        """获取 range 基础路径"""
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        if stack is None: stack = self.stack_combo.currentText()
        stack_map = {"50bb": "cash6m_50bb_nl50_gto_gto", "100bb": "cash6m_100bb_nl50_gto_gto", "200bb": "cash6m_200bb_nl50_gto_gto"}
        folder = stack_map.get(stack, stack_map["100bb"])
        return os.path.join(project_root, "assets", "range", folder)
    
    def _on_sequence_changed(self, sequence):
        self._detect_positions(sequence)
    
    def _detect_positions(self, sequence):
        if not sequence:
            self.oop_position = None; self.ip_position = None
            self.oop_pos_label.setText("OOP: --"); self.ip_pos_label.setText("IP: --")
            self.hint_label.setText("请先构建行动序列（至少选择 opener 和一个 caller/3bettor）")
            self.hint_label.setStyleSheet("color: #ffaa00; font-size: 11px;")
            self.load_ranges_btn.setEnabled(False)
            return
        participants = set()
        for pos, action in sequence:
            if action.lower() != "fold": participants.add(pos)
        if len(participants) < 2:
            self.oop_position = None; self.ip_position = None
            self.oop_pos_label.setText("OOP: --"); self.ip_pos_label.setText("IP: --")
            self.hint_label.setText("需要至少两个参与者（非 fold）才能确定 OOP/IP")
            self.hint_label.setStyleSheet("color: #ffaa00; font-size: 11px;")
            self.load_ranges_btn.setEnabled(False)
            return
        sorted_p = sorted(participants, key=lambda p: self.POSTFLOP_ORDER.index(p) if p in self.POSTFLOP_ORDER else 99)
        self.oop_position = sorted_p[0]; self.ip_position = sorted_p[-1]
        self.oop_pos_label.setText(f"OOP: {self.oop_position}"); self.ip_pos_label.setText(f"IP: {self.ip_position}")
        self.hint_label.setText(f"✓ 已识别：{self.oop_position}(OOP) vs {self.ip_position}(IP)")
        self.hint_label.setStyleSheet("color: #00ff00; font-size: 11px;")
        self.load_ranges_btn.setEnabled(True)
    
    def _load_both_ranges(self):
        if not self.oop_position or not self.ip_position: return
        self._load_range_for_position_internal(self.oop_position, "OOP")
        self._load_range_for_position_internal(self.ip_position, "IP")
    
    def _get_hand_combos(self, hand):
        """计算手牌组合数"""
        if len(hand) == 2: return 6 # Pair
        if hand.endswith('s'): return 4 # Suited
        return 12 # Offsuit

    def _load_range_for_position_internal(self, position, player_type):
        current_path = self.action_builder._get_current_path()
        if not current_path: 
            self.hint_label.setText("Error: Could not determine preflop path")
            self.hint_label.setStyleSheet("color: #ff6666; font-size: 11px;")
            return False
            
        range_file = os.path.join(current_path, position, f"{position}.txt")
        if not os.path.exists(range_file): range_file = os.path.join(current_path, f"{position}.txt")
        
        if not os.path.exists(range_file):
            msg = f"Range file not found for {position}"
            if player_type == "OOP": self.oop_status_label.setText("(Not found)")
            else: self.ip_status_label.setText("(Not found)")
            return False
            
        range_data = self._parse_range_file(range_file)
        if range_data:
            # 计算总 combo 数
            total_combos = sum(self._get_hand_combos(h) * freq for h, freq in range_data.items())
            pct = total_combos / 1326 * 100
            status_text = f"{total_combos:.1f} combos ({pct:.1f}%)"
            
            if player_type == "OOP": 
                self.oop_range_editor.set_range(HandRange(weights=range_data))
                self.oop_status_label.setText(status_text)
                self.oop_status_label.setStyleSheet("color: #00ff00; font-size: 11px;")
            else: 
                self.ip_range_editor.set_range(HandRange(weights=range_data))
                self.ip_status_label.setText(status_text)
                self.ip_status_label.setStyleSheet("color: #00ff00; font-size: 11px;")
            return True
        return False
    
    def _parse_range_file(self, path):
        range_data = {}
        try:
            with open(path, 'r') as f:
                content = f.read().strip()
                for item in content.split(','):
                    if ':' in item:
                        hand, freq = item.split(':')
                        range_data[hand.strip()] = float(freq.strip())
        except: pass
        return range_data
    
    def _back_to_line_builder(self):
        self.current_substep = 0; self.substep_stacked.setCurrentIndex(0)
        self.back_substep_btn.hide(); self.skip_btn.show()
    
    def _skip_to_adjust(self):
        self.current_substep = 1; self.substep_stacked.setCurrentIndex(1)
        self.back_substep_btn.show(); self.skip_btn.hide()
    
    def _continue_to_adjust(self):
        self.current_substep = 1; self.substep_stacked.setCurrentIndex(1)
        self.back_substep_btn.show(); self.skip_btn.hide()
    
    def get_ranges(self): return self.oop_range_editor.get_range(), self.ip_range_editor.get_range()
    
    def get_pot_size(self):
        return self.estimate_pot_size()
    
    def estimate_pot_size(self):
        if not hasattr(self, 'action_builder') or not self.action_builder: return 2.5
        sequence = self.action_builder.action_sequence
        if not sequence: return 2.5
        
        log_debug("H4", "estimate_pot_size sequence", "solver_page.py:503", {"seq": sequence})
        # 初始盲注
        investments = {"SB": 0.5, "BB": 1.0}
        pot = 1.5
        last_bet = 1.0
        
        for pos, action in sequence:
            act = action.lower()
            if "bb" in act:
                import re
                m = re.search(r'(\d+\.?\d*)', act)
                if m:
                    total_bet = float(m.group(1))
                    prev_investment = investments.get(pos, 0.0)
                    added = total_bet - prev_investment
                    if added > 0:
                        pot += added
                        investments[pos] = total_bet
                        last_bet = total_bet
            elif act == "call":
                prev_investment = investments.get(pos, 0.0)
                added = last_bet - prev_investment
                if added > 0:
                    pot += added
                    investments[pos] = last_bet
        
        log_debug("H4", "estimate_pot_size result", "solver_page.py:528", {"pot": pot, "investments": investments})
        return pot
    
    def validate(self):
        oop, ip = self.get_ranges()
        if not oop.weights or not ip.weights: return False, "Please set both ranges"
        return True, ""


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("Step 2: Parameters"); title.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        layout.addWidget(title); self.settings_panel = SettingsPanel(); layout.addWidget(self.settings_panel, 1)
    def get_settings(self):
        return {
            'pot': self.settings_panel.get_pot(), 
            'stacks': self.settings_panel.get_stacks(), 
            'bet_sizes': self.settings_panel.get_bet_sizes(), 
            'raise_sizes': self.settings_panel.get_raise_sizes(),
            'parallel': self.settings_panel.is_parallel()
        }
    def validate(self):
        s = self.get_settings()
        if not s['bet_sizes']: return False, "Please select bet sizes"
        return True, ""


class SolvePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("Step 3: Solve"); title.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        flop_frame = QFrame(); flop_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 8px; padding: 16px;")
        flop_layout = QVBoxLayout(flop_frame)
        self.card_selector = CardSelector(max_selection=3); flop_layout.addWidget(self.card_selector)
        self.iter_combo = QComboBox(); self.iter_combo.addItems(["100 (Fast)", "500 (Medium)", "1000 (Standard)", "2000 (Accurate)"])
        flop_layout.addWidget(self.iter_combo); layout.addWidget(flop_frame); layout.addStretch()
        self.solve_btn = QPushButton("Start Solving"); self.solve_btn.setMinimumHeight(50); layout.addWidget(self.solve_btn)
    def get_flop(self):
        cards = self.card_selector.get_selected_cards()
        while len(cards) < 3: cards.append("")
        return tuple(cards[:3])
    def get_iterations(self):
        text = self.iter_combo.currentText()
        if "2000" in text: return 2000
        elif "1000" in text: return 1000
        elif "500" in text: return 500
        return 100
    def validate(self):
        f1, f2, f3 = self.get_flop()
        if not f1 or not f2 or not f3: return False, "Please select 3 cards"
        return True, ""


from ui.pages.solver.results_page import ResultsPage

class SolverPage(QWidget):
    def __init__(self, db_manager=None):
        super().__init__(); self.db = db_manager; self.current_step = 0; self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        nav_frame = QFrame(); nav_frame.setStyleSheet("background-color: #2a2a2a; padding: 12px;")
        nav_layout = QHBoxLayout(nav_frame)
        self.step_labels = []
        for i, name in enumerate(["Range", "Settings", "Solve", "Results"]):
            lbl = QLabel(f"{i+1}. {name}"); self.step_labels.append(lbl); nav_layout.addWidget(lbl)
        nav_layout.addStretch()
        self.prev_btn = QPushButton("← Previous"); self.prev_btn.clicked.connect(self._on_prev); nav_layout.addWidget(self.prev_btn)
        self.next_btn = QPushButton("Next →"); self.next_btn.clicked.connect(self._on_next); nav_layout.addWidget(self.next_btn)
        layout.addWidget(nav_frame)
        self.stacked = QStackedWidget()
        self.range_page = RangePage(); self.settings_page = SettingsPage(); self.solve_page = SolvePage(); self.results_page = ResultsPage()
        self.solve_page.solve_btn.clicked.connect(self._on_solve_clicked)
        self.stacked.addWidget(self.range_page); self.stacked.addWidget(self.settings_page); self.stacked.addWidget(self.solve_page); self.stacked.addWidget(self.results_page)
        layout.addWidget(self.stacked, 1); self._update_step_indicator(0)
    
    def _update_step_indicator(self, step):
        for i, lbl in enumerate(self.step_labels):
            lbl.setStyleSheet("color: white; background-color: #4a9eff; font-weight: bold;" if i == step else "color: #666666;")
        self.prev_btn.setEnabled(step > 0)
        self.next_btn.setText("New Solve" if step == 3 else "Next →")
        
        # 不允许在 Solve 页面未点击开始解算就直接点 Next 进入 Results
        if step == 2:
            self.next_btn.setEnabled(False)
        else:
            self.next_btn.setEnabled(True)
    
    def _on_prev(self):
        if self.current_step > 0: self.current_step -= 1; self.stacked.setCurrentIndex(self.current_step); self._update_step_indicator(self.current_step)
    
    def _on_next(self):
        if self.current_step == 0: # From Range to Settings
            pot = self.range_page.get_pot_size()
            self.settings_page.settings_panel.set_pot(pot)
            
        if self.current_step == 3: self.current_step = 2; self.stacked.setCurrentIndex(2); self._update_step_indicator(2); return
        self.current_step += 1; self.stacked.setCurrentIndex(self.current_step); self._update_step_indicator(self.current_step)

    def _on_solve_clicked(self):
        oop_range, ip_range = self.range_page.get_ranges()
        settings = self.settings_page.get_settings()
        f1, f2, f3 = self.solve_page.get_flop()
        board = parse_cards(f"{f1} {f2} {f3}")
        iterations = self.solve_page.get_iterations()
        
        # 准备 C++ 建树配置
        betting_config = {
            'pot': settings['pot'],
            'stacks': settings['stacks'],
            'bet_sizes': {
                'flop': settings['bet_sizes'], 
                'turn': settings['bet_sizes'], 
                'river': settings['bet_sizes']
            },
            'raise_sizes': {
                'flop': settings['raise_sizes'],
                'turn': settings['raise_sizes'],
                'river': settings['raise_sizes']
            },
            'max_raises': 2
        }

        self.current_step = 3; self.stacked.setCurrentIndex(3); self._update_step_indicator(3)
        self.results_page.show_progress(0, iterations)
        
        self.worker = SolverWorker(oop_range, ip_range, board, iterations, settings.get('parallel', True), betting_config)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_solve_finished)
        self.worker.error.connect(self._on_solve_error)
        self.worker.start()

    def _on_progress(self, it, total): self.results_page.show_progress(it, total)
    def _on_solve_finished(self):
        log_debug("H1/H2", "Solve finished handler start", "solver_page.py:641")
        self.results_page.hide_progress()
        f1, f2, f3 = self.solve_page.get_flop(); board = parse_cards(f"{f1} {f2} {f3}")
        oop_range, ip_range = self.range_page.get_ranges()
        settings = self.settings_page.get_settings()
        
        log_debug("H4", "Pot size for results", "solver_page.py:647", {"pot": settings['pot']})
        
        try:
            root = self.worker.engine.tree
            log_debug("H1", "Root node proxy check", "solver_page.py:651", {"root_id": getattr(root, '_node_id', 'N/A')})
            
            self.results_page.set_data(
                self.worker.engine, 
                root, 
                board, 
                oop_range, 
                ip_range, 
                self.solve_page.get_iterations(),
                pot_size=settings['pot']
            )
            log_debug("H1/H2", "set_data call completed", "solver_page.py:663")
        except Exception as e:
            log_debug("H1", "Error in set_data", "solver_page.py:665", {"error": str(e)})
            raise
    def _on_solve_error(self, msg): self.results_page.hide_progress(); QMessageBox.critical(self, "Error", msg)
    def _on_continue_to_next_street(self, *args): pass
