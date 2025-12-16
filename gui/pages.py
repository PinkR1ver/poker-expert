import os
import datetime
import numpy as np
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QFrame, QTableView, QHeaderView, QPushButton,
                               QFileDialog, QProgressBar, QSpacerItem, QSizePolicy,
                               QComboBox, QCheckBox)
from PySide6.QtCore import Qt, QAbstractTableModel, QThread, Signal, QDate
from PySide6.QtGui import QColor, QBrush

# Matplotlib
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
except ImportError:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates

from poker_parser import parse_file
from db_manager import DBManager
from gui.styles import PROFIT_GREEN, PROFIT_RED

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
        left_layout.addWidget(self.lbl_total_hands)
        left_layout.addWidget(self.lbl_net_won)
        left_layout.addWidget(self.lbl_rake)
        left_layout.addWidget(self.lbl_insurance)
        
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
        
        # Stats
        hands = self.db.get_all_hands()
        total_hands = len(hands)
        total_profit = sum(h[5] for h in hands) if hands else 0
        total_rake = sum(h[6] for h in hands) if hands else 0
        # insurance_premium is at index 14 (added via ALTER TABLE, so it's at the end)
        total_insurance = sum(h[14] if len(h) > 14 and h[14] else 0 for h in hands) if hands else 0

        self.lbl_total_hands.setText(f"Hands: {total_hands}")
        self.lbl_net_won.setText(f"Net: ${total_profit:.2f}")
        self.lbl_net_won.setStyleSheet(f"color: {PROFIT_GREEN if total_profit >= 0 else PROFIT_RED}; font-weight: bold;")
        self.lbl_rake.setText(f"Rake: ${total_rake:.2f}")
        self.lbl_insurance.setText(f"Insurance: ${total_insurance:.2f}")


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
        layout.addWidget(self.table_view)

        self.refresh_data()

    def refresh_data(self):
        hands_data = self.db.get_all_hands()
        # Sort by date desc (newest first) as default
        hands_data.sort(key=lambda x: x[1] if x[1] else "", reverse=True)
        model = HandsTableModel(hands_data)
        self.table_view.setModel(model)
        # Set default sort indicator on Date column (column 0, descending)
        self.table_view.horizontalHeader().setSortIndicator(0, Qt.DescendingOrder)

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

