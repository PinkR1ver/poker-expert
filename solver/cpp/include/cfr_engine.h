#include "cfr_types.h"
#include "hand_evaluator.h"
#include "game_tree_builder.h"
#include <vector>
#include <unordered_map>
#include <random>
#include <functional>
#include <atomic>
#include <mutex>
#include <memory>

// 前向声明 pybind11
namespace pybind11 { class object; }

namespace poker {

class CppCFREngine {
public:
    CppCFREngine(const CFRConfig& config = CFRConfig{});
    ~CppCFREngine();
    
    void build_tree(const BettingConfig& config, const std::vector<CardInt>& board);
    void set_tree(const std::vector<CppNode>& nodes, int root_id);
    
    void set_oop_range(const std::vector<Combo>& combos);
    void set_ip_range(const std::vector<Combo>& combos);
    void set_board(const std::vector<CardInt>& board);
    
    void solve(int iterations, std::function<void(int, int)> progress_callback = nullptr);
    void stop();

    bool is_refining(int iteration) const {
        if (max_iterations_ <= 0) return false;
        return iteration > (int)(max_iterations_ * 0.8);
    }

    std::unordered_map<int, std::vector<float>> get_node_strategies() const;
    std::unordered_map<std::string, std::vector<float>> get_node_hand_strategies(int node_id) const;
    
    // 新增：获取节点详细数据（供 Python Proxy 使用）
    std::unordered_map<std::string, pybind11::object> get_node_data(int node_id) const;
    
    void dump_tree_to_file(const std::string& filepath) const;

    float get_average_regret() const;
    const std::vector<float>& get_regret_history() const { return iteration_regrets_; }
    
    int get_node_count() const { return pool_ ? static_cast<int>(pool_->nodes->size()) : 0; }
    int get_oop_combo_count() const { return static_cast<int>(oop_combos_.size()); }
    int get_ip_combo_count() const { return static_cast<int>(ip_combos_.size()); }

private:
    CFRConfig config_;
    std::unique_ptr<TreeDataPool> pool_;
    int root_id_ = 0;
    
    std::vector<Combo> oop_combos_;
    std::vector<Combo> ip_combos_;
    
    std::vector<CardInt> initial_board_;
    CardMask initial_board_mask_ = 0;
    
    mutable std::vector<NodeRegrets> node_regrets_;
    
    // 互斥锁池：减少锁的数量以节省内存
    static constexpr size_t NUM_MUTEXES = 2048;
    mutable std::vector<std::mutex> node_mutexes_;

    std::vector<float> iteration_regrets_;
    int max_iterations_ = 100;
    std::atomic<bool> should_stop_{false};
    std::mt19937_64 rng_;

    std::vector<HandRank> oop_river_ranks_;
    std::vector<HandRank> ip_river_ranks_;
    bool river_ranks_precomputed_ = false;

    void precompute_river_ranks();
    void run_iteration(int iteration);
    
    float cfr_traverse(int node_id, int player, int my_idx, int opp_idx, float reach_prob, int iteration);
    float player_node_cfr(const CppNode& node, int player, int my_idx, int opp_idx, float reach_prob, int iteration);
    float opponent_node_cfr(const CppNode& node, int player, int my_idx, int opp_idx, float reach_prob, int iteration);
    float chance_node_cfr(const CppNode& node, int player, int my_idx, int opp_idx, float reach_prob, int iteration);
    float terminal_ev(const CppNode& node, int player, int my_idx, int opp_idx);

    std::vector<float> get_current_strategy(int node_id, int player, int combo_idx, int iteration) const;
    void apply_discount(int iteration);
    
    bool cards_conflict(const HoleCards& h1, const HoleCards& h2) const;
    bool cards_conflict(const HoleCards& hole, const CardInt* board, int board_len) const;
    bool cards_conflict(CardInt card, const HoleCards& hole) const;

    std::mutex& get_node_mutex(int node_id) const { return node_mutexes_[static_cast<size_t>(node_id) % NUM_MUTEXES]; }
    
    std::string card_to_string(CardInt c) const;
};

} // namespace poker
