#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include <pybind11/functional.h>
#include <fstream>
#include <chrono>
#include "hand_evaluator.h"
#include "cfr_engine.h"
#include "game_tree_builder.h"

namespace py = pybind11;

// ============================================================================
// 辅助函数：Python 端 Card 转换
// ============================================================================

poker::CardInt py_card_to_cpp(int rank, int suit) {
    return poker::make_card(rank, suit);
}

poker::Board py_board_to_cpp(const std::vector<std::pair<int, int>>& py_board) {
    poker::Board board = {poker::CARD_NONE, poker::CARD_NONE, poker::CARD_NONE, 
                          poker::CARD_NONE, poker::CARD_NONE};
    for (size_t i = 0; i < py_board.size() && i < 5; i++) {
        board[i] = poker::make_card(py_board[i].first, py_board[i].second);
    }
    return board;
}

// ============================================================================
// Python 接口封装
// ============================================================================

std::pair<int, uint32_t> evaluate_hand(
    int h1_rank, int h1_suit,
    int h2_rank, int h2_suit,
    const std::vector<std::pair<int, int>>& board
) {
    poker::HoleCards hole = {
        poker::make_card(h1_rank, h1_suit),
        poker::make_card(h2_rank, h2_suit)
    };
    poker::Board cpp_board = py_board_to_cpp(board);
    int board_size = static_cast<int>(board.size());
    poker::HandRank rank = poker::get_hand_evaluator().evaluate(hole, cpp_board, board_size);
    return {poker::get_rank_type(rank), rank};
}

double calculate_equity(
    int h1_rank, int h1_suit,
    int h2_rank, int h2_suit,
    int v1_rank, int v1_suit,
    int v2_rank, int v2_suit,
    const std::vector<std::pair<int, int>>& board,
    int num_simulations = 10000
) {
    if (h1_rank < 0 || h1_rank > 12 || h2_rank < 0 || h2_rank > 12 ||
        v1_rank < 0 || v1_rank > 12 || v2_rank < 0 || v2_rank > 12) {
        fprintf(stderr, "[CFR-CPP] CRITICAL ERROR: Invalid rank in calculate_equity! h1=%d, h2=%d, v1=%d, v2=%d\n", 
                h1_rank, h2_rank, v1_rank, v2_rank);
        fflush(stderr);
        return 0.5;
    }
    
    // fprintf(stderr, "[CFR-CPP] calculate_equity start\n"); fflush(stderr);
    poker::HoleCards hero = {poker::make_card(h1_rank, h1_suit), poker::make_card(h2_rank, h2_suit)};
    poker::HoleCards villain = {poker::make_card(v1_rank, v1_suit), poker::make_card(v2_rank, v2_suit)};
    poker::Board cpp_board = py_board_to_cpp(board);
    int board_size = static_cast<int>(board.size());
    double res = poker::get_equity_calculator().calculate_equity(hero, villain, cpp_board, board_size, num_simulations);
    // fprintf(stderr, "[CFR-CPP] calculate_equity end: %.4f\n", res); fflush(stderr);
    return res;
}

// ============================================================================
// CFR Engine 封装类
// ============================================================================

class PyCFREngine {
public:
    PyCFREngine() : engine_(poker::CFRConfig{}) {}
    
    void build_tree_cpp(
        float pot,
        float oop_stack,
        float ip_stack,
        const std::vector<float>& flop_bet_sizes,
        const std::vector<float>& flop_raise_sizes,
        const std::vector<float>& turn_bet_sizes,
        const std::vector<float>& turn_raise_sizes,
        const std::vector<float>& river_bet_sizes,
        const std::vector<float>& river_raise_sizes,
        const std::vector<std::pair<int, int>>& initial_board,
        int max_raises = 3
    ) {
        poker::BettingConfig config;
        config.initial_pot = pot;
        config.oop_stack = oop_stack;
        config.ip_stack = ip_stack;
        config.flop_bet_sizes = flop_bet_sizes;
        config.flop_raise_sizes = flop_raise_sizes;
        config.turn_bet_sizes = turn_bet_sizes;
        config.turn_raise_sizes = turn_raise_sizes;
        config.river_bet_sizes = river_bet_sizes;
        config.river_raise_sizes = river_raise_sizes;
        config.max_raises = max_raises;

        std::vector<poker::CardInt> cpp_board;
        for (const auto& c : initial_board) {
            cpp_board.push_back(poker::make_card(c.first, c.second));
        }

        engine_.build_tree(config, cpp_board);
    }

