"""
手牌强度评估 - 复用 equity_calculator 的逻辑
"""
from solver.card_utils import RANK_VALUES
from solver.data_types import Card
from itertools import combinations
from functools import lru_cache
import random

# 全局 equity 缓存
_equity_cache = {}


def evaluate_five(cards: list[Card]) -> tuple[int, list[int]]:
    """
    评估 5 张牌的牌型
    返回 (rank_type, tiebreakers)
    rank_type: 1=高牌, 2=一对, 3=两对, 4=三条, 5=顺子, 6=同花, 7=葫芦, 8=四条, 9=同花顺
    """
    if len(cards) != 5:
        return (0, [])
    
    ranks = sorted([c.rank for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    
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


def hand_rank(cards: list[Card]) -> tuple[int, list[int]]:
    """
    评估 7 张牌的最佳 5 张组合
    返回一个可比较的元组 (rank_type, tiebreakers)
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


def calculate_equity(
    hero_cards: list[Card],
    villain_cards: list[Card],
    board: list[Card],
    num_simulations: int = 5000
) -> float:
    """
    计算 Hero 的 equity (胜率 + 平局率/2)，带缓存
    
    Args:
        hero_cards: Hero 的手牌
        villain_cards: 对手的手牌
        board: 公共牌 (可以是 3, 4, 或 5 张)
        num_simulations: Monte Carlo 模拟次数
    
    Returns:
        float: Hero 的 equity (0.0 - 1.0)
    """
    global _equity_cache
    
    if not hero_cards or not villain_cards or len(hero_cards) != 2 or len(villain_cards) != 2:
        return 0.5
    
    # 创建缓存 key（排序后的牌）
    hero_key = tuple(sorted((c.rank, c.suit) for c in hero_cards))
    villain_key = tuple(sorted((c.rank, c.suit) for c in villain_cards))
    board_key = tuple((c.rank, c.suit) for c in board)
    cache_key = (hero_key, villain_key, board_key)
    
    # 检查缓存
    if cache_key in _equity_cache:
        return _equity_cache[cache_key]
    
    # 检查牌冲突
    all_known = hero_cards + villain_cards + board
    if len(all_known) != len(set(all_known)):
        _equity_cache[cache_key] = 0.5
        return 0.5
    
    # 创建剩余牌堆
    all_cards = []
    for rank in range(13):
        for suit in range(4):
            all_cards.append(Card(rank=rank, suit=suit))
    
    remaining_deck = [c for c in all_cards if c not in all_known]
    cards_needed = 5 - len(board)
    
    if cards_needed <= 0:
        # Board 已经完整，直接比较
        final_board = board[:5]
        hero_rank = hand_rank(hero_cards + final_board)
        villain_rank = hand_rank(villain_cards + final_board)
        
        if hero_rank > villain_rank:
            result = 1.0
        elif hero_rank == villain_rank:
            result = 0.5
        else:
            result = 0.0
        _equity_cache[cache_key] = result
        return result
    
    wins = 0
    ties = 0
    
    for _ in range(num_simulations):
        # 随机发剩余的公共牌
        runout = random.sample(remaining_deck, cards_needed)
        final_board = board + runout
        
        # 评估双方手牌
        hero_rank = hand_rank(hero_cards + final_board)
        villain_rank = hand_rank(villain_cards + final_board)
        
        if hero_rank > villain_rank:
            wins += 1
        elif hero_rank == villain_rank:
            ties += 1
    
    equity = (wins + ties / 2) / num_simulations
    _equity_cache[cache_key] = equity
    return equity


def clear_equity_cache():
    """清空 equity 缓存"""
    global _equity_cache
    _equity_cache = {}

