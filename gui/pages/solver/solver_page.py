"""
Postflop Solver 主页面 - 多步骤向导界面
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QStackedWidget, QMessageBox, QComboBox, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal
from gui.pages.solver.range_editor import RangeEditorWidget
from gui.pages.solver.settings_panel import SettingsPanel
from gui.pages.solver.results_view import ResultsView
from solver.data_types import HandRange
from solver.card_utils import parse_cards
from solver.game_tree import GameTreeBuilder
from solver.cfr_engine import DCFREngine
import os


class SolverWorker(QThread):
    """后台 Solver 计算线程"""
    progress = Signal(int, int)  # iteration, total
    finished = Signal()  # 完成信号（不传递复杂对象）
    error = Signal(str)
    
    def __init__(self, game_tree, oop_range, ip_range, board, iterations=1000, parallel=True):
        super().__init__()
        self.game_tree = game_tree
        self.oop_range = oop_range
        self.ip_range = ip_range
        self.board = board
        self.iterations = iterations
        self.parallel = parallel
        self.engine = None
        self.strategy = None  # 存储结果，不通过信号传递
    
    def run(self):
        try:
            self.engine = DCFREngine(
                self.game_tree,
                self.oop_range,
                self.ip_range,
                self.board
            )
            
            def callback(iteration, strategy):
                self.progress.emit(iteration, self.iterations)
            
            self.engine.solve(self.iterations, callback, parallel=self.parallel)
            self.strategy = self.engine.get_strategy()  # 存储在实例变量中
            self.finished.emit()  # 只发送完成信号
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
        from gui.pages.preflop_range import ActionSequenceBuilder
        stack = self.stack_combo.currentText()
        base_path = self._get_range_base_path(stack)
        
        # 如果 action_builder 已存在且 load_from_line_widget 已创建，则需要移除旧的
        if self.action_builder and hasattr(self, 'load_from_line_widget') and self.load_from_line_widget:
            # 移除旧的
            left_layout = self.load_from_line_widget.findChild(QVBoxLayout)
            if left_layout:
                left_layout.removeWidget(self.action_builder)
                self.action_builder.deleteLater()
        
        # 创建新的
        self.action_builder = ActionSequenceBuilder(base_path)
        self.action_builder.sequence_changed.connect(self._on_sequence_changed)
        
        # 如果 load_from_line_widget 已创建，插入到 Stack Depth 之后
        if hasattr(self, 'load_from_line_widget') and self.load_from_line_widget:
            left_panel = self.load_from_line_widget.findChild(QFrame)
            if left_panel:
                left_layout = left_panel.layout()
                # 找到 stack_frame 的位置
                stack_frame = self.stack_combo.parent().parent()
                stack_index = left_layout.indexOf(stack_frame)
                left_layout.insertWidget(stack_index + 1, self.action_builder)
    
    def _get_range_base_path(self, stack=None):
        """获取 range 基础路径"""
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        
        if stack is None:
            stack = self.stack_combo.currentText()
        
        stack_map = {
            "50bb": "cash6m_50bb_nl50_gto_gto",
            "100bb": "cash6m_100bb_nl50_gto_gto",
            "200bb": "cash6m_200bb_nl50_gto_gto",
        }
        folder = stack_map.get(stack, stack_map["100bb"])
        return os.path.join(project_root, "assets", "range", folder)
    
    def _on_sequence_changed(self, sequence):
        """行动序列变化，自动识别 OOP/IP"""
        self._detect_positions(sequence)
    
    def _detect_positions(self, sequence):
        """根据行动序列自动检测 OOP 和 IP 位置"""
        if not sequence:
            self.oop_position = None
            self.ip_position = None
            self.oop_pos_label.setText("OOP: --")
            self.ip_pos_label.setText("IP: --")
            self.oop_status_label.setText("")
            self.ip_status_label.setText("")
            self.hint_label.setText("请先构建行动序列（至少选择 opener 和一个 caller/3bettor）")
            self.hint_label.setStyleSheet("color: #ffaa00; font-size: 11px;")
            self.load_ranges_btn.setEnabled(False)
            return
        
        # 找出所有没有 fold 的位置（参与者）
        participants = set()
        for pos, action in sequence:
            action_lower = action.lower()
            if action_lower != "fold":
                participants.add(pos)
        
        if len(participants) < 2:
            self.oop_position = None
            self.ip_position = None
            self.oop_pos_label.setText("OOP: --")
            self.ip_pos_label.setText("IP: --")
            self.hint_label.setText("需要至少两个参与者（非 fold）才能确定 OOP/IP")
            self.hint_label.setStyleSheet("color: #ffaa00; font-size: 11px;")
            self.load_ranges_btn.setEnabled(False)
            return
        
        # 按 postflop 位置顺序排序参与者
        # OOP 是 postflop 先行动（位置顺序靠前），IP 是后行动（位置顺序靠后）
        sorted_participants = sorted(participants, key=lambda p: self.POSTFLOP_ORDER.index(p) if p in self.POSTFLOP_ORDER else 99)
        
        # 取位置最靠前和最靠后的两个
        self.oop_position = sorted_participants[0]
        self.ip_position = sorted_participants[-1]
        
        # 更新 UI
        self.oop_pos_label.setText(f"OOP: {self.oop_position}")
        self.ip_pos_label.setText(f"IP: {self.ip_position}")
        self.oop_status_label.setText("")
        self.ip_status_label.setText("")
        
        if len(participants) > 2:
            self.hint_label.setText(f"检测到 {len(participants)} 个参与者，Solver 仅支持 Heads-up，将使用最前({self.oop_position})和最后({self.ip_position})位置")
            self.hint_label.setStyleSheet("color: #ffaa00; font-size: 11px;")
        else:
            self.hint_label.setText(f"✓ 已识别 Heads-up：{self.oop_position} vs {self.ip_position}")
            self.hint_label.setStyleSheet("color: #00ff00; font-size: 11px;")
        
        self.load_ranges_btn.setEnabled(True)
    
    def _load_both_ranges(self):
        """一键加载 OOP 和 IP 的 Range"""
        if not self.oop_position or not self.ip_position:
            QMessageBox.warning(self, "Error", "请先构建行动序列")
            return
        
        current_path = self.action_builder._get_current_path()
        if not current_path:
            QMessageBox.warning(self, "Error", "请先完成行动序列")
            return
        
        # 加载 OOP
        oop_loaded = self._load_range_for_position_internal(self.oop_position, "OOP")
        # 加载 IP
        ip_loaded = self._load_range_for_position_internal(self.ip_position, "IP")
        
        if oop_loaded and ip_loaded:
            self.hint_label.setText(f"✓ 已加载 {self.oop_position}(OOP) 和 {self.ip_position}(IP) 的 GTO Range")
            self.hint_label.setStyleSheet("color: #00ff00; font-size: 11px;")
    
    def _load_range_for_position_internal(self, position, player_type):
        """加载指定位置的 range（内部方法）"""
        current_path = self.action_builder._get_current_path()
        if not current_path:
            return False
        
        # 查找该位置的 range 文件
        range_file = os.path.join(current_path, position, f"{position}.txt")
        
        if not os.path.exists(range_file):
            # 尝试直接在当前路径查找
            range_file = os.path.join(current_path, f"{position}.txt")
        
        if not os.path.exists(range_file):
            if player_type == "OOP":
                self.oop_status_label.setText("(Not found)")
                self.oop_status_label.setStyleSheet("color: #ff6666; font-size: 11px;")
            else:
                self.ip_status_label.setText("(Not found)")
                self.ip_status_label.setStyleSheet("color: #ff6666; font-size: 11px;")
            return False
        
        # 解析并加载 range
        range_data = self._parse_range_file(range_file)
        if range_data:
            if player_type == "OOP":
                self.oop_range_editor.set_range(HandRange(weights=range_data))
                self.oop_status_label.setText(f"({len(range_data)} hands)")
                self.oop_status_label.setStyleSheet("color: #00ff00; font-size: 11px;")
            else:
                self.ip_range_editor.set_range(HandRange(weights=range_data))
                self.ip_status_label.setText(f"({len(range_data)} hands)")
                self.ip_status_label.setStyleSheet("color: #00ff00; font-size: 11px;")
            return True
        return False
    
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
            print(f"Error loading range: {e}")
        return range_data
    
    def _back_to_line_builder(self):
        """返回到 Line Builder 子步骤"""
        self.current_substep = 0
        self.substep_stacked.setCurrentIndex(0)
        self.substep_label.setText("1a. Load from Preflop Line (Optional)")
        self.back_substep_btn.hide()
        self.skip_btn.show()
    
    def _skip_to_adjust(self):
        """跳过到手动调整"""
        self.current_substep = 1
        self.substep_stacked.setCurrentIndex(1)
        self.substep_label.setText("1b. Manual Adjust")
        self.back_substep_btn.show()
        self.skip_btn.hide()
    
    def _continue_to_adjust(self):
        """继续到手动调整"""
        self.current_substep = 1
        self.substep_stacked.setCurrentIndex(1)
        self.substep_label.setText("1b. Manual Adjust")
        self.back_substep_btn.show()
        self.skip_btn.hide()
    
    def get_ranges(self):
        """获取设置的 ranges"""
        return self.oop_range_editor.get_range(), self.ip_range_editor.get_range()
    
    def estimate_pot_size(self):
        """根据 preflop action sequence 估算 pot size (BB)"""
        if not hasattr(self, 'action_builder') or not self.action_builder:
            return 2.5  # 默认：SB(0.5) + BB(1) + 1bb open = 2.5bb
        
        sequence = self.action_builder.action_sequence
        if not sequence:
            return 2.5
        
        # 简单估算：从 sequence 中解析
        # 假设格式：[(position, action), ...] where action like "2bb", "6bb", "call", etc.
        pot = 1.5  # SB + BB
        last_bet = 1.0  # BB
        
        for pos, action in sequence:
            action_lower = action.lower()
            if action_lower == "call":
                pot += last_bet
            elif action_lower == "fold":
                pass  # 不影响 pot
            elif action_lower == "allin":
                # All-in 复杂，简化处理
                pot += 100  # 假设 100bb
                last_bet = 100
            elif "bb" in action_lower:
                # 提取数字，如 "2bb" -> 2, "6bb" -> 6
                import re
                match = re.search(r'(\d+\.?\d*)', action_lower)
                if match:
                    bet_size = float(match.group(1))
                    pot += bet_size
                    last_bet = bet_size
        
        return pot
    
    def validate(self):
        """验证 ranges 是否有效"""
        oop_range, ip_range = self.get_ranges()
        if not oop_range.weights or not ip_range.weights:
            return False, "Please set both OOP and IP ranges"
        return True, ""


class SettingsPage(QWidget):
    """第二步：超参数设置页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("Step 2: Configure Parameters")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        
        # 说明
        desc = QLabel("设置底池大小、筹码深度和下注/加注尺寸。")
        desc.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(desc)
        
        # Settings Panel
        self.settings_panel = SettingsPanel()
        layout.addWidget(self.settings_panel, 1)
    
    def get_settings(self):
        """获取设置"""
        return {
            'pot': self.settings_panel.get_pot(),
            'stacks': self.settings_panel.get_stacks(),
            'bet_sizes': self.settings_panel.get_bet_sizes(),
            'raise_sizes': self.settings_panel.get_raise_sizes(),
            'multi_street': self.settings_panel.is_multi_street(),
            'parallel': self.settings_panel.is_parallel()
        }
    
    def validate(self):
        """验证设置是否有效"""
        settings = self.get_settings()
        if not settings['bet_sizes'] or not settings['raise_sizes']:
            return False, "Please select at least one bet size and raise size"
        return True, ""


