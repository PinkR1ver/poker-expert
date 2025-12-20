import os
import datetime
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QTableView, QHeaderView, QPushButton,
    QFileDialog, QProgressBar, QSpacerItem, QSizePolicy,
    QComboBox, QCheckBox, QListWidget, QListWidgetItem,
    QTextEdit, QSplitter
)
from PySide6.QtCore import Qt, QAbstractTableModel, QThread, Signal, QDate, QTimer
from PySide6.QtGui import QColor, QBrush, QPixmap, QIcon, QTextCursor

# Matplotlib
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
except ImportError:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates

from poker_parser import parse_file, get_hand_by_id
from db_manager import DBManager
from gui.styles import PROFIT_GREEN, PROFIT_RED
from gui.widgets import ReplayTableWidget

# --- Helper Components ---

class StatCard(QFrame):
    def __init__(self, title, value, parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("CardTitle")
        
        self.lbl_value = QLabel(value)
        self.lbl_value.setObjectName("CardValue")
        
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)
        self.setFixedHeight(100)

    def set_value(self, value, color=None):
        self.lbl_value.setText(value)
        if color:
            self.lbl_value.setStyleSheet(f"color: {color};")
        else:
            self.lbl_value.setStyleSheet("") # Reset to default stylesheet

# --- Models ---

class HandsTableModel(QAbstractTableModel):
    def __init__(self, data=None):
        super().__init__()
        self._data = data if data else []
        # DB returns: (hand_id, date, blinds, game, cards, profit, rake, pot)
        self._headers = ["Date", "Game", "Stakes", "Hand", "Net Won", "Pot", "Rake"]

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
            
        row = self._data[index.row()]
        col = index.column()
        
        # Mapping DB columns to View columns
        # DB: 0:id, 1:date, 2:blinds, 3:game, 4:cards, 5:profit, 6:rake, 7:pot
        
        if role == Qt.DisplayRole:
            if col == 0: return str(row[1]) # Date
            if col == 1: return str(row[3]) # Game
            if col == 2: return str(row[2]) # Stakes
            if col == 3: return str(row[4]) # Cards
            if col == 4: return f"${row[5]:.2f}" # Profit
            if col == 5: return f"${row[7]:.2f}" # Pot
            if col == 6: return f"${row[6]:.2f}" # Rake
            
        if role == Qt.ForegroundRole:
            if col == 4: # Profit column
                profit = row[5]
                if profit > 0:
                    return QBrush(QColor(PROFIT_GREEN))
                elif profit < 0:
                    return QBrush(QColor(PROFIT_RED))
        
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return None

    def sort(self, column, order):
        """Sort the model by the given column in the given order."""
        self.beginResetModel()
        
        # Map view column to DB column index
        # View: 0:Date, 1:Game, 2:Stakes, 3:Hand, 4:Net Won, 5:Pot, 6:Rake
        # DB:   0:id, 1:date, 2:blinds, 3:game, 4:cards, 5:profit, 6:rake, 7:pot
        
        reverse = (order == Qt.DescendingOrder)
        
        if column == 0:  # Date
            self._data.sort(key=lambda x: x[1] if x[1] else "", reverse=reverse)
        elif column == 1:  # Game
            self._data.sort(key=lambda x: str(x[3]) if x[3] else "", reverse=reverse)
        elif column == 2:  # Stakes
            self._data.sort(key=lambda x: str(x[2]) if x[2] else "", reverse=reverse)
        elif column == 3:  # Hand (cards)
            self._data.sort(key=lambda x: str(x[4]) if x[4] else "", reverse=reverse)
        elif column == 4:  # Net Won (profit)
            self._data.sort(key=lambda x: float(x[5]) if x[5] is not None else 0.0, reverse=reverse)
        elif column == 5:  # Pot
            self._data.sort(key=lambda x: float(x[7]) if len(x) > 7 and x[7] is not None else 0.0, reverse=reverse)
        elif column == 6:  # Rake
            self._data.sort(key=lambda x: float(x[6]) if x[6] is not None else 0.0, reverse=reverse)
        
        self.endResetModel()

    def update_data(self, new_data):
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()

# --- Workers ---

class ImportWorker(QThread):
    progress = Signal(str)
    finished = Signal(int, int) # added, duplicates

    def __init__(self, file_paths, db_path="poker_tracker.db"):
        super().__init__()
        self.file_paths = file_paths
        self.db_path = db_path

    def run(self):
        db = DBManager(self.db_path)
        added_count = 0
        duplicate_count = 0
        
        for path in self.file_paths:
            self.progress.emit(f"Parsing {os.path.basename(path)}...")
            try:
                hands = parse_file(path)
                for hand in hands:
                    if db.add_hand(hand):
                        added_count += 1
                    else:
                        duplicate_count += 1
            except Exception as e:
                print(f"Error parsing {path}: {e}")
        
        db.close()
        self.finished.emit(added_count, duplicate_count)

