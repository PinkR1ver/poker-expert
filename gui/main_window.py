from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout,
    QListWidget, QListWidgetItem, QStackedWidget
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

from db_manager import DBManager
from gui.pages import DashboardPage, CashGamePage, ImportPage, ReplayPage
from gui.styles import DARK_THEME_QSS, SIDEBAR_COLOR


class ReplayWindow(QMainWindow):
    """
    独立的 Hand Replay 窗口。
    复用 ReplayPage 作为 central widget。
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hand Replayer")
        self.resize(1400, 900)  # 放大窗口，给 table 更多空间
        # 弹窗内不需要左侧手牌列表列
        self.replay_page = ReplayPage(db_manager, show_hand_list=False)
        self.setCentralWidget(self.replay_page)

    def load_hand(self, hand_id: str):
        self.replay_page.load_hand(hand_id)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GGPoker Hand Tracker")
        self.resize(1200, 800)
        self.setStyleSheet(DARK_THEME_QSS)

        self.db = DBManager()
        self.replay_window = None  # 独立 Replay 窗口实例

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
        
        # Add Items (Replay 不占侧边栏，只保留 Dashboard / Cash Games / Import)
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
        self.page_replay = ReplayPage(self.db)  # 内部备用（目前主要给弹窗复用状态）
        self.page_import = ImportPage()

        # Connect Signals
        self.page_import.data_changed.connect(self.on_data_changed)
        self.page_cash.hand_selected.connect(self.on_hand_selected)

        # Add to Stack（与 sidebar 对齐：0=Dashboard,1=Cash,2=Import）
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

    def on_hand_selected(self, hand_id):
        """
        当在 Cash Games 双击一手牌时：
        - 更新内部的 ReplayPage 状态（便于弹窗和后续扩展）
        - 弹出独立 ReplayWindow 播放这手牌
        """
        # 更新内部 ReplayPage（不再通过侧边栏展示）
        self.page_replay.load_hand(hand_id)

        # 再处理独立 Replay 窗口
        if self.replay_window is None:
            self.replay_window = ReplayWindow(self.db, self)
        self.replay_window.load_hand(hand_id)
        self.replay_window.show()
        self.replay_window.raise_()
        self.replay_window.activateWindow()





