#include "cfr_engine.h"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <numeric>
#include <cstdio>
#include <iomanip>
#include <sstream>
#include <fstream>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace py = pybind11;

namespace poker {

// ============================================================================
// Action 辅助方法
// ============================================================================
std::string Action::to_string() const {
    switch (type) {
        case ActionType::FOLD: return "fold";
        case ActionType::CHECK: return "check";
        case ActionType::CALL: return "call (" + std::to_string((int)size) + ")";
        case ActionType::BET: return "bet " + std::to_string((int)size);
        case ActionType::RAISE: return "raise " + std::to_string((int)size);
        case ActionType::ALLIN: return "allin (" + std::to_string((int)size) + ")";
        default: return "unknown";
    }
}

CppCFREngine::CppCFREngine(const CFRConfig& config)
    : config_(config), rng_(std::random_device{}()) {
#ifdef _OPENMP
    if (config_.num_threads > 0) omp_set_num_threads(config_.num_threads);
#endif
    // 初始化锁池
    node_mutexes_ = std::vector<std::mutex>(NUM_MUTEXES);
}

CppCFREngine::~CppCFREngine() = default;

void CppCFREngine::build_tree(const BettingConfig& config, const std::vector<CardInt>& board) {
    GameTreeBuilder builder(config);
    pool_ = builder.build_tree(board);
    root_id_ = 0;
    
    size_t num_nodes = pool_->nodes->size();
    node_regrets_.assign(num_nodes, NodeRegrets{});

    // 调试日志：验证根节点动作
    if (num_nodes > 0) {
        const auto& root = (*pool_->nodes)[0];
        fprintf(stderr, "[CFR-CPP] Root Node Verified. Actions: %d, ChildStart: %d\n", (int)root.action_count, (int)root.child_start);
        for (int i = 0; i < root.action_count; i++) {
            fprintf(stderr, "  Action %d: %s\n", i, (*pool_->actions)[root.action_start + i].to_string().c_str());
        }
        fflush(stderr);
    }
}

void CppCFREngine::set_tree(const std::vector<CppNode>& nodes, int root_id) {
    pool_ = std::make_unique<TreeDataPool>();
    pool_->clear();
    for (const auto& n : nodes) pool_->nodes->push_back(n);
    root_id_ = root_id;
    
    size_t num_nodes = pool_->nodes->size();
    node_regrets_.assign(num_nodes, NodeRegrets{});
}

void CppCFREngine::set_oop_range(const std::vector<Combo>& combos) {
    oop_combos_ = combos;
}

void CppCFREngine::set_ip_range(const std::vector<Combo>& combos) {
    ip_combos_ = combos;
}

void CppCFREngine::set_board(const std::vector<CardInt>& board) {
    initial_board_ = board;
    initial_board_mask_ = 0;
    for (CardInt c : board) initial_board_mask_ = add_card_to_mask(initial_board_mask_, c);
    river_ranks_precomputed_ = false;
}

void CppCFREngine::precompute_river_ranks() {
    if (initial_board_.size() != 5 || river_ranks_precomputed_) return;
    fprintf(stderr, "[CFR-CPP] Precomputing River ranks...\n"); fflush(stderr);
    HandEvaluator eval;
    Board b_arr;
    for (int i = 0; i < 5; i++) b_arr[i] = initial_board_[i];
    auto precalc = [&](const std::vector<Combo>& combos, std::vector<HandRank>& ranks) {
        ranks.assign(combos.size(), 0);
        #pragma omp parallel for if(config_.use_parallel)
        for (size_t i = 0; i < combos.size(); i++) ranks[i] = eval.evaluate(combos[i].cards, b_arr, 5);
    };
    precalc(oop_combos_, oop_river_ranks_);
    precalc(ip_combos_, ip_river_ranks_);
    river_ranks_precomputed_ = true;
}

void CppCFREngine::solve(int iterations, std::function<void(int, int)> progress_callback) {
    fprintf(stderr, "[CFR-CPP] Starting solve with %d iterations (No Buckets, Sample: %d)\n", 
            iterations, config_.base_sample_size); 
    fflush(stderr);
    max_iterations_ = iterations;
    iteration_regrets_.clear();
    iteration_regrets_.reserve(iterations);
    should_stop_ = false;
    precompute_river_ranks();

    for (int t = 1; t <= iterations && !should_stop_; t++) {
        run_iteration(t);
        if (t % 2 == 0) apply_discount(t);
        if (progress_callback && (t % 10 == 0 || t == iterations)) {
            progress_callback(t, iterations);
        }
        if (t % 50 == 0 || t == 1) {
            fprintf(stderr, "[CFR-CPP] Iter %d/%d, Exploitability: %.4f\n", t, iterations, get_average_regret());
            fflush(stderr);
        }
    }
    fprintf(stderr, "[CFR-CPP] Solve finished\n"); fflush(stderr);
}

void CppCFREngine::run_iteration(int iteration) {
    for (int p = 0; p < 2; p++) {
        const auto& my_combos = (p == 0) ? oop_combos_ : ip_combos_;
        const auto& opp_combos = (p == 0) ? ip_combos_ : oop_combos_;
        #pragma omp parallel for if(config_.use_parallel)
        for (int i = 0; i < config_.base_sample_size; i++) {
            thread_local std::mt19937_64 local_rng(std::random_device{}());
            size_t my_idx = std::uniform_int_distribution<size_t>(0, my_combos.size() - 1)(local_rng);
            size_t opp_idx = std::uniform_int_distribution<size_t>(0, opp_combos.size() - 1)(local_rng);
            const Combo& my_c = my_combos[my_idx];
            const Combo& opp_c = opp_combos[opp_idx];
            if (cards_conflict(my_c.cards, opp_c.cards) || 
                cards_conflict(my_c.cards, initial_board_.data(), (int)initial_board_.size()) || 
                cards_conflict(opp_c.cards, initial_board_.data(), (int)initial_board_.size())) continue;
            
            cfr_traverse(root_id_, p, (int)my_idx, (int)opp_idx, 1.0f, iteration);
        }
    }
    
    // 根节点悔恨值计算
    float total_max_regret = 0.0f;
    int hands_counted = 0;
    
    std::lock_guard<std::mutex> lock(get_node_mutex(root_id_));
    if (root_id_ < (int)node_regrets_.size() && !node_regrets_[root_id_].regrets.empty()) {
        for (auto const& [idx, r] : node_regrets_[root_id_].regrets) {
            float max_r = 0.0f;
            for (float val : r) if (val > max_r) max_r = val;
            total_max_regret += max_r;
            hands_counted++;
        }
    }
    
    float samples_so_far = (float)iteration * config_.base_sample_size;
    iteration_regrets_.push_back(hands_counted > 0 ? (total_max_regret / hands_counted) / samples_so_far : 0.0f);
}

float CppCFREngine::cfr_traverse(int node_id, int player, int my_idx, int opp_idx, float reach_prob, int iteration) {
    if (node_id < 0) return 0.0f;
    const CppNode& node = (*pool_->nodes)[node_id];
    if (node.is_terminal()) return terminal_ev(node, player, my_idx, opp_idx);
    if (node.is_chance()) return chance_node_cfr(node, player, my_idx, opp_idx, reach_prob, iteration);
    if (node.player == player) return player_node_cfr(node, player, my_idx, opp_idx, reach_prob, iteration);
    else return opponent_node_cfr(node, player, my_idx, opp_idx, reach_prob, iteration);
}

float CppCFREngine::player_node_cfr(const CppNode& node, int player, int my_idx, int opp_idx, float reach_prob, int iteration) {
    std::vector<float> strategy = get_current_strategy(node.node_id, player, my_idx, iteration);
    std::vector<float> action_utils(node.action_count, 0.0f);
    float node_util = 0.0f;
    
    for (uint8_t a = 0; a < node.action_count; a++) {
        int child_id = (*pool_->child_ids)[node.child_start + a];
        action_utils[a] = cfr_traverse(child_id, player, my_idx, opp_idx, reach_prob, iteration);
        node_util += strategy[a] * action_utils[a];
    }
    
    {
        std::lock_guard<std::mutex> lock(get_node_mutex(node.node_id));
        NodeRegrets& nr = node_regrets_[node.node_id];
        auto& regrets = nr.regrets[my_idx];
        auto& cum_strat = nr.cumulative_strategy[my_idx];
        if (regrets.size() < node.action_count) regrets.assign(node.action_count, 0.0f);
        if (cum_strat.size() < node.action_count) cum_strat.assign(node.action_count, 0.0f);
        for (uint8_t a = 0; a < node.action_count; a++) {
            regrets[a] += action_utils[a] - node_util;
            // 修正：在外部采样 MCCFR 中，平均策略只需累加当前采样策略
            cum_strat[a] += strategy[a];
        }
    }
    return node_util;
}

float CppCFREngine::opponent_node_cfr(const CppNode& node, int player, int my_idx, int opp_idx, float reach_prob, int iteration) {
    std::vector<float> strategy = get_current_strategy(node.node_id, 1 - player, opp_idx, iteration);
    thread_local std::mt19937_64 local_rng(std::random_device{}());
    std::discrete_distribution<int> dist(strategy.begin(), strategy.end());
    int a = dist(local_rng);
    int child_id = (*pool_->child_ids)[node.child_start + a];
    return cfr_traverse(child_id, player, my_idx, opp_idx, reach_prob, iteration);
}

float CppCFREngine::chance_node_cfr(const CppNode& node, int player, int my_idx, int opp_idx, float reach_prob, int iteration) {
    const Combo& my_c = (player == 0) ? oop_combos_[my_idx] : ip_combos_[my_idx];
    const Combo& opp_c = (player == 0) ? ip_combos_[opp_idx] : oop_combos_[opp_idx];
    
    thread_local std::mt19937_64 local_rng(std::random_device{}());
    std::vector<int> valid;
    for (uint16_t i = 0; i < node.chance_count; i++) {
        CardInt c = (*pool_->chance_cards)[node.chance_card_start + i];
        if (!cards_conflict(c, my_c.cards) && !cards_conflict(c, opp_c.cards))
            valid.push_back(i);
    }
    if (valid.empty()) return 0.0f;
    int idx = valid[std::uniform_int_distribution<int>(0, (int)valid.size()-1)(local_rng)];
    int child_id = (*pool_->child_ids)[node.chance_child_start + idx];
    return cfr_traverse(child_id, player, my_idx, opp_idx, reach_prob, iteration);
}

float CppCFREngine::terminal_ev(const CppNode& node, int player, int my_idx, int opp_idx) {
    float initial_stack = (*pool_->nodes)[root_id_].stacks[player];
    if (node.pot < 0.01f) return node.stacks[player] - initial_stack;
    
    const Combo& my_c = (player == 0) ? oop_combos_[my_idx] : ip_combos_[my_idx];
    const Combo& opp_c = (player == 0) ? ip_combos_[opp_idx] : oop_combos_[opp_idx];
    
    float equity = 0.5f;
    HandEvaluator eval;
    Board b_arr;
    for (int i = 0; i < node.board_len && i < 5; i++) b_arr[i] = node.board[i];
    
    if (node.board_len == 5) {
        HandRank r1 = eval.evaluate(my_c.cards, b_arr, 5);
        HandRank r2 = eval.evaluate(opp_c.cards, b_arr, 5);
        if (r1 > r2) equity = 1.0f; else if (r1 < r2) equity = 0.0f;
    } else {
        EquityCalculator calc;
        equity = (float)calc.calculate_equity(my_c.cards, opp_c.cards, b_arr, (int)node.board_len, 50);
    }
    return equity * node.pot - (initial_stack - node.stacks[player]);
}

std::vector<float> CppCFREngine::get_current_strategy(int node_id, int player, int combo_idx, int iteration) const {
    const CppNode& node = (*pool_->nodes)[node_id];
    std::vector<float> strategy(node.action_count, 0.0f);
    float sum = 0.0f;
    
    {
        std::lock_guard<std::mutex> lock(get_node_mutex(node_id));
        if (node_id < (int)node_regrets_.size()) {
            auto const& nr = node_regrets_[node_id];
            auto it = nr.regrets.find(combo_idx);
            if (it != nr.regrets.end()) {
                for (uint8_t a = 0; a < node.action_count; a++) {
                    strategy[a] = std::max(0.0f, it->second[a]);
                    sum += strategy[a];
                }
            }
        }
    }
    
    if (sum > 0) for (float& s : strategy) s /= sum;
    else std::fill(strategy.begin(), strategy.end(), 1.0f / (float)node.action_count);
    return strategy;
}

void CppCFREngine::apply_discount(int iteration) {
    float d = std::pow((float)iteration, config_.alpha) / (std::pow((float)iteration, config_.alpha) + 1.0f);
    float dc = std::pow((float)iteration, config_.gamma) / (std::pow((float)iteration, config_.gamma) + 1.0f);
    
    for (auto& nr : node_regrets_) {
        for (auto& [idx, r] : nr.regrets) {
            for (float& val : r) if (val < 0) val *= 0.5f; else val *= d;
        }
        for (auto& [idx, c] : nr.cumulative_strategy) {
            for (float& val : c) val *= dc;
        }
    }
}

float CppCFREngine::get_average_regret() const {
    if (iteration_regrets_.empty()) return 0.0f;
    return iteration_regrets_.back();
}

bool CppCFREngine::cards_conflict(const HoleCards& h1, const HoleCards& h2) const {
    return h1[0] == h2[0] || h1[0] == h2[1] || h1[1] == h2[0] || h1[1] == h2[1];
}
bool CppCFREngine::cards_conflict(const HoleCards& hole, const CardInt* board, int board_len) const {
    for (int i=0; i<board_len; i++) if (board[i] == hole[0] || board[i] == hole[1]) return true;
    return false;
}
bool CppCFREngine::cards_conflict(CardInt card, const HoleCards& hole) const {
    return card == hole[0] || card == hole[1];
}
void CppCFREngine::stop() { should_stop_ = true; }

std::string CppCFREngine::card_to_string(CardInt c) const {
    const char* ranks = "23456789TJQKA";
    const char* suits = "cdhs";
    std::string s = "";
    s += ranks[card_rank(c)];
    s += suits[card_suit(c)];
    return s;
}

void CppCFREngine::dump_tree_to_file(const std::string& filepath) const {
    // 暂未实现完整导出，保留占位
}

std::unordered_map<int, std::vector<float>> CppCFREngine::get_node_strategies() const {
    std::unordered_map<int, std::vector<float>> res;
    return res;
}

std::unordered_map<std::string, std::vector<float>> CppCFREngine::get_node_hand_strategies(int node_id) const {
    std::unordered_map<std::string, std::vector<float>> res;
    if (node_id < 0 || node_id >= (int)pool_->nodes->size()) return res;
    
    std::lock_guard<std::mutex> lock(get_node_mutex(node_id));
    if (node_id >= (int)node_regrets_.size()) return res;
    
    const auto& nr = node_regrets_[node_id];
    const auto& node = (*pool_->nodes)[node_id];
    const auto& combos = (node.player == 0) ? oop_combos_ : ip_combos_;

    for (auto const& [idx, c] : nr.cumulative_strategy) {
        if (idx >= 0 && idx < (int)combos.size()) {
            const std::string& hand = combos[idx].hand_str;
            if (res.find(hand) == res.end()) {
                res[hand] = c;
            } else {
                // 对相同 shorthand 的不同花色组合进行累加
                for (size_t a = 0; a < c.size(); a++) {
                    res[hand][a] += c[a];
                }
            }
        }
    }
    return res;
}

std::unordered_map<std::string, py::object> CppCFREngine::get_node_data(int node_id) const {
    // fprintf(stderr, "[CFR-CPP] get_node_data for id=%d\n", node_id); fflush(stderr);
    std::unordered_map<std::string, py::object> data;
    if (!pool_ || node_id < 0 || (size_t)node_id >= pool_->nodes->size()) {
        fprintf(stderr, "[CFR-CPP] ERROR: get_node_data invalid id=%d\n", node_id); fflush(stderr);
        return data;
    }
    
    const auto& node = (*pool_->nodes)[node_id];
    
    data["id"] = py::cast(node.node_id);
    data["player"] = py::cast((int)node.player);
    data["street"] = py::cast((int)node.street);
    data["pot"] = py::cast(node.pot);
    data["stacks"] = py::cast(std::vector<float>{node.stacks[0], node.stacks[1]});
    data["to_call"] = py::cast(node.to_call);
    
    std::string type_str = "player";
    if (node.is_terminal()) type_str = "terminal";
    else if (node.is_chance()) type_str = "chance";
    data["type"] = py::cast(type_str);
    
    // Actions
    std::vector<std::string> action_strs;
    std::vector<int> child_ids;
    for (uint8_t i = 0; i < node.action_count; i++) {
        size_t action_idx = node.action_start + i;
        size_t child_idx = node.child_start + i;
        if (action_idx < pool_->actions->size()) {
            action_strs.push_back((*pool_->actions)[action_idx].to_string());
        }
        if (child_idx < pool_->child_ids->size()) {
            child_ids.push_back((*pool_->child_ids)[child_idx]);
        }
    }
    data["actions"] = py::cast(action_strs);
    data["child_ids"] = py::cast(child_ids);
    
    // Board
    std::vector<std::pair<int, int>> board;
    for (uint8_t i = 0; i < node.board_len; i++) {
        board.push_back({card_rank(node.board[i]), card_suit(node.board[i])});
    }
    data["board"] = py::cast(board);
    
    // Chance data
    if (node.is_chance()) {
        std::vector<std::pair<int, int>> chance_cards;
        std::vector<int> chance_child_ids;
        for (uint16_t i = 0; i < node.chance_count; i++) {
            size_t c_idx = node.chance_card_start + i;
            size_t cc_idx = node.chance_child_start + i;
            if (c_idx < pool_->chance_cards->size()) {
                CardInt c = (*pool_->chance_cards)[c_idx];
                chance_cards.push_back({card_rank(c), card_suit(c)});
            }
            if (cc_idx < pool_->child_ids->size()) {
                chance_child_ids.push_back((*pool_->child_ids)[cc_idx]);
            }
        }
        data["chance_cards"] = py::cast(chance_cards);
        data["chance_child_ids"] = py::cast(chance_child_ids);
    }
    
    return data;
}

} // namespace poker