class SolvePage(QWidget):
    """第三步：Solve 页面（简化版，只有 Flop 输入和进度）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("Step 3: Solve")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        
        # 说明
        desc = QLabel("输入 Flop 牌面并开始求解。")
        desc.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(desc)
        
        # Flop 输入区域
        flop_frame = QFrame()
        flop_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 8px; padding: 16px;")
        flop_layout = QVBoxLayout(flop_frame)
        flop_layout.setSpacing(12)
        
        flop_label = QLabel("Flop Cards:")
        flop_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        flop_layout.addWidget(flop_label)
        
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)
        
        self.flop_input1 = QLineEdit()
        self.flop_input1.setPlaceholderText("e.g. Ah")
        self.flop_input1.setMaximumWidth(80)
        self.flop_input1.setStyleSheet("""
            QLineEdit {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-size: 14px;
            }
        """)
        input_layout.addWidget(self.flop_input1)
        
        self.flop_input2 = QLineEdit()
        self.flop_input2.setPlaceholderText("e.g. Ks")
        self.flop_input2.setMaximumWidth(80)
        self.flop_input2.setStyleSheet(self.flop_input1.styleSheet())
        input_layout.addWidget(self.flop_input2)
        
        self.flop_input3 = QLineEdit()
        self.flop_input3.setPlaceholderText("e.g. 7c")
        self.flop_input3.setMaximumWidth(80)
        self.flop_input3.setStyleSheet(self.flop_input1.styleSheet())
        input_layout.addWidget(self.flop_input3)
        
        input_layout.addStretch()
        flop_layout.addLayout(input_layout)
        
        # Iterations 配置
        iter_layout = QHBoxLayout()
        iter_layout.setSpacing(8)
        
        iter_label = QLabel("Iterations:")
        iter_label.setStyleSheet("color: white; font-size: 12px;")
        iter_layout.addWidget(iter_label)
        
        self.iter_combo = QComboBox()
        self.iter_combo.addItems(["100 (Fast)", "500 (Medium)", "1000 (Standard)", "2000 (Accurate)"])
        self.iter_combo.setCurrentIndex(0)  # 默认 100
        self.iter_combo.setStyleSheet("""
            QComboBox {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                min-width: 150px;
            }
        """)
        iter_layout.addWidget(self.iter_combo)
        iter_layout.addStretch()
        
        flop_layout.addLayout(iter_layout)
        layout.addWidget(flop_frame)
        
        # 进度展示区域
        self.results_view = ResultsView()
        layout.addWidget(self.results_view, 1)
        
        # Solve 按钮
        self.solve_btn = QPushButton("Start Solving")
        self.solve_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                border: none;
                padding: 12px 32px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5aaeff;
            }
            QPushButton:disabled {
                background-color: #3a3a3a;
                color: #666666;
            }
        """)
        layout.addWidget(self.solve_btn)
    
    def get_flop(self):
        """获取 Flop 输入"""
        return (
            self.flop_input1.text().strip(),
            self.flop_input2.text().strip(),
            self.flop_input3.text().strip()
        )
    
    def get_iterations(self):
        """获取迭代次数"""
        text = self.iter_combo.currentText()
        if "100" in text:
            return 100
        elif "500" in text:
            return 500
        elif "1000" in text:
            return 1000
        elif "2000" in text:
            return 2000
        return 100
    
    def validate(self):
        """验证 Flop 输入"""
        flop1, flop2, flop3 = self.get_flop()
        if not flop1 or not flop2 or not flop3:
            return False, "Please enter all 3 flop cards"
        try:
            board = parse_cards(f"{flop1} {flop2} {flop3}")
            if len(board) != 3:
                raise ValueError("Invalid flop cards")
        except Exception as e:
            return False, f"Invalid flop cards: {e}"
        return True, ""


