"""
手牌表格数据模型
"""
from PySide6.QtCore import Qt, QAbstractTableModel
from PySide6.QtGui import QColor, QBrush

from gui.styles import PROFIT_GREEN, PROFIT_RED


class HandsTableModel(QAbstractTableModel):
    """手牌表格的数据模型"""
    
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

