#pragma once

#include "types.h"
#include <random>

namespace poker {

// ============================================================================
// Hand Evaluator
// ============================================================================

class HandEvaluator {
public:
    HandEvaluator();
    
    // 评估 5 张牌的牌型
    HandRank evaluate_five(const CardInt cards[5]) const;
    
    // 评估 7 张牌的最佳 5 张组合
    HandRank evaluate_seven(const CardInt cards[7]) const;
    
    // 评估 hole cards + board
    HandRank evaluate(const HoleCards& hole, const Board& board, int board_size) const;

private:
    // 内部辅助函数
    HandRank evaluate_five_internal(CardInt c0, CardInt c1, CardInt c2, 
                                     CardInt c3, CardInt c4) const;
};

// ============================================================================
// Equity Calculator
// ============================================================================

class EquityCalculator {
public:
    EquityCalculator();
    
    // 计算 hero vs villain 的 equity
    // 返回值: hero 的胜率 (0.0 - 1.0)
    double calculate_equity(
        const HoleCards& hero,
        const HoleCards& villain,
        const Board& board,
        int board_size,
        int num_simulations = 10000
    );
    
    // 批量计算 equity（用于 CFR）
    // hero_hands: hero 的所有可能手牌
    // villain_hands: villain 的所有可能手牌
    // 返回: hero_hands.size() 的 equity 数组
    std::vector<double> calculate_equity_batch(
        const std::vector<HoleCards>& hero_hands,
        const std::vector<HoleCards>& villain_hands,
        const std::vector<double>& villain_weights,
        const Board& board,
        int board_size,
        int num_simulations = 1000
    );
    
    // 设置随机种子（用于测试）
    void set_seed(uint64_t seed);

private:
    HandEvaluator evaluator_;
    std::mt19937_64 rng_;
    
    // 预生成的剩余牌堆
    std::vector<CardInt> make_deck(CardMask dead_cards) const;
};

// ============================================================================
// 全局单例（可选）
// ============================================================================

HandEvaluator& get_hand_evaluator();
EquityCalculator& get_equity_calculator();

}  // namespace poker