# ResultsPage 从单独文件导入
from gui.pages.solver.results_page import ResultsPage


class SolverPage(QWidget):
    """Postflop Solver 主页面 - 多步骤向导"""
    
    def __init__(self, db_manager=None):
        super().__init__()
        self.db = db_manager
        self.worker = None
        self.game_tree = None
        self.current_step = 0
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 顶部导航栏
        nav_frame = QFrame()
        nav_frame.setStyleSheet("background-color: #2a2a2a; padding: 12px;")
        nav_layout = QHBoxLayout(nav_frame)
        nav_layout.setContentsMargins(20, 0, 20, 0)
        
        # 步骤指示器
        self.step_labels = []
        steps = ["Range", "Settings", "Solve", "Results"]
        for i, step_name in enumerate(steps):
            step_label = QLabel(f"{i+1}. {step_name}")
            step_label.setStyleSheet("""
                QLabel {
                    color: #666666;
                    font-size: 14px;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
            """)
            if i == 0:
                step_label.setStyleSheet("""
                    QLabel {
                        color: white;
                        background-color: #4a9eff;
                        font-size: 14px;
                        padding: 8px 16px;
                        border-radius: 4px;
                        font-weight: bold;
                    }
                """)
            nav_layout.addWidget(step_label)
            self.step_labels.append(step_label)
            
            if i < len(steps) - 1:
                arrow = QLabel("→")
                arrow.setStyleSheet("color: #666666; font-size: 14px; padding: 0 8px;")
                nav_layout.addWidget(arrow)
        
        nav_layout.addStretch()
        
        # 导航按钮
        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #555555;
            }
        """)
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self._on_prev)
        nav_layout.addWidget(self.prev_btn)
        
        self.next_btn = QPushButton("Next →")
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5aaeff;
            }
        """)
        self.next_btn.clicked.connect(self._on_next)
        nav_layout.addWidget(self.next_btn)
        
        layout.addWidget(nav_frame)
        
        # 内容区域（Stacked Widget）
        self.stacked = QStackedWidget()
        
        # 创建四个页面
        self.range_page = RangePage()
        self.settings_page = SettingsPage()
        self.solve_page = SolvePage()
        self.results_page = ResultsPage()
        self.solve_page.solve_btn.clicked.connect(self._on_solve_clicked)
        
        self.stacked.addWidget(self.range_page)
        self.stacked.addWidget(self.settings_page)
        self.stacked.addWidget(self.solve_page)
        self.stacked.addWidget(self.results_page)
        
        # 连接 ResultsPage 的 continue_to_next_street signal
        self.results_page.continue_to_next_street.connect(self._on_continue_to_next_street)
        
        layout.addWidget(self.stacked, 1)
    
    def _update_step_indicator(self, step):
        """更新步骤指示器"""
        for i, label in enumerate(self.step_labels):
            if i == step:
                label.setStyleSheet("""
                    QLabel {
                        color: white;
                        background-color: #4a9eff;
                        font-size: 14px;
                        padding: 8px 16px;
                        border-radius: 4px;
                        font-weight: bold;
                    }
                """)
            else:
                label.setStyleSheet("""
                    QLabel {
                        color: #666666;
                        font-size: 14px;
                        padding: 8px 16px;
                        border-radius: 4px;
                    }
                """)
        
        # 更新按钮状态
        self.prev_btn.setEnabled(step > 0)
        if step < 2:
            self.next_btn.setText("Next →")
            self.next_btn.setEnabled(True)
        elif step == 2:
            self.next_btn.setText("Ready to Solve")
            self.next_btn.setEnabled(False)
        else:  # step == 3 (Results)
            self.next_btn.setText("New Solve")
            self.next_btn.setEnabled(True)
    
    def _on_prev(self):
        """上一步"""
        if self.current_step > 0:
            self.current_step -= 1
            self.stacked.setCurrentIndex(self.current_step)
            self._update_step_indicator(self.current_step)
    
    def _on_next(self):
        """下一步"""
        # 如果在 Results 页面，点击 "New Solve" 返回到 Solve 页面
        if self.current_step == 3:
            self.current_step = 2
            self.stacked.setCurrentIndex(2)
            self._update_step_indicator(2)
            return
        
        # 验证当前页面
        if self.current_step == 0:
            valid, msg = self.range_page.validate()
            if not valid:
                QMessageBox.warning(self, "Invalid Range", msg)
                return
            # 从 Range 页进入 Settings 页时，自动估算 pot size
            estimated_pot = self.range_page.estimate_pot_size()
            self.settings_page.settings_panel.set_pot(estimated_pot)
        elif self.current_step == 1:
            valid, msg = self.settings_page.validate()
            if not valid:
                QMessageBox.warning(self, "Invalid Settings", msg)
                return
        
        if self.current_step < 2:
            self.current_step += 1
            self.stacked.setCurrentIndex(self.current_step)
            self._update_step_indicator(self.current_step)
    
    def _on_solve_clicked(self):
        """点击 Solve 按钮"""
        # 验证 Flop 输入
        valid, msg = self.solve_page.validate()
        if not valid:
            QMessageBox.warning(self, "Invalid Input", msg)
            return
        
        # 获取所有数据
        oop_range, ip_range = self.range_page.get_ranges()
        settings = self.settings_page.get_settings()
        flop1, flop2, flop3 = self.solve_page.get_flop()
        
        try:
            board = parse_cards(f"{flop1} {flop2} {flop3}")
        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", f"Invalid flop cards: {e}")
            return
        
        # 构建 game tree
        try:
            is_multi_street = settings.get('multi_street', True)
            
            builder = GameTreeBuilder(
                pot=settings['pot'],
                stacks=settings['stacks'],
                board=board,
                bet_sizes=settings['bet_sizes'],
                raise_sizes=settings['raise_sizes'],
                max_raises=2,
                street="flop",
                use_card_abstraction=is_multi_street,  # 多街时使用 card abstraction
                abstraction_buckets=6  # 将 47 张牌分成 6 个 bucket
            )
            self.game_tree = builder.build_tree()
            
            # 显示树的统计信息
            stats = builder.get_stats()
            mode_str = "Multi-Street" if is_multi_street else "Single-Street"
            self.solve_page.results_view.status_label.setText(
                f"🌲 {mode_str}: {stats['total_nodes']} nodes"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to build game tree: {e}")
            return
        
        # 获取迭代次数
        iterations = self.solve_page.get_iterations()
        
        # 启动后台计算
        self.solve_page.solve_btn.setEnabled(False)
        self.solve_page.solve_btn.setText("Solving...")
        self.solve_page.results_view.clear()
        self.solve_page.results_view.start_timer()
        self.solve_page.results_view.set_progress(0, iterations)
        
        is_parallel = settings.get('parallel', True)
        self.worker = SolverWorker(
            self.game_tree,
            oop_range,
            ip_range,
            board,
            iterations=iterations,
            parallel=is_parallel
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_solve_finished)
        self.worker.error.connect(self._on_solve_error)
        self.worker.start()
    
    def _on_progress(self, iteration: int, total: int):
        """进度更新"""
        self.solve_page.results_view.set_progress(iteration, total)
    
    def _on_solve_finished(self):
        """解算完成"""
        self.solve_page.solve_btn.setEnabled(True)
        self.solve_page.solve_btn.setText("Start Solving")
        self.solve_page.results_view.hide_progress()
        self.solve_page.results_view.status_label.setText("✓ Solve completed!")
        self.solve_page.results_view.status_label.setStyleSheet("color: #00ff00; font-size: 13px; font-weight: bold;")
        
        # 获取 board
        flop1, flop2, flop3 = self.solve_page.get_flop()
        board = parse_cards(f"{flop1} {flop2} {flop3}")
        
        # 获取 ranges
        oop_range, ip_range = self.range_page.get_ranges()
        
        # 获取位置信息
        oop_pos = self.range_page.oop_position or "OOP"
        ip_pos = self.range_page.ip_position or "IP"
        
        # 获取迭代次数
        iterations = self.solve_page.get_iterations()
        
        # 获取 pot size
        settings = self.settings_page.get_settings()
        pot_size = settings['pot']
        
        # 设置 Results 页面的数据（使用新的 API）
        if self.worker and self.worker.engine:
            self.results_page.set_data(
                engine=self.worker.engine,
                game_tree=self.game_tree,
                board=board,
                oop_range=oop_range,
                ip_range=ip_range,
                iterations=iterations,
                oop_position=oop_pos,
                ip_position=ip_pos,
                pot_size=pot_size
            )
        
        # 跳转到 Results 页面
        self.current_step = 3
        self.stacked.setCurrentIndex(3)
        self._update_step_indicator(3)
    
    def _on_solve_error(self, error_msg: str):
        """解算错误"""
        self.solve_page.solve_btn.setEnabled(True)
        self.solve_page.solve_btn.setText("Start Solving")
        self.solve_page.results_view.hide_progress()
        self.solve_page.results_view.status_label.setText("✗ Error occurred")
        self.solve_page.results_view.status_label.setStyleSheet("color: #ff6666; font-size: 13px; font-weight: bold;")
        QMessageBox.critical(self, "Solver Error", f"An error occurred:\n{error_msg}")
    
    def _on_continue_to_next_street(self, new_board: list, oop_range, ip_range, pot_size: float, street_name: str):
        """继续到下一条街（Turn/River）"""
        # 确定街道类型
        if len(new_board) == 4:
            street = "turn"
        elif len(new_board) == 5:
            street = "river"
        else:
            QMessageBox.warning(self, "Error", f"Invalid board length: {len(new_board)}")
            return
        
        # 获取当前设置
        settings = self.settings_page.get_settings()
        
        # 构建新的 game tree
        try:
            builder = GameTreeBuilder(
                pot=pot_size,
                stacks=settings['stacks'],
                board=new_board,
                bet_sizes=settings['bet_sizes'],
                raise_sizes=settings['raise_sizes'],
                max_raises=2,
                street=street
            )
            self.game_tree = builder.build_tree()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to build game tree for {street_name}: {e}")
            return
        
        # 获取迭代次数
        iterations = self.solve_page.get_iterations()
        
        # 显示进度
        self.solve_page.results_view.clear()
        self.solve_page.results_view.start_timer()
        self.solve_page.results_view.set_progress(0, iterations)
        self.solve_page.results_view.status_label.setText(f"Solving {street_name}...")
        self.solve_page.results_view.status_label.setStyleSheet("color: #ffaa00; font-size: 13px; font-weight: bold;")
        
        # 更新当前步骤显示
        self.current_step = 2  # 回到 Solve 页面显示进度
        self.stacked.setCurrentIndex(2)
        self._update_step_indicator(2)
        
        # 保存用于完成后使用
        self._next_street_board = new_board
        self._next_street_oop_range = oop_range
        self._next_street_ip_range = ip_range
        self._next_street_pot = pot_size
        self._next_street_name = street_name
        
        # 启动后台计算
        self.solve_page.solve_btn.setEnabled(False)
        self.solve_page.solve_btn.setText(f"Solving {street_name}...")
        
        self.worker = SolverWorker(
            self.game_tree,
            oop_range,
            ip_range,
            new_board,
            iterations=iterations
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_next_street_finished)
        self.worker.error.connect(self._on_solve_error)
        self.worker.start()
    
    def _on_next_street_finished(self):
        """下一条街解算完成"""
        self.solve_page.solve_btn.setEnabled(True)
        self.solve_page.solve_btn.setText("Start Solving")
        self.solve_page.results_view.hide_progress()
        self.solve_page.results_view.status_label.setText(f"✓ {self._next_street_name} solved!")
        self.solve_page.results_view.status_label.setStyleSheet("color: #00ff00; font-size: 13px; font-weight: bold;")
        
        # 获取位置信息
        oop_pos = self.range_page.oop_position or "OOP"
        ip_pos = self.range_page.ip_position or "IP"
        
        # 获取迭代次数
        iterations = self.solve_page.get_iterations()
        
        # 设置 Results 页面的数据
        if self.worker and self.worker.engine:
            self.results_page.set_data(
                engine=self.worker.engine,
                game_tree=self.game_tree,
                board=self._next_street_board,
                oop_range=self._next_street_oop_range,
                ip_range=self._next_street_ip_range,
                iterations=iterations,
                oop_position=oop_pos,
                ip_position=ip_pos,
                pot_size=self._next_street_pot
            )
        
        # 跳转到 Results 页面
        self.current_step = 3
        self.stacked.setCurrentIndex(3)
        self._update_step_indicator(3)


