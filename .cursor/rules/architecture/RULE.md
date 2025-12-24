---
description: "System architecture, module design, data flow, and technical implementation details"
alwaysApply: false
---

# Architecture

## 整体架构

采用 **MVC-like 架构**，分为数据层、业务逻辑层和表现层：

```
┌────────────────────────────────────────────────────────────────┐
│                 Presentation Layer (GUI)                       │
│  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌──────────┐ │
│  │Dashboard │ │CashGame │ │ Import │ │ Report │ │  Replay  │ │
│  └──────────┘ └──────────┘ └────────┘ └────────┘ └──────────┘ │
└────────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│        Business Logic Layer             │
│  ┌──────────────┐  ┌─────────────────┐ │
│  │PokerParser   │  │EquityCalculator │ │
│  └──────────────┘  └─────────────────┘ │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│           Data Layer                     │
│  ┌──────────────┐                       │
│  │  DBManager   │                       │
│  │  (SQLite)    │                       │
│  └──────────────┘                       │
└─────────────────────────────────────────┘
```

## 核心模块

### 1. 数据解析层 (`poker_parser.py`)

**职责**: 解析 GGPoker 手牌历史文本文件

**核心类**:
- `PokerHand`: 手牌数据模型
  - 基础信息：hand_id, date_time, blinds, game_type
  - 盈利数据：net_profit, rake, total_pot, insurance_premium
  - 分析数据：showdown_winnings, non_showdown_winnings, all_in_ev
  - EV 计算数据：board_at_allin, villain_cards, showdown_players

**核心函数**:
- `parse_file(filepath)`: 解析整个文件，返回 `PokerHand` 列表
- `parse_hand(lines)`: 解析单手牌文本

**解析逻辑**:
- 使用正则表达式匹配各种格式
- 按 street（Preflop, Flop, Turn, River）跟踪动作
- 计算 showdown vs non-showdown 盈利
- 检测 all-in 情况并计算 EV

### 2. 数据存储层 (`db_manager.py`)

**职责**: SQLite 数据库操作

**核心类**:
- `DBManager`: 数据库管理器
  - 单例模式（每个线程独立实例）
  - 自动创建表和迁移

**数据库 Schema**:
```sql
CREATE TABLE hands (
    hand_id TEXT PRIMARY KEY,
    date_time TEXT,
    blinds TEXT,
    game_type TEXT,
    hero_hole_cards TEXT,
    profit REAL,
    rake REAL,
    total_pot REAL,
    insurance_premium REAL DEFAULT 0,
    showdown_winnings REAL DEFAULT 0,
    non_showdown_winnings REAL DEFAULT 0,
    went_to_showdown INTEGER DEFAULT 0,
    is_all_in INTEGER DEFAULT 0,
    all_in_ev REAL DEFAULT 0
)
```

**核心方法**:
- `create_tables()`: 创建表结构，支持自动迁移
- `add_hand(hand)`: 添加手牌，返回 True（新）或 False（重复）
- `get_all_hands()`: 获取所有手牌
- `get_graph_data(start_date, end_date)`: 获取图表数据

### 3. 业务逻辑层

#### 3.1 期望值计算 (`equity_calculator.py`)

**职责**: 计算 All-in 时的期望值

**核心函数**:
- `calculate_equity(hero_cards, villain_cards, board_cards, iterations=2000)`: 
  - 使用 Monte Carlo 模拟计算胜率
  - 返回 hero 的 equity（0.0-1.0）

**算法**:
- 随机发牌完成 board
- 比较双方手牌强度
- 统计 hero 获胜次数
- 计算期望值：`EV = (Total Pot × Equity) - Hero投入`

### 4. 表现层 (GUI)

#### 4.1 主窗口 (`gui/main_window.py`)

**布局**: 侧边栏导航 + 内容区域（StackedWidget）

