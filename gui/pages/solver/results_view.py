"""
结果展示组件 - 显示 Solver 的策略和 EV
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar, QTextEdit
)
from PySide6.QtCore import Qt, QElapsedTimer
from solver.data_types import Node, Action


class ResultsView(QWidget):
    """Solver 结果展示"""
    
    def __init__(self):
        super().__init__()
        self.current_node = None
        self.strategy = {}  # {Action: frequency}
        self.timer = QElapsedTimer()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # 标题
        self.title_label = QLabel("Results")
        self.title_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        layout.addWidget(self.title_label)
        
        # 进度区域
        progress_frame = QFrame()
        progress_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 6px; padding: 8px;")
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setContentsMargins(12, 12, 12, 12)
        progress_layout.setSpacing(8)
        
        # 状态标签
        self.status_label = QLabel("Ready to solve")
        self.status_label.setStyleSheet("color: #4a9eff; font-size: 13px; font-weight: bold;")
        progress_layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e1e1e;
                border: none;
                border-radius: 4px;
                height: 24px;
                text-align: center;
                color: white;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a9eff, stop:1 #7b68ee);
                border-radius: 4px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        # 时间信息
        self.time_label = QLabel("")
        self.time_label.setStyleSheet("color: #888888; font-size: 11px;")
        progress_layout.addWidget(self.time_label)
        
        layout.addWidget(progress_frame)
        
        # 策略显示
        self.strategy_label = QLabel("No solution yet")
        self.strategy_label.setStyleSheet("color: #888888; font-size: 12px;")
        self.strategy_label.setWordWrap(True)
        layout.addWidget(self.strategy_label)
        
        # 详细信息
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-family: monospace;
            }
        """)
        layout.addWidget(self.details_text, 1)
    
    def start_timer(self):
        """开始计时"""
        self.timer.start()
    
    def set_progress(self, iteration: int, total: int):
        """设置进度"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(iteration)
        
        percentage = (iteration / total) * 100 if total > 0 else 0
        self.progress_bar.setFormat(f"{percentage:.0f}%  ({iteration}/{total} iterations)")
        
        # 更新状态
        self.status_label.setText(f"🔄 Solving... Iteration {iteration}/{total}")
        self.status_label.setStyleSheet("color: #ffaa00; font-size: 13px; font-weight: bold;")
        
        # 计算预估时间
        if iteration > 0 and self.timer.isValid():
            elapsed_ms = self.timer.elapsed()
            elapsed_sec = elapsed_ms / 1000
            rate = iteration / elapsed_sec if elapsed_sec > 0 else 0
            remaining = (total - iteration) / rate if rate > 0 else 0
            
            self.time_label.setText(
                f"Elapsed: {elapsed_sec:.1f}s | "
                f"Speed: {rate:.1f} iter/s | "
                f"ETA: {remaining:.1f}s"
            )
    
    def hide_progress(self):
        """隐藏进度条"""
        self.progress_bar.setVisible(False)
        self.time_label.setText("")
    
    def update_strategy(self, node: Node, strategy: dict):
        """更新策略显示"""
        self.current_node = node
        self.strategy = strategy
        
        if not strategy:
            self.strategy_label.setText("No strategy available")
            return
        
        # 构建策略文本
        strategy_parts = []
        for action, freq in sorted(strategy.items(), key=lambda x: -x[1]):
            if freq > 0.01:  # 只显示 > 1% 的策略
                strategy_parts.append(f"{action}: {freq*100:.1f}%")
        
        strategy_text = " / ".join(strategy_parts) if strategy_parts else "No actions"
        self.strategy_label.setText(f"📊 Strategy: {strategy_text}")
        self.strategy_label.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
        
        # 详细信息
        details = []
        details.append("=" * 40)
        details.append(f"  ROOT NODE STRATEGY")
        details.append("=" * 40)
        details.append("")
        details.append(f"  Player: {'OOP' if node.player == 0 else 'IP'} to act")
        details.append(f"  Pot: ${node.state.pot:.2f}")
        details.append(f"  Stacks: OOP ${node.state.stacks[0]:.2f} / IP ${node.state.stacks[1]:.2f}")
        details.append(f"  To Call: ${node.state.to_call:.2f}")
        details.append("")
        details.append("-" * 40)
        details.append("  GTO STRATEGY:")
        details.append("-" * 40)
        for action, freq in sorted(strategy.items(), key=lambda x: -x[1]):
            bar_len = int(freq * 30)
            bar = "█" * bar_len + "░" * (30 - bar_len)
            details.append(f"  {str(action):12s} {bar} {freq*100:5.1f}%")
        details.append("")
        
        self.details_text.setText("\n".join(details))
    
    def clear(self):
        """清空显示"""
        self.current_node = None
        self.strategy = {}
        self.strategy_label.setText("No solution yet")
        self.strategy_label.setStyleSheet("color: #888888; font-size: 12px;")
        self.status_label.setText("Ready to solve")
        self.status_label.setStyleSheet("color: #4a9eff; font-size: 13px; font-weight: bold;")
        self.time_label.setText("")
        self.details_text.clear()
        self.hide_progress()

