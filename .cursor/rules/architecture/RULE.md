---
description: "System architecture, module design, data flow, and technical implementation details"
alwaysApply: false
---

# Architecture

## 整体架构

采用 **MVC-like 架构**，分为数据层、业务逻辑层和表现层：

```
┌─────────────────────────────────────────┐
│         Presentation Layer (GUI)        │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │Dashboard │  │CashGame │  │ Import │ │
│  └──────────┘  └──────────┘  └────────┘ │
└─────────────────────────────────────────┘
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
- `QListWidget`: 侧边栏（Dashboard, Cash Games, Import）
- `QStackedWidget`: 内容区域，切换不同页面

#### 4.2 页面组件 (`gui/pages.py`)

**DashboardPage**:
- **布局**: 左侧筛选面板（220px）+ 右侧图表区域
- **筛选控件**:
  - 日期范围下拉框（All Time, This Year, This Month, This Week, Today）
  - X轴模式（By Hands / By Date）
  - 曲线显示复选框（Net Won, All-in EV, Showdown Won, Non-Showdown Won）
- **图表**: Matplotlib 多曲线图
- **Summary**: 底部统计（Hands, Net, Rake, Insurance）

**CashGamePage**:
- **表格**: `QTableView` + `HandsTableModel`
- **功能**: 
  - 列排序（点击表头）
  - 行选择
  - 颜色编码（盈利绿色，亏损红色）
- **列**: Date, Game, Stakes, Hand, Net Won, Pot, Rake

**ImportPage**:
- **功能**: 文件/文件夹导入
- **后台线程**: `ImportWorker` (QThread)
- **反馈**: 进度条 + 状态标签（New Hands, Duplicates）

#### 4.3 样式 (`gui/styles.py`)

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