**组件**:
- `QListWidget`: 侧边栏（Dashboard, Cash Game Graph, Cash Games, Report, Import）
- `QStackedWidget`: 内容区域，切换不同页面
- `ReplayWindow`: 独立的手牌回放弹窗

#### 4.2 页面模块 (`gui/pages/`)

页面模块已拆分为独立文件，降低耦合度：

```
gui/pages/
├── __init__.py              # 导出所有页面类
├── dashboard.py             # DashboardPage
├── cash_game.py             # CashGamePage, CashGameGraphPage
├── import_page.py           # ImportPage, ImportWorker
├── replay.py                # ReplayPage
├── preflop_range.py         # PreflopRangePage（GTO Range 查表）
├── leak_analyze/            # Leak 分析模块
│   ├── __init__.py
│   ├── leak_analyze_page.py # LeakAnalyzePage（功能选择器）
│   └── preflop_range_check.py # PreflopRangeCheck（翻前检查）
└── reports/                 # 报告模块
    ├── __init__.py
    ├── report_page.py       # ReportPage（报告选择器）
    └── position_analysis.py # PositionTableWidget, PositionAnalysisReport
```

**DashboardPage** (`gui/pages/dashboard.py`):
- **布局**: 左侧筛选面板（220px）+ 右侧图表区域 + 报告链接
- **筛选控件**:
  - 日期范围下拉框（All Time, This Year, This Month, This Week, Today）
  - X轴模式（By Hands / By Date）
  - 曲线显示复选框（Net Won, All-in EV, Showdown Won, Non-Showdown Won）
- **图表**: Matplotlib 多曲线图
- **Summary**: 底部统计（Hands, Net, Rake, Insurance）
- **Reports 链接**: 快速跳转到报告页面

**CashGamePage (Sessions)** (`gui/pages/cash_game.py`):
- **布局**: 上方 Summary 统计 + 上下分栏（Sessions 列表 + 手牌详情）
- **Summary**: 显示总计统计（Total: X hands, Net Won, VPIP, PFR, 3Bet, WTSD, W$SD, Agg）
- **Sessions 列表**:
  - 按时间分组（间隔 30 分钟算新 session）
  - 统计指标：Hands, Net Won, VPIP, PFR, 3Bet, WTSD%, W$SD%, Postflop Agg%
  - 点击 session 显示该 session 的手牌
  - **支持列排序**（点击列头排序，再次点击切换升降序）
- **手牌详情表格**:
  - 列：Time, Stakes, Stack(bb), Cards, Line, Board, Net Won, bb, Pos, PF Line
  - **Line**: Hero 各街行动线（包括 Preflop），格式：`RC,XB,XC` = Preflop Raise-Call, Flop Check-Bet, Turn Check-Call
  - **PF Line**: Hero 翻前行动类型（Raiser, 3B, C, F）
  - **支持列排序**（时间列按实际时间排序，正确处理 AM/PM）
  - **双击行打开 Replay 弹窗**
- **行动缩写**（Line 列）:
  - B = Bet, R = Raise, C = Call, X = Check, F = Fold, A = All-in
  - 只记录实际行动，排除盲注、底池操作等

**CashGameGraphPage** (`gui/pages/cash_game.py`):
- 独立的盈亏曲线图表页面
- 与 DashboardPage 图表功能相同但全屏显示

**ImportPage** (`gui/pages/import_page.py`):
- **功能**: 文件/文件夹导入
- **后台线程**: `ImportWorker` (QThread)
- **反馈**: 进度条 + 状态标签（New Hands, Duplicates）

**ReportPage** (`gui/pages/reports/report_page.py`):
- **布局**: 左侧报告选择器（树形结构）+ 右侧报告内容区域
- **报告分类**: RESULTS, PREFLOP, ANALYSIS, DATE AND TIME
- **已实现报告**: Position Analysis

