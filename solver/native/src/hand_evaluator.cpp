#include "hand_evaluator.h"
#include <algorithm>
#include <array>
#include <numeric>

namespace poker {

// ============================================================================
// HandEvaluator 实现
// ============================================================================

HandEvaluator::HandEvaluator() {
    // 可以在这里初始化查找表
}

HandRank HandEvaluator::evaluate_five_internal(
    CardInt c0, CardInt c1, CardInt c2, CardInt c3, CardInt c4
) const {
    // 提取 rank 和 suit
    std::array<int, 5> ranks = {
        card_rank(c0), card_rank(c1), card_rank(c2), 
        card_rank(c3), card_rank(c4)
    };
    std::array<int, 5> suits = {
        card_suit(c0), card_suit(c1), card_suit(c2), 
        card_suit(c3), card_suit(c4)
    };
    
    // 排序 ranks（降序）
    std::sort(ranks.begin(), ranks.end(), std::greater<int>());
    
    // 检查同花
    bool is_flush = (suits[0] == suits[1] && suits[1] == suits[2] && 
                     suits[2] == suits[3] && suits[3] == suits[4]);
    
    // 检查顺子
    bool is_straight = false;
    int straight_high = 0;
    
    // 获取唯一的 ranks
    std::array<int, 5> unique_ranks = ranks;
    auto last = std::unique(unique_ranks.begin(), unique_ranks.end());
    int num_unique = std::distance(unique_ranks.begin(), last);
    
    if (num_unique == 5) {
        // 检查普通顺子
        if (ranks[0] - ranks[4] == 4) {
            is_straight = true;
            straight_high = ranks[0];
        }
        // 检查 A-2-3-4-5 (wheel)
        else if (ranks[0] == 12 && ranks[1] == 3 && ranks[2] == 2 && 
                 ranks[3] == 1 && ranks[4] == 0) {
            is_straight = true;
            straight_high = 3;  // 5-high
        }
    }
    
    // 统计每个 rank 的数量
    std::array<int, 13> rank_counts = {0};
    for (int r : ranks) {
        rank_counts[r]++;
    }
    
    // 获取 count 分布
    std::array<int, 5> counts = {0};
    int count_idx = 0;
    for (int c : rank_counts) {
        if (c > 0) counts[count_idx++] = c;
    }
    std::sort(counts.begin(), counts.begin() + count_idx, std::greater<int>());
    
    // 同花顺
    if (is_flush && is_straight) {
        return make_hand_rank(RANK_STRAIGHT_FLUSH, straight_high);
    }
    
    // 四条
    if (counts[0] == 4) {
        int quad_rank = -1, kicker = -1;
        for (int r = 12; r >= 0; r--) {
            if (rank_counts[r] == 4) quad_rank = r;
            else if (rank_counts[r] == 1) kicker = r;
        }
        return make_hand_rank(RANK_FOUR_OF_A_KIND, quad_rank, kicker);
    }
    
    // 葫芦
    if (counts[0] == 3 && counts[1] == 2) {
        int trip_rank = -1, pair_rank = -1;
        for (int r = 12; r >= 0; r--) {
            if (rank_counts[r] == 3) trip_rank = r;
            else if (rank_counts[r] == 2) pair_rank = r;
        }
        return make_hand_rank(RANK_FULL_HOUSE, trip_rank, pair_rank);
    }
    
    // 同花
    if (is_flush) {
        return make_hand_rank(RANK_FLUSH, ranks[0], ranks[1], ranks[2], ranks[3], ranks[4]);
    }
    
    // 顺子
    if (is_straight) {
        return make_hand_rank(RANK_STRAIGHT, straight_high);
    }
    
    // 三条
    if (counts[0] == 3) {
        int trip_rank = -1;
        std::vector<int> kickers;
        for (int r = 12; r >= 0; r--) {
            if (rank_counts[r] == 3) trip_rank = r;
            else if (rank_counts[r] == 1) kickers.push_back(r);
        }
        return make_hand_rank(RANK_THREE_OF_A_KIND, trip_rank, 
                             kickers.size() > 0 ? kickers[0] : 0,
                             kickers.size() > 1 ? kickers[1] : 0);
    }
    
    // 两对
    if (counts[0] == 2 && counts[1] == 2) {
        std::vector<int> pairs;
        int kicker = -1;
        for (int r = 12; r >= 0; r--) {
            if (rank_counts[r] == 2) pairs.push_back(r);
            else if (rank_counts[r] == 1) kicker = r;
        }
        return make_hand_rank(RANK_TWO_PAIR, pairs[0], pairs[1], kicker);
    }
    
    // 一对
    if (counts[0] == 2) {
        int pair_rank = -1;
        std::vector<int> kickers;
        for (int r = 12; r >= 0; r--) {
            if (rank_counts[r] == 2) pair_rank = r;
            else if (rank_counts[r] == 1) kickers.push_back(r);
        }
        return make_hand_rank(RANK_ONE_PAIR, pair_rank, 
                             kickers.size() > 0 ? kickers[0] : 0,
                             kickers.size() > 1 ? kickers[1] : 0,
                             kickers.size() > 2 ? kickers[2] : 0);
    }
    
    // 高牌
    return make_hand_rank(RANK_HIGH_CARD, ranks[0], ranks[1], ranks[2], ranks[3], ranks[4]);
}

HandRank HandEvaluator::evaluate_five(const CardInt cards[5]) const {
    return evaluate_five_internal(cards[0], cards[1], cards[2], cards[3], cards[4]);
}

HandRank HandEvaluator::evaluate_seven(const CardInt cards[7]) const {
    HandRank best = 0;
    
    // 遍历所有 C(7,5) = 21 种组合
    for (int i = 0; i < 7; i++) {
        for (int j = i + 1; j < 7; j++) {
            // 跳过 i 和 j，选择其余 5 张
            CardInt five[5];
            int idx = 0;
            for (int k = 0; k < 7; k++) {
                if (k != i && k != j) {
                    five[idx++] = cards[k];
                }
            }
            
            HandRank rank = evaluate_five(five);
            if (rank > best) {
                best = rank;
            }
        }
    }
    
    return best;
}

HandRank HandEvaluator::evaluate(const HoleCards& hole, const Board& board, int board_size) const {
    // 合并手牌和公共牌
    CardInt all_cards[7];
    all_cards[0] = hole[0];
    all_cards[1] = hole[1];
    for (int i = 0; i < board_size && i < 5; i++) {
        all_cards[2 + i] = board[i];
    }
    
    int total = 2 + board_size;
    
    if (total < 5) {
        return 0;  // 牌不够
    } else if (total == 5) {
        return evaluate_five(all_cards);
    } else if (total == 6) {
        // 6 选 5
        HandRank best = 0;
        for (int skip = 0; skip < 6; skip++) {
            CardInt five[5];
            int idx = 0;
            for (int i = 0; i < 6; i++) {
                if (i != skip) five[idx++] = all_cards[i];
            }
            HandRank rank = evaluate_five(five);
            if (rank > best) best = rank;
        }
        return best;
    } else {
        return evaluate_seven(all_cards);
    }
}

// ============================================================================
// Thread-local RNG for thread-safe parallel execution
// ============================================================================

namespace {
    // 每个线程独立的随机数生成器
    std::mt19937_64& get_thread_local_rng() {
        thread_local std::mt19937_64 rng(std::random_device{}());
        return rng;
    }
}  // namespace

// ============================================================================
// EquityCalculator 实现
// ============================================================================

EquityCalculator::EquityCalculator() : rng_(std::random_device{}()) {
}

void EquityCalculator::set_seed(uint64_t seed) {
    rng_.seed(seed);
    // 注意: 这只设置主线程的 seed，thread_local RNG 不受影响
}

std::vector<CardInt> EquityCalculator::make_deck(CardMask dead_cards) const {
    std::vector<CardInt> deck;
    deck.reserve(52);
    for (CardInt c = 0; c < 52; c++) {
        if (!mask_has_card(dead_cards, c)) {
            deck.push_back(c);
        }
    }
    return deck;
}

double EquityCalculator::calculate_equity(
    const HoleCards& hero,
    const HoleCards& villain,
    const Board& board,
    int board_size,
    int num_simulations
) {
    // 构建死牌掩码
    CardMask dead = 0;
    dead = add_card_to_mask(dead, hero[0]);
    dead = add_card_to_mask(dead, hero[1]);
    dead = add_card_to_mask(dead, villain[0]);
    dead = add_card_to_mask(dead, villain[1]);
    for (int i = 0; i < board_size; i++) {
        dead = add_card_to_mask(dead, board[i]);
    }
    
    // 检查是否有重复的牌
    int dead_count = __builtin_popcountll(dead);
    if (dead_count != 4 + board_size) {
        return 0.5;  // 有冲突，返回 50%
    }
    
    int cards_needed = 5 - board_size;
    
    if (cards_needed <= 0) {
        // Board 已完整，直接比较
        HandRank hero_rank = evaluator_.evaluate(hero, board, board_size);
        HandRank villain_rank = evaluator_.evaluate(villain, board, board_size);
        
        if (hero_rank > villain_rank) return 1.0;
        if (hero_rank < villain_rank) return 0.0;
        return 0.5;
    }
    
    // Monte Carlo 模拟
    std::vector<CardInt> deck = make_deck(dead);
    int deck_size = static_cast<int>(deck.size());
    
    // 使用 thread_local RNG，线程安全
    std::mt19937_64& rng = get_thread_local_rng();
    
    int wins = 0;
    int ties = 0;
    
    for (int sim = 0; sim < num_simulations; sim++) {
        // Fisher-Yates shuffle 取前 cards_needed 张
        for (int i = 0; i < cards_needed; i++) {
            std::uniform_int_distribution<int> dist(i, deck_size - 1);
            int j = dist(rng);
            std::swap(deck[i], deck[j]);
        }
        
        // 构建完整 board
        Board full_board = board;
        for (int i = 0; i < cards_needed; i++) {
            full_board[board_size + i] = deck[i];
        }
        
        // 评估
        HandRank hero_rank = evaluator_.evaluate(hero, full_board, 5);
        HandRank villain_rank = evaluator_.evaluate(villain, full_board, 5);
        
        if (hero_rank > villain_rank) {
            wins++;
        } else if (hero_rank == villain_rank) {
            ties++;
        }
    }
    
    return (wins + ties * 0.5) / num_simulations;
}

std::vector<double> EquityCalculator::calculate_equity_batch(
    const std::vector<HoleCards>& hero_hands,
    const std::vector<HoleCards>& villain_hands,
    const std::vector<double>& villain_weights,
    const Board& board,
    int board_size,
    int num_simulations
) {
    std::vector<double> results(hero_hands.size(), 0.0);
    
    // 为每个 hero hand 计算 equity
    // 使用 thread_local RNG，线程安全
    #pragma omp parallel for schedule(dynamic)
    for (size_t h = 0; h < hero_hands.size(); h++) {
        const HoleCards& hero = hero_hands[h];
        
        double total_equity = 0.0;
        double total_weight = 0.0;
        
        // 对所有 villain hands 加权平均
        for (size_t v = 0; v < villain_hands.size(); v++) {
            const HoleCards& villain = villain_hands[v];
            double weight = villain_weights[v];
            
            // 检查是否有冲突
            if (hero[0] == villain[0] || hero[0] == villain[1] ||
                hero[1] == villain[0] || hero[1] == villain[1]) {
                continue;
            }
            
            // 使用本地 calculator 避免线程冲突
            double eq = calculate_equity(hero, villain, board, board_size, 
                                        num_simulations / static_cast<int>(villain_hands.size()));
            total_equity += eq * weight;
            total_weight += weight;
        }
        
        if (total_weight > 0) {
            results[h] = total_equity / total_weight;
        } else {
            results[h] = 0.5;
        }
    }
    
    return results;
}

// ============================================================================
// 全局单例
// ============================================================================

HandEvaluator& get_hand_evaluator() {
    static HandEvaluator instance;
    return instance;
}

EquityCalculator& get_equity_calculator() {
    static EquityCalculator instance;
    return instance;
}

}  // namespace poker

