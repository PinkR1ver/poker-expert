#pragma once

#include "types.h"
#include <vector>
#include <array>
#include <string>
#include <unordered_map>
#include <cstdint>
#include <memory>

namespace poker {

// ============================================================================
// Action & NodeType
// ============================================================================

enum class ActionType : uint8_t {
    FOLD = 0, CHECK = 1, CALL = 2, BET = 3, RAISE = 4, ALLIN = 5
};

struct Action {
    ActionType type;
    float size; // 使用 size 保持与 Python 一致
    
    std::string to_string() const;
};

enum class NodeType : uint8_t {
    PLAYER = 0, CHANCE = 1, TERMINAL = 2
};

enum class Street : uint8_t {
    FLOP = 0, TURN = 1, RIVER = 2
};

// ============================================================================
// 扁平化 CppNode (POD 类型，适合磁盘映射)
// ============================================================================

struct CppNode {
    int32_t node_id;
    int32_t bucket_id;
    NodeType type;
    int8_t player;  // 0=OOP, 1=IP, -1=chance
    uint8_t street;
    float pot;
    float stacks[2];
    float to_call;
    
    // 动态数据的偏移量（指向全局大数组）
    uint32_t action_start;
    uint8_t action_count;
    uint32_t child_start;
    
    // Chance 专用偏移量
    uint32_t chance_card_start;
    uint16_t chance_count;
    uint32_t chance_child_start;

    // 固定大小的牌面
    CardInt board[5];
    uint8_t board_len;

    bool is_terminal() const { return type == NodeType::TERMINAL; }
    bool is_chance() const { return type == NodeType::CHANCE; }
    bool is_player() const { return type == NodeType::PLAYER; }
};

// ============================================================================
// Combo & Regrets
// ============================================================================

struct Combo {
    HoleCards cards;
    float weight;
    std::string hand_str;
};

// NodeRegrets 现在也需要扁平化以节省内存
struct NodeRegrets {
    // 键改为 combo_idx (int) 以节省内存和提升速度
    // 之前使用 std::string 极其昂贵
    std::unordered_map<int, std::vector<float>> regrets;
    std::unordered_map<int, std::vector<float>> cumulative_strategy;
};

struct CFRConfig {
    float alpha = 1.5f;
    float beta = 0.0f;
    float gamma = 2.0f;
    int base_sample_size = 64; // 提升采样率
    bool use_parallel = true;
    int num_threads = 0;
};

} // namespace poker