# --- Pages ---

class DashboardPage(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Left Panel - Filter/Controls (like PokerTracker style)
        left_panel = QFrame()
        left_panel.setFixedWidth(220)
        left_panel.setStyleSheet("""
            QFrame { background-color: #252525; border-right: 1px solid #3a3a3a; }
            QLabel { color: #b0b0b0; font-size: 11px; }
            QCheckBox { color: #e0e0e0; font-size: 12px; padding: 4px 0; }
            QCheckBox::indicator { width: 14px; height: 14px; }
            QComboBox { background-color: #333; color: white; border: 1px solid #555; padding: 4px; }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 16, 12, 16)
        left_layout.setSpacing(8)
        
        # Section: Date Filter
        left_layout.addWidget(QLabel("DATE RANGE"))
        self.combo_filter = QComboBox()
        self.combo_filter.addItems(["All Time", "This Year", "This Month", "This Week", "Today"])
        self.combo_filter.currentTextChanged.connect(self.refresh_data)
        left_layout.addWidget(self.combo_filter)
        
        left_layout.addSpacing(12)
        
        # Section: X-Axis
        left_layout.addWidget(QLabel("X-AXIS"))
        self.combo_xaxis = QComboBox()
        self.combo_xaxis.addItems(["Hands Played", "Date/Time"])
        self.combo_xaxis.currentTextChanged.connect(self.refresh_data)
        left_layout.addWidget(self.combo_xaxis)
        
        left_layout.addSpacing(16)
        
        # Section: Curves
        left_layout.addWidget(QLabel("SHOW LINES"))
        
        # Curve checkboxes with colored indicators
        self.chk_net_won = QCheckBox("● Net Won")
        self.chk_net_won.setChecked(True)
        self.chk_net_won.setStyleSheet("QCheckBox { color: #4caf50; }")
        self.chk_net_won.stateChanged.connect(self.refresh_data)
        
        self.chk_showdown = QCheckBox("● Showdown Won")
        self.chk_showdown.setChecked(False)
        self.chk_showdown.setStyleSheet("QCheckBox { color: #2196f3; }")
        self.chk_showdown.stateChanged.connect(self.refresh_data)
        
        self.chk_non_showdown = QCheckBox("● Non-Showdown Won")
        self.chk_non_showdown.setChecked(False)
        self.chk_non_showdown.setStyleSheet("QCheckBox { color: #f44336; }")
        self.chk_non_showdown.stateChanged.connect(self.refresh_data)
        
        self.chk_ev = QCheckBox("● All-in EV Adj")
        self.chk_ev.setChecked(False)
        self.chk_ev.setStyleSheet("QCheckBox { color: #ff9800; }")
        self.chk_ev.stateChanged.connect(self.refresh_data)
        
        left_layout.addWidget(self.chk_net_won)
        left_layout.addWidget(self.chk_showdown)
        left_layout.addWidget(self.chk_non_showdown)
        left_layout.addWidget(self.chk_ev)
        
        left_layout.addStretch()
        
        # KPI summary at bottom of left panel
        left_layout.addWidget(QLabel("SUMMARY"))
        self.lbl_total_hands = QLabel("Hands: 0")
        self.lbl_total_hands.setStyleSheet("color: white; font-weight: bold;")
        self.lbl_net_won = QLabel("Net: $0.00")
        self.lbl_net_won.setStyleSheet("color: #4caf50; font-weight: bold;")
        self.lbl_rake = QLabel("Rake: $0.00")
        self.lbl_rake.setStyleSheet("color: #f44336;")
        self.lbl_insurance = QLabel("Insurance: $0.00")
        self.lbl_insurance.setStyleSheet("color: #ff9800;")
        self.lbl_jackpot = QLabel("Jackpot: $0.00")
        self.lbl_jackpot.setStyleSheet("color: #9c27b0;")
        left_layout.addWidget(self.lbl_total_hands)
        left_layout.addWidget(self.lbl_net_won)
        left_layout.addWidget(self.lbl_rake)
        left_layout.addWidget(self.lbl_insurance)
        left_layout.addWidget(self.lbl_jackpot)
        
        main_layout.addWidget(left_panel)
        
        # Right Panel - Graph Area
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        
        self.figure = Figure(facecolor='#1e1e1e')
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background-color: #1e1e1e;")
        right_layout.addWidget(self.canvas)
        
        main_layout.addWidget(right_panel, 1)
        
        self.refresh_data()

    def get_date_range(self):
        filter_text = self.combo_filter.currentText()
        today = QDate.currentDate()
        start_date = None
        
        if filter_text == "This Year":
            start_date = QDate(today.year(), 1, 1)
        elif filter_text == "This Month":
            start_date = QDate(today.year(), today.month(), 1)
        elif filter_text == "This Week":
            # Monday as start of week
            start_date = today.addDays(-(today.dayOfWeek() - 1))
        elif filter_text == "Today":
            start_date = today
            
        if start_date:
            # Format: YYYY-MM-DD 00:00:00
            return start_date.toString("yyyy-MM-dd 00:00:00"), None
        return None, None

    def refresh_data(self):
        start_date, end_date = self.get_date_range()
        
        # Graph
        self.plot_graph(start_date, end_date)
        
        # Stats：需要和当前 filter 一致，所以使用相同的日期范围过滤
        hands = self.db.get_hands_in_range(start_date, end_date) if hasattr(self.db, "get_hands_in_range") else self.db.get_all_hands()
        total_hands = len(hands)
        total_profit = sum(h[5] for h in hands) if hands else 0
        total_rake = sum((h[6] or 0) for h in hands) if hands else 0
        # insurance_premium 列在 schema 中是第 9 列（索引 8）
        total_insurance = sum((row[8] or 0) for row in hands if len(row) > 8) if hands else 0
        # jackpot 列在 schema 中是第 15 列（索引 14）
        total_jackpot = sum((row[14] or 0) for row in hands if len(row) > 14) if hands else 0

        # 你赢到 pot 的手（这里用 profit>0 近似“赢的局”，用于区分输赢局的费用统计）
        won_rake = sum((row[6] or 0) for row in hands if (row[5] or 0) > 0) if hands else 0
        won_jackpot = sum((row[14] or 0) for row in hands if len(row) > 14 and (row[5] or 0) > 0) if hands else 0

        self.lbl_total_hands.setText(f"Hands: {total_hands}")
        self.lbl_net_won.setText(f"Net: ${total_profit:.2f}")
        self.lbl_net_won.setStyleSheet(f"color: {PROFIT_GREEN if total_profit >= 0 else PROFIT_RED}; font-weight: bold;")
        self.lbl_rake.setText(f"Rake: ${total_rake:.2f}  (Won: ${won_rake:.2f})")
        self.lbl_insurance.setText(f"Insurance: ${total_insurance:.2f}")
        self.lbl_jackpot.setText(f"Jackpot: ${total_jackpot:.2f}  (Won: ${won_jackpot:.2f})")


    def plot_graph(self, start_date=None, end_date=None):
        graph_data = self.db.get_graph_data(start_date, end_date)
        self.figure.clear()
        
        dates_str = graph_data['dates']
        if not dates_str:
            self.canvas.draw()
            return

        ax = self.figure.add_subplot(111)
        ax.set_facecolor('#1e1e1e')
        
        # Axis styling
        ax.tick_params(axis='x', colors='#b0b0b0', labelsize=9)
        ax.tick_params(axis='y', colors='#b0b0b0', labelsize=9)
        for spine in ax.spines.values():
            spine.set_color('#3a3a3a')
        ax.xaxis.label.set_color('#b0b0b0')
        ax.yaxis.label.set_color('#b0b0b0')

        # Determine X-axis mode
        xaxis_mode = self.combo_xaxis.currentText()
        n_points = len(dates_str)
        
        if xaxis_mode == "Hands Played":
            x_values = list(range(1, n_points + 1))
            ax.set_xlabel("Hands Played", fontsize=10)
        else:  # Date/Time
            try:
                x_values = [datetime.datetime.strptime(d, "%Y-%m-%d %H:%M:%S") for d in dates_str]
            except:
                x_values = list(range(1, n_points + 1))
            ax.set_xlabel("Date", fontsize=10)

        # Define curve styles (like PokerTracker)
        curves = [
            ('net_won', self.chk_net_won, '#4caf50', '-', 2.0, 'Net Won'),
            ('showdown_won', self.chk_showdown, '#2196f3', '-', 1.5, 'Showdown Won'),
            ('non_showdown_won', self.chk_non_showdown, '#f44336', '-', 1.5, 'Non-SD Won'),
            ('all_in_ev', self.chk_ev, '#ff9800', '-', 1.5, 'All-in EV'),
        ]
        
        plotted_any = False
        for key, checkbox, color, linestyle, linewidth, label in curves:
            if checkbox.isChecked() and graph_data[key]:
                ax.plot(x_values, graph_data[key], color=color, linestyle=linestyle, 
                       linewidth=linewidth, label=label)
                plotted_any = True
        
        # Grid and zero line
        ax.grid(True, linestyle='--', alpha=0.15, color='#888888')
        ax.axhline(0, color='#555555', linewidth=1, linestyle='-')
        
        # Y-axis label
        ax.set_ylabel("Amount ($)", fontsize=10, color='#b0b0b0')
        
        # Format X-axis for date mode
        if xaxis_mode == "Date/Time" and x_values and isinstance(x_values[0], datetime.datetime):
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            self.figure.autofmt_xdate(rotation=45)
        
        # Legend (bottom center, like PokerTracker)
        if plotted_any:
            legend = ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), 
                              ncol=4, facecolor='#252525', edgecolor='#3a3a3a',
                              labelcolor='white', fontsize=9)
            legend.get_frame().set_alpha(0.9)

        self.figure.tight_layout()
        self.figure.subplots_adjust(bottom=0.18)  # Make room for legend
        self.canvas.draw()

class CashGamePage(QWidget):
    hand_selected = Signal(str)
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title / Filter placeholder
        header = QLabel("Cash Game Hands")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)

        # Table
        self.table_view = QTableView()
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)  # Enable column sorting
        self.table_view.doubleClicked.connect(self.on_row_double_clicked)
        layout.addWidget(self.table_view)

        self.refresh_data()

    def refresh_data(self):
        hands_data = self.db.get_all_hands()
        # Sort by date desc (newest first) as default
        hands_data.sort(key=lambda x: x[1] if x[1] else "", reverse=True)
        self._hands_data = hands_data
        model = HandsTableModel(hands_data)
        self.table_view.setModel(model)
        # Set default sort indicator on Date column (column 0, descending)
        self.table_view.horizontalHeader().setSortIndicator(0, Qt.DescendingOrder)

    def on_row_double_clicked(self, index):
        if not hasattr(self, "_hands_data"):
            return
        row = index.row()
        if 0 <= row < len(self._hands_data):
            hand_id = self._hands_data[row][0]
            if hand_id:
                self.hand_selected.emit(str(hand_id))

class ImportPage(QWidget):
    data_changed = Signal()

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Center Container
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        
        lbl_title = QLabel("Import Hand History")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        
        lbl_desc = QLabel("Select GGPoker text files to import hands into the database.")
        lbl_desc.setAlignment(Qt.AlignCenter)
        lbl_desc.setStyleSheet("color: #aaaaaa; margin-bottom: 30px;")

        self.btn_import = QPushButton("Select Files...")
        self.btn_import.setFixedSize(200, 50)
        self.btn_import.setStyleSheet("font-size: 16px;")
        self.btn_import.clicked.connect(self.import_files)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)

        center_layout.addWidget(lbl_title)
        center_layout.addWidget(lbl_desc)
        center_layout.addWidget(self.btn_import, 0, Qt.AlignCenter)
        center_layout.addWidget(self.progress_bar)
        center_layout.addWidget(self.lbl_status)
        center_layout.addStretch()

        layout.addStretch()
        layout.addWidget(center_container)
        layout.addStretch()

    def import_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Hand History Files", "", "Text Files (*.txt);;All Files (*)"
        )
        if files:
            self.btn_import.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0) # Infinite loading
            
            self.worker = ImportWorker(files)
            self.worker.progress.connect(self.update_status)
            self.worker.finished.connect(self.import_finished)
            self.worker.start()

    def update_status(self, msg):
        self.lbl_status.setText(msg)

    def import_finished(self, added, duplicates):
        self.lbl_status.setText(f"Import Complete.\nNew Hands: {added} | Duplicates: {duplicates}")
        self.progress_bar.setVisible(False)
        self.btn_import.setEnabled(True)
        self.data_changed.emit() # Notify main window to refresh


class ReplayPage(QWidget):
    """
    Simple hand replayer page.
    Layout（向 RIROPO 靠拢的简化版）:
    - 左侧：手牌列表（可选）
    - 中间：牌桌区域（背景图 + 座位 + 公共牌）
    - 右侧：动作 / "chat" 区域
    - 底部：导航按钮（Prev Hand / Prev Action / Play / Next Action / Next Hand）
    """

    def __init__(self, db_manager, show_hand_list=True):
        super().__init__()
        self.db = db_manager
        # 是否在左侧显示手牌列表列（主界面可选牌时，弹窗可以关闭这列）
        self.show_hand_list = show_hand_list
        self.current_hand_id = None
        self.current_hand = None
        self.current_action_index = -1
        self.actions = []
        self.replay_timer = QTimer(self)
        self.replay_timer.setInterval(800)
        self.replay_timer.timeout.connect(self.next_action)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        title = QLabel("Hand Replayer")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        main_layout.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        # Left: hands list（可选）
        if self.show_hand_list:
            left_panel = QWidget()
            left_layout = QVBoxLayout(left_panel)
            left_layout.setContentsMargins(0, 0, 0, 0)
            left_layout.setSpacing(6)

            lbl_hands = QLabel("Hands")
            lbl_hands.setStyleSheet("font-weight: bold;")
            left_layout.addWidget(lbl_hands)

            self.list_hands = QListWidget()
            self.list_hands.itemDoubleClicked.connect(self.on_hand_item_double_clicked)
            left_layout.addWidget(self.list_hands, 1)

            splitter.addWidget(left_panel)

        # Center: table area (canvas-style widget + info)
        center_panel = QFrame()
        center_panel.setObjectName("ReplayTable")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(4)

        self.table_widget = ReplayTableWidget()
        center_layout.addWidget(self.table_widget, 1)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(8, 4, 8, 0)
        info_layout.setSpacing(2)

        self.lbl_main_info = QLabel("Select a hand from the list or double-click in Cash Games.")
        self.lbl_main_info.setStyleSheet("font-size: 13px;")
        info_layout.addWidget(self.lbl_main_info)

        self.lbl_hero = QLabel("")
        self.lbl_board = QLabel("")
        self.lbl_pot = QLabel("")
        self.lbl_hero.setStyleSheet("font-weight: bold;")

        info_layout.addWidget(self.lbl_hero)
        info_layout.addWidget(self.lbl_board)
        info_layout.addWidget(self.lbl_pot)

        center_layout.addLayout(info_layout)

        splitter.addWidget(center_panel)

        # Right: "chat" / actions
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        lbl_chat = QLabel("Actions")
        lbl_chat.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(lbl_chat)

        # 控制是否展示对手底牌
        self.chk_show_villain = QCheckBox("Show Villain Cards")
        self.chk_show_villain.setChecked(False)
        self.chk_show_villain.stateChanged.connect(self.on_toggle_villain_cards)
        right_layout.addWidget(self.chk_show_villain)

        # 控制是否用 Big Blinds 视角（仿 RIROPO 的 "Show Stack Values in Big Blinds"）
        self.chk_show_bb = QCheckBox("Show Stack Values in Big Blinds")
        self.chk_show_bb.setChecked(False)
        self.chk_show_bb.stateChanged.connect(self.on_toggle_big_blinds)
        right_layout.addWidget(self.chk_show_bb)

        self.txt_actions = QTextEdit()
        self.txt_actions.setReadOnly(True)
        right_layout.addWidget(self.txt_actions, 1)

        splitter.addWidget(right_panel)
        # 根据是否有左侧列表设定初始比例（放大 table 区域）
        if self.show_hand_list:
            # 左侧列表 + 中间牌桌 + 右侧动作
            splitter.setSizes([200, 600, 250])
        else:
            # 只有中间牌桌和右侧动作（放大 table）
            splitter.setSizes([900, 300])

        # Bottom controls (navigation) - 只要三个按钮：prev action, play/pause, next action
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(0, 6, 0, 0)
        nav_layout.setSpacing(8)

        nav_layout.addStretch()

        self.btn_prev_action = QPushButton("◀ Prev")
        self.btn_play = QPushButton("▶ Play")
        self.btn_next_action = QPushButton("Next ▶")

        # 设置按钮样式和大小
        button_style = """
            QPushButton {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 13px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3b3b3b;
                border-color: #777;
            }
            QPushButton:pressed {
                background-color: #1b1b1b;
            }
            QPushButton:disabled {
                background-color: #1b1b1b;
                color: #666;
                border-color: #333;
            }
        """
        self.btn_prev_action.setStyleSheet(button_style)
        self.btn_play.setStyleSheet(button_style)
        self.btn_next_action.setStyleSheet(button_style)
        
        self.btn_prev_action.setToolTip("Previous Action")
        self.btn_play.setToolTip("Play / Pause")
        self.btn_next_action.setToolTip("Next Action")

        self.btn_prev_action.clicked.connect(self.prev_action)
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_next_action.clicked.connect(self.next_action)

        nav_layout.addWidget(self.btn_prev_action)
        nav_layout.addWidget(self.btn_play)
        nav_layout.addWidget(self.btn_next_action)

        nav_layout.addStretch()

        main_layout.addLayout(nav_layout)

        self.refresh_hand_list()

    # _setup_nav_button 方法已移除，现在使用简单的文本按钮

    # --- Public API ---
    def load_hand(self, hand_id):
        """Called from MainWindow when user double-clicks in CashGamePage."""
        self.current_hand_id = hand_id

        # 优先从数据库的稳定 JSON 结构恢复 replay（避免版本变更导致旧 hand 不可回放）
        self.current_hand = None
        payload = None
        if hasattr(self.db, "get_replay_payload"):
            payload = self.db.get_replay_payload(hand_id)

        if payload:
            # 轻量级对象，形状与 PokerHand 的回放字段兼容
            class ReplayHand:
                pass

            h = ReplayHand()
            h.hand_id = payload.get("hand_id")
            h.date_time = payload.get("date_time")
            h.game_type = payload.get("game_type", "")
            h.blinds = payload.get("blinds", "")
            h.hero_name = payload.get("hero_name", "Hero")
            h.hero_seat = payload.get("hero_seat", 0)
            h.hero_hole_cards = payload.get("hero_hole_cards", "")
            h.button_seat = payload.get("button_seat", 0)
            h.total_pot = payload.get("total_pot", 0.0)
            h.rake = payload.get("rake", 0.0)
            h.jackpot = payload.get("jackpot", 0.0)
            h.net_profit = payload.get("net_profit", 0.0)
            h.went_to_showdown = bool(payload.get("went_to_showdown", 0))
            h.board_cards = payload.get("board_cards", [])
            h.actions = payload.get("actions", [])

            # players_info: {seat: {name, chips_start, hole_cards}}
            h.players_info = {}
            for p in payload.get("players", []):
                seat = p.get("seat")
                if seat is None:
                    continue
                h.players_info[int(seat)] = {
                    "name": p.get("name"),
                    "chips_start": p.get("stack_start", 0.0),
                    "hole_cards": p.get("hole_cards", ""),
                }

            self.current_hand = h
        else:
            # 回退到当前会话的内存缓存（只对新解析的 hand 生效）
            self.current_hand = get_hand_by_id(hand_id)
        self.current_action_index = -1
        self.actions = []
        self.txt_actions.clear()

        if not self.current_hand:
            self.lbl_main_info.setText(f"Hand {hand_id} not available for replay (not in current session).")
            self.lbl_hero.setText("")
            self.lbl_board.setText("")
            self.lbl_pot.setText("")
            self.table_widget.set_hand(None)
            return

        self.lbl_main_info.setText(
            f"{self.current_hand.game_type} @ {self.current_hand.blinds}  |  {self.current_hand.date_time}"
        )
        self.lbl_hero.setText(f"Hero: {self.current_hand.hero_hole_cards}  (Profit: ${self.current_hand.net_profit:.2f})")

        # Board（兼容 run-it-twice：actions 里会有 board 节点，分别带 board_run=1/2）
        board1 = []
        board2 = []
        has_timeline_board = False
        for a in getattr(self.current_hand, "actions", []) or []:
            if not isinstance(a, dict):
                continue
            if a.get("action_type") != "board":
                continue
            has_timeline_board = True
            run_idx = a.get("board_run") or 1
            cards = a.get("board_cards") or []
            if not isinstance(cards, list):
                cards = []
            if run_idx == 2:
                board2 = list(cards)
            else:
                board1 = list(cards)

        if has_timeline_board:
            if board2:
                self.lbl_board.setText(
                    f"Board: 1st: {' '.join(board1) if board1 else '-'} | 2nd: {' '.join(board2) if board2 else '-'}"
                )
            else:
                self.lbl_board.setText(f"Board: {' '.join(board1) if board1 else '-'}")
        else:
            full_board = []
            for street in getattr(self.current_hand, "board_cards", []) or []:
                if isinstance(street, dict):
                    full_board.extend(street.get("cards", []) or [])
            self.lbl_board.setText(f"Board: {' '.join(full_board)}" if full_board else "Board: -")

        jackpot = getattr(self.current_hand, "jackpot", 0.0) or 0.0
        pot_text = f"Total Pot: ${self.current_hand.total_pot:.2f} | Rake: ${self.current_hand.rake:.2f}"
        if jackpot > 0:
            pot_text += f" | Jackpot: ${jackpot:.2f}"
        self.lbl_pot.setText(pot_text)

        # Update table canvas
        self.table_widget.set_hand(self.current_hand)

        # Use recorded actions as timeline
        # 先保留一份原始 actions（run-it-twice 的最终 board 需要用到全部 board 节点）
        raw_actions = list(getattr(self.current_hand, "actions", []) or [])
        self.actions = list(raw_actions)

        # run-it-twice：预先计算两条 run 的“最终完整 board”（各 5 张），供桌面 all-in 后一次性亮牌使用
        board1 = []
        board2 = []
        has_raw_timeline_board = False
        for a in raw_actions:
            if not isinstance(a, dict):
                continue
            if a.get("action_type") != "board":
                continue
            has_raw_timeline_board = True
            run_idx = a.get("board_run") or 1
            cards = a.get("board_cards") or []
            if not isinstance(cards, list):
                cards = []
            if run_idx == 2:
                board2 = list(cards)
            else:
                board1 = list(cards)
        if has_raw_timeline_board:
            setattr(self.current_hand, "run_it_twice", True)
            setattr(self.current_hand, "rit_final_board_1", list(board1))
            setattr(self.current_hand, "rit_final_board_2", list(board2))
        # 兼容旧版 replay 数据：同一 street 不应出现多个 pot_complete
        #（旧逻辑可能在每条 collected 前都插入一次 pot_complete，导致时间线错误）
        seen_pot_complete_streets = set()
        normalized = []
        for a in self.actions:
            if not isinstance(a, dict):
                continue
            if a.get("action_type") == "pot_complete":
                street = a.get("street", "")
                if street in seen_pot_complete_streets:
                    continue
                seen_pot_complete_streets.add(street)
            normalized.append(a)
        self.actions = normalized

        # run-it-twice：board 节点很多，但我们现在是“Preflop 结束后直接亮出完整两条 board”
        # 所以保留第一个 board 节点作为“亮牌触发点”，其余 board 节点直接折叠掉，避免 next 没画面变化
        has_timeline_board = any(
            isinstance(a, dict) and a.get("action_type") == "board" for a in (self.actions or [])
        )
        if has_timeline_board:
            first_board_seen = False
            collapsed = []
            for a in self.actions:
                if not isinstance(a, dict):
                    continue
                if a.get("action_type") == "board":
                    if first_board_seen:
                        continue
                    first_board_seen = True
                collapsed.append(a)
            self.actions = collapsed
        # 从能看到牌、大小盲都操作完之后的界面开始
        # 找到 blinds 后的第一个非-blind action（发牌后的第一个 action）
        start_index = -1
        if self.actions:
            # 找到最后一个 blind action
            last_blind_index = -1
            for i, act in enumerate(self.actions):
                act_type = act.get("action_type", "")
                if act_type in ["post_small_blind", "post_big_blind", "post_straddle_blind"]:
                    last_blind_index = i
            # 从最后一个 blind 后的第一个 action 开始（发牌后的第一个 action）
            if last_blind_index >= 0 and last_blind_index < len(self.actions) - 1:
                start_index = last_blind_index  # 显示到最后一个 blind，这样可以看到 blinds 的筹码和发牌后的状态
            elif last_blind_index >= 0:
                # 如果 blinds 是最后一个 action，就从那里开始
                start_index = last_blind_index
        self.current_action_index = start_index
        # 同步给牌桌组件
        self.table_widget.set_timeline(self.actions, self.current_action_index)
        self.append_actions_text(reset=True)

        # Also highlight in list widget if present
        if self.show_hand_list:
            for i in range(self.list_hands.count()):
                item = self.list_hands.item(i)
                if item.data(Qt.UserRole) == hand_id:
                    self.list_hands.setCurrentRow(i)
                    break

        # 根据当前手牌是否摊牌，决定 toggle 默认是否可用（先保持勾选状态不变）
        # 这里只是触发一次刷新，具体逻辑在 ReplayTableWidget 内判断
        self.table_widget.set_show_villain_cards(self.chk_show_villain.isChecked())
        self.table_widget.set_show_big_blinds(self.chk_show_bb.isChecked())

    # --- Navigation handlers ---
    def prev_hand(self):
        if not self.show_hand_list:
            return
        current_row = self.list_hands.currentRow()
        if current_row > 0:
            self.list_hands.setCurrentRow(current_row - 1)
            item = self.list_hands.currentItem()
            if item:
                hand_id = item.data(Qt.UserRole)
                self.load_hand(hand_id)

    def next_hand(self):
        if not self.show_hand_list:
            return
        current_row = self.list_hands.currentRow()
        if current_row < self.list_hands.count() - 1:
            self.list_hands.setCurrentRow(current_row + 1)
            item = self.list_hands.currentItem()
            if item:
                hand_id = item.data(Qt.UserRole)
                self.load_hand(hand_id)

    def prev_action(self):
        if not self.actions:
            return
        # 不让某些“计算用事件”占一画（例如 uncalled_bet_returned）
        skip_types = {"uncalled_bet_returned"}
        idx = max(-1, self.current_action_index - 1)
        while idx >= 0 and isinstance(self.actions[idx], dict) and self.actions[idx].get("action_type") in skip_types:
            idx -= 1
        self.current_action_index = idx
        # 如果停止播放，更新按钮文本
        if self.replay_timer.isActive():
            self.replay_timer.stop()
            self.btn_play.setText("▶ Play")
        # 更新牌桌与动作文本
        self.table_widget.set_timeline(self.actions, self.current_action_index)
        self.append_actions_text(reset=True)

    def next_action(self):
        if not self.actions:
            return
        # 不让某些“计算用事件”占一画（例如 uncalled_bet_returned）
        skip_types = {"uncalled_bet_returned"}
        if self.current_action_index < len(self.actions) - 1:
            idx = self.current_action_index + 1
            while idx < len(self.actions) and isinstance(self.actions[idx], dict) and self.actions[idx].get("action_type") in skip_types:
                idx += 1
            self.current_action_index = min(idx, len(self.actions) - 1)
            # 更新牌桌与动作文本
            self.table_widget.set_timeline(self.actions, self.current_action_index)
            self.append_actions_text(reset=True)
        else:
            # reached the end, stop autoplay
            if self.replay_timer.isActive():
                self.replay_timer.stop()
                self.btn_play.setText("▶ Play")

    def toggle_play(self):
        if not self.actions:
            return
        if self.replay_timer.isActive():
            self.replay_timer.stop()
            self.btn_play.setText("▶ Play")
        else:
            self.replay_timer.start()
            self.btn_play.setText("⏸ Pause")

    # --- Helpers ---
    def refresh_hand_list(self):
        """Load simple hand list from DB into the left panel."""
        if not self.show_hand_list:
            return
        self.list_hands.clear()
        hands = self.db.get_all_hands()
        # newest first
        hands.sort(key=lambda x: x[1] if x[1] else "", reverse=True)
        for row in hands:
            hand_id = row[0]
            date = row[1] or ""
            blinds = row[2] or ""
            game = row[3] or ""
            cards = row[4] or ""
            profit = row[5] or 0.0
            text = f"{date} | {game} {blinds} | {cards} | ${profit:.2f}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, hand_id)
            self.list_hands.addItem(item)

    def append_actions_text(self, reset=False):
        """
        Render actions up to current_action_index in the right-side text area.
        从最开始显示，初始状态（index=-1）不显示任何 action。
        """
        if reset:
            self.txt_actions.clear()
        
        if not self.actions:
            return

        # max_index = -1 表示初始状态，不显示任何 action
        max_index = self.current_action_index
        
        # 初始状态：不显示任何 action
        if max_index < 0:
            self.txt_actions.append("Ready to start replay...")
            self.txt_actions.moveCursor(QTextCursor.Start)
            return
        
        # 显示到 current_action_index 为止的所有 actions（从最开始）
        for i, act in enumerate(self.actions):
            # 只显示到当前 index 为止
            if i > max_index:
                break
                
            street = act.get("street", "")
            player = act.get("player", "")
            action_type = act.get("action_type", "")
            amount = act.get("amount")
            to_amount = act.get("to_amount")
            pot_size = act.get("pot_size")

            parts = []
            if street:
                parts.append(f"[{street}]")
            if player:
                parts.append(player + ":")
            if action_type:
                parts.append(action_type)
            if amount is not None and amount != 0:
                parts.append(f"${amount:.2f}")
            if to_amount is not None:
                parts.append(f"to ${to_amount:.2f}")
            if pot_size is not None:
                parts.append(f"(pot: ${pot_size:.2f})")

            line = " ".join(parts)
            if line:
                if i == max_index:
                    self.txt_actions.append(f"> {line}")
                else:
                    self.txt_actions.append(f"  {line}")

        # 滚动到当前 action
        cursor = self.txt_actions.textCursor()
        cursor.movePosition(QTextCursor.Start)
        # 移动到第 max_index + 1 行（因为第一行是 index 0）
        for _ in range(max_index + 1):
            if not cursor.movePosition(QTextCursor.Down):
                break
        self.txt_actions.setTextCursor(cursor)

    def on_hand_item_double_clicked(self, item):
        if not self.show_hand_list:
            return
        hand_id = item.data(Qt.UserRole)
        if hand_id:
            self.load_hand(hand_id)

    def on_toggle_villain_cards(self, state):
        # 仅在摊牌局中起效，内部会再做一次校验
        self.table_widget.set_show_villain_cards(bool(state))

    def on_toggle_big_blinds(self, state):
        # 切换 $ 和 BB 视角
        self.table_widget.set_show_big_blinds(bool(state))
