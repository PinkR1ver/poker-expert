import os
import re

from PySide6.QtCore import Qt, QRect, QTimer, QPointF
from PySide6.QtGui import QPainter, QPixmap, QFont, QColor
from PySide6.QtWidgets import QWidget


def _get_chips_values():
    """
    仿 RIROPO 的 getChipsValues:
    从 0.01 开始，不断乘以 [5,5,4,5,2] 循环，生成递增筹码面值序列。
    """
    values = [0.01, 0.05, 0.25, 1.0]
    sequence = [5, 5, 4, 5, 2]

    idx = 0
    # 足够覆盖本项目的金额范围即可
    while values[-1] < 1e6:
        if idx == len(sequence):
            idx = 0
        values.append(round(values[-1] * sequence[idx], 2))
        idx += 1
    return values


CHIP_VALUES = _get_chips_values()


def _get_chip_index(amount: float) -> int:
    """返回最接近 amount 的筹码面值下标。"""
    if amount <= 0:
        return 0
    # 简单线性搜索即可（表长有限）
    best_idx = 0
    best_diff = float("inf")
    for i, v in enumerate(CHIP_VALUES):
        diff = abs(v - amount)
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    return best_idx


def _split_amount_to_chips(amount: float):
    """
    按 CHIP_VALUES 从大到小拆分金额，返回一个筹码面值列表。
    例如 5.27 -> [5.0, 0.25, 0.01, 0.01]
    """
    remaining = round(float(amount), 2)
    result = []
    for v in reversed(CHIP_VALUES):
        if v <= 0:
            continue
        while remaining + 1e-9 >= v:
            remaining = round(remaining - v, 2)
            result.append(v)
        if remaining <= 0:
            break
    return result


