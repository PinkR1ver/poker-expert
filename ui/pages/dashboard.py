"""
Dashboard 页面 - 显示盈亏图表和统计摘要
"""
import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QComboBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QDate

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
except ImportError:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates

from ui.styles import PROFIT_GREEN, PROFIT_RED


class DashboardPage(QWidget):
    """Dashboard 页面，显示盈亏图表和统计摘要"""
    
    # 信号：当用户点击报告链接时发出
    report_link_clicked = Signal(str)  # report_id
    
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Left Panel - Filter/Controls
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
        
        # KPI summary at bottom
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
        
        # Right Panel - Graph
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)
        
        # Graph Area
        graph_container = QWidget()
        graph_layout = QVBoxLayout(graph_container)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        self.figure = Figure(facecolor='#1e1e1e')
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background-color: #1e1e1e;")
        graph_layout.addWidget(self.canvas)
        right_layout.addWidget(graph_container, 1)
        
        # Reports Navigation Links
        reports_nav = QWidget()
        reports_nav_layout = QVBoxLayout(reports_nav)
        reports_nav_layout.setContentsMargins(0, 8, 0, 0)
        reports_nav_layout.setSpacing(8)
        
        lbl_reports_title = QLabel("REPORTS")
        lbl_reports_title.setStyleSheet("color: #888888; font-size: 10px; font-weight: bold; padding: 4px 0;")
        reports_nav_layout.addWidget(lbl_reports_title)
        
        self.lbl_position_link = QLabel('<a href="position" style="color: #4caf50; text-decoration: none;">Position Analysis</a>')
        self.lbl_position_link.setOpenExternalLinks(False)
        self.lbl_position_link.linkActivated.connect(self.on_report_link_clicked)
        self.lbl_position_link.setStyleSheet("color: #4caf50; padding: 4px 0; font-size: 13px;")
        reports_nav_layout.addWidget(self.lbl_position_link)
        
        reports_nav_layout.addStretch()
        right_layout.addWidget(reports_nav, 1)
        
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
            start_date = today.addDays(-(today.dayOfWeek() - 1))
        elif filter_text == "Today":
            start_date = today
            
        if start_date:
            return start_date.toString("yyyy-MM-dd 00:00:00"), None
        return None, None

    def on_report_link_clicked(self, link):
        """当用户点击报告链接时发出信号"""
        self.report_link_clicked.emit(link)

    def refresh_data(self):
        start_date, end_date = self.get_date_range()
        
        self.plot_graph(start_date, end_date)
        
        hands = self.db.get_hands_in_range(start_date, end_date) if hasattr(self.db, "get_hands_in_range") else self.db.get_all_hands()
        total_hands = len(hands)
        total_profit = sum(h[5] for h in hands) if hands else 0
        total_rake = sum((h[6] or 0) for h in hands) if hands else 0
        total_insurance = sum((row[8] or 0) for row in hands if len(row) > 8) if hands else 0
        total_jackpot = sum((row[14] or 0) for row in hands if len(row) > 14) if hands else 0

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
        
        ax.tick_params(axis='x', colors='#b0b0b0', labelsize=9)
        ax.tick_params(axis='y', colors='#b0b0b0', labelsize=9)
        for spine in ax.spines.values():
            spine.set_color('#3a3a3a')
        ax.xaxis.label.set_color('#b0b0b0')
        ax.yaxis.label.set_color('#b0b0b0')

        xaxis_mode = self.combo_xaxis.currentText()
        n_points = len(dates_str)
        
        if xaxis_mode == "Hands Played":
            x_values = list(range(1, n_points + 1))
            ax.set_xlabel("Hands Played", fontsize=10)
        else:
            try:
                x_values = [datetime.datetime.strptime(d, "%Y-%m-%d %H:%M:%S") for d in dates_str]
            except:
                x_values = list(range(1, n_points + 1))
            ax.set_xlabel("Date", fontsize=10)

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
        
        ax.grid(True, linestyle='--', alpha=0.15, color='#888888')
        ax.axhline(0, color='#555555', linewidth=1, linestyle='-')
        ax.set_ylabel("Amount ($)", fontsize=10, color='#b0b0b0')
        
        if xaxis_mode == "Date/Time" and x_values and isinstance(x_values[0], datetime.datetime):
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            self.figure.autofmt_xdate(rotation=45)
        
        if plotted_any:
            legend = ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), 
                              ncol=4, facecolor='#252525', edgecolor='#3a3a3a',
                              labelcolor='white', fontsize=9)
            legend.get_frame().set_alpha(0.9)

        self.figure.tight_layout()
        self.figure.subplots_adjust(bottom=0.18)
        self.canvas.draw()




