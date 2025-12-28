"""
牌面工具函数
"""
from solver.data_types import Card
from itertools import combinations

# 169 种起手牌矩阵
HAND_MATRIX = [
    ["AA", "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s"],
    ["AKo", "KK", "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s"],
    ["AQo", "KQo", "QQ", "QJs", "QTs", "Q9s", "Q8s", "Q7s", "Q6s", "Q5s", "Q4s", "Q3s", "Q2s"],
    ["AJo", "KJo", "QJo", "JJ", "JTs", "J9s", "J8s", "J7s", "J6s", "J5s", "J4s", "J3s", "J2s"],
    ["ATo", "KTo", "QTo", "JTo", "TT", "T9s", "T8s", "T7s", "T6s", "T5s", "T4s", "T3s", "T2s"],
    ["A9o", "K9o", "Q9o", "J9o", "T9o", "99", "98s", "97s", "96s", "95s", "94s", "93s", "92s"],
    ["A8o", "K8o", "Q8o", "J8o", "T8o", "98o", "88", "87s", "86s", "85s", "84s", "83s", "82s"],
    ["A7o", "K7o", "Q7o", "J7o", "T7o", "97o", "87o", "77", "76s", "75s", "74s", "73s", "72s"],
    ["A6o", "K6o", "Q6o", "J6o", "T6o", "96o", "86o", "76o", "66", "65s", "64s", "63s", "62s"],
    ["A5o", "K5o", "Q5o", "J5o", "T5o", "95o", "85o", "75o", "65o", "55", "54s", "53s", "52s"],
    ["A4o", "K4o", "Q4o", "J4o", "T4o", "94o", "84o", "74o", "64o", "54o", "44", "43s", "42s"],
    ["A3o", "K3o", "Q3o", "J3o", "T3o", "93o", "83o", "73o", "63o", "53o", "43o", "33", "32s"],
    ["A2o", "K2o", "Q2o", "J2o", "T2o", "92o", "82o", "72o", "62o", "52o", "42o", "32o", "22"],
]

RANKS = '23456789TJQKA'
SUITS = 'cdhs'
RANK_VALUES = {r: i for i, r in enumerate(RANKS)}


def parse_card(card_str: str) -> Card:
    """解析单张牌字符串 e.g. 'Ah' -> Card"""
    if len(card_str) != 2:
        raise ValueError(f"Invalid card format: {card_str}")
    
    rank_char = card_str[0].upper()
    suit_char = card_str[1].lower()
    
    if rank_char not in RANK_VALUES:
        raise ValueError(f"Invalid rank: {rank_char}")
    if suit_char not in SUITS:
        raise ValueError(f"Invalid suit: {suit_char}")
    
    return Card(
        rank=RANK_VALUES[rank_char],
        suit=SUITS.index(suit_char)
    )


def parse_cards(cards_str: str) -> list[Card]:
    """解析多张牌字符串 e.g. 'Ah Ks 7c' -> [Card, Card, Card]"""
    cards = []
    for card_str in cards_str.split():
        cards.append(parse_card(card_str))
    return cards


def card_to_string(card: Card) -> str:
    """Card 转字符串"""
    return str(card)


def get_hand_combos(hand_str: str) -> list[tuple[Card, Card]]:
    """
    获取手牌字符串对应的所有 combo
    e.g. "AA" -> [(Ac, Ad), (Ac, Ah), (Ac, As), (Ad, Ah), (Ad, As), (Ah, As)]
    e.g. "AKs" -> [(Ac, Kc), (Ad, Kd), (Ah, Kh), (As, Ks)]
    e.g. "AKo" -> 所有不同花色的组合
    """
    if len(hand_str) < 2:
        return []
    
    rank1_char = hand_str[0]
    rank2_char = hand_str[1]
    is_suited = len(hand_str) > 2 and hand_str[2].lower() == 's'
    is_offsuit = len(hand_str) > 2 and hand_str[2].lower() == 'o'
    
    rank1 = RANK_VALUES.get(rank1_char)
    rank2 = RANK_VALUES.get(rank2_char)
    
    if rank1 is None or rank2 is None:
        return []
    
    combos = []
    
    if rank1 == rank2:
        # Pocket pair - 所有不同花色的组合
        for suit1 in range(4):
            for suit2 in range(suit1 + 1, 4):
                combos.append((
                    Card(rank=rank1, suit=suit1),
                    Card(rank=rank2, suit=suit2)
                ))
    elif is_suited:
        # Suited - 同花色
        for suit in range(4):
            combos.append((
                Card(rank=rank1, suit=suit),
                Card(rank=rank2, suit=suit)
            ))
    elif is_offsuit:
        # Offsuit - 不同花色
        for suit1 in range(4):
            for suit2 in range(4):
                if suit1 != suit2:
                    combos.append((
                        Card(rank=rank1, suit=suit1),
                        Card(rank=rank2, suit=suit2)
                    ))
    else:
        # 默认当作 offsuit
        for suit1 in range(4):
            for suit2 in range(4):
                if suit1 != suit2:
                    combos.append((
                        Card(rank=rank1, suit=suit1),
                        Card(rank=rank2, suit=suit2)
                    ))
    
    return combos


def get_all_combos() -> dict[str, list[tuple[Card, Card]]]:
    """获取所有手牌字符串对应的 combos"""
    all_combos = {}
    for row in HAND_MATRIX:
        for hand_str in row:
            all_combos[hand_str] = get_hand_combos(hand_str)
    return all_combos


def cards_conflict(cards1: list[Card], cards2: list[Card]) -> bool:
    """检查两组牌是否有冲突（重复的牌）"""
    set1 = set(cards1)
    set2 = set(cards2)
    return bool(set1 & set2)


def is_valid_board(board: list[Card]) -> bool:
    """检查 board 是否有效（无重复）"""
    return len(board) == len(set(board))


