from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, 
                               QListWidget, QListWidgetItem, QStackedWidget)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

from db_manager import DBManager
from gui.pages import DashboardPage, CashGamePage, ImportPage
from gui.styles import DARK_THEME_QSS, SIDEBAR_COLOR

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GGPoker Hand Tracker")
        self.resize(1200, 800)
        self.setStyleSheet(DARK_THEME_QSS)

        self.db = DBManager()

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(220)
        self.sidebar.currentRowChanged.connect(self.switch_page)
        
        # Add Items
        items = ["Dashboard", "Cash Games", "Import"]
        # In a real app, you'd add icons here (QIcon)
        for item_text in items:
            item = QListWidgetItem(item_text)
            item.setSizeHint(QSize(0, 50))
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.sidebar.addItem(item)
            
        main_layout.addWidget(self.sidebar)

        # 2. Content Area (Stacked)
        self.content_area = QStackedWidget()
        main_layout.addWidget(self.content_area)

        # Initialize Pages
        self.page_dashboard = DashboardPage(self.db)
        self.page_cash = CashGamePage(self.db)
        self.page_import = ImportPage()

        # Connect Signals
        self.page_import.data_changed.connect(self.on_data_changed)

        # Add to Stack
        self.content_area.addWidget(self.page_dashboard)
        self.content_area.addWidget(self.page_cash)
        self.content_area.addWidget(self.page_import)

        # Select first item
        self.sidebar.setCurrentRow(0)

    def switch_page(self, index):
        self.content_area.setCurrentIndex(index)

    def on_data_changed(self):
        # Refresh all data pages
        self.page_dashboard.refresh_data()
        self.page_cash.refresh_data()

