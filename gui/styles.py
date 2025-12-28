# Dark Theme Colors
BACKGROUND_COLOR = "#2b2b2b"
SIDEBAR_COLOR = "#323232"
TEXT_COLOR = "#ffffff"
ACCENT_COLOR = "#0d47a1"  # Blueish
HOVER_COLOR = "#3d3d3d"
BORDER_COLOR = "#444444"

# Text Colors for Profit
PROFIT_GREEN = "#4caf50"
PROFIT_RED = "#f44336"

# Stylesheet
DARK_THEME_QSS = f"""
QMainWindow {{
    background-color: {BACKGROUND_COLOR};
    color: {TEXT_COLOR};
}}

QWidget {{
    background-color: {BACKGROUND_COLOR};
    color: {TEXT_COLOR};
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 14px;
}}

/* Sidebar Styling */
QListWidget {{
    background-color: {SIDEBAR_COLOR};
    border: none;
    outline: none;
    font-size: 16px;
}}

QListWidget::item {{
    height: 50px;
    padding-left: 15px;
    border-left: 3px solid transparent;
}}

QListWidget::item:selected {{
    background-color: {HOVER_COLOR};
    border-left: 3px solid {ACCENT_COLOR};
    color: {TEXT_COLOR};
}}

QListWidget::item:hover {{
    background-color: {HOVER_COLOR};
}}

/* Table Styling */
QTableView {{
    background-color: {BACKGROUND_COLOR};
    gridline-color: {BORDER_COLOR};
    border: 1px solid {BORDER_COLOR};
    selection-background-color: {ACCENT_COLOR};
    selection-color: {TEXT_COLOR};
}}

QHeaderView::section {{
    background-color: {SIDEBAR_COLOR};
    padding: 5px;
    border: 1px solid {BORDER_COLOR};
    font-weight: bold;
}}

QTableView QTableCornerButton::section {{
    background-color: {SIDEBAR_COLOR};
    border: 1px solid {BORDER_COLOR};
}}

/* Card Styling */
QFrame#StatCard {{
    background-color: {SIDEBAR_COLOR};
    border-radius: 8px;
    border: 1px solid {BORDER_COLOR};
}}

QLabel#CardTitle {{
    color: #aaaaaa;
    font-size: 13px;
    font-weight: bold;
}}

QLabel#CardValue {{
    color: {TEXT_COLOR};
    font-size: 24px;
    font-weight: bold;
}}

/* Buttons */
QPushButton {{
    background-color: {ACCENT_COLOR};
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: bold;
}}

QPushButton:hover {{
    background-color: #1565c0;
}}

QPushButton:disabled {{
    background-color: #555555;
    color: #888888;
}}

/* Scrollbars */
QScrollBar:vertical {{
    border: none;
    background: {BACKGROUND_COLOR};
    width: 10px;
    margin: 0px 0px 0px 0px;
}}

QScrollBar::handle:vertical {{
    background: #555555;
    min-height: 20px;
    border-radius: 5px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    border: none;
    background: none;
}}
"""