    void set_oop_range(const std::vector<std::tuple<int, int, int, int, float, std::string>>& combos) {
        std::vector<poker::Combo> cpp_combos;
        for (const auto& c : combos) {
            poker::Combo combo;
            combo.cards[0] = poker::make_card(std::get<0>(c), std::get<1>(c));
            combo.cards[1] = poker::make_card(std::get<2>(c), std::get<3>(c));
            combo.weight = std::get<4>(c);
            combo.hand_str = std::get<5>(c);
            cpp_combos.push_back(combo);
        }
        engine_.set_oop_range(cpp_combos);
    }
    
    void set_ip_range(const std::vector<std::tuple<int, int, int, int, float, std::string>>& combos) {
        std::vector<poker::Combo> cpp_combos;
        for (const auto& c : combos) {
            poker::Combo combo;
            combo.cards[0] = poker::make_card(std::get<0>(c), std::get<1>(c));
            combo.cards[1] = poker::make_card(std::get<2>(c), std::get<3>(c));
            combo.weight = std::get<4>(c);
            combo.hand_str = std::get<5>(c);
            cpp_combos.push_back(combo);
        }
        engine_.set_ip_range(cpp_combos);
    }
    
    void set_board(const std::vector<std::pair<int, int>>& board) {
        std::vector<poker::CardInt> cpp_board;
        for (const auto& c : board) {
            cpp_board.push_back(poker::make_card(c.first, c.second));
        }
        engine_.set_board(cpp_board);
    }
    
    void solve(int iterations, py::object callback) {
        if (callback.is_none()) {
            py::gil_scoped_release release;
            engine_.solve(iterations, nullptr);
        } else {
            py::gil_scoped_release release;
            // 捕获方式改为按值捕获 [callback]，增加 refcount，更安全
            engine_.solve(iterations, [callback](int current, int total) {
                py::gil_scoped_acquire acquire;
                callback(current, total);
            });
        }
    }

    void dump_all_data(const std::string& filepath) const {
        engine_.dump_tree_to_file(filepath);
    }

    void stop() { engine_.stop(); }
    
    std::unordered_map<int, std::vector<float>> get_node_strategies() const {
        return engine_.get_node_strategies();
    }
    
    std::unordered_map<std::string, std::vector<float>> get_node_hand_strategies(int node_id) const {
        return engine_.get_node_hand_strategies(node_id);
    }
    
    float get_average_regret() const { return engine_.get_average_regret(); }
    std::vector<float> get_regret_history() const { return engine_.get_regret_history(); }
    int get_node_count() const { return engine_.get_node_count(); }
    
    py::dict get_node_data(int node_id) const {
        auto data = engine_.get_node_data(node_id);
        py::dict res;
        for (auto const& [k, v] : data) res[k.c_str()] = v;
        return res;
    }
    
private:
    poker::CppCFREngine engine_;
};

PYBIND11_MODULE(poker_solver_cpp, m) {
    py::class_<PyCFREngine>(m, "CFREngine")
        .def(py::init<>())
        .def("build_tree_cpp", &PyCFREngine::build_tree_cpp,
             py::arg("pot"), py::arg("oop_stack"), py::arg("ip_stack"),
             py::arg("flop_bet_sizes"), py::arg("flop_raise_sizes"),
             py::arg("turn_bet_sizes"), py::arg("turn_raise_sizes"),
             py::arg("river_bet_sizes"), py::arg("river_raise_sizes"),
             py::arg("initial_board"), py::arg("max_raises") = 3)
        .def("set_oop_range", &PyCFREngine::set_oop_range)
        .def("set_ip_range", &PyCFREngine::set_ip_range)
        .def("set_board", &PyCFREngine::set_board)
        .def("solve", &PyCFREngine::solve)
        .def("dump_all_data", &PyCFREngine::dump_all_data)
        .def("stop", &PyCFREngine::stop)
        .def("get_node_strategies", &PyCFREngine::get_node_strategies)
        .def("get_node_hand_strategies", &PyCFREngine::get_node_hand_strategies)
        .def("get_average_regret", &PyCFREngine::get_average_regret)
        .def("get_regret_history", &PyCFREngine::get_regret_history)
        .def("get_node_data", &PyCFREngine::get_node_data)
        .def_property_readonly("node_count", &PyCFREngine::get_node_count);
        
    m.def("evaluate_hand", &evaluate_hand);
    m.def("calculate_equity", &calculate_equity);
}
