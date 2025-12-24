---
description: "Project background, goals, current status, and key concepts"
alwaysApply: false
---

# Project Context

## 项目概述

**Poker Expert** 是一个基于 Python 和 PySide6 开发的德州扑克手牌追踪与分析软件，专门用于解析和分析 GGPoker 平台的手牌历史记录。

## 项目目标（当前阶段）

1. **数据导入与存储**：解析 GGPoker 手牌历史文件（.txt），提取关键信息并存储到 SQLite 数据库
2. **数据可视化**：提供盈亏曲线、多条 EV / Showdown / Non-Showdown 曲线
3. **手牌管理**：支持手牌列表查看、排序等基础管理功能

## 当前状态

### 已完成功能
- ✅ GGPoker 手牌历史文件解析（`poker_parser.py`）
- ✅ SQLite 数据库存储与管理（`db_manager.py`）
- ✅ 基础 GUI 框架（侧边栏导航 + 多页面堆叠）
- ✅ Dashboard 页面：多曲线图表（Net Won, All-in EV, Showdown Won, Non-Showdown Won）
- ✅ Cash Game Graph 页面：独立的盈亏曲线图表
- ✅ Sessions 页面：Session 统计（VPIP, PFR, 3Bet, WTSD%, W$SD%, Agg%）+ 手牌详情（Stack Size, Line, Board, PF Line）+ 列排序 + 双击进入 Replay
- ✅ Import 页面：文件导入，重复检测
- ✅ Report 页面：报告选择器 + 报告内容区域
  - ✅ Position Analysis：位置分析报告（扑克桌样式可视化、bb/100、Flop%、Showdown 统计）
- ✅ Replay 页面：手牌回放功能（独立弹窗 + 内嵌页面）
- ✅ **Preflop Range 页面**：GTO Range 查表功能（类似 GTO Wizard）
  - 支持 50bb / 100bb / 200bb 三种筹码深度
  - 行动序列构建器（Back/Reset 操作）
  - Range 视图：查看已行动位置的 range
  - Strategy 视图：查看待行动位置的策略分布（垂直堆叠多色显示）
  - 颜色系统：Fold(蓝灰)、Check(青)、Call(绿)、Raise(浅红→深红渐变)、All-in(橙)
- ✅ **Leak Analyze 页面**：Leak 分析功能（带二级侧边栏）
  - Preflop Range Check：检查翻前行动是否符合 GTO 策略
    - 分析 Hero 的 open raise 是否在 GTO range 内
    - 分析面对 open 时的 3bet/call/fold 是否正确
    - 显示 GTO 频率、状态（正确/错误）、盈亏统计
- ✅ All-in EV 计算（Monte Carlo 模拟）
- ✅ Insurance 费用解析与统计
- ✅ 图表筛选功能（日期范围、X轴切换）

### 待实现（只列下一步明确计划）

- Report 页面的其他报告类型（CBet Success、Sessions by Day 等）

## 技术栈

- **语言**: Python 3.11+
- **GUI 框架**: PySide6 (Qt for Python)
- **数据库**: SQLite3
- **数据可视化**: Matplotlib
- **数值计算**: NumPy
- **环境管理**: Conda (`.conda` 环境)

## 数据源

- **平台**: GGPoker
- **格式**: 文本文件（.txt），每手牌以空行分隔
- **示例路径**: `dev-doc/ggpoker-history-record/*.txt`

## 项目结构

```
poker-expert/
├── main.py                 # 应用入口
├── poker_parser.py         # 手牌历史解析器
├── db_manager.py           # 数据库管理
├── equity_calculator.py    # All-in EV 计算
├── requirements.txt        # Python 依赖
├── gui/                    # GUI 模块
│   ├── main_window.py      # 主窗口 + ReplayWindow
│   ├── pages.py            # 兼容性导入文件（实际实现在 pages/ 目录）
│   ├── styles.py           # 样式定义
│   ├── components/         # 可复用组件
│   │   ├── stat_card.py    # 统计卡片组件
│   │   └── hands_table_model.py  # 手牌表格数据模型
│   ├── pages/              # 页面模块
│   │   ├── dashboard.py    # Dashboard 页面
│   │   ├── cash_game.py    # CashGamePage, CashGameGraphPage
│   │   ├── import_page.py  # ImportPage, ImportWorker
│   │   ├── replay.py       # ReplayPage
│   │   ├── preflop_range.py # Preflop Range 页面（GTO 查表）
│   │   ├── leak_analyze/   # Leak 分析模块
│   │   │   ├── leak_analyze_page.py  # LeakAnalyzePage（功能选择器）
│   │   │   └── preflop_range_check.py # Preflop Range Check 分析
│   │   └── reports/        # 报告模块
│   │       ├── report_page.py      # ReportPage（报告选择器）
│   │       └── position_analysis.py # Position Analysis 报告
│   └── widgets/            # 自定义 widgets
│       └── replay_table.py # 牌桌可视化组件
├── assets/                 # 静态资源
│   └── range/              # GTO Range 数据
│       ├── cash6m_50bb_nl50_gto_gto/   # 50bb 深度
│       ├── cash6m_100bb_nl50_gto_gto/  # 100bb 深度
│       └── cash6m_200bb_nl50_gto_gto/  # 200bb 深度
├── dev-doc/                # 开发文档
└── .cursor/rules/          # Cursor AI 规则文档
```

## 关键概念

- **Hero**: 玩家自己（手牌历史记录中的主角）
- **Showdown**: 摊牌（所有玩家都亮牌比较）
- **All-in EV**: 全下时的期望值（Expected Value）
- **bb/100**: 每百手大盲盈利（衡量技术水平的指标）
- **Insurance**: GGPoker 的 All-in Insurance 功能

