"""
Report 页面容器 - 包含报告选择器和报告内容区域
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QStackedWidget, QTreeWidget, QTreeWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush

from .position_analysis import PositionAnalysisReport


class ReportPage(QWidget):
    """
    Report 页面，包含报告选择器和报告内容区域
    """
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.init_ui()
    
    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Left: Report Selector
        report_selector = QFrame()
        report_selector.setFixedWidth(240)
        report_selector.setStyleSheet("""
            QFrame { background-color: #252525; border-right: 1px solid #3a3a3a; }
            QLabel { color: #b0b0b0; font-size: 11px; }
            QTreeWidget { background-color: #252525; border: none; color: #e0e0e0; }
            QTreeWidget::item { padding: 6px; }
            QTreeWidget::item:selected { background-color: #3a3a3a; }
            QTreeWidget::item:hover { background-color: #2f2f2f; }
        """)
        selector_layout = QVBoxLayout(report_selector)
        selector_layout.setContentsMargins(12, 16, 12, 16)
        selector_layout.setSpacing(8)
        
        lbl_report_title = QLabel("REPORT")
        lbl_report_title.setStyleSheet("color: #888888; font-size: 10px; font-weight: bold; padding: 4px 0;")
        selector_layout.addWidget(lbl_report_title)
        
        # Report Tree
        self.report_tree = QTreeWidget()
        self.report_tree.setHeaderHidden(True)
        self.report_tree.setRootIsDecorated(True)
        self.report_tree.itemClicked.connect(self.on_report_selected)
        
        # RESULTS category
        results_cat = QTreeWidgetItem(self.report_tree)
        results_cat.setText(0, "RESULTS")
        results_cat.setExpanded(False)
        results_cat.setFlags(results_cat.flags() & ~Qt.ItemIsSelectable)
        results_cat.setForeground(0, QBrush(QColor("#b0b0b0")))
        
        # PREFLOP category
        preflop_cat = QTreeWidgetItem(self.report_tree)
        preflop_cat.setText(0, "PREFLOP")
        preflop_cat.setExpanded(False)
        preflop_cat.setFlags(preflop_cat.flags() & ~Qt.ItemIsSelectable)
        preflop_cat.setForeground(0, QBrush(QColor("#b0b0b0")))
        
        # ANALYSIS category
        analysis_cat = QTreeWidgetItem(self.report_tree)
        analysis_cat.setText(0, "ANALYSIS")
        analysis_cat.setExpanded(True)
        analysis_cat.setFlags(analysis_cat.flags() & ~Qt.ItemIsSelectable)
        analysis_cat.setForeground(0, QBrush(QColor("#b0b0b0")))
        
        position_item = QTreeWidgetItem(analysis_cat)
        position_item.setText(0, "Position")
        position_item.setData(0, Qt.UserRole, "position")
        
        cbet_item = QTreeWidgetItem(analysis_cat)
        cbet_item.setText(0, "CBet Success")
        cbet_item.setData(0, Qt.UserRole, "cbet_success")
        
        ev_item = QTreeWidgetItem(analysis_cat)
        ev_item.setText(0, "Expected Value by Stakes")
        ev_item.setData(0, Qt.UserRole, "ev_by_stakes")
        
        tag_item = QTreeWidgetItem(analysis_cat)
        tag_item.setText(0, "Tag")
        tag_item.setData(0, Qt.UserRole, "tag")
        
        multitbl_item = QTreeWidgetItem(analysis_cat)
        multitbl_item.setText(0, "Multi-Table")
        multitbl_item.setData(0, Qt.UserRole, "multi_table")
        
        # DATE AND TIME category
        datetime_cat = QTreeWidgetItem(self.report_tree)
        datetime_cat.setText(0, "DATE AND TIME")
        datetime_cat.setExpanded(False)
        datetime_cat.setFlags(datetime_cat.flags() & ~Qt.ItemIsSelectable)
        datetime_cat.setForeground(0, QBrush(QColor("#b0b0b0")))
        
        sessions_item = QTreeWidgetItem(datetime_cat)
        sessions_item.setText(0, "Sessions")
        sessions_item.setData(0, Qt.UserRole, "sessions")
        
        sessions_day_item = QTreeWidgetItem(datetime_cat)
        sessions_day_item.setText(0, "Sessions by Day")
        sessions_day_item.setData(0, Qt.UserRole, "sessions_by_day")
        
        sessions_month_item = QTreeWidgetItem(datetime_cat)
        sessions_month_item.setText(0, "Sessions by Month")
        sessions_month_item.setData(0, Qt.UserRole, "sessions_by_month")
        
        sessions_table_item = QTreeWidgetItem(datetime_cat)
        sessions_table_item.setText(0, "Sessions by Table")
        sessions_table_item.setData(0, Qt.UserRole, "sessions_by_table")
        
        hour_item = QTreeWidgetItem(datetime_cat)
        hour_item.setText(0, "Hour of Day")
        hour_item.setData(0, Qt.UserRole, "hour_of_day")
        
        dayweek_item = QTreeWidgetItem(datetime_cat)
        dayweek_item.setText(0, "Day of Week")
        dayweek_item.setData(0, Qt.UserRole, "day_of_week")
        
        selector_layout.addWidget(self.report_tree)
        selector_layout.addStretch()
        
        main_layout.addWidget(report_selector)
        
        # Right: Report Content Area
        self.report_content = QStackedWidget()
        self.report_content.setStyleSheet("background-color: #1e1e1e;")
        main_layout.addWidget(self.report_content, 1)
        
        # Register reports
        self.report_widgets = {}
        
        # Position Analysis Report
        self.position_report = PositionAnalysisReport(self.db)
        self.report_content.addWidget(self.position_report)
        self.report_widgets["position"] = self.position_report
        
        # Default selection
        position_item.setSelected(True)
        self.report_content.setCurrentWidget(self.position_report)
    
    def on_report_selected(self, item, column):
        """Handle report selection"""
        report_id = item.data(0, Qt.UserRole)
        if not report_id:
            return
        
        if report_id in self.report_widgets:
            widget = self.report_widgets[report_id]
            self.report_content.setCurrentWidget(widget)
            if hasattr(widget, "refresh_data"):
                widget.refresh_data(None, None)
        else:
            if "placeholder" not in self.report_widgets:
                placeholder = QLabel(f"Report '{report_id}' is coming soon...")
                placeholder.setStyleSheet("color: #b0b0b0; font-size: 14px; padding: 40px;")
                placeholder.setAlignment(Qt.AlignCenter)
                self.report_content.addWidget(placeholder)
                self.report_widgets["placeholder"] = placeholder
            self.report_content.setCurrentWidget(self.report_widgets["placeholder"])
    
    def select_report(self, report_id):
        """Select a report by ID"""
        root = self.report_tree.invisibleRootItem()
        for i in range(root.childCount()):
            category = root.child(i)
            category.setExpanded(True)
            for j in range(category.childCount()):
                item = category.child(j)
                if item.data(0, Qt.UserRole) == report_id:
                    item.setSelected(True)
                    self.report_tree.setCurrentItem(item)
                    self.on_report_selected(item, 0)
                    return
    
    def refresh_data(self):
        """Refresh current report data"""
        current_widget = self.report_content.currentWidget()
        if hasattr(current_widget, "refresh_data"):
            current_widget.refresh_data(None, None)

