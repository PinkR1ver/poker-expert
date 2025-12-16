"""
简化版 Equity Calculator
使用 Monte Carlo 模拟计算 All-in 时的手牌 Equity
"""
import random
from itertools import combinations

# 牌面定义
RANKS = '23456789TJQKA'
SUITS = 'cdhs'
RANK_VALUES = {r: i for i, r in enumerate(RANKS)}

def parse_card(card_str):
    """解析单张牌 e.g. 'Ah' -> ('A', 'h')"""
    if len(card_str) == 2:
        return (card_str[0], card_str[1])
    return None

def parse_cards(cards_str):
    """解析多张牌 e.g. '7h Ah' -> [('7', 'h'), ('A', 'h')]"""
    cards = []
    for card in cards_str.replace('[', '').replace(']', '').split():
        c = parse_card(card)
        if c:
            cards.append(c)
    return cards

def create_deck():
    """创建一副完整的牌"""
    return [(r, s) for r in RANKS for s in SUITS]

def remove_cards(deck, cards):
    """从牌堆中移除已知的牌"""
    return [c for c in deck if c not in cards]

def hand_rank(cards):
    """
    评估 7 张牌的最佳 5 张组合
    返回一个可比较的元组 (rank_type, tiebreakers)
    rank_type: 1=高牌, 2=一对, 3=两对, 4=三条, 5=顺子, 6=同花, 7=葫芦, 8=四条, 9=同花顺
    """
    if len(cards) < 5:
        return (0, [])
    
    # 尝试所有 5 张牌的组合，返回最佳
    best = (0, [])
    for combo in combinations(cards, 5):
        rank = evaluate_five(list(combo))
        if rank > best:
            best = rank
    return best

def evaluate_five(cards):
    """评估 5 张牌的牌型"""
    ranks = sorted([RANK_VALUES[c[0]] for c in cards], reverse=True)
    suits = [c[1] for c in cards]
    
    is_flush = len(set(suits)) == 1
    
    # 检查顺子
    is_straight = False
    straight_high = 0
    unique_ranks = sorted(set(ranks), reverse=True)
    
    if len(unique_ranks) >= 5:
        for i in range(len(unique_ranks) - 4):
            if unique_ranks[i] - unique_ranks[i+4] == 4:
                is_straight = True
                straight_high = unique_ranks[i]
                break
        # 特殊情况: A-2-3-4-5 (wheel)
        if set([12, 3, 2, 1, 0]).issubset(set(ranks)):
            is_straight = True
            straight_high = 3  # 5-high straight
    
    # 统计每个 rank 的数量
    rank_counts = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1
    
    counts = sorted(rank_counts.values(), reverse=True)
    
    # 同花顺
    if is_flush and is_straight:
        return (9, [straight_high])
    
    # 四条
    if counts == [4, 1]:
        quad_rank = [r for r, c in rank_counts.items() if c == 4][0]
        kicker = [r for r, c in rank_counts.items() if c == 1][0]
        return (8, [quad_rank, kicker])
    
    # 葫芦
    if counts == [3, 2]:
        trip_rank = [r for r, c in rank_counts.items() if c == 3][0]
        pair_rank = [r for r, c in rank_counts.items() if c == 2][0]
        return (7, [trip_rank, pair_rank])
    
    # 同花
    if is_flush:
        return (6, ranks)
    
    # 顺子
    if is_straight:
        return (5, [straight_high])
    
    # 三条
    if counts == [3, 1, 1]:
        trip_rank = [r for r, c in rank_counts.items() if c == 3][0]
        kickers = sorted([r for r, c in rank_counts.items() if c == 1], reverse=True)
        return (4, [trip_rank] + kickers)
    
    # 两对
    if counts == [2, 2, 1]:
        pairs = sorted([r for r, c in rank_counts.items() if c == 2], reverse=True)
        kicker = [r for r, c in rank_counts.items() if c == 1][0]
        return (3, pairs + [kicker])
    
    # 一对
    if counts == [2, 1, 1, 1]:
        pair_rank = [r for r, c in rank_counts.items() if c == 2][0]
        kickers = sorted([r for r, c in rank_counts.items() if c == 1], reverse=True)
        return (2, [pair_rank] + kickers)
    
    # 高牌
    return (1, ranks)

