"""
Replay 页面 - 手牌回放器
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QListWidget, QListWidgetItem,
    QTextEdit, QSplitter, QCheckBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor

from poker_parser import get_hand_by_id
from gui.widgets import ReplayTableWidget


class ReplayPage(QWidget):
    """
    手牌回放页面
    """

    def __init__(self, db_manager, show_hand_list=True):
        super().__init__()
        self.db = db_manager
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

        # Left: hands list
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

        # Center: table area
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

        # Right: actions
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        lbl_chat = QLabel("Actions")
        lbl_chat.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(lbl_chat)

        self.chk_show_villain = QCheckBox("Show Villain Cards")
        self.chk_show_villain.setChecked(False)
        self.chk_show_villain.stateChanged.connect(self.on_toggle_villain_cards)
        right_layout.addWidget(self.chk_show_villain)

        self.chk_show_bb = QCheckBox("Show Stack Values in Big Blinds")
        self.chk_show_bb.setChecked(False)
        self.chk_show_bb.stateChanged.connect(self.on_toggle_big_blinds)
        right_layout.addWidget(self.chk_show_bb)

        self.txt_actions = QTextEdit()
        self.txt_actions.setReadOnly(True)
        right_layout.addWidget(self.txt_actions, 1)

        splitter.addWidget(right_panel)
        
        if self.show_hand_list:
            splitter.setSizes([200, 600, 250])
        else:
            splitter.setSizes([900, 300])

        # Bottom controls
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(0, 6, 0, 0)
        nav_layout.setSpacing(8)

        nav_layout.addStretch()

        self.btn_prev_action = QPushButton("◀ Prev")
        self.btn_play = QPushButton("▶ Play")
        self.btn_next_action = QPushButton("Next ▶")

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
        
        self.btn_prev_action.clicked.connect(self.prev_action)
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_next_action.clicked.connect(self.next_action)

        nav_layout.addWidget(self.btn_prev_action)
        nav_layout.addWidget(self.btn_play)
        nav_layout.addWidget(self.btn_next_action)

        nav_layout.addStretch()

        main_layout.addLayout(nav_layout)

        self.refresh_hand_list()

    def load_hand(self, hand_id):
        """Load and display a hand"""
        self.current_hand_id = hand_id
        self.current_hand = None
        payload = None
        
        if hasattr(self.db, "get_replay_payload"):
            payload = self.db.get_replay_payload(hand_id)

        if payload:
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
            self.current_hand = get_hand_by_id(hand_id)
            
        self.current_action_index = -1
        self.actions = []
        self.txt_actions.clear()

        if not self.current_hand:
            self.lbl_main_info.setText(f"Hand {hand_id} not available for replay.")
            self.lbl_hero.setText("")
            self.lbl_board.setText("")
            self.lbl_pot.setText("")
            self.table_widget.set_hand(None)
            return

        self.lbl_main_info.setText(
            f"{self.current_hand.game_type} @ {self.current_hand.blinds}  |  {self.current_hand.date_time}"
        )
        self.lbl_hero.setText(f"Hero: {self.current_hand.hero_hole_cards}  (Profit: ${self.current_hand.net_profit:.2f})")

        # Board
        board1, board2 = [], []
        has_timeline_board = False
        for a in getattr(self.current_hand, "actions", []) or []:
            if not isinstance(a, dict) or a.get("action_type") != "board":
                continue
            has_timeline_board = True
            run_idx = a.get("board_run") or 1
            cards = a.get("board_cards") or []
            if run_idx == 2:
                board2 = list(cards)
            else:
                board1 = list(cards)

        if has_timeline_board:
            if board2:
                self.lbl_board.setText(f"Board: 1st: {' '.join(board1) if board1 else '-'} | 2nd: {' '.join(board2)}")
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

        self.table_widget.set_hand(self.current_hand)

        raw_actions = list(getattr(self.current_hand, "actions", []) or [])
        self.actions = list(raw_actions)

        # Process actions for timeline
        self._process_actions_for_timeline(raw_actions)

        # Find start index after blinds
        start_index = -1
        if self.actions:
            last_blind_index = -1
            for i, act in enumerate(self.actions):
                act_type = act.get("action_type", "")
                if act_type in ["post_small_blind", "post_big_blind", "post_straddle_blind"]:
                    last_blind_index = i
            if last_blind_index >= 0:
                start_index = last_blind_index
                
        self.current_action_index = start_index
        self.table_widget.set_timeline(self.actions, self.current_action_index)
        self.append_actions_text(reset=True)

        if self.show_hand_list:
            for i in range(self.list_hands.count()):
                item = self.list_hands.item(i)
                if item.data(Qt.UserRole) == hand_id:
                    self.list_hands.setCurrentRow(i)
                    break

        self.table_widget.set_show_villain_cards(self.chk_show_villain.isChecked())
        self.table_widget.set_show_big_blinds(self.chk_show_bb.isChecked())

    def _process_actions_for_timeline(self, raw_actions):
        """Process raw actions for timeline display"""
        # Handle run-it-twice boards
        board1, board2 = [], []
        has_raw_timeline_board = False
        for a in raw_actions:
            if not isinstance(a, dict) or a.get("action_type") != "board":
                continue
            has_raw_timeline_board = True
            run_idx = a.get("board_run") or 1
            cards = a.get("board_cards") or []
            if run_idx == 2:
                board2 = list(cards)
            else:
                board1 = list(cards)
                
        if has_raw_timeline_board:
            setattr(self.current_hand, "run_it_twice", True)
            setattr(self.current_hand, "rit_final_board_1", list(board1))
            setattr(self.current_hand, "rit_final_board_2", list(board2))

        # Normalize pot_complete events
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

        # Collapse board nodes
        has_timeline_board = any(
            isinstance(a, dict) and a.get("action_type") == "board" for a in self.actions
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

    def prev_action(self):
        if not self.actions:
            return
        skip_types = {"uncalled_bet_returned"}
        idx = max(-1, self.current_action_index - 1)
        while idx >= 0 and self.actions[idx].get("action_type") in skip_types:
            idx -= 1
        self.current_action_index = idx
        if self.replay_timer.isActive():
            self.replay_timer.stop()
            self.btn_play.setText("▶ Play")
        self.table_widget.set_timeline(self.actions, self.current_action_index)
        self.append_actions_text(reset=True)

    def next_action(self):
        if not self.actions:
            return
        skip_types = {"uncalled_bet_returned"}
        if self.current_action_index < len(self.actions) - 1:
            idx = self.current_action_index + 1
            while idx < len(self.actions) and self.actions[idx].get("action_type") in skip_types:
                idx += 1
            self.current_action_index = min(idx, len(self.actions) - 1)
            self.table_widget.set_timeline(self.actions, self.current_action_index)
            self.append_actions_text(reset=True)
        else:
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

    def refresh_hand_list(self):
        if not self.show_hand_list:
            return
        self.list_hands.clear()
        hands = self.db.get_all_hands()
        hands.sort(key=lambda x: x[1] if x[1] else "", reverse=True)
        for row in hands:
            hand_id, date, blinds, game, cards, profit = row[0], row[1] or "", row[2] or "", row[3] or "", row[4] or "", row[5] or 0.0
            text = f"{date} | {game} {blinds} | {cards} | ${profit:.2f}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, hand_id)
            self.list_hands.addItem(item)

    def append_actions_text(self, reset=False):
        if reset:
            self.txt_actions.clear()
        
        if not self.actions:
            return

        max_index = self.current_action_index
        
        if max_index < 0:
            self.txt_actions.append("Ready to start replay...")
            self.txt_actions.moveCursor(QTextCursor.Start)
            return
        
        for i, act in enumerate(self.actions):
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
                prefix = "> " if i == max_index else "  "
                self.txt_actions.append(f"{prefix}{line}")

        cursor = self.txt_actions.textCursor()
        cursor.movePosition(QTextCursor.Start)
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
        self.table_widget.set_show_villain_cards(bool(state))

    def on_toggle_big_blinds(self, state):
        self.table_widget.set_show_big_blinds(bool(state))


