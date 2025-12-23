"""
Sessions 页面 - 显示 Session 统计和手牌历史
"""
import datetime
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QTableView, QHeaderView, QComboBox, QCheckBox,
    QSplitter, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QDate, QAbstractTableModel, QSortFilterProxyModel
from PySide6.QtGui import QColor, QBrush

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
except ImportError:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates

from gui.styles import PROFIT_GREEN, PROFIT_RED


class SortableProxyModel(QSortFilterProxyModel):
    """支持多列排序的代理模型"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._sort_columns = []  # [(column, order), ...]
    
    def lessThan(self, left, right):
        """使用 UserRole 数据进行排序"""
        left_data = self.sourceModel().data(left, Qt.UserRole)
        right_data = self.sourceModel().data(right, Qt.UserRole)
        
        # 处理 None
        if left_data is None:
            return True
        if right_data is None:
            return False
        
        # 比较
        try:
            return left_data < right_data
        except TypeError:
            return str(left_data) < str(right_data)
    
    def get_source_row(self, proxy_row):
        """获取源模型的行号"""
        proxy_index = self.index(proxy_row, 0)
        source_index = self.mapToSource(proxy_index)
        return source_index.row()


class SessionsTableModel(QAbstractTableModel):
    """Sessions 表格数据模型"""
    
    def __init__(self, data=None):
        super().__init__()
        self._data = data if data else []
        self._headers = ["Session Start", "Hands", "Net Won", "VPIP", "PFR", "3Bet", "WTSD%", "W$SD%", "Agg%"]

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        row_idx = index.row()
        col = index.column()
        
        if row_idx >= len(self._data):
            return None
        row = self._data[row_idx]
        
        if role == Qt.DisplayRole:
            if col == 0: return row.get("start_time", "")
            if col == 1: return str(row.get("total_hands", 0))
            if col == 2: return f"${row.get('net_won', 0):.2f}"
            if col == 3: return f"{row.get('vpip', 0):.1f}"
            if col == 4: return f"{row.get('pfr', 0):.1f}"
            if col == 5: return f"{row.get('three_bet', 0):.1f}"
            if col == 6: return f"{row.get('wtsd', 0):.1f}"
            if col == 7: return f"{row.get('wssd', 0):.1f}"
            if col == 8: return f"{row.get('agg', 0):.1f}"
        
        # 用于排序的原始数据
        if role == Qt.UserRole:
            if col == 0: return row.get("start_dt", row.get("start_time", ""))  # 使用 datetime 对象排序
            if col == 1: return row.get("total_hands", 0)
            if col == 2: return row.get("net_won", 0)
            if col == 3: return row.get("vpip", 0)
            if col == 4: return row.get("pfr", 0)
            if col == 5: return row.get("three_bet", 0)
            if col == 6: return row.get("wtsd", 0)
            if col == 7: return row.get("wssd", 0)
            if col == 8: return row.get("agg", 0)
            
        if role == Qt.ForegroundRole:
            if col == 2:  # Net Won
                net = row.get('net_won', 0)
                if net > 0:
                    return QBrush(QColor(PROFIT_GREEN))
                elif net < 0:
                    return QBrush(QColor(PROFIT_RED))
        
        if role == Qt.TextAlignmentRole:
            if col >= 1:  # 数字列右对齐
                return Qt.AlignRight | Qt.AlignVCenter
        
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return None

    def update_data(self, new_data):
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()
    
    def get_session_data(self, row):
        """获取指定行的 session 数据"""
        if 0 <= row < len(self._data):
            return self._data[row]
        return None


class HandsDetailTableModel(QAbstractTableModel):
    """手牌详情表格数据模型"""
    
    def __init__(self, data=None):
        super().__init__()
        self._data = data if data else []
        self._headers = ["Time", "Stakes", "Stack(bb)", "Cards", "Line", "Board", "Net Won", "bb", "Pos", "PF Line"]

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0: return row.get("time", "")
            if col == 1: return row.get("stakes", "")
            if col == 2: return f"{row.get('stack_bb', 0):.1f}"
            if col == 3: return row.get("cards", "")
            if col == 4: return row.get("line", "")
            if col == 5: return row.get("board", "")
            if col == 6: return f"${row.get('net_won', 0):.2f}"
            if col == 7: return f"{row.get('net_won_bb', 0):.1f}"
            if col == 8: return row.get("position", "")
            if col == 9: return row.get("pf_line", "")
        
        # 用于排序的原始数据
        if role == Qt.UserRole:
            if col == 0: return row.get("time_sort", "")  # 使用原始时间格式排序
            if col == 1: return row.get("stakes", "")
            if col == 2: return row.get("stack_bb", 0)
            if col == 3: return row.get("cards", "")
            if col == 4: return row.get("line", "")
            if col == 5: return row.get("board", "")
            if col == 6: return row.get("net_won", 0)
            if col == 7: return row.get("net_won_bb", 0)
            if col == 8: return row.get("position", "")
            if col == 9: return row.get("pf_line", "")

        if role == Qt.ForegroundRole:
            if col in [6, 7]:  # Net Won columns
                net = row.get('net_won', 0)
                if net > 0:
                    return QBrush(QColor(PROFIT_GREEN))
                elif net < 0:
                    return QBrush(QColor(PROFIT_RED))

        if role == Qt.TextAlignmentRole:
            if col in [2, 6, 7]:  # 数字列右对齐
                return Qt.AlignRight | Qt.AlignVCenter
            if col in [8, 9]:  # 位置和 PF Line 居中
                return Qt.AlignCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return None

    def update_data(self, new_data):
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()
    
    def get_hand_id(self, row):
        """获取指定行的 hand_id"""
        if 0 <= row < len(self._data):
            return self._data[row].get("hand_id")
        return None


class CashGamePage(QWidget):
    """Sessions 页面，显示 Session 统计和手牌历史"""
    
    hand_selected = Signal(str)
    
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self._sessions_data = []
        self._hands_detail = []
        self._all_hands_detail = []  # 所有手牌详情（用于全局显示）
        self._sessions_proxy = None  # Sessions 表格排序代理
        self._hands_proxy = None     # Hands 表格排序代理
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 主分栏
        splitter = QSplitter(Qt.Vertical)
        
        # 上半部分 - Sessions 列表
        sessions_container = QWidget()
        sessions_layout = QVBoxLayout(sessions_container)
        sessions_layout.setContentsMargins(16, 16, 16, 8)
        sessions_layout.setSpacing(8)
        
        # 标题行
        title_layout = QHBoxLayout()
        title = QLabel("SESSIONS")
        title.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        title_layout.addWidget(title)
        title_layout.addStretch()
        sessions_layout.addLayout(title_layout)
        
        # Sessions 表格
        self.sessions_table = QTableView()
        self.sessions_table.setSelectionBehavior(QTableView.SelectRows)
        self.sessions_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.sessions_table.setAlternatingRowColors(True)
        self.sessions_table.verticalHeader().setVisible(False)
        self.sessions_table.setSortingEnabled(True)  # 启用排序
        self.sessions_table.setStyleSheet("""
            QTableView {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                color: #e0e0e0;
                gridline-color: #3a3a3a;
            }
            QTableView::item { padding: 4px; }
            QTableView::item:selected { background-color: #3a5a7a; }
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #e0e0e0;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #3a3a3a;
            }
            QHeaderView::section:hover {
                background-color: #3a3a3a;
            }
        """)
        self.sessions_table.clicked.connect(self.on_session_clicked)
        
        # Summary 区域（显示在表格上方，简洁风格）
        summary_widget = QWidget()
        summary_layout = QHBoxLayout(summary_widget)
        summary_layout.setContentsMargins(4, 0, 4, 8)
        summary_layout.setSpacing(6)
        
        # Total: X hands | $XXX
        self.lbl_summary_main = QLabel("Total: 0 hands")
        self.lbl_summary_main.setStyleSheet("color: #888888; font-size: 12px;")
        summary_layout.addWidget(self.lbl_summary_main)
        
        self.lbl_summary_net = QLabel("$0.00")
        self.lbl_summary_net.setStyleSheet("color: #e0e0e0; font-size: 12px; font-weight: bold;")
        summary_layout.addWidget(self.lbl_summary_net)
        
        # 分隔符
        sep1 = QLabel("|")
        sep1.setStyleSheet("color: #555555; font-size: 12px;")
        summary_layout.addWidget(sep1)
        
        self.lbl_summary_vpip = QLabel("VPIP: 0.0")
        self.lbl_summary_vpip.setStyleSheet("color: #888888; font-size: 12px;")
        summary_layout.addWidget(self.lbl_summary_vpip)
        
        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #555555; font-size: 12px;")
        summary_layout.addWidget(sep2)
        
        self.lbl_summary_pfr = QLabel("PFR: 0.0")
        self.lbl_summary_pfr.setStyleSheet("color: #888888; font-size: 12px;")
        summary_layout.addWidget(self.lbl_summary_pfr)
        
        sep3 = QLabel("|")
        sep3.setStyleSheet("color: #555555; font-size: 12px;")
        summary_layout.addWidget(sep3)
        
        self.lbl_summary_3bet = QLabel("3Bet: 0.0")
        self.lbl_summary_3bet.setStyleSheet("color: #888888; font-size: 12px;")
        summary_layout.addWidget(self.lbl_summary_3bet)
        
        sep4 = QLabel("|")
        sep4.setStyleSheet("color: #555555; font-size: 12px;")
        summary_layout.addWidget(sep4)
        
        self.lbl_summary_wtsd = QLabel("WTSD: 0.0")
        self.lbl_summary_wtsd.setStyleSheet("color: #888888; font-size: 12px;")
        summary_layout.addWidget(self.lbl_summary_wtsd)
        
        sep5 = QLabel("|")
        sep5.setStyleSheet("color: #555555; font-size: 12px;")
        summary_layout.addWidget(sep5)
        
        self.lbl_summary_wssd = QLabel("W$SD: 0.0")
        self.lbl_summary_wssd.setStyleSheet("color: #888888; font-size: 12px;")
        summary_layout.addWidget(self.lbl_summary_wssd)
        
        sep6 = QLabel("|")
        sep6.setStyleSheet("color: #555555; font-size: 12px;")
        summary_layout.addWidget(sep6)
        
        self.lbl_summary_agg = QLabel("Agg: 0.0")
        self.lbl_summary_agg.setStyleSheet("color: #888888; font-size: 12px;")
        summary_layout.addWidget(self.lbl_summary_agg)
        
        summary_layout.addStretch()
        
        sessions_layout.addWidget(summary_widget)
        sessions_layout.addWidget(self.sessions_table)

        splitter.addWidget(sessions_container)
        
        # 下半部分 - 手牌详情
        hands_container = QWidget()
        hands_layout = QVBoxLayout(hands_container)
        hands_layout.setContentsMargins(16, 8, 16, 16)
        hands_layout.setSpacing(8)
        
        # 标题
        hands_title = QLabel("HANDS")
        hands_title.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        hands_layout.addWidget(hands_title)
        
        # 手牌详情表格
        self.hands_table = QTableView()
        self.hands_table.setSelectionBehavior(QTableView.SelectRows)
        self.hands_table.setAlternatingRowColors(True)
        self.hands_table.verticalHeader().setVisible(False)
        self.hands_table.setSortingEnabled(True)  # 启用排序
        self.hands_table.setStyleSheet("""
            QTableView {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                color: #e0e0e0;
                gridline-color: #3a3a3a;
            }
            QTableView::item { padding: 4px; }
            QTableView::item:selected { background-color: #3a5a7a; }
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #e0e0e0;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #3a3a3a;
            }
            QHeaderView::section:hover {
                background-color: #3a3a3a;
            }
        """)
        self.hands_table.doubleClicked.connect(self.on_hand_double_clicked)
        hands_layout.addWidget(self.hands_table)
        
        splitter.addWidget(hands_container)
        
        # 设置分栏比例
        splitter.setSizes([300, 400])
        
        layout.addWidget(splitter)
        
        self.refresh_data()

    def refresh_data(self):
        """刷新数据"""
        hands = self.db.get_all_hands()
        hands.sort(key=lambda x: x[1] if x[1] else "", reverse=True)

        # 计算 sessions 和手牌详情
        self._sessions_data, self._all_hands_detail = self._calculate_sessions(hands)

        # 更新 Sessions 表格（使用 Proxy Model 支持排序）
        sessions_model = SessionsTableModel(self._sessions_data)
        self._sessions_proxy = SortableProxyModel()
        self._sessions_proxy.setSourceModel(sessions_model)
        self.sessions_table.setModel(self._sessions_proxy)
        self.sessions_table.sortByColumn(0, Qt.DescendingOrder)  # 默认按时间降序

        # 设置列宽
        header = self.sessions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 9):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        # 更新 Summary 显示
        self._update_summary_display()

        # 默认显示所有手牌（使用 Proxy Model 支持排序）
        self._hands_detail = self._all_hands_detail
        hands_model = HandsDetailTableModel(self._hands_detail)
        self._hands_proxy = SortableProxyModel()
        self._hands_proxy.setSourceModel(hands_model)
        self.hands_table.setModel(self._hands_proxy)
        self.hands_table.sortByColumn(0, Qt.DescendingOrder)  # 默认按时间降序
        
        # 设置手牌表格列宽
        hands_header = self.hands_table.horizontalHeader()
        hands_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Time
        hands_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Stakes
        hands_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Stack
        hands_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Cards
        hands_header.setSectionResizeMode(4, QHeaderView.Stretch)  # Line
        hands_header.setSectionResizeMode(5, QHeaderView.Stretch)  # Board
        hands_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Net Won
        hands_header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # bb
        hands_header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # Pos
        hands_header.setSectionResizeMode(9, QHeaderView.ResizeToContents)  # PF Line

    def _calculate_sessions(self, hands):
        """计算 sessions 统计和手牌详情"""
        if not hands:
            return [], []
        
        # 收集所有手牌的详细信息
        hands_detail = []
        
        # 按时间分组成 sessions（间隔超过 30 分钟算新 session）
        session_gap_minutes = 30
        sessions = []
        current_session = None
        
        # 按时间正序处理（从旧到新）
        sorted_hands = sorted(hands, key=lambda x: x[1] if x[1] else "")
        
        for row in sorted_hands:
            hand_id = row[0]
            date_time_str = row[1] or ""
            blinds = row[2] or ""
            profit = float(row[5] or 0.0)
            went_to_showdown = bool(row[11] if len(row) > 11 else 0)
            
            # 解析时间
            try:
                dt = datetime.datetime.strptime(date_time_str, "%Y-%m-%d %H:%M:%S")
            except:
                continue
            
            # 解析大盲
            big_blind = self._parse_big_blind(blinds)
            
            # 获取 replay payload
            payload = self.db.get_replay_payload(hand_id, min_version=2)
            if not payload:
                continue
            
            # 计算手牌详情
            hand_detail = self._calculate_hand_detail(row, payload, big_blind)
            hands_detail.append(hand_detail)
            
            # Session 分组
            if current_session is None:
                current_session = self._create_new_session(dt)
            else:
                last_time = current_session["last_time"]
                if (dt - last_time).total_seconds() > session_gap_minutes * 60:
                    # 完成当前 session，开始新 session
                    self._finalize_session(current_session)
                    sessions.append(current_session)
                    current_session = self._create_new_session(dt)
            
            # 添加手牌到当前 session
            self._add_hand_to_session(current_session, hand_detail, payload, profit, went_to_showdown)
            current_session["last_time"] = dt
        
        # 完成最后一个 session
        if current_session:
            self._finalize_session(current_session)
            sessions.append(current_session)
        
        # 按时间倒序排列（最新在前）
        sessions.reverse()
        hands_detail.reverse()
        
        return sessions, hands_detail

    def _create_new_session(self, dt):
        """创建新的 session"""
        return {
            "start_time": dt.strftime("%m/%d/%Y %I:%M %p"),
            "start_dt": dt,
            "last_time": dt,
            "total_hands": 0,
            "net_won": 0.0,
            "hands": [],
            # VPIP/PFR/3Bet 计数
            "vpip_count": 0,
            "pfr_count": 0,
            "three_bet_opportunities": 0,
            "three_bet_count": 0,
            # WTSD/W$SD 计数
            "saw_flop_count": 0,
            "wtsd_count": 0,
            "wssd_count": 0,
            # Postflop Agg 计数
            "postflop_bets_raises": 0,
            "postflop_actions": 0,
        }

    def _add_hand_to_session(self, session, hand_detail, payload, profit, went_to_showdown):
        """将手牌添加到 session"""
        session["total_hands"] += 1
        session["net_won"] += profit
        session["hands"].append(hand_detail)
        
        # 分析 preflop actions
        actions = payload.get("actions", [])
        hero_name = payload.get("hero_name", "Hero")
        
        preflop_actions = [a for a in actions if isinstance(a, dict) and a.get("street") == "Preflop"]
        postflop_actions = [a for a in actions if isinstance(a, dict) and a.get("street") in ["Flop", "Turn", "River"]]
        
        # VPIP: 自愿投入（除盲注外有 call/raise/bet）
        vpip = False
        pfr = False
        for act in preflop_actions:
            if act.get("player") != hero_name:
                continue
            action_type = act.get("action_type", "")
            if action_type in ["calls", "raises", "bets"]:
                vpip = True
            if action_type == "raises":
                pfr = True
        
        if vpip:
            session["vpip_count"] += 1
        if pfr:
            session["pfr_count"] += 1
        
        # 3Bet: 面对 open raise 后 re-raise
        first_raise_seen = False
        hero_3bet = False
        for act in preflop_actions:
            action_type = act.get("action_type", "")
            player = act.get("player")
            
            if action_type == "raises":
                if not first_raise_seen:
                    first_raise_seen = True
                    if player != hero_name:
                        # Hero 面对 open raise
                        session["three_bet_opportunities"] += 1
                elif player == hero_name:
                    # Hero re-raise = 3bet
                    hero_3bet = True
        
        if hero_3bet:
            session["three_bet_count"] += 1
        
        # Saw Flop: 有 postflop action
        saw_flop = any(a.get("player") == hero_name for a in postflop_actions)
        if saw_flop:
            session["saw_flop_count"] += 1
        
        # WTSD
        if went_to_showdown:
            session["wtsd_count"] += 1
            # W$SD: 摊牌时赢钱
            if profit > 0:
                session["wssd_count"] += 1
        
        # Postflop Aggression
        for act in postflop_actions:
            if act.get("player") != hero_name:
                continue
            action_type = act.get("action_type", "")
            if action_type in ["bets", "raises"]:
                session["postflop_bets_raises"] += 1
                session["postflop_actions"] += 1
            elif action_type in ["calls", "checks", "folds"]:
                session["postflop_actions"] += 1

    def _finalize_session(self, session):
        """完成 session 统计计算"""
        total = session["total_hands"]
        
        # VPIP %
        session["vpip"] = (session["vpip_count"] / total * 100) if total > 0 else 0.0
        
        # PFR %
        session["pfr"] = (session["pfr_count"] / total * 100) if total > 0 else 0.0
        
        # 3Bet %
        session["three_bet"] = (session["three_bet_count"] / session["three_bet_opportunities"] * 100) if session["three_bet_opportunities"] > 0 else 0.0
        
        # WTSD %
        session["wtsd"] = (session["wtsd_count"] / session["saw_flop_count"] * 100) if session["saw_flop_count"] > 0 else 0.0
        
        # W$SD %
        session["wssd"] = (session["wssd_count"] / session["wtsd_count"] * 100) if session["wtsd_count"] > 0 else 0.0
        
        # Postflop Agg %
        session["agg"] = (session["postflop_bets_raises"] / session["postflop_actions"] * 100) if session["postflop_actions"] > 0 else 0.0

    def _calculate_hand_detail(self, row, payload, big_blind):
        """计算单手牌的详细信息"""
        hand_id = row[0]
        date_time_str = row[1] or ""
        blinds = row[2] or ""
        cards = row[4] or ""
        profit = float(row[5] or 0.0)
        
        # 时间格式化
        try:
            dt = datetime.datetime.strptime(date_time_str, "%Y-%m-%d %H:%M:%S")
            time_str = dt.strftime("%m/%d/%Y %I:%M %p")
        except:
            time_str = date_time_str
        
        # Stack Size (bb)
        hero_seat = payload.get("hero_seat", 0)
        players = payload.get("players", [])
        stack_bb = 0.0
        for p in players:
            if p.get("seat") == hero_seat:
                stack_start = p.get("stack_start", 0.0)
                stack_bb = (stack_start / big_blind) if big_blind > 0 else 0.0
                break
        
        # Position
        button_seat = payload.get("button_seat", 0)
        position = self._calculate_position(hero_seat, button_seat)
        
        # Board
        board_cards = self._extract_board(payload)
        board_str = " ".join(board_cards) if board_cards else ""
        
        # Action Line 和 PF Line
        actions = payload.get("actions", [])
        hero_name = payload.get("hero_name", "Hero")
        line, pf_line = self._calculate_action_lines(actions, hero_name)
        
        # Net Won (bb)
        net_won_bb = (profit / big_blind) if big_blind > 0 else 0.0
        
        return {
            "hand_id": hand_id,
            "time": time_str,
            "time_sort": date_time_str,  # 原始时间字符串用于排序 (YYYY-MM-DD HH:MM:SS)
            "stakes": blinds,
            "stack_bb": stack_bb,
            "cards": cards,
            "line": line,
            "board": board_str,
            "net_won": profit,
            "net_won_bb": net_won_bb,
            "position": position,
            "pf_line": pf_line,
        }

    def _parse_big_blind(self, blinds_str):
        """解析大盲"""
        try:
            m = re.search(r'\$?([\d\.]+)\s*/\s*\$?([\d\.]+)', blinds_str)
            if m:
                return float(m.group(2))
            m = re.search(r'\$?([\d\.]+)\s*-\s*\$?([\d\.]+)', blinds_str)
            if m:
                return float(m.group(2))
            numbers = re.findall(r'[\d\.]+', blinds_str)
            if len(numbers) >= 2:
                return float(numbers[1])
            elif len(numbers) == 1:
                return float(numbers[0])
        except:
            pass
        return 0.02

    def _calculate_position(self, hero_seat, button_seat):
        """计算位置"""
        if not hero_seat or not button_seat:
            return ""
        relative_pos = (hero_seat - button_seat + 6) % 6
        pos_map = {0: "BTN", 1: "SB", 2: "BB", 3: "UTG", 4: "MP", 5: "CO"}
        return pos_map.get(relative_pos, "")

    def _extract_board(self, payload):
        """提取公共牌"""
        board_cards = []
        actions = payload.get("actions", [])
        for act in actions:
            if isinstance(act, dict) and act.get("action_type") == "board":
                cards = act.get("board_cards", [])
                if cards:
                    board_cards = list(cards)
        
        if not board_cards:
            # 尝试从 board_cards 字段获取
            bc = payload.get("board_cards", [])
            if bc:
                for street in bc:
                    if isinstance(street, dict):
                        board_cards.extend(street.get("cards", []) or [])
        
        return board_cards

    def _calculate_action_lines(self, actions, hero_name):
        """计算行动线

        Line: Hero 在各街的行动线
        PF Line: Hero 的翻前行动类型
        """
        # Hero 的翻前行动（用于 PF Line）
        hero_pf_actions = []
        
        # Hero 在各街的行动（用于 Line，包括 Preflop）
        hero_street_actions = {"Preflop": [], "Flop": [], "Turn": [], "River": []}

        first_raise_player = None
        hero_faced_raise = False
        
        # 只记录这些实际行动
        valid_actions = {"bets", "raises", "calls", "checks", "folds", "all_in"}

        for act in actions:
            if not isinstance(act, dict):
                continue

            street = act.get("street", "")
            player = act.get("player")
            action_type = act.get("action_type", "")
            
            # 只处理有效的实际行动
            if action_type not in valid_actions:
                continue

            if street == "Preflop":
                # 跟踪第一个加注者（用于判断 3Bet）
                if action_type == "raises" and first_raise_player is None:
                    first_raise_player = player
                    if player != hero_name:
                        hero_faced_raise = True

                # Hero 的翻前行动
                if player == hero_name:
                    hero_pf_actions.append(action_type)
                    hero_street_actions["Preflop"].append(action_type)

            elif street in hero_street_actions:
                # Hero 的翻后行动
                if player == hero_name:
                    hero_street_actions[street].append(action_type)
        
        # PF Line 简化（Hero 的翻前行动类型）
        pf_line = ""
        if hero_pf_actions:
            has_raise = "raises" in hero_pf_actions
            has_call = "calls" in hero_pf_actions
            has_fold = "folds" in hero_pf_actions
            
            if has_raise:
                if hero_faced_raise:
                    pf_line = "3B"  # 3-bet
                else:
                    pf_line = "Raiser"  # Open raise
            elif has_call:
                pf_line = "C"
            elif has_fold:
                pf_line = "F"
        
        # Action Line: Hero 在各街的行动缩写（包括 Preflop）
        action_abbrev = {
            "bets": "B", "raises": "R", "calls": "C",
            "checks": "X", "folds": "F", "all_in": "A"
        }

        line_parts = []
        for street in ["Preflop", "Flop", "Turn", "River"]:
            street_actions = hero_street_actions.get(street, [])
            if street_actions:
                abbrevs = [action_abbrev.get(a, a[0].upper()) for a in street_actions]
                line_parts.append("".join(abbrevs))

        line = ",".join(line_parts) if line_parts else ""

        return line, pf_line

    def _update_summary_display(self):
        """更新 Summary 区域显示"""
        if not self._sessions_data:
            self.lbl_summary_main.setText("Total: 0 hands")
            self.lbl_summary_net.setText("$0.00")
            self.lbl_summary_net.setStyleSheet("color: #888888; font-size: 12px; font-weight: bold;")
            self.lbl_summary_vpip.setText("VPIP: 0.0")
            self.lbl_summary_pfr.setText("PFR: 0.0")
            self.lbl_summary_3bet.setText("3Bet: 0.0")
            self.lbl_summary_wtsd.setText("WTSD: 0.0")
            self.lbl_summary_wssd.setText("W$SD: 0.0")
            self.lbl_summary_agg.setText("Agg: 0.0")
            return

        total_hands = sum(s["total_hands"] for s in self._sessions_data)
        total_net = sum(s["net_won"] for s in self._sessions_data)

        # 计算总体 VPIP/PFR 等
        total_vpip = sum(s["vpip_count"] for s in self._sessions_data)
        total_pfr = sum(s["pfr_count"] for s in self._sessions_data)
        total_3bet_opp = sum(s["three_bet_opportunities"] for s in self._sessions_data)
        total_3bet = sum(s["three_bet_count"] for s in self._sessions_data)
        total_saw_flop = sum(s["saw_flop_count"] for s in self._sessions_data)
        total_wtsd = sum(s["wtsd_count"] for s in self._sessions_data)
        total_wssd = sum(s["wssd_count"] for s in self._sessions_data)
        total_agg_br = sum(s["postflop_bets_raises"] for s in self._sessions_data)
        total_agg_actions = sum(s["postflop_actions"] for s in self._sessions_data)

        vpip_pct = (total_vpip / total_hands * 100) if total_hands > 0 else 0
        pfr_pct = (total_pfr / total_hands * 100) if total_hands > 0 else 0
        three_bet_pct = (total_3bet / total_3bet_opp * 100) if total_3bet_opp > 0 else 0
        wtsd_pct = (total_wtsd / total_saw_flop * 100) if total_saw_flop > 0 else 0
        wssd_pct = (total_wssd / total_wtsd * 100) if total_wtsd > 0 else 0
        agg_pct = (total_agg_br / total_agg_actions * 100) if total_agg_actions > 0 else 0

        # 更新 labels
        self.lbl_summary_main.setText(f"Total: {total_hands} hands")
        
        net_color = PROFIT_GREEN if total_net >= 0 else PROFIT_RED
        self.lbl_summary_net.setText(f"${total_net:.2f}")
        self.lbl_summary_net.setStyleSheet(f"color: {net_color}; font-size: 12px; font-weight: bold;")
        
        self.lbl_summary_vpip.setText(f"VPIP: {vpip_pct:.1f}")
        self.lbl_summary_pfr.setText(f"PFR: {pfr_pct:.1f}")
        self.lbl_summary_3bet.setText(f"3Bet: {three_bet_pct:.1f}")
        self.lbl_summary_wtsd.setText(f"WTSD: {wtsd_pct:.1f}")
        self.lbl_summary_wssd.setText(f"W$SD: {wssd_pct:.1f}")
        self.lbl_summary_agg.setText(f"Agg: {agg_pct:.1f}")

    def on_session_clicked(self, index):
        """点击 session 时显示该 session 的手牌"""
        proxy = self.sessions_table.model()
        if not proxy:
            return
        
        # 通过 proxy 获取源模型的行号
        source_row = self._sessions_proxy.get_source_row(index.row())
        source_model = self._sessions_proxy.sourceModel()
        
        session = source_model.get_session_data(source_row)
        if session:
            self._hands_detail = session.get("hands", [])
        else:
            return

        # 更新手牌表格（使用 Proxy Model 支持排序）
        hands_model = HandsDetailTableModel(self._hands_detail)
        self._hands_proxy = SortableProxyModel()
        self._hands_proxy.setSourceModel(hands_model)
        self.hands_table.setModel(self._hands_proxy)
        self.hands_table.sortByColumn(0, Qt.DescendingOrder)

        # 重新设置列宽
        hands_header = self.hands_table.horizontalHeader()
        hands_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hands_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hands_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hands_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hands_header.setSectionResizeMode(4, QHeaderView.Stretch)
        hands_header.setSectionResizeMode(5, QHeaderView.Stretch)
        hands_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        hands_header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        hands_header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        hands_header.setSectionResizeMode(9, QHeaderView.ResizeToContents)

    def on_hand_double_clicked(self, index):
        """双击手牌时打开回放"""
        if not self._hands_proxy:
            return
        
        # 通过 proxy 获取源模型的行号
        source_row = self._hands_proxy.get_source_row(index.row())
        source_model = self._hands_proxy.sourceModel()
        
        hand_id = source_model.get_hand_id(source_row)
        if hand_id:
            self.hand_selected.emit(str(hand_id))


class CashGameGraphPage(QWidget):
    """独立的 Cash Game Graph 页面"""
    
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
        
        left_layout.addWidget(QLabel("DATE RANGE"))
        self.combo_filter = QComboBox()
        self.combo_filter.addItems(["All Time", "This Year", "This Month", "This Week", "Today"])
        self.combo_filter.currentTextChanged.connect(self.refresh_data)
        left_layout.addWidget(self.combo_filter)
        
        left_layout.addSpacing(12)
        
        left_layout.addWidget(QLabel("X-AXIS"))
        self.combo_xaxis = QComboBox()
        self.combo_xaxis.addItems(["Hands Played", "Date/Time"])
        self.combo_xaxis.currentTextChanged.connect(self.refresh_data)
        left_layout.addWidget(self.combo_xaxis)
        
        left_layout.addSpacing(16)
        
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
        
        main_layout.addWidget(left_panel)
        
        # Right Panel - Graph
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
            start_date = today.addDays(-(today.dayOfWeek() - 1))
        elif filter_text == "Today":
            start_date = today
            
        if start_date:
            return start_date.toString("yyyy-MM-dd 00:00:00"), None
        return None, None

    def refresh_data(self):
        start_date, end_date = self.get_date_range()
        self.plot_graph(start_date, end_date)

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