def calculate_equity(hero_cards, villain_cards, board, num_simulations=5000):
    """
    计算 Hero 的 equity (胜率 + 平局率/2)
    
    Args:
        hero_cards: Hero 的手牌 e.g. [('A', 'h'), ('K', 's')]
        villain_cards: 对手的手牌
        board: 公共牌 (可以是 3, 4, 或 5 张)
        num_simulations: Monte Carlo 模拟次数
    
    Returns:
        float: Hero 的 equity (0.0 - 1.0)
    """
    if not hero_cards or not villain_cards:
        return 0.5  # 无效输入返回 50%
    
    # 创建剩余牌堆
    known_cards = hero_cards + villain_cards + board
    remaining_deck = remove_cards(create_deck(), known_cards)
    
    cards_needed = 5 - len(board)
    
    wins = 0
    ties = 0
    
    for _ in range(num_simulations):
        # 随机发剩余的公共牌
        if cards_needed > 0:
            runout = random.sample(remaining_deck, cards_needed)
            final_board = board + runout
        else:
            final_board = board
        
        # 评估双方手牌
        hero_hand = hero_cards + final_board
        villain_hand = villain_cards + final_board
        
        hero_rank = hand_rank(hero_hand)
        villain_rank = hand_rank(villain_hand)
        
        if hero_rank > villain_rank:
            wins += 1
        elif hero_rank == villain_rank:
            ties += 1
    
    equity = (wins + ties / 2) / num_simulations
    return equity

def calculate_all_in_ev(hero_cards_str, villain_cards_str, board_str, pot_size, hero_invested):
    """
    计算 All-in EV
    
    Args:
        hero_cards_str: Hero 手牌字符串 e.g. "7h Ah"
        villain_cards_str: 对手手牌字符串 e.g. "5c 5d"
        board_str: 公共牌字符串 e.g. "5h 8c 4h"
        pot_size: 总底池大小
        hero_invested: Hero 投入的金额
    
    Returns:
        dict: {'equity': float, 'ev': float, 'ev_diff': float}
    """
    hero_cards = parse_cards(hero_cards_str)
    villain_cards = parse_cards(villain_cards_str)
    board = parse_cards(board_str)
    
    if not hero_cards or not villain_cards:
        return {'equity': 0.5, 'ev': 0, 'ev_diff': 0}
    
    equity = calculate_equity(hero_cards, villain_cards, board)
    
    # EV = (Pot × Equity) - Investment
    # 注意：这里的 pot_size 是总底池，hero_invested 是 Hero 投入的部分
    expected_return = pot_size * equity
    ev = expected_return - hero_invested
    
    return {
        'equity': equity,
        'ev': ev
    }


# 测试
if __name__ == "__main__":
    # 测试案例: Hero [7h Ah] vs Villain [5c 5d] on [5h 8c 4h]
    # Hero 有 flush draw + gutshot
    result = calculate_all_in_ev(
        hero_cards_str="7h Ah",
        villain_cards_str="5c 5d", 
        board_str="5h 8c 4h",
        pot_size=5.0,
        hero_invested=2.42
    )
    print(f"Test 1 - Hero flush draw vs set:")
    print(f"  Equity: {result['equity']:.1%}")
    print(f"  EV: ${result['ev']:.2f}")
    
    # 测试案例 2: AA vs KK preflop (约 80% vs 20%)
    result2 = calculate_all_in_ev(
        hero_cards_str="As Ac",
        villain_cards_str="Kh Kd",
        board_str="",
        pot_size=200.0,
        hero_invested=100.0
    )
    print(f"\nTest 2 - AA vs KK preflop:")
    print(f"  Equity: {result2['equity']:.1%}")
    print(f"  EV: ${result2['ev']:.2f}")
    
    # 测试手牌评估
    print("\n\nHand ranking tests:")
    test_hands = [
        [('A', 's'), ('K', 's'), ('Q', 's'), ('J', 's'), ('T', 's')],  # Royal flush
        [('5', 'h'), ('5', 'd'), ('5', 'c'), ('5', 's'), ('K', 'h')],  # Quads
        [('A', 'h'), ('A', 'd'), ('K', 'h'), ('K', 'd'), ('K', 'c')],  # Full house
    ]
    for hand in test_hands:
        rank = evaluate_five(hand)
        print(f"  {hand} -> {rank}")

