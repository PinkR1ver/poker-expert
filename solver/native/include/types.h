#pragma once

#include <vector>
#include <array>
#include <string>
#include <unordered_map>
#include <cstdint>

namespace poker {

// ============================================================================
// Card 表示
// ============================================================================

// Card 使用 0-51 的整数表示
// card = rank * 4 + suit
// rank: 0-12 (2-A)
// suit: 0-3 (c, d, h, s)
using CardInt = uint8_t;

constexpr CardInt CARD_NONE = 255;

inline constexpr CardInt make_card(int rank, int suit) {
    return static_cast<CardInt>(rank * 4 + suit);
}

inline constexpr int card_rank(CardInt card) {
    return card / 4;
}

inline constexpr int card_suit(CardInt card) {
    return card % 4;
}

inline std::string card_to_string(CardInt card) {
    static const char* ranks = "23456789TJQKA";
    static const char* suits = "cdhs";
    if (card >= 52) return "??";
    return std::string(1, ranks[card_rank(card)]) + suits[card_suit(card)];
}

// ============================================================================
// Hand Rank 表示
// ============================================================================

// 手牌强度使用单个 32 位整数表示，方便比较
// 高 4 位: 牌型 (1-9)
// 低 28 位: tiebreakers
using HandRank = uint32_t;

constexpr int RANK_HIGH_CARD = 1;
constexpr int RANK_ONE_PAIR = 2;
constexpr int RANK_TWO_PAIR = 3;
constexpr int RANK_THREE_OF_A_KIND = 4;
constexpr int RANK_STRAIGHT = 5;
constexpr int RANK_FLUSH = 6;
constexpr int RANK_FULL_HOUSE = 7;
constexpr int RANK_FOUR_OF_A_KIND = 8;
constexpr int RANK_STRAIGHT_FLUSH = 9;

inline constexpr HandRank make_hand_rank(int rank_type, int tb1 = 0, int tb2 = 0, 
                                          int tb3 = 0, int tb4 = 0, int tb5 = 0) {
    // 每个 tiebreaker 用 4 bits (0-15 足够表示 rank 0-12)
    return (static_cast<uint32_t>(rank_type) << 28) |
           (static_cast<uint32_t>(tb1 & 0xF) << 20) |
           (static_cast<uint32_t>(tb2 & 0xF) << 16) |
           (static_cast<uint32_t>(tb3 & 0xF) << 12) |
           (static_cast<uint32_t>(tb4 & 0xF) << 8) |
           (static_cast<uint32_t>(tb5 & 0xF) << 4);
}

inline int get_rank_type(HandRank rank) {
    return static_cast<int>(rank >> 28);
}

// ============================================================================
// Board 和 Combo 表示
// ============================================================================

// 最多 5 张公共牌
using Board = std::array<CardInt, 5>;

// 手牌 = 2 张牌
using HoleCards = std::array<CardInt, 2>;

// ============================================================================
// 用于快速查找的位图
// ============================================================================

// 52 位牌的位图
using CardMask = uint64_t;

inline constexpr CardMask card_to_mask(CardInt card) {
    return 1ULL << card;
}

inline constexpr bool mask_has_card(CardMask mask, CardInt card) {
    return (mask & (1ULL << card)) != 0;
}

inline constexpr CardMask add_card_to_mask(CardMask mask, CardInt card) {
    return mask | (1ULL << card);
}

// ============================================================================
// 预计算表（在 hand_evaluator.cpp 中初始化）
// ============================================================================

// 5 张牌 -> HandRank 的查找表（用于加速）
// 使用完美哈希或压缩表示

}  // namespace poker


