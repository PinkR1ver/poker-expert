#include "game_tree_builder.h"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <iomanip>
#include <sstream>

namespace poker {

GameTreeBuilder::GameTreeBuilder(const BettingConfig& config) : config_(config) {}

std::string GameTreeBuilder::get_state_key(float oop_s, float ip_s, float pot, int player, Street street, const std::vector<CardInt>& board, float current_bet, float actor_invested, int raise_count, bool is_all_in) {
    std::stringstream ss;
    float to_call = current_bet - actor_invested;
    // 显式包含所有关键博弈维度，防止去重冲突
    ss << std::fixed << std::setprecision(2)
       << oop_s << "|" << ip_s << "|" << pot << "|" << player << "|" 
       << (int)street << "|" << to_call << "|" << raise_count << "|" << (int)is_all_in;
    for(auto c : board) ss << "," << (int)c;
    return ss.str();
}

std::unique_ptr<TreeDataPool> GameTreeBuilder::build_tree(const std::vector<CardInt>& board) {
    pool_ = std::make_unique<TreeDataPool>();
    pool_->clear();
    transposition_table_.clear();

    std::cout << "[CFR-CPP] Building Tree (Perfect Deduplication, No Abstraction)..." << std::endl;

    // 预留 0 号位
    CppNode dummy; dummy.node_id = 0;
    pool_->nodes->push_back(dummy);

    Street initial_street;
    if (board.size() == 3) initial_street = Street::FLOP;
    else if (board.size() == 4) initial_street = Street::TURN;
    else initial_street = Street::RIVER;

    int real_root_id = build_recursive(
        config_.oop_stack, config_.ip_stack, config_.initial_pot,
        0, initial_street, board, 0, 0, 0, false
    );

    if (real_root_id != 0) {
        CppNode root_data = (*pool_->nodes)[real_root_id];
        root_data.node_id = 0;
        (*pool_->nodes)[0] = root_data;
    }

    std::cout << "[CFR-CPP] Build Finished. Nodes: " << pool_->nodes->size() 
              << ", Actions: " << pool_->actions->size() << std::endl;
    
    return std::move(pool_);
}

int GameTreeBuilder::write_node_to_pool(
    const std::string& key, int player, Street street, float pot,
    float oop_stack, float ip_stack, float to_call,
    const std::vector<Action>& actions, const std::vector<int>& child_ids,
    const std::vector<CardInt>& board
) {
    int current_id = (int)pool_->nodes->size();
    CppNode node;
    node.node_id = current_id;
    node.player = (int8_t)player;
    node.street = (uint8_t)street;
    node.pot = pot;
    node.stacks[0] = oop_stack;
    node.stacks[1] = ip_stack;
    node.to_call = std::max(0.0f, to_call);
    node.type = actions.empty() ? NodeType::TERMINAL : NodeType::PLAYER;
    node.board_len = (uint8_t)board.size();
    for(int i=0; i<node.board_len; i++) node.board[i] = board[i];
    node.bucket_id = -1;

    // 动作和子节点必须连续写入，且偏移量要在写入那一刻获取
    node.action_start = (uint32_t)pool_->actions->size();
    node.action_count = (uint8_t)actions.size();
    for (const auto& a : actions) pool_->actions->push_back(a);

    node.child_start = (uint32_t)pool_->child_ids->size();
    for (int id : child_ids) pool_->child_ids->push_back(id);

    node.chance_count = 0;
    node.chance_card_start = 0;
    node.chance_child_start = 0;

    pool_->nodes->push_back(node);
    transposition_table_[key] = current_id;
    return current_id;
}

int GameTreeBuilder::build_recursive(
    float oop_stack, float ip_stack, float pot, int player, Street street,
    const std::vector<CardInt>& board, int raise_count, float current_bet,
    float actor_invested, bool is_all_in
) {
    if (street > Street::RIVER) return -1; 

    auto key = get_state_key(oop_stack, ip_stack, pot, player, street, board, current_bet, actor_invested, raise_count, is_all_in);
    if (transposition_table_.count(key)) return transposition_table_[key];

    std::vector<Action> local_actions;
    std::vector<int> local_child_ids;
    float to_call = current_bet - actor_invested;

    // --- All-in 场景处理 ---
    // 如果是对方已经全下了，而我【还没跟注】（to_call > 0），必须允许我决策
    // 如果我已经跟注了全下（to_call == 0），且博弈没结束，自动发牌
    if (is_all_in && to_call < 0.01f) {
        if (street == Street::RIVER) {
            // River All-in 已跟注，博弈结束
            return write_node_to_pool(key, player, street, pot, oop_stack, ip_stack, to_call, {}, {}, board);
        } else {
            // Flop/Turn All-in 已跟注，自动发牌到下一条街
            int chance_id = add_chance_node_recursive(oop_stack, ip_stack, pot, (Street)((int)street + 1), board);
            local_actions.push_back({ActionType::CALL, 0}); // 占位
            local_child_ids.push_back(chance_id);
            return write_node_to_pool(key, player, street, pot, oop_stack, ip_stack, to_call, local_actions, local_child_ids, board);
        }
    }

    float actor_stack = (player == 0) ? oop_stack : ip_stack;

    // 1. Fold
    if (to_call > 0.1f) {
        local_actions.push_back({ActionType::FOLD, 0});
        int f_id = write_node_to_pool("TERM_FOLD_" + std::to_string(pool_->nodes->size()), player, street, 0, oop_stack, ip_stack, 0, {}, {}, board);
        local_child_ids.push_back(f_id);
    }

    // 2. Check / Call
    if (to_call < 0.1f) {
        local_actions.push_back({ActionType::CHECK, 0});
        if (player == 1) { // IP Check 结束街道
            if (street == Street::RIVER) {
                int t_id = write_node_to_pool("TERM_SD_" + std::to_string(pool_->nodes->size()), player, street, pot, oop_stack, ip_stack, 0, {}, {}, board);
                local_child_ids.push_back(t_id);
            } else {
                int chance_id = add_chance_node_recursive(oop_stack, ip_stack, pot, (Street)((int)street + 1), board);
                local_child_ids.push_back(chance_id);
            }
        } else { // OOP Check，轮到 IP
            int c_id = build_recursive(oop_stack, ip_stack, pot, 1, street, board, 0, 0, 0, false);
            local_child_ids.push_back(c_id);
        }
    } else {
        float call_amt = std::min(actor_stack, to_call);
        local_actions.push_back({ActionType::CALL, call_amt});
        float next_oop = (player == 0) ? oop_stack - call_amt : oop_stack;
        float next_ip = (player == 1) ? ip_stack - call_amt : ip_stack;
        float next_pot = pot + call_amt;
        bool next_is_all_in = (next_oop <= 0.01f || next_ip <= 0.01f);

        if (street == Street::RIVER || next_is_all_in) {
            if (street == Street::RIVER) {
                int t_id = write_node_to_pool("TERM_SD_" + std::to_string(pool_->nodes->size()), player, street, next_pot, next_oop, next_ip, 0, {}, {}, board);
                local_child_ids.push_back(t_id);
            } else {
                // All-in Call on Flop/Turn -> Move to next street
                int chance_id = add_chance_node_recursive(next_oop, next_ip, next_pot, (Street)((int)street + 1), board);
                local_child_ids.push_back(chance_id);
            }
        } else {
            // Normal Call ends street -> Chance node
            int chance_id = add_chance_node_recursive(next_oop, next_ip, next_pot, (Street)((int)street + 1), board);
            local_child_ids.push_back(chance_id);
        }
    }

    // 3. Bet / Raise
    if (raise_count < config_.max_raises && actor_stack > to_call + 0.01f) {
        bool is_bet = (to_call < 0.01f);
        const auto& sizes = is_bet ? 
            ((street == Street::FLOP) ? config_.flop_bet_sizes : (street == Street::TURN) ? config_.turn_bet_sizes : config_.river_bet_sizes) :
            ((street == Street::FLOP) ? config_.flop_raise_sizes : (street == Street::TURN) ? config_.turn_raise_sizes : config_.river_raise_sizes);
        
        for (float s : sizes) {
            float bet_val = is_bet ? std::floor(pot * s) : std::floor((pot + to_call) * s);
            if (bet_val < 1.0f) bet_val = 1.0f; 
            float invest = std::min(actor_stack, to_call + bet_val);
            if (invest <= to_call + 0.01f) continue;
            
            local_actions.push_back({is_bet ? ActionType::BET : ActionType::RAISE, invest});
            float n_oop = (player == 0) ? oop_stack - invest : oop_stack;
            float n_ip = (player == 1) ? ip_stack - invest : ip_stack;
            int c_id = build_recursive(n_oop, n_ip, pot + invest, 1 - player, street, board, raise_count + 1, invest, current_bet, invest >= actor_stack - 0.01f);
            local_child_ids.push_back(c_id);
        }
        if (actor_stack > to_call + 1.0f) {
            local_actions.push_back({ActionType::ALLIN, actor_stack});
            float n_oop = (player == 0) ? 0 : oop_stack;
            float n_ip = (player == 1) ? 0 : ip_stack;
            int c_id = build_recursive(n_oop, n_ip, pot + actor_stack, 1 - player, street, board, raise_count + 1, actor_stack, current_bet, true);
            local_child_ids.push_back(c_id);
        }
    }

    return write_node_to_pool(key, player, street, pot, oop_stack, ip_stack, to_call, local_actions, local_child_ids, board);
}

int GameTreeBuilder::add_chance_node_recursive(float oop_s, float ip_s, float pot, Street next_street, const std::vector<CardInt>& board) {
    std::vector<CardInt> chance_cards;
    std::vector<int> chance_child_ids;

    CardMask mask = 0; for (auto c : board) mask = add_card_to_mask(mask, c);

    // 1. 先递归生成所有子树
    for (int r = 0; r < 13; r++) {
        CardInt representative_card = CARD_NONE;
        bool has_available = false;
        for (int s = 0; s < 4; s++) {
            CardInt c = make_card(r, s);
            if (!mask_has_card(mask, c)) { representative_card = c; has_available = true; break; }
        }
        if (has_available) {
            chance_cards.push_back(representative_card);
            std::vector<CardInt> next_b = board; next_b.push_back(representative_card);
            // 这里会触发子树的 ID 分配和 pool 写入
            int child_id = build_recursive(oop_s, ip_s, pot, 0, next_street, next_b, 0, 0, 0, (oop_s < 0.01f || ip_s < 0.01f));
            chance_child_ids.push_back(child_id);
        }
    }

    // 2. 所有子树写入完毕后，创建 Chance Node 本身
    int chance_id = (int)pool_->nodes->size();
    CppNode c_node;
    c_node.node_id = chance_id;
    c_node.type = NodeType::CHANCE;
    c_node.pot = pot;
    c_node.stacks[0] = oop_s;
    c_node.stacks[1] = ip_s;
    c_node.street = (uint8_t)next_street;
    c_node.board_len = (uint8_t)board.size();
    for(int i=0; i<c_node.board_len; i++) c_node.board[i] = board[i];
    
    // 在写入前那一刻获取偏移量，确保物理连续且不被子树数据打断
    c_node.chance_card_start = (uint32_t)pool_->chance_cards->size();
    c_node.chance_count = (uint16_t)chance_cards.size();
    for (auto c : chance_cards) pool_->chance_cards->push_back(c);

    c_node.chance_child_start = (uint32_t)pool_->child_ids->size();
    // 这里不再使用 chance_count，因为 chance_child 的数量和 chance_card 严格对应
    for (int id : chance_child_ids) pool_->child_ids->push_back(id);

    c_node.action_count = 0;
    c_node.action_start = 0;
    c_node.child_start = 0;

    pool_->nodes->push_back(c_node);
    return chance_id;
}

} // namespace poker