class ReplayTableWidget(QWidget):
    """
    Canvas 风格的牌桌渲染组件，尽量仿照 RIROPO 的布局：
    - 背景图：bg-vector-792x555.jpg
    - 6-max 座位：使用 display-positions.js 中 6 人桌的坐标
    - 每个座位：empty-seat + status + 玩家名 + 起始筹码
    - Hero 座位：用 status-highlight 叠加高亮

    后续可以在此基础上继续扩展（hole cards、in-play 图标、动作图标等）。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(900, 600)  # 放大 table 区域，避免 pot 和 board 重叠

        # 资源路径
        base_path = os.path.join("assets", "img", "replay")
        self.pix_bg = self._load_pix(os.path.join(base_path, "bg-vector-792x555.jpg"))
        self.pix_empty_seat = self._load_pix(os.path.join(base_path, "empty-seat-90x90.png"))
        self.pix_status = self._load_pix(os.path.join(base_path, "status-93x33.png"))
        self.pix_status_highlight = self._load_pix(os.path.join(base_path, "status-highlight-97x37.png"))
        self.pix_chips_sheet = self._load_pix(os.path.join(base_path, "chips-22-484x20.png"))
        self.pix_actions_sheet = self._load_pix(os.path.join(base_path, "actions-300x22.png"))
        # 大牌面（桌面上显示的主牌）
        self.pix_deck_big_sheet = self._load_pix(os.path.join(base_path, "deck-ps-50x70-650x280.png"))
        # 小牌精灵，保留作备选
        self.pix_small_deck_sheet = self._load_pix(os.path.join(base_path, "deck-small-16x20-208-80.png"))

        # 从 sprite sheet 拆出的子图
        self.dealer_button = None      # 单个 dealer 图标
        self.chip_sprites = []         # 多种筹码颜色
        self.action_sprites = []       # bets / calls / checks / raises / folds
        # 大牌面 [suit][rank]，50x70
        self.card_sprites_big = [[None] * 13 for _ in range(4)]
        # 小牌面 [suit][rank]，16x20（备用）
        self.card_sprites_small = [[None] * 13 for _ in range(4)]

        # 当前手牌与玩家状态
        self.hand = None
        # players_slots: [{seat_num,name,chips,is_hero,is_button,hole_cards}]
        self.players_slots = []
        # 动作时间线
        self.actions = []
        self.action_index = -1
        self.big_blind = None  # 从 blinds 文本解析出的大盲
        self.board_cards = []
        self.hand_went_to_showdown = False
        self.show_villain_cards = False
        self.show_big_blinds = False  # 是否用 BB 视角显示筹码
        
        # Pot 动画相关
        self.pot_animation_timer = QTimer(self)
        self.pot_animation_timer.setInterval(30)  # 30ms per frame, like RIROPO
        self.pot_animation_timer.timeout.connect(self._update_pot_animation)
        self.pot_animation_frame = 0
        self.pot_animation_frames = 10  # 10 frames total
        self.pot_animation_chips = []  # List of chip positions for animation
        self.pot_animation_target = None  # Target position (winner's betChips)
        self.pot_animation_amount = 0.0  # Amount being animated
        self.pot_animation_winner_name = None  # Winner's name
        # 动画延迟启动期间的“pending”状态（防止 collected 节点出现中间 pot + winner pot 同时存在）
        self.pot_animation_pending = False
        self.pot_animation_pending_token = 0

        # 6-max 座位坐标（从 display-positions.js 中抽取，做了轻微整理）
        # 只保留 emptySeat/status/name/stack 相关坐标，单位为像素。
        self.seats_coords = [
            # seatIndex 0 -> seatFixed 2
            {
                "seat_fixed": 2,
                "emptySeat": (614, 61),
                "status": (698, 89),
                "dealer": (642, 156),
                "betChips": (572, 144),
            },
            # seatIndex 1 -> seatFixed 3
            {
                "seat_fixed": 3,
                "emptySeat": (693, 189),
                "status": (691, 274),
                "dealer": (668, 240),
                "betChips": (624, 240),
            },
            # seatIndex 2 -> seatFixed 4
            {
                "seat_fixed": 4,
                "emptySeat": (571, 305),
                "status": (484, 337),
                "dealer": (550, 316),
                "betChips": (528, 296),
            },
            # seatIndex 3 -> seatFixed 6
            {
                "seat_fixed": 6,
                "emptySeat": (139, 303),
                "status": (225, 337),
                "dealer": (233, 316),
                "betChips": (240, 292),
            },
            # seatIndex 4 -> seatFixed 7
            {
                "seat_fixed": 7,
                "emptySeat": (13, 189),
                "status": (13, 275),
                "dealer": (107, 242),
                "betChips": (144, 240),
            },
            # seatIndex 5 -> seatFixed 8
            {
                "seat_fixed": 8,
                "emptySeat": (95, 60),
                "status": (9, 89),
                "dealer": (128, 146),
                "betChips": (212, 144),
            },
        ]

        self._compute_text_positions()
        self._slice_sprite_sheets()

    # --- Public API ---------------------------------------------------------
    def set_hand(self, hand):
        """
        设置当前要展示的 hand（poker_parser.PokerHand 实例）。
        主要使用 hand.players_info / hand.hero_name / hero_seat。
        """
        self.hand = hand
        self.players_slots = []
        self.actions = []
        self.action_index = -1
        self.big_blind = self._parse_big_blind(getattr(hand, "blinds", None))
        # board & showdown 信息
        self.board_cards = list(getattr(hand, "board_cards", []))
        self.hand_went_to_showdown = bool(getattr(hand, "went_to_showdown", False))

        if not hand or not getattr(hand, "players_info", None):
            self.update()
            return

        # players_info: {seat_num: {name, chips_start, hole_cards}}
        # 这里简单按 seat_num 排序，然后映射到 6 个显示位置。
        items = sorted(hand.players_info.items(), key=lambda kv: kv[0])
        for idx, (seat_num, info) in enumerate(items[:6]):
            name = info.get("name", f"Seat {seat_num}")
            chips = info.get("chips_start", 0.0)
            is_hero = (name == getattr(hand, "hero_name", "Hero"))
            is_button = False
            try:
                is_button = int(seat_num) == int(getattr(hand, "button_seat", 0))
            except Exception:
                is_button = False
            hole_cards = info.get("hole_cards") or ""
            # Hero hole cards 兜底
            if is_hero and not hole_cards:
                hole_cards = getattr(hand, "hero_hole_cards", "") or ""

            self.players_slots.append(
                {
                    "seat_num": seat_num,
                    "name": name,
                    "chips": chips,
                    "is_hero": is_hero,
                    "is_button": is_button,
                    "hole_cards": hole_cards,
                }
            )

        self.update()

    def _format_amount(self, amount: float) -> str:
        """
        统一格式化金额显示（pot 和动画中的金额使用相同的格式）。
        仿 RIROPO 的 displayValueAbsx 函数。
        """
        if self.show_big_blinds and self.big_blind and self.big_blind > 0:
            bb_amount = amount / self.big_blind
            return f"{bb_amount:.1f} BB"
        else:
            return f"${amount:.2f}"

    def _parse_big_blind(self, blinds: str):
        """
        从类似 '0.01 - 0.02 - 6max' 或 '0.01/0.02' 字符串中解析大盲。
        """
        if not blinds:
            return None
        # 取最后一个带数字和小数点的 token
        # 先找形如 a/b 的部分
        m = re.search(r'([\d\.]+)\s*/\s*([\d\.]+)', blinds)
        target = None
        if m:
            target = m.group(2)
        else:
            # 退化：按 '/' 分隔取最后一段
            parts = blinds.split('/')
            target = parts[-1]
        if not target:
            return None
        m2 = re.search(r'([\d\.]+)', target)
        if not m2:
            return None
        try:
            return float(m2.group(1))
        except ValueError:
            return None

    def set_timeline(self, actions, index):
        """
        设置动作时间线和当前指针，用于根据当前 action 高亮玩家 / 更新底池等。
        每个节点的画面是预先计算好的，不进行实时计算。
        """
        self.actions = actions or []
        old_index = self.action_index
        self.action_index = index if index is not None else -1
        
        # 检查是否有 collected 动作，如果有则启动 pot 动画
        # 只有当 index 变化且是 collected action 时才启动动画
        if self.action_index != old_index:
            self._check_and_start_pot_animation()
        
        self.update()

    def set_show_villain_cards(self, show: bool):
        """控制是否在摊牌局中展示对手的底牌。"""
        self.show_villain_cards = bool(show)
        self.update()

    def set_show_big_blinds(self, show: bool):
        """控制是否用 Big Blinds 视角显示筹码（而非美元）。"""
        self.show_big_blinds = bool(show)
        self.update()

    # --- Internals ----------------------------------------------------------
    def _load_pix(self, path):
        if os.path.exists(path):
            return QPixmap(path)
        return None

    def _compute_text_positions(self):
        """
        根据 status 坐标计算 name/stack 文本位置。
        参考 display-positions.js 里的 easeName/easeStack：
        - name: status.x + (46, 9)
        - stack: status.x + (46, 25)
        """
        for seat in self.seats_coords:
            sx, sy = seat["status"]
            # status-93x33.png 自身就是“名字/筹码”黑条区域
            # 文本应在黑条内左侧留一点 padding，而不是 +46 那种偏移
            # （+46 会把文本推到条外，导致“姓名/筹码偏移”）
            seat["name_pos"] = (sx + 6, sy + 14)
            seat["stack_pos"] = (sx + 6, sy + 28)

            # 动作图标位置（参考 display-positions.js 中 easeAction）
            ex, ey = seat["emptySeat"]
            action_x = ex + 15
            action_y = ey + 35
            seat["action_pos"] = (action_x, action_y)

            # 手牌位置（参考 easeHoleCards: action.x - 2, action.y - 25）
            seat["hole_pos"] = (action_x - 2, action_y - 25)

            # 筹码金额文字位置（参考 easeChipsValue，但增加距离避免太贴近）
            chips_width = 22
            chips_height = 20
            seat_fixed = seat.get("seat_fixed", 0)
            left_align = seat_fixed >= 5
            off_x = chips_width + 4 if left_align else -4
            off_y = chips_height + 8  # 从 -2 改为 +8，拉开距离避免糊在一起
            bx, by = seat["betChips"]
            seat["chips_value_pos"] = (bx + off_x, by + off_y)

    def _slice_sprite_sheets(self):
        """
        模仿 RIROPO 的 load-images.js:
        - chips-22-484x20.png: 22x20 精灵，第一格是 dealer，其余是筹码
        - actions-300x22.png: 每个 60x22，一共 5 个动作
        - deck-small-16x20-208-80.png: 4 行 13 列，16x20，小牌面
        """
        # Chips & dealer
        if self.pix_chips_sheet and not self.pix_chips_sheet.isNull():
            chip_w, chip_h = 22, 20
            cols = self.pix_chips_sheet.width() // chip_w
            sprites = []
            for i in range(cols):
                x = i * chip_w
                sprites.append(self.pix_chips_sheet.copy(x, 0, chip_w, chip_h))
            if sprites:
                self.dealer_button = sprites[0]
                self.chip_sprites = sprites[1:]

        # Actions
        if self.pix_actions_sheet and not self.pix_actions_sheet.isNull():
            act_w, act_h = 60, 22
            cols = self.pix_actions_sheet.width() // act_w
            self.action_sprites = []
            for i in range(cols):
                x = i * act_w
                self.action_sprites.append(self.pix_actions_sheet.copy(x, 0, act_w, act_h))

        # Big deck cards（主牌面）
        if self.pix_deck_big_sheet and not self.pix_deck_big_sheet.isNull():
            card_w, card_h = 50, 70
            for row in range(4):
                for col in range(13):
                    x = col * card_w
                    y = row * card_h
                    self.card_sprites_big[row][col] = self.pix_deck_big_sheet.copy(
                        x, y, card_w, card_h
                    )

        # Small deck cards（备用）
        if self.pix_small_deck_sheet and not self.pix_small_deck_sheet.isNull():
            card_w, card_h = 16, 20
            for row in range(4):
                for col in range(13):
                    x = col * card_w
                    y = row * card_h
                    self.card_sprites_small[row][col] = self.pix_small_deck_sheet.copy(
                        x, y, card_w, card_h
                    )

    # --- Painting -----------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 背景
        if self.pix_bg and not self.pix_bg.isNull():
            target_rect = self._centered_rect(self.pix_bg.size(), self.rect())
            painter.drawPixmap(target_rect, self.pix_bg)

        painter.setPen(Qt.white)
        font = QFont("Segoe UI", 9)
        painter.setFont(font)

        # 计算当前 action / player / pot
        current_action = None
        if self.actions and 0 <= self.action_index < len(self.actions):
            current_action = self.actions[self.action_index]

        acting_player = current_action.get("player") if current_action else None
        
        # 当前街（用于决定是否进入 showdown 阶段）
        # 注意：有些旧 replay 数据可能把结算动作的 street 仍标成 River/Preflop，
        # 所以这里用“是否已经进入过 Showdown/是否到了最后一帧且 went_to_showdown”做兜底。
        order = {"Preflop": 0, "Flop": 1, "Turn": 2, "River": 3, "Showdown": 4}
        current_rank = 0
        if current_action:
            current_rank = order.get(current_action.get("street", "Preflop"), 0)

        seen_showdown_marker = False
        if self.actions and self.action_index >= 0:
            for i in range(0, min(self.action_index + 1, len(self.actions))):
                a = self.actions[i]
                if isinstance(a, dict) and a.get("street") == "Showdown":
                    seen_showdown_marker = True
                    break

        is_last_frame = bool(self.actions) and (self.action_index >= len(self.actions) - 1)
        in_showdown_phase = (current_rank >= order["Showdown"]) or seen_showdown_marker or (
            bool(getattr(self, "hand_went_to_showdown", False)) and is_last_frame
        )

        # 计算到当前 action 为止哪些玩家已经 fold（fold 后对手手牌应消失）
        folded_players = set()
        if self.actions and self.action_index >= 0:
            for i in range(0, min(self.action_index + 1, len(self.actions))):
                a = self.actions[i]
                if not isinstance(a, dict):
                    continue
                if (a.get("action_type") in ("folds", "fold")) and a.get("player"):
                    folded_players.add(a.get("player"))

        # --- 名字框内的筹码数（下注时减少）---
        # 以 players_slots 的起始筹码为基准，按时间线回放到当前 action_index，得到每个玩家当前 stack
        stacks = {slot.get("name"): float(slot.get("chips") or 0.0) for slot in (self.players_slots or [])}
        if self.actions and self.action_index >= 0:
            cur_street = None
            on_street = {}  # {player: amount_on_current_street}
            for i in range(0, min(self.action_index + 1, len(self.actions))):
                act = self.actions[i]
                if not isinstance(act, dict):
                    continue
                street = act.get("street", "Preflop")
                if cur_street is None:
                    cur_street = street
                elif street != cur_street:
                    cur_street = street
                    on_street = {}

                act_type = act.get("action_type", "")
                player = act.get("player")
                amount = float(act.get("amount") or 0.0)

                if act_type == "pot_complete":
                    # 桌面筹码推入中间 pot：新一段开始
                    on_street = {}
                    continue

                if act_type in ["post_small_blind", "post_big_blind", "post_straddle_blind", "bets", "calls"]:
                    if player in stacks and amount > 0:
                        stacks[player] -= amount
                        on_street[player] = on_street.get(player, 0.0) + amount
                    continue

                if act_type == "raises":
                    if player in stacks:
                        to_amount = float(act.get("to_amount") or 0.0)
                        prev = float(on_street.get(player, 0.0))
                        delta = max(0.0, to_amount - prev)
                        if delta > 0:
                            stacks[player] -= delta
                        on_street[player] = max(prev, to_amount)
                    continue

                if act_type == "uncalled_bet_returned":
                    if player in stacks and amount > 0:
                        stacks[player] += amount
                        if player in on_street:
                            on_street[player] = max(0.0, float(on_street.get(player, 0.0)) - amount)
                    continue

                if act_type == "collected":
                    if player in stacks and amount > 0:
                        stacks[player] += amount
                    continue
        
        # 直接使用 action 节点记录的 pot_size，不要实时计算
        # pot_size = pot - sum(street_amount)，所以 blinds 时 pot_size = 0（筹码还在玩家面前）
        current_pot = 0.0
        if self.action_index >= 0 and current_action and current_action.get("pot_size") is not None:
            # 正常状态：使用当前 action 的 pot_size
            current_pot = float(current_action.get("pot_size") or 0.0)
        elif self.action_index == -1:
            # 初始状态（blinds 后）：pot_size 应该是 0（筹码还在玩家面前，还没进入 pot）
            current_pot = 0.0

        # 把 RIROPO 的绝对坐标映射到当前控件 rect 中心（简单平移）
        # 这里假设背景大小约为 792x555。
        table_width = 792
        table_height = 555
        widget_rect = self.rect()
        offset_x = (widget_rect.width() - table_width) / 2
        offset_y = (widget_rect.height() - table_height) / 2

        # --- 顶部实时 Pot（下注就加，不等每条街结算）---
        # 计算当前街所有玩家仍在桌面上的筹码（amountOnStreet），用于顶部实时 pot
        live_player_bets = {}
        if self.actions:
            if self.action_index >= 0 and current_action:
                live_street = current_action.get("street", "Preflop")
                for i in range(0, min(self.action_index + 1, len(self.actions))):
                    act = self.actions[i]
                    if not isinstance(act, dict):
                        continue
                    if act.get("street") != live_street:
                        continue
                    act_type = act.get("action_type", "")
                    player = act.get("player")
                    amount = float(act.get("amount") or 0.0)

                    # pot_complete 表示“桌面筹码已推入中间底池”，需要清空本街桌面筹码
                    if act_type == "pot_complete":
                        live_player_bets = {}
                        continue

                    if act_type in ["bets", "calls", "raises", "post_small_blind", "post_big_blind", "post_straddle_blind"]:
                        if not player:
                            continue
                        if act_type == "raises":
                            to_amount = float(act.get("to_amount") or 0.0)
                            if to_amount > 0:
                                live_player_bets[player] = to_amount
                        else:
                            if amount > 0:
                                live_player_bets[player] = live_player_bets.get(player, 0.0) + amount
            elif self.action_index == -1:
                # 初始状态：只显示 blinds（与下注筹码显示逻辑一致）
                for act in self.actions:
                    if not isinstance(act, dict):
                        continue
                    act_type = act.get("action_type", "")
                    if act_type in ["post_small_blind", "post_big_blind", "post_straddle_blind"]:
                        player = act.get("player")
                        amount = float(act.get("amount") or 0.0)
                        if player and amount > 0:
                            live_player_bets[player] = live_player_bets.get(player, 0.0) + amount

        # 顶部实时 pot = 中间已结算 pot（current_pot） + 当前街桌面筹码（live_player_bets）
        # 注意：如果当前节点已经 pot_complete/collected，本街桌面筹码应为 0（上面 pot_complete 会清空）
        live_pot = float(current_pot or 0.0) + float(sum(live_player_bets.values()) or 0.0)

        # --- 公共牌（board） ---
        # 简化规则：
        # - **all-in 之后**：不管 run 几次，直接把剩余公共牌一次性发完（避免一张张翻）
        # - run-it-twice：显示两条完整 board（各 5 张），来源于 ReplayPage 预先计算的 rit_final_board_1/2
        # - 非 all-in：保持原逻辑（按街逐步展示）
        visible_board_1 = []
        visible_board_2 = []

        if self.action_index >= 0 and self.actions:
            # all-in 检测：
            # - 优先使用 parser 的 is_all_in
            # - 兜底：根据回放栈推演，若某次下注导致某玩家 stack<=0 也视为 all-in
            all_in_idx = None
            sim_stacks = {slot.get("name"): float(slot.get("chips") or 0.0) for slot in (self.players_slots or [])}
            sim_on_street = {}
            sim_street = None
            for i in range(0, min(self.action_index + 1, len(self.actions))):
                a = self.actions[i]
                if not isinstance(a, dict):
                    continue
                street = a.get("street", "Preflop")
                if sim_street is None:
                    sim_street = street
                elif street != sim_street:
                    sim_street = street
                    sim_on_street = {}

                act_type = a.get("action_type", "")
                player = a.get("player")
                amount = float(a.get("amount") or 0.0)
                if act_type == "pot_complete":
                    sim_on_street = {}
                    continue
                if act_type in ["post_small_blind", "post_big_blind", "post_straddle_blind", "bets", "calls"]:
                    if player in sim_stacks and amount > 0:
                        sim_stacks[player] -= amount
                        sim_on_street[player] = sim_on_street.get(player, 0.0) + amount
                elif act_type == "raises":
                    if player in sim_stacks:
                        to_amount = float(a.get("to_amount") or 0.0)
                        prev = float(sim_on_street.get(player, 0.0))
                        delta = max(0.0, to_amount - prev)
                        if delta > 0:
                            sim_stacks[player] -= delta
                        sim_on_street[player] = max(prev, to_amount)
                elif act_type == "uncalled_bet_returned":
                    if player in sim_stacks and amount > 0:
                        sim_stacks[player] += amount
                        if player in sim_on_street:
                            sim_on_street[player] = max(0.0, float(sim_on_street.get(player, 0.0)) - amount)

                if all_in_idx is None:
                    flag = bool(a.get("is_all_in", False))
                    hit_zero = (player in sim_stacks) and (sim_stacks[player] <= 1e-9)
                    if flag or hit_zero:
                        all_in_idx = i

            # “all-in 之后直接发完牌”——但 **preflop 还没结束时不要亮牌**：
            # - 若当前已经到 Flop/之后：一旦到达 all-in_idx 就可以发完
            # - 若当前仍是 Preflop：必须等到进入第一个 board 节点/Flop 之后才发完
            current_rank = 0
            if current_action:
                current_rank = order.get(current_action.get("street", "Preflop"), 0)
            board_trigger_idx = None
            for i, a in enumerate(self.actions):
                if isinstance(a, dict) and a.get("action_type") == "board":
                    board_trigger_idx = i
                    break
            if all_in_idx is None:
                reveal_all_board = False
            elif current_rank >= order["Flop"]:
                reveal_all_board = self.action_index >= all_in_idx
            else:
                # still Preflop
                reveal_all_board = (board_trigger_idx is not None) and (self.action_index >= board_trigger_idx)

            # run-it-twice：使用预先计算的最终 board
            rit_b1 = getattr(self.hand, "rit_final_board_1", None)
            rit_b2 = getattr(self.hand, "rit_final_board_2", None)
            is_rit = bool(getattr(self.hand, "run_it_twice", False)) and isinstance(rit_b1, list)

            if is_rit and reveal_all_board:
                visible_board_1 = list(rit_b1 or [])
                visible_board_2 = list(rit_b2 or [])
            else:
                # 非 all-in 或非 RIT：保持旧逻辑（按街逐步展示）
                order = {"Preflop": 0, "Flop": 1, "Turn": 2, "River": 3, "Showdown": 4}
                current_rank = 0
                if current_action:
                    current_rank = order.get(current_action.get("street", "Preflop"), 0)
                for entry in getattr(self, "board_cards", []) or []:
                    if not isinstance(entry, dict):
                        continue
                    street_name = entry.get("street", "")
                    if order.get(street_name, 0) <= current_rank:
                        visible_board_1.extend(entry.get("cards", []) or [])

        def _draw_board_row(cards, y, label=None):
            if not cards or self.card_sprites_big[0][0] is None:
                return
            card_w, card_h = 50, 70
            gap = 8
            n = len(cards)
            total_width = n * card_w + (n - 1) * gap
            start_x = widget_rect.x() + widget_rect.width() / 2 - total_width / 2
            if label:
                painter.setPen(QColor(255, 255, 255, 180))
                painter.setFont(QFont("Segoe UI", 9))
                painter.drawText(int(start_x) - 50, int(y + card_h / 2), str(label))
                painter.setPen(Qt.white)
            for i, card in enumerate(cards):
                if not isinstance(card, str) or len(card) < 2:
                    continue
                rank = card[0]
                suit = card[1]
                rank_index = "23456789TJQKA".find(rank)
                suit_index = "cdhs".find(suit.lower())
                cx = start_x + i * (card_w + gap)
                if (
                    0 <= suit_index < 4
                    and 0 <= rank_index < 13
                    and self.card_sprites_big[suit_index][rank_index] is not None
                ):
                    painter.drawPixmap(int(cx), int(y), self.card_sprites_big[suit_index][rank_index])

        # board 上移，给 pot 留出空间；run2 时画两排
        base_y = widget_rect.y() + widget_rect.height() / 2 - 70 - 60
        if visible_board_2:
            _draw_board_row(visible_board_1, base_y - 18, label="1st")
            _draw_board_row(visible_board_2, base_y + 56, label="2nd")
        else:
            _draw_board_row(visible_board_1, base_y)

        # 顶部实时 Pot 标签（仿 RIROPO：白底黑字 "Pot: $x.xx"）
        if self.action_index >= -1 and live_pot > 0:
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            pot_text = f"Pot: {self._format_amount(live_pot)}"
            metrics = painter.fontMetrics()
            tw = metrics.horizontalAdvance(pot_text)
            th = metrics.height()
            top_x = widget_rect.x() + widget_rect.width() / 2
            top_y = widget_rect.y() + offset_y + 18
            rect = QRect(int(top_x - tw / 2 - 10), int(top_y - th / 2 - 4), int(tw + 20), int(th + 8))
            painter.setPen(QColor("#2b2b2b"))
            painter.setBrush(QColor("#f2f2f2"))
            painter.drawRoundedRect(rect, 6, 6)
            painter.setPen(QColor("#111111"))
            painter.drawText(rect, Qt.AlignCenter, pot_text)

        if not self.players_slots:
            painter.end()
            return

        for idx, slot in enumerate(self.players_slots):
            if idx >= len(self.seats_coords):
                break
            coord = self.seats_coords[idx]

            # empty seat
            ex, ey = coord["emptySeat"]
            ex += offset_x
            ey += offset_y
            if self.pix_empty_seat and not self.pix_empty_seat.isNull():
                painter.drawPixmap(int(ex), int(ey), self.pix_empty_seat)

            # status / highlight（当前动作玩家 / Hero 高亮）
            sx, sy = coord["status"]
            sx += offset_x
            sy += offset_y
            is_acting = bool(acting_player) and slot["name"] == acting_player
            # 只高亮当前行动玩家；Hero 不再永久高亮
            if is_acting and self.pix_status_highlight and not self.pix_status_highlight.isNull():
                painter.drawPixmap(int(sx - 2), int(sy - 2), self.pix_status_highlight)
            elif self.pix_status and not self.pix_status.isNull():
                painter.drawPixmap(int(sx), int(sy), self.pix_status)

            # dealer 按钮
            if slot.get("is_button") and self.dealer_button:
                dx, dy = coord.get("dealer", coord["status"])
                dx += offset_x
                dy += offset_y
                painter.drawPixmap(int(dx), int(dy), self.dealer_button)

            # 文本：名字 + 筹码
            name_x, name_y = coord["name_pos"]
            stack_x, stack_y = coord["stack_pos"]
            name_x += offset_x
            name_y += offset_y
            stack_x += offset_x
            stack_y += offset_y

            # 名字
            painter.setPen(Qt.white)
            painter.drawText(int(name_x), int(name_y), slot["name"])

            # 筹码数值（根据 show_big_blinds 切换 $ 或 BB）
            chips_val = stacks.get(slot["name"], slot["chips"])
            # hero 的筹码数也用白色
            painter.setPen(Qt.white)
            if self.show_big_blinds and self.big_blind and self.big_blind > 0:
                bb_val = chips_val / self.big_blind
                stack_text = f"{bb_val:.1f} BB"
            else:
                stack_text = f"${chips_val:.2f}"
            painter.drawText(int(stack_x), int(stack_y), stack_text)

            # 手牌（Hero 永远明牌；对手默认背牌，fold 后消失；showdown/开关开启时翻面）
            # 只要时间线上出现 blinds，就认为已经发牌（进入能看到 hole cards 的阶段）
            has_blinds = bool(self.actions) and any(
                isinstance(act, dict)
                and act.get("action_type", "") in ["post_small_blind", "post_big_blind", "post_straddle_blind"]
                for act in self.actions
            )

            def _draw_card_back(x, y, w=50, h=70):
                rect = QRect(int(x), int(y), int(w), int(h))
                painter.setPen(QColor("#263238"))
                painter.setBrush(QColor("#0b1b2b"))
                painter.drawRoundedRect(rect, 6, 6)
                inner = rect.adjusted(4, 4, -4, -4)
                painter.setPen(QColor("#1e88e5"))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(inner, 4, 4)
                painter.setPen(QColor(255, 255, 255, 160))
                painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                painter.drawText(inner, Qt.AlignCenter, "GG")

            def _draw_face_cards(cards_str, hx, hy):
                cards = (cards_str or "").replace("[", "").replace("]", "").split()
                if not cards:
                    return
                card_w, card_h = 50, 70
                offset_x_card = 15
                offset_y_card = 4
                for i, card in enumerate(cards[:2]):
                    if len(card) < 2:
                        continue
                    rank = card[0]
                    suit = card[1]
                    rank_index = "23456789TJQKA".find(rank)
                    suit_index = "cdhs".find(suit.lower())
                    cx = hx + offset_x_card * i
                    cy = hy + offset_y_card * i
                    if (
                        0 <= suit_index < 4
                        and 0 <= rank_index < 13
                        and self.card_sprites_big[suit_index][rank_index] is not None
                    ):
                        painter.drawPixmap(int(cx), int(cy), self.card_sprites_big[suit_index][rank_index])
                    else:
                        rect = QRect(int(cx), int(cy), card_w, card_h)
                        painter.setPen(Qt.white)
                        painter.setBrush(QColor("#154360"))
                        painter.drawRoundedRect(rect, 4, 4)
                        painter.setPen(Qt.white)
                        painter.setFont(QFont("Segoe UI", 8))
                        painter.drawText(rect.adjusted(3, 3, -3, -3), Qt.AlignLeft | Qt.AlignTop, card)

            if has_blinds:
                # fold 后对手手牌消失（Hero 不受影响）
                if (not slot["is_hero"]) and (slot.get("name") in folded_players):
                    pass
                else:
                    hx, hy = coord.get("hole_pos", (stack_x, stack_y + 14))
                    hx += offset_x
                    hy += offset_y

                    if slot["is_hero"]:
                        _draw_face_cards(slot.get("hole_cards") or "", hx, hy)
                    else:
                        known = (slot.get("hole_cards") or "").strip()
                        reveal = bool(getattr(self, "show_villain_cards", False)) or (
                            bool(getattr(self, "hand_went_to_showdown", False)) and in_showdown_phase
                        )
                        if reveal and known:
                            _draw_face_cards(known, hx, hy)
                        else:
                            _draw_card_back(hx, hy)
                            _draw_card_back(hx + 15, hy + 4)

            # 当前动作图标（bets/calls/checks/raises/folds）
            # 初始状态不显示动作图标
            if self.action_index >= 0 and is_acting and current_action and self.action_sprites:
                act_type = current_action.get("action_type") or ""
                mapping = ["bets", "calls", "checks", "raises", "folds"]
                try:
                    act_index = mapping.index(act_type)
                except ValueError:
                    act_index = -1
                if 0 <= act_index < len(self.action_sprites):
                    ax, ay = coord.get("action_pos", (sx, sy + 40))
                    ax += offset_x
                    ay += offset_y
                    painter.drawPixmap(int(ax), int(ay), self.action_sprites[act_index])

        # 画中间底池（每条街结算堆在一起的那堆）+ 筹码造型
        # 完全使用 action 节点记录的 pot_size，不进行任何实时计算
        # pot_complete action 时：显示 pot 在中间（所有筹码都进入 pot，这是一个中间节点）
        # collected action 时：
        #   - 动画开始前：显示 pot 在中间（所有筹码都进入 pot）
        #   - 动画进行中：显示 pot 在中间（筹码还在 pot 里，动画中的筹码正在移动）
        #   - 动画结束后：不显示 pot（筹码已经在 winner 面前）
        # 其他情况：正常显示 pot
        has_collected = False
        has_pot_complete = False
        if self.action_index >= 0 and current_action:
            has_collected = current_action.get("action_type") == "collected"
            has_pot_complete = current_action.get("action_type") == "pot_complete"
        
        animation_in_progress = self.pot_animation_timer.isActive() and self.pot_animation_chips
        animation_pending = bool(getattr(self, "pot_animation_pending", False))
        animation_active = bool(animation_in_progress or animation_pending)
        animation_ended = self.pot_animation_chips and self.pot_animation_frame >= self.pot_animation_frames

        # --- split pot / run-it-twice：collected 可能出现多次 ---
        # 规则（更贴近真实分锅/多次 run）：
        # - 先把中间 pot 按 collected 次数拆成 N 堆（两次 run 就是 2 堆），都放在中间
        # - 每次 collected 只移动“对应那一堆”，其它堆留在桌面上，不会凭空消失
        # - 如果 action 带 run=1/2，则按 run 指向对应堆；否则按出现顺序分配
        segment_pot_amount = float(current_pot or 0.0)
        paid_by_winner = {}  # {winner: paid_amount_so_far (visual)}
        split_collected_count = 0
        split_share = 0.0
        # 哪些堆已经被发出去了（pile_idx -> True）
        awarded_piles = set()
        # 当前 collected 动画应从哪一堆起飞（pile_idx），动画期间该堆不再画在中间
        active_pile_idx = None
        if self.actions and self.action_index >= 0 and (has_collected or has_pot_complete):
            # 找到最近的 pot_complete（代表中间 pot 已经“归拢完成”的起点）
            seg_start = 0
            for j in range(self.action_index, -1, -1):
                a = self.actions[j]
                if isinstance(a, dict) and a.get("action_type") == "pot_complete":
                    seg_start = j
                    try:
                        segment_pot_amount = float(a.get("pot_size") or segment_pot_amount)
                    except Exception:
                        pass
                    break

            # 统计这一段的 collected 次数（用于 split：拆成 N 堆）
            for j in range(seg_start, len(self.actions)):
                a = self.actions[j]
                if not isinstance(a, dict):
                    continue
                if a.get("action_type") == "pot_complete" and j != seg_start:
                    break
                if a.get("action_type") == "collected":
                    split_collected_count += 1

            split_share = (
                float(segment_pot_amount) / float(split_collected_count)
                if split_collected_count and split_collected_count > 0
                else 0.0
            )

            # 统计 seg_start..action_index 的 collected（决定哪些堆已经被发出，以及赢家面前应显示多少）
            seq_idx = 0
            for j in range(seg_start, self.action_index + 1):
                a = self.actions[j]
                if not isinstance(a, dict):
                    continue
                if a.get("action_type") != "collected":
                    continue
                winner = a.get("player")
                if not winner:
                    continue
                run_tag = a.get("run")  # 1/2...
                if run_tag is not None:
                    try:
                        pile_idx = max(0, int(run_tag) - 1)
                    except Exception:
                        pile_idx = seq_idx
                else:
                    pile_idx = seq_idx
                seq_idx += 1

                # 当前 action 的 collected：
                # - pending（延迟 500ms）阶段：不要把堆从中间隐藏（否则会“消失一瞬”），但也不算已到手
                # - 真正动画进行中：把对应堆从中间移除（正在飞），也不算已到手
                if j == self.action_index and has_collected and (animation_pending or animation_in_progress) and not animation_ended:
                    if animation_in_progress:
                        active_pile_idx = pile_idx
                    continue

                # 动画结束或历史节点：视为已经发出
                awarded_piles.add(pile_idx)
                paid_by_winner[winner] = paid_by_winner.get(winner, 0.0) + float(split_share)
        
        # 中间 pot：split 模式下不再“递减数字”，而是用 N 堆 + 已发堆的方式表达剩余
        middle_pot_amount = float(current_pot or 0.0)

        split_mode = split_collected_count > 1
        remaining_piles = 0
        if split_mode and split_collected_count > 0:
            remaining_piles = max(0, int(split_collected_count) - int(len(awarded_piles)) - (1 if active_pile_idx is not None else 0))

        # 非 split：保持原规则（collected 动画结束后，中间 pot 消失）
        # split：只要还有剩余堆，就必须继续显示中间 pot（避免“一堆飞走，另一堆也消失”）
        show_middle_pot = (
            middle_pot_amount > 0
            and (not (has_collected and animation_ended) or (split_mode and remaining_piles > 0))
            and (not (has_collected and animation_in_progress) or split_mode)  # split 时动画期间仍显示剩余堆
        )
        if show_middle_pot:
            center_x = widget_rect.x() + widget_rect.width() / 2
            # 中间 pot 位置（略下移，避免和 board 重叠）
            center_y = widget_rect.y() + widget_rect.height() / 2 + 30

            # 1) 先画中间 pot 的筹码堆
            if self.chip_sprites and middle_pot_amount > 0:
                chip_w = 22
                margin = 2
                if split_mode and split_share > 0:
                    # N 堆：横向排开
                    piles = split_collected_count
                    gap = 18
                    total_span = piles * chip_w + (piles - 1) * gap
                    start_pile_x = center_x - total_span / 2
                    base_y = center_y + 6

                    for p_idx in range(piles):
                        # 已发出的堆不再画在中间；正在动画的堆也不画在中间
                        if p_idx in awarded_piles:
                            continue
                        if active_pile_idx is not None and p_idx == active_pile_idx:
                            continue

                        pile_x = start_pile_x + p_idx * (chip_w + gap)
                        chips_values = _split_amount_to_chips(split_share)
                        chip_indices = [_get_chip_index(v) for v in chips_values]
                        unique_idxs = sorted(set(chip_indices))
                        # 每堆内部做 multi-stack
                        for col, u in enumerate(unique_idxs):
                            stack = [idx for idx in chip_indices if idx == u]
                            chip_pix = self.chip_sprites[u % len(self.chip_sprites)]
                            cx = pile_x + col * (chip_w + margin)
                            for h_idx, _ in enumerate(stack[:10]):
                                cy = base_y - h_idx * 4
                                painter.drawPixmap(int(cx), int(cy), chip_pix)

                        # 金额文字（每堆下方）
                        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                        txt = self._format_amount(split_share)
                        metrics = painter.fontMetrics()
                        tw = metrics.horizontalAdvance(txt)
                        th = metrics.height()
                        text_x = pile_x - tw / 2 + chip_w / 2
                        text_y = center_y + 28
                        painter.setPen(QColor(0, 0, 0, 140))
                        painter.drawText(int(text_x + 1), int(text_y + th / 2 + 1), txt)
                        painter.setPen(QColor("#ffffff"))
                        painter.drawText(int(text_x), int(text_y + th / 2), txt)
                else:
                    # 非 split：单堆原样
                    chips_values = _split_amount_to_chips(middle_pot_amount)
                    if chips_values:
                        chip_indices = [_get_chip_index(v) for v in chips_values]
                        unique_idxs = sorted(set(chip_indices))
                        stacks = []
                        for u in unique_idxs:
                            stack = [idx for idx in chip_indices if idx == u]
                            stacks.append((u, stack))

                        total_width = len(stacks) * chip_w + (len(stacks) - 1) * margin
                        start_x = center_x - total_width / 2
                        base_y = center_y + 6

                        for col, (chip_idx, stack) in enumerate(stacks):
                            chip_pix = self.chip_sprites[chip_idx % len(self.chip_sprites)]
                            cx = start_x + col * (chip_w + margin)
                            for h_idx, _ in enumerate(stack[:10]):  # 单列最多 10 枚
                                cy = base_y - h_idx * 4
                                painter.drawPixmap(int(cx), int(cy), chip_pix)

                    painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                    pot_amount_text = self._format_amount(middle_pot_amount)
                    metrics = painter.fontMetrics()
                    tw = metrics.horizontalAdvance(pot_amount_text)
                    th = metrics.height()
                    text_y = center_y + 28
                    painter.setPen(QColor(0, 0, 0, 140))
                    painter.drawText(int(center_x - tw / 2 + 1), int(text_y + th / 2 + 1), pot_amount_text)
                    painter.setPen(QColor("#ffffff"))
                    painter.drawText(int(center_x - tw / 2), int(text_y + th / 2), pot_amount_text)

        # 为所有玩家画当前街的累积下注筹码（筹码持续显示，直到下一条街）
        # 仿 RIROPO：筹码放在桌子上后，一直显示，直到下一条街开始时才进入 pot
        # 但是：如果有 collected action，显示筹码在赢家面前（而不是玩家面前的投注筹码）
        if self.chip_sprites:
            # 检查是否有 collected action（如果有，筹码应该在赢家面前，这是预先计算好的画面）
            has_collected = False
            collected_winner = None
            collected_amount = 0.0
            if self.action_index >= 0 and current_action:
                if current_action.get("action_type") == "collected":
                    has_collected = True
                    collected_winner = current_action.get("player")
                    collected_amount = float(current_action.get("amount") or 0.0)
            
            # pot_complete action 时：不显示玩家面前的投注筹码（因为筹码已经进入 pot）
            # collected action 时的逻辑：
            #   - 动画开始前：不显示玩家面前的投注筹码（因为筹码已经进入 pot）
            #   - 动画进行中：不显示预先计算好的画面（只显示动画中的筹码，从 pot 移动到 winner）
            #   - 动画结束后：显示预先计算好的画面（筹码在 winner 面前）
            animation_in_progress = self.pot_animation_timer.isActive() and self.pot_animation_chips
            animation_ended = self.pot_animation_chips and self.pot_animation_frame >= self.pot_animation_frames
            
            # 已经派奖的筹码堆（支持 split：可能有多个 winner / 多次 collected）
            # - 动画进行中：显示“之前已经发出去的那部分”
            # - 动画结束后：包含当前 collected 这次的筹码堆
            if (has_collected or has_pot_complete) and paid_by_winner:
                for winner_name, amt in paid_by_winner.items():
                    if amt > 0:
                        self._draw_collected_chips(painter, winner_name, amt, offset_x, offset_y)
            elif has_collected or has_pot_complete:
                # collected 或 pot_complete action，不显示玩家面前的投注筹码
                # 因为筹码已经进入 pot（pot_complete）或等待动画开始（collected）
                pass
            else:
                # 非 collected/pot_complete action，正常显示玩家面前的投注筹码
                # 计算每个玩家在当前街的累积投注金额（amountOnStreet）
                player_bets = {}  # {player_name: total_amount_on_current_street}
                
                if self.action_index >= 0 and current_action:
                    # 正常状态：计算到当前 action 为止，当前街所有玩家的累积投注
                    current_street = current_action.get("street", "Preflop")
                    for i in range(self.action_index + 1):
                        if i < len(self.actions):
                            act = self.actions[i]
                            if act.get("street") == current_street:
                                act_type = act.get("action_type", "")
                                player = act.get("player")
                                amount = float(act.get("amount") or 0.0)
                                
                                # 只统计 bets, calls, raises（不包括 folds, checks, collected）
                                if act_type in ["bets", "calls", "raises", "post_small_blind", "post_big_blind", "post_straddle_blind"]:
                                    if player:
                                        # 对于 raises，to_amount 是玩家在这个街的总投注金额
                                        if act_type == "raises":
                                            to_amount = float(act.get("to_amount") or 0.0)
                                            if to_amount > 0:
                                                player_bets[player] = to_amount
                                        else:
                                            # bets, calls, blinds: 累加
                                            if amount > 0:
                                                player_bets[player] = player_bets.get(player, 0.0) + amount
                elif self.action_index == -1:
                    # 初始状态：显示所有 blinds 的 bet chips
                    if self.actions:
                        for act in self.actions:
                            act_type = act.get("action_type", "")
                            if act_type in ["post_small_blind", "post_big_blind", "post_straddle_blind"]:
                                player = act.get("player")
                                amount = float(act.get("amount") or 0.0)
                                if player and amount > 0:
                                    player_bets[player] = amount
                
                # 绘制所有玩家在当前街的累积投注筹码
                for player_name, total_amount in player_bets.items():
                    if total_amount > 0:
                        self._draw_bet_chips(painter, player_name, total_amount, offset_x, offset_y)

        # 画 pot 动画（只在动画进行中时显示，动画结束后使用预先计算好的画面）
        # collected action 的最终画面是预先计算好的（筹码在赢家面前），不依赖动画
        if self.pot_animation_timer.isActive() and self.pot_animation_chips:
            self._draw_pot_animation(painter, offset_x, offset_y)

        painter.end()

    def _draw_bet_chips(self, painter, player_name, amount, offset_x, offset_y):
        """绘制玩家下注的筹码堆和金额文本。"""
        # 转成筹码面值
        chips_values = _split_amount_to_chips(amount)
        # 取该玩家的 betChips 坐标
        for idx, slot in enumerate(self.players_slots):
            if slot["name"] == player_name and idx < len(self.seats_coords):
                coord = self.seats_coords[idx]
                bx, by = coord.get("betChips", coord.get("status", (0, 0)))
                bx += offset_x
                by += offset_y
                # 将每个筹码垂直叠放（x 不偏移），更接近 RIROPO
                for i, chip_value in enumerate(chips_values[:8]):  # 限制最大显示数量
                    chip_idx = _get_chip_index(chip_value)
                    chip_pix = self.chip_sprites[chip_idx % len(self.chip_sprites)]
                    cx = bx
                    cy = by - i * 4
                    painter.drawPixmap(int(cx), int(cy), chip_pix)

                # 金额文本（根据 show_big_blinds 切换），放在 chips_value_pos
                val_x, val_y = coord.get("chips_value_pos", (bx, by - 10))
                val_x += offset_x
                val_y += offset_y
                painter.setPen(Qt.white)
                painter.setFont(QFont("Segoe UI", 9))
                if self.show_big_blinds and self.big_blind and self.big_blind > 0:
                    bb_val = amount / self.big_blind
                    txt = f"{bb_val:.1f} BB"
                else:
                    txt = f"${amount:.2f}"
                painter.drawText(int(val_x), int(val_y), txt)
                break

    def _draw_collected_chips(self, painter, winner_name, amount, offset_x, offset_y):
        """绘制 collected 时赢家面前的筹码堆（预先计算好的画面）。"""
        # 找到 winner 的座位
        winner_idx = -1
        for idx, slot in enumerate(self.players_slots):
            if slot["name"] == winner_name:
                winner_idx = idx
                break
        
        if winner_idx < 0 or winner_idx >= len(self.seats_coords):
            return
        
        coord = self.seats_coords[winner_idx]
        target_bet_chips = coord.get("betChips", (0, 0))
        
        # 目标位置（winner 的 betChips）
        target_x = target_bet_chips[0] + offset_x
        target_y = target_bet_chips[1] + offset_y
        
        # 生成筹码堆
        chip_w = 22
        margin = 2
        chips_values = _split_amount_to_chips(amount)
        chip_indices = [_get_chip_index(v) for v in chips_values]
        unique_idxs = sorted(set(chip_indices))
        
        # 构造多列堆栈（类似 middle-pot.js 的 makeChipsOutSets）
        chips_out_sets = []
        for col, u_idx in enumerate(unique_idxs):
            stack = [idx for idx in chip_indices if idx == u_idx]
            for h_idx, chip_idx in enumerate(stack[:10]):  # 单列最多 10 枚
                chips_out_sets.append({
                    "index": chip_idx,
                    "x": col * (chip_w + margin),
                    "y": -h_idx * 4
                })
        
        # 计算筹码堆的总宽度
        uniques_count = len(unique_idxs)
        chips_span = uniques_count * chip_w + (uniques_count - 1) * margin
        
        # 绘制筹码堆（在赢家面前，这是预先计算好的画面）
        start_x = target_x - chips_span / 2
        
        for chip_info in chips_out_sets:
            chip_idx = chip_info["index"]
            rel_x = chip_info["x"]
            rel_y = chip_info["y"]
            
            if self.chip_sprites:
                chip_pix = self.chip_sprites[chip_idx % len(self.chip_sprites)]
                cx = start_x + rel_x
                cy = target_y + rel_y
                painter.drawPixmap(int(cx), int(cy), chip_pix)
        
        # 绘制金额文本（放在筹码堆下方，避免遮挡筹码，保持与中间 pot 一致）
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        txt = self._format_amount(amount)
        metrics = painter.fontMetrics()
        tw = metrics.horizontalAdvance(txt)
        th = metrics.height()
        text_x = target_x - tw / 2
        text_y = target_y + 28  # 在筹码堆底部下方
        painter.setPen(QColor(0, 0, 0, 140))
        painter.drawText(int(text_x + 1), int(text_y + th / 2 + 1), txt)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(int(text_x), int(text_y + th / 2), txt)

    def _centered_rect(self, pix_size, target_rect: QRect) -> QRect:
        """返回一个居中显示 pixmap 的 QRect。"""
        w, h = pix_size.width(), pix_size.height()
        x = target_rect.x() + (target_rect.width() - w) / 2
        y = target_rect.y() + (target_rect.height() - h) / 2
        return QRect(int(x), int(y), w, h)

    def _check_and_start_pot_animation(self):
        """检查当前 action 是否是 collected，如果是则启动 pot 动画（仅用于播放过程）。"""
        # 停止之前的动画
        if self.pot_animation_timer.isActive():
            self.pot_animation_timer.stop()
        
        # 清空动画状态（每个节点都应该有预先计算好的画面，不依赖动画状态）
        self.pot_animation_chips = []
        self.pot_animation_frame = 0
        self.pot_animation_pending = False
        self.pot_animation_pending_token += 1
        my_token = self.pot_animation_pending_token
        
        # 检查当前 action 是否是 collected，如果是则启动动画（仅用于播放过程）
        # pot_complete 节点不需要动画，它只是显示所有筹码都进入 pot 的状态
        if self.action_index >= 0 and self.action_index < len(self.actions):
            current_action = self.actions[self.action_index]
            if current_action.get("action_type") == "collected":
                winner_name = current_action.get("player")
                # split pot / run-it-twice：可能出现多次 collected，需要“分多次”把筹码发到赢家手里
                # - 如果这一段（从最近一次 pot_complete 到结束）只有 1 个 collected：动画移动整堆中间 pot
                # - 如果有多个 collected：每次按“中间 pot 平均分的一份”动画（每次发走一半/1/N，不扣 rake/jackpot）
                animate_amount = 0.0
                initial_override = None
                try:
                    # 找到最近的 pot_complete
                    seg_start = 0
                    for j in range(self.action_index, -1, -1):
                        a = self.actions[j]
                        if isinstance(a, dict) and a.get("action_type") == "pot_complete":
                            seg_start = j
                            break
                    collected_count = 0
                    seg_pot_amount = 0.0
                    seq_idx = 0
                    pile_idx_for_this = None
                    for j in range(seg_start, len(self.actions)):
                        a = self.actions[j]
                        if not isinstance(a, dict):
                            continue
                        if a.get("action_type") == "pot_complete" and j == seg_start:
                            seg_pot_amount = float(a.get("pot_size") or 0.0)
                        elif a.get("action_type") == "pot_complete" and j != seg_start:
                            break
                        elif a.get("action_type") == "collected":
                            collected_count += 1
                            if j == self.action_index:
                                run_tag = a.get("run")
                                if run_tag is not None:
                                    try:
                                        pile_idx_for_this = max(0, int(run_tag) - 1)
                                    except Exception:
                                        pile_idx_for_this = seq_idx
                                else:
                                    pile_idx_for_this = seq_idx
                            seq_idx += 1
                    if collected_count > 1:
                        if seg_pot_amount <= 0:
                            seg_pot_amount = float(current_action.get("pot_size") or 0.0) or 0.0
                        animate_amount = float(seg_pot_amount) / float(collected_count) if seg_pot_amount > 0 else float(current_action.get("amount") or 0.0)
                        # split：动画从对应那一堆起飞（中间两堆/多堆之一）
                        if pile_idx_for_this is not None:
                            # 计算该堆的中间位置（需和 paintEvent 里一致）
                            widget_rect = self.rect()
                            table_width = 792
                            table_height = 555
                            offset_x = (widget_rect.width() - table_width) / 2
                            offset_y = (widget_rect.height() - table_height) / 2
                            center_x = widget_rect.x() + widget_rect.width() / 2
                            center_y = widget_rect.y() + widget_rect.height() / 2 + 30
                            chip_w = 22
                            gap = 18
                            total_span = collected_count * chip_w + (collected_count - 1) * gap
                            start_pile_x = center_x - total_span / 2
                            pile_x = start_pile_x + pile_idx_for_this * (chip_w + gap) + chip_w / 2
                            initial_override = (pile_x, center_y + 6)
                    else:
                        animate_amount = float(current_action.get("pot_size") or 0.0) or float(current_action.get("amount") or 0.0)
                except Exception:
                    animate_amount = float(current_action.get("amount") or 0.0)

                if winner_name and animate_amount > 0:
                    # 延迟启动动画，先显示 pot 在中间（所有筹码都进入 pot）
                    # 使用 QTimer.singleShot 延迟启动，让用户先看到完整的 pot
                    # 动画只是播放过程，最终画面是预先计算好的（在 _draw_collected_chips 中）
                    from PySide6.QtCore import QTimer as QTimerSingle
                    self.pot_animation_pending = True

                    def _fire():
                        # 如果用户在 500ms 内跳走了，不要启动旧动画
                        if self.pot_animation_pending_token != my_token:
                            return
                        if not (0 <= self.action_index < len(self.actions)):
                            return
                        a = self.actions[self.action_index]
                        if not (isinstance(a, dict) and a.get("action_type") == "collected"):
                            return
                        if initial_override:
                            self._start_pot_animation(winner_name, animate_amount, initial_override)
                        else:
                            self._start_pot_animation(winner_name, animate_amount)

                    QTimerSingle.singleShot(500, _fire)

    def _start_pot_animation(self, winner_name: str, amount: float, initial_override=None):
        """启动 pot 动画：从中间移动到 winner 的 betChips 位置。"""
        # 进入真正动画后，pending 结束
        self.pot_animation_pending = False
        # 找到 winner 的座位
        winner_slot = None
        winner_idx = -1
        for idx, slot in enumerate(self.players_slots):
            if slot["name"] == winner_name:
                winner_slot = slot
                winner_idx = idx
                break
        
        if winner_idx < 0 or winner_idx >= len(self.seats_coords):
            return
        
        coord = self.seats_coords[winner_idx]
        target_bet_chips = coord.get("betChips", (0, 0))
        
        # 计算初始位置（中间 pot 位置）
        widget_rect = self.rect()
        table_width = 792
        table_height = 555
        offset_x = (widget_rect.width() - table_width) / 2
        offset_y = (widget_rect.height() - table_height) / 2
        initial_x = widget_rect.x() + widget_rect.width() / 2
        initial_y = widget_rect.y() + widget_rect.height() / 2 + 30
        if initial_override and isinstance(initial_override, (tuple, list)) and len(initial_override) == 2:
            try:
                initial_x = float(initial_override[0])
                initial_y = float(initial_override[1])
            except Exception:
                pass
        
        # 目标位置（winner 的 betChips）
        target_x = target_bet_chips[0] + offset_x
        target_y = target_bet_chips[1] + offset_y
        
        # 生成筹码堆
        chip_w = 22
        margin = 2
        chips_values = _split_amount_to_chips(amount)
        chip_indices = [_get_chip_index(v) for v in chips_values]
        unique_idxs = sorted(set(chip_indices))
        
        # 构造多列堆栈（类似 middle-pot.js 的 makeChipsOutSets）
        chips_out_sets = []
        for col, u_idx in enumerate(unique_idxs):
            stack = [idx for idx in chip_indices if idx == u_idx]
            for h_idx, chip_idx in enumerate(stack[:10]):  # 单列最多 10 枚
                chips_out_sets.append({
                    "index": chip_idx,
                    "x": col * (chip_w + margin),
                    "y": -h_idx * 4
                })
        
        # 计算筹码堆的总宽度
        uniques_count = len(unique_idxs)
        chips_span = uniques_count * chip_w + (uniques_count - 1) * margin
        
        # 保存动画参数
        self.pot_animation_chips = chips_out_sets
        self.pot_animation_target = (target_x, target_y)
        self.pot_animation_amount = amount
        self.pot_animation_winner_name = winner_name
        self.pot_animation_initial = (initial_x, initial_y)
        self.pot_animation_chips_span = chips_span
        self.pot_animation_frame = 0
        
        # 启动定时器
        self.pot_animation_timer.start()

    def _update_pot_animation(self):
        """更新 pot 动画帧。"""
        self.pot_animation_frame += 1
        if self.pot_animation_frame >= self.pot_animation_frames:
            self.pot_animation_timer.stop()
            # 动画结束后，保持筹码在玩家面前（不重置，让画面停在玩家面前）
            # self.pot_animation_frame = 0  # 不重置 frame，保持最后一帧
            # self.pot_animation_chips = []  # 不清空筹码，保持显示
        self.update()

    def _draw_pot_animation(self, painter, offset_x, offset_y):
        """绘制 pot 动画：从中间移动到 winner 位置。"""
        if not self.pot_animation_chips or not self.pot_animation_target:
            return
        
        # 线性插值（lerp）
        initial_x, initial_y = self.pot_animation_initial
        target_x, target_y = self.pot_animation_target
        
        # 如果动画已经结束，保持在目标位置（不回到中间）
        if self.pot_animation_frame >= self.pot_animation_frames:
            t = 1.0  # 保持在目标位置
        else:
            t = self.pot_animation_frame / self.pot_animation_frames
        
        # 计算当前帧的位置
        current_x = initial_x + (target_x - initial_x) * t
        current_y = initial_y + (target_y - initial_y) * t
        
        # 绘制筹码堆
        chips_span = self.pot_animation_chips_span
        start_x = current_x - chips_span / 2
        
        for chip_info in self.pot_animation_chips:
            chip_idx = chip_info["index"]
            rel_x = chip_info["x"]
            rel_y = chip_info["y"]
            
            if self.chip_sprites:
                chip_pix = self.chip_sprites[chip_idx % len(self.chip_sprites)]
                cx = start_x + rel_x
                cy = current_y + rel_y
                painter.drawPixmap(int(cx), int(cy), chip_pix)
        
        # 绘制金额文本（放在筹码堆下方，避免遮挡筹码，保持与中间 pot 一致）
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        txt = self._format_amount(self.pot_animation_amount)
        metrics = painter.fontMetrics()
        tw = metrics.horizontalAdvance(txt)
        th = metrics.height()
        text_x = current_x - tw / 2
        text_y = current_y + 28
        painter.setPen(QColor(0, 0, 0, 140))
        painter.drawText(int(text_x + 1), int(text_y + th / 2 + 1), txt)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(int(text_x), int(text_y + th / 2), txt)


