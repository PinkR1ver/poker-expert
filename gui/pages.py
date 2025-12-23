"""
兼容性导入文件 - 保持向后兼容性

注意：这个文件保留是为了向后兼容。
实际的页面类已经拆分到 gui/pages/ 目录下：
- gui/pages/dashboard.py - DashboardPage
- gui/pages/cash_game.py - CashGamePage, CashGameGraphPage
- gui/pages/import_page.py - ImportPage, ImportWorker
- gui/pages/replay.py - ReplayPage
- gui/pages/reports/ - ReportPage, PositionAnalysisReport

建议使用新的导入路径：
    from gui.pages import DashboardPage, CashGamePage, ...
"""

# 从新模块重新导出所有类，保持向后兼容性
from gui.pages.dashboard import DashboardPage
from gui.pages.cash_game import CashGamePage, CashGameGraphPage
from gui.pages.import_page import ImportPage, ImportWorker
from gui.pages.replay import ReplayPage
from gui.pages.reports import ReportPage, PositionAnalysisReport, PositionTableWidget
from gui.components import StatCard, HandsTableModel

__all__ = [
    'StatCard',
    'HandsTableModel',
    'ImportWorker',
    'DashboardPage',
    'CashGameGraphPage',
    'ReportPage',
    'PositionTableWidget',
    'PositionAnalysisReport',
    'CashGamePage',
    'ImportPage',
    'ReplayPage',
]
