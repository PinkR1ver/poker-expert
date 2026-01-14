#pragma once
#include "cfr_types.h"
#include "mmap_buffer.h"
#include <vector>
#include <string>
#include <memory>
#include <atomic>
#include <map>

namespace poker {

// 全局池：使用 MmapBuffer 存储所有动态生成的树数据，支持用硬盘换内存
struct TreeDataPool {
    std::unique_ptr<MmapBuffer<CppNode>> nodes;
    std::unique_ptr<MmapBuffer<Action>> actions;
    std::unique_ptr<MmapBuffer<int32_t>> child_ids;
    std::unique_ptr<MmapBuffer<CardInt>> chance_cards;
    
    TreeDataPool() {
        // 大幅提升上限：5000 万节点，1 亿个动作和子节点 ID
        // 由于是 sparse files，只有真正写入的部分才会占用硬盘
        nodes = std::make_unique<MmapBuffer<CppNode>>("tmp/nodes.bin", 50000000);
        actions = std::make_unique<MmapBuffer<Action>>("tmp/actions.bin", 100000000);
        child_ids = std::make_unique<MmapBuffer<int32_t>>("tmp/child_ids.bin", 100000000);
        chance_cards = std::make_unique<MmapBuffer<CardInt>>("tmp/chance_cards.bin", 10000000);
    }
    
    void clear() {
        nodes->clear();
        actions->clear();
        child_ids->clear();
        chance_cards->clear();
    }
};

struct BettingConfig {
    float initial_pot;
    float oop_stack;
    float ip_stack;
    std::vector<float> flop_bet_sizes;   
    std::vector<float> turn_bet_sizes;
    std::vector<float> river_bet_sizes;
    std::vector<float> flop_raise_sizes;
    std::vector<float> turn_raise_sizes;
    std::vector<float> river_raise_sizes;
    int max_raises = 3;
};

class GameTreeBuilder {
public:
    GameTreeBuilder(const BettingConfig& config);
    
    std::unique_ptr<TreeDataPool> build_tree(
        const std::vector<CardInt>& board
    );

private:
    BettingConfig config_;
    std::unique_ptr<TreeDataPool> pool_;
    
    // 节点去重表：StateKey -> NodeID
    std::map<std::string, int> transposition_table_;
    
    std::string get_state_key(float oop_s, float ip_s, float pot, int player, Street street, const std::vector<CardInt>& board, float current_bet, float actor_invested, int raise_count, bool is_all_in);

    int build_recursive(
        float oop_stack,
        float ip_stack,
        float pot,
        int player,
        Street street,
        const std::vector<CardInt>& board,
        int raise_count,
        float current_bet,
        float actor_invested,
        bool is_all_in
    );

    int write_node_to_pool(
        const std::string& key,
        int player,
        Street street,
        float pot,
        float oop_stack,
        float ip_stack,
        float to_call,
        const std::vector<Action>& actions,
        const std::vector<int>& child_ids,
        const std::vector<CardInt>& board
    );

    int add_chance_node_recursive(float oop_s, float ip_s, float pot, Street next_street, const std::vector<CardInt>& board);
};

} // namespace poker
