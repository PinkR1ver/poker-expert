"""
设置面板 - Pot size, Stack sizes, Bet sizing 配置
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QCheckBox, QFrame, QDoubleSpinBox
)
from PySide6.QtCore import Signal


class SettingsPanel(QWidget):
    """Solver 设置面板"""
    
    settings_changed = Signal()  # 设置变化时发出信号
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # 标题
        title = QLabel("Settings")
        title.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Pot Size
        pot_frame = QFrame()
        pot_layout = QVBoxLayout(pot_frame)
        pot_layout.setContentsMargins(0, 0, 0, 0)
        pot_label = QLabel("Pot Size")
        pot_label.setStyleSheet("color: #888888; font-size: 11px;")
        pot_layout.addWidget(pot_label)
        self.pot_input = QDoubleSpinBox()
        self.pot_input.setMinimum(0.01)
        self.pot_input.setMaximum(10000.0)
        self.pot_input.setValue(1.0)
        self.pot_input.setSingleStep(0.1)
        self.pot_input.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #3a3a3a;
                color: white;
                border: none;
                padding: 6px;
                border-radius: 4px;
            }
        """)
        self.pot_input.valueChanged.connect(self._on_settings_changed)
        pot_layout.addWidget(self.pot_input)
        layout.addWidget(pot_frame)
        
        # Stack Sizes
        stack_frame = QFrame()
        stack_layout = QVBoxLayout(stack_frame)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_label = QLabel("Stack Sizes (bb)")
        stack_label.setStyleSheet("color: #888888; font-size: 11px;")
        stack_layout.addWidget(stack_label)
        
        oop_stack_layout = QHBoxLayout()
        oop_stack_layout.addWidget(QLabel("OOP:"))
        self.oop_stack_input = QDoubleSpinBox()
        self.oop_stack_input.setMinimum(0.1)
        self.oop_stack_input.setMaximum(1000.0)
        self.oop_stack_input.setValue(100.0)
        self.oop_stack_input.setSingleStep(1.0)
        self.oop_stack_input.setStyleSheet(self.pot_input.styleSheet())
        self.oop_stack_input.valueChanged.connect(self._on_settings_changed)
        oop_stack_layout.addWidget(self.oop_stack_input)
        stack_layout.addLayout(oop_stack_layout)
        
        ip_stack_layout = QHBoxLayout()
        ip_stack_layout.addWidget(QLabel("IP:"))
        self.ip_stack_input = QDoubleSpinBox()
        self.ip_stack_input.setMinimum(0.1)
        self.ip_stack_input.setMaximum(1000.0)
        self.ip_stack_input.setValue(100.0)
        self.ip_stack_input.setSingleStep(1.0)
        self.ip_stack_input.setStyleSheet(self.pot_input.styleSheet())
        self.ip_stack_input.valueChanged.connect(self._on_settings_changed)
        ip_stack_layout.addWidget(self.ip_stack_input)
        stack_layout.addLayout(ip_stack_layout)
        
        layout.addWidget(stack_frame)
        
        # Bet Sizes
        bet_frame = QFrame()
        bet_layout = QVBoxLayout(bet_frame)
        bet_layout.setContentsMargins(0, 0, 0, 0)
        bet_label = QLabel("Bet Sizes (% pot)")
        bet_label.setStyleSheet("color: #888888; font-size: 11px;")
        bet_layout.addWidget(bet_label)
        
        self.bet_checkboxes = {}
        bet_sizes = [0.25, 0.33, 0.50, 0.67, 0.75, 1.0, 1.5, 2.0]  # 更多选项
        bet_grid = QHBoxLayout()
        default_bet_sizes = {0.33, 0.67}  # 默认只选 33% 和 67%
        for size in bet_sizes:
            cb = QCheckBox(f"{int(size*100)}%")
            cb.setChecked(size in default_bet_sizes)  # 只选默认的
            cb.setStyleSheet("""
                QCheckBox {
                    color: white;
                    font-size: 11px;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                }
            """)
            cb.stateChanged.connect(self._on_settings_changed)
            self.bet_checkboxes[size] = cb
            bet_grid.addWidget(cb)
        bet_layout.addLayout(bet_grid)
        layout.addWidget(bet_frame)
        
        # Raise Sizes
        raise_frame = QFrame()
        raise_layout = QVBoxLayout(raise_frame)
        raise_layout.setContentsMargins(0, 0, 0, 0)
        raise_label = QLabel("Raise Sizes (% pot)")
        raise_label.setStyleSheet("color: #888888; font-size: 11px;")
        raise_layout.addWidget(raise_label)
        
        self.raise_checkboxes = {}
        raise_sizes = [0.50, 0.67, 0.75, 1.0, 1.5, 2.0, 2.5]  # 更多选项
        raise_grid = QHBoxLayout()
        checkbox_style = """
            QCheckBox {
                color: white;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
            }
        """
        default_raise_sizes = {0.75}  # 默认只选 75%
        for size in raise_sizes:
            cb = QCheckBox(f"{int(size*100)}%")
            cb.setChecked(size in default_raise_sizes)  # 只选默认的
            cb.setStyleSheet(checkbox_style)
            cb.stateChanged.connect(self._on_settings_changed)
            self.raise_checkboxes[size] = cb
            raise_grid.addWidget(cb)
        raise_layout.addLayout(raise_grid)
        layout.addWidget(raise_frame)
        
        layout.addStretch()
    
    def _on_settings_changed(self):
        """设置变化回调"""
        self.settings_changed.emit()
    
    def get_pot(self) -> float:
        """获取 pot size"""
        return self.pot_input.value()
    
    def get_stacks(self) -> list[float]:
        """获取 stack sizes [OOP, IP]"""
        return [self.oop_stack_input.value(), self.ip_stack_input.value()]
    
    def get_bet_sizes(self) -> list[float]:
        """获取选中的 bet sizes"""
        return [size for size, cb in self.bet_checkboxes.items() if cb.isChecked()]
    
    def get_raise_sizes(self) -> list[float]:
        """获取选中的 raise sizes"""
        return [size for size, cb in self.raise_checkboxes.items() if cb.isChecked()]
    
    def set_pot(self, value: float):
        """设置 pot size"""
        self.pot_input.setValue(value)