**PositionAnalysisReport** (`gui/pages/reports/position_analysis.py`):
- **可视化**: 扑克桌样式（椭圆桌子 + 6个位置圆圈 + 中心统计框）
- **数据**: bb/100、Winloss、Flop%、Showdown 统计
- **切换按钮**: Total/bb/100、$/BB 切换
- **表格**: 按位置汇总的统计数据
- **混合级别支持**: 每手牌按实际 BB 计算后累加，支持多级别混合打的正确 bb/100 计算

**ReplayPage** (`gui/pages/replay.py`):
- **功能**: 手牌回放
- **组件**: 手牌列表 + 牌桌可视化 + 动作面板
- **控制**: Prev/Play/Next 按钮

**PreflopRangePage** (`gui/pages/preflop_range.py`):
- **功能**: GTO Preflop Range 查表（类似 GTO Wizard）
- **数据源**: `assets/range/` 目录下的 GTO 数据文件
- **布局**: 左侧控制面板（300px）+ 右侧 Range 矩阵

**左侧控制面板**:
- **Stack Depth**: 50bb / 100bb / 200bb 选择
- **Action Sequence**: 行动序列构建器
  - 显示当前序列（如 "UTG 2bb → HJ 6bb"）
  - 显示可用的下一步行动（按位置分组、按行动类型着色）
  - Back/Reset 按钮
- **View Range (Acted)**: 蓝色按钮，查看已行动位置的 Range
- **View Strategy (Next)**: 绿色按钮，查看待行动位置的策略
- **Filter Action**: 策略视图下筛选特定行动
- **统计信息**: 显示各行动的 combos 和百分比

**右侧 Range 矩阵** (`StrategyMatrixWidget`):
- **13×13 手牌矩阵**: 标准 range 显示格式
- **Strategy 视图**: 垂直堆叠多色显示策略分布
  - 从下到上: Fold → Check → Call → Raise → All-in
- **Range 视图**: 单色显示特定行动的 range
- **悬停提示**: 显示手牌详细策略分布
- **图例**: 动态更新，只显示非零频率的行动

**颜色系统**:
- **Fold**: 蓝灰色 `#5d6d7e`（作为背景）
- **Check**: 青色 `#16a085`
- **Call**: 绿色 `#27ae60`
- **Raise**: 浅红→深红渐变（根据 bb 大小：2bb 最浅，20bb+ 最深）
- **All-in**: 橙色 `#e67e22`

**数据结构**:
```
assets/range/cash6m_{depth}_nl50_gto_gto/
└── ranges/
    └── {opener}/           # UTG, HJ, CO, BTN, SB
        └── {open_size}/    # 2bb, 2.5bb, allin
            └── {position}/ # 下一个位置
                └── {action}/  # call, 6bb, 8bb, allin
                    └── ...
                        └── {position}.txt  # Range 文件
```

**Range 文件格式**:
```
AA:1.0,AKs:0.8,AQs:0.5,...  # 手牌:频率
```

**关键方法**:
- `_find_range_file()`: 递归搜索行动分支下的第一个 range 文件
- `_load_strategy()`: 加载某位置的完整策略（所有行动的分布）
- `_load_acted_range()`: 加载已行动位置的 Range
- `get_action_color()`: 根据行动类型返回颜色（raise 使用连续渐变）

**LeakAnalyzePage** (`gui/pages/leak_analyze/leak_analyze_page.py`):
- **功能**: Leak 分析功能集合（类似 Report 页面的结构）
- **布局**: 左侧功能选择器（200px）+ 右侧内容区域

**左侧功能选择器**:
- 二级侧边栏，显示可用的 Leak 分析功能
- 当前功能：Preflop Range Check
- 未来扩展：Postflop Analysis、Bet Sizing Check 等

**PreflopRangeCheck** (`gui/pages/leak_analyze/preflop_range_check.py`):
- **功能**: 检查用户 Preflop 行动是否符合 GTO
- **数据源**: `hand_replay` 表的 JSON 数据 + GTO range 数据

