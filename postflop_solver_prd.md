# Postflop Solver 重构与优化 PRD

## 1. 背景与愿景
本项目已实现了一个高性能的 C++ CFR Solver 核心，能够构建大规模博弈树并进行快速解算。然而，目前的 Python UI 与 C++ 核心之间仍存在一些逻辑耦合与数据不一致的问题。本 PRD 的目标是为下一阶段的重构提供清晰的蓝图，以建立一个更加稳定、精确且易于扩展的 Poker Solver。

## 2. 核心目标
- **极致稳定性**: 彻底消除 Python/C++ 边界的类型不一致和内存溢出风险。
- **高精度策略**: 改进 CFR 收敛算法，支持更精细的策略权重显示（考虑 Range 与 Blocker）。
- **解耦架构**: 明确 Python 侧作为“展示与配置层”，C++ 侧作为“状态机与计算层”的界限。

## 3. 关键功能要求

### 3.1 C++ 核心层 (Computation Layer)
- **统一状态机**: 所有的博弈逻辑（Bet size 计算、Street 推进、All-in 判定）应完全由 C++ 维护。
- **完美的去重 (Deduplication)**: 增强 `Transposition Table` 的哈希键值，包含 `raise_count` 和 `is_all_in` 等关键状态，防止策略泄露。
- **磁盘缓冲优化**: 进一步优化 `MmapBuffer`，支持更大规模的博弈树（目标：500M+ Actions）。
- **策略归一化**: 在 C++ 侧提供预归一化的策略导出接口，减少 Python 侧的计算压力。

### 3.2 Python 代理层 (Proxy Layer)
- **Lazy Loading 增强**: `NodeProxy` 应实现全属性缓存，确保单次访问 C++ 内存后不再重复调用。
- **类型安全适配器**: 实现一个统一的适配器类，将 C++ 的 `shorthand`（如 87s）准确映射到 UI 矩阵的坐标。
- **错误恢复机制**: 当 C++ 解算失败或 Mmap 溢出时，提供优雅的降级方案（如回退到 Python 引擎或显示明确的错误指引）。

### 3.3 UI 展现层 (Presentation Layer)
- **Range-Aware Strategy Display**: 策略矩阵应始终结合当前玩家的 `Reach Probability`（权重）进行显示，避免显示“不存在”的手牌策略。
- **Real-time Blocker Filtering**: 在 UI 层实时应用 Board Blockers，确保显示的 Combo 数与理论一致。
- **异步导航**: 树导航应在独立线程进行，确保点击 Action 按钮时 UI 不卡顿。

## 4. 非功能性需求
- **可维护性**: 使用 Doxygen 风格注释记录 C++ 核心逻辑。
- **可测试性**: 建立 C++ 单元测试框架（如 GTest），验证博弈树构建的准确性（尤其是 pot size 和 to_call）。
- **性能**: Flop 节点的加载时间应小于 100ms。

## 5. 待办事项 (Next Steps)
1. **统一接口协议**: 定义一套标准的 JSON/Struct 协议，用于 Python 与 C++ 之间交换博弈状态。
2. **重构 BettingConfig**: 支持更复杂的下注规则（如 Pot Limit, Fixed Limit）。
3. **增加保存/加载功能**: 支持将解算好的 Mmap 文件持久化存储，方便后续复盘。