**分析逻辑**:
1. 从数据库获取所有手牌的 replay 数据
2. 解析 Hero 的位置（根据 button_seat 计算）
3. 构建 preflop 行动序列（抽象为 raise/call/fold/allin）
4. 与 GTO range 数据比对
5. 判断行动是否正确（GTO 频率 > 1%）

**分析场景**:
- **Open Raise**: Hero 是第一个 raise 的人
- **Facing Open**: Hero 面对 opener 的行动（3bet/call/fold）

**结果显示**:
- 统计概览：总手数、正确率、错误手牌盈亏
- 详细表格：Hand ID、Cards、Position、Action、GTO Freq、Status、Profit

**关键类**:
- `AnalyzeWorker (QThread)`: 后台分析线程，避免阻塞 UI
- `PreflopRangeCheck`: 功能界面，包含分析按钮、进度条、结果表格

#### 4.3 组件模块 (`gui/components/`)

可复用的 GUI 组件：

```
gui/components/
├── __init__.py
├── stat_card.py             # StatCard - 统计卡片组件
└── hands_table_model.py     # HandsTableModel - 手牌表格数据模型
```

#### 4.4 样式 (`gui/styles.py`)

**主题**: 深色模式
- 背景色: `#2b2b2b`
- 盈利色: `#4caf50` (绿色)
- 亏损色: `#f44336` (红色)
- 强调色: `#2196f3` (蓝色), `#ff9800` (橙色)

## 数据流

### 导入流程

```
用户选择文件
    ↓
ImportPage 启动 ImportWorker (QThread)
    ↓
ImportWorker 调用 parse_file()
    ↓
PokerParser 解析文件 → 返回 PokerHand 列表
    ↓
ImportWorker 调用 db_manager.add_hand()
    ↓
DBManager 插入数据库（检测重复）
    ↓
发出 data_changed 信号
    ↓
DashboardPage 和 CashGamePage 刷新数据
```

### 图表渲染流程

```
用户选择筛选条件
    ↓
DashboardPage.refresh_data()
    ↓
调用 db_manager.get_graph_data()
    ↓
SQL 查询返回数据
    ↓
根据复选框状态选择曲线
    ↓
Matplotlib 绘制图表
    ↓
更新 Canvas
```

## 线程模型

- **主线程**: GUI 事件循环
- **工作线程**: `ImportWorker` (QThread)
  - 文件解析
  - 数据库插入
  - 通过 Signal 与主线程通信

**线程安全**:
- 每个 `ImportWorker` 创建独立的 `DBManager` 实例
- SQLite 连接不跨线程共享

## 设计模式

- **单例模式**: `DBManager`（每个线程一个实例）
- **观察者模式**: Qt Signal/Slot 机制
- **工厂模式**: `parse_hand()` 创建 `PokerHand` 对象
- **策略模式**: 不同的筛选策略（日期、X轴模式）

## 重要计算逻辑

### 混合级别 BB 计算

当玩家混合打多个级别（如 $0.01/$0.02 和 $0.05/$0.10）时，BB 值和 bb/100 的计算必须**每手牌单独计算后累加**，而不是用平均 BB 计算总盈利。

**正确做法**:
```python
# 每手牌单独计算 BB
for hand in hands:
    big_blind = parse_big_blind(hand.blinds)
    stats["total_bb"] += hand.profit / big_blind

# 最后计算 bb/100
bb_per_100 = (stats["total_bb"] / total_hands) * 100
```

**错误做法**（会导致混合级别计算错误）:
```python
# 用平均 BB 计算总盈利的 BB 值
avg_bb = sum(big_blinds) / len(big_blinds)
total_bb = total_profit / avg_bb  # ❌ 错误
```

**示例**:
- 手牌 1: $0.01/$0.02，赢 $0.10 = 5 BB
- 手牌 2: $0.05/$0.10，输 $0.30 = -3 BB
- 正确 total_bb = 5 + (-3) = **+2 BB**
- 错误（用平均 BB）= -$0.20 / $0.06 = **-3.33 BB**

