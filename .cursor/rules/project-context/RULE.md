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
- ✅ Cash Games 页面：手牌列表表格，支持列排序
- ✅ Import 页面：文件导入，重复检测
- ✅ All-in EV 计算（Monte Carlo 模拟）
- ✅ Insurance 费用解析与统计
- ✅ 图表筛选功能（日期范围、X轴切换）

### 待实现（只列下一步明确计划）

（当前阶段无手牌回放相关计划，后续如需加入由用户重新指定方案）

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
│   ├── main_window.py      # 主窗口
│   ├── pages.py            # 页面组件（Dashboard, CashGame, Import）
│   └── styles.py           # 样式定义
├── dev-doc/                # 开发文档
└── .cursor/rules/          # Cursor AI 规则文档
```

## 关键概念

- **Hero**: 玩家自己（手牌历史记录中的主角）
- **Showdown**: 摊牌（所有玩家都亮牌比较）
- **All-in EV**: 全下时的期望值（Expected Value）
- **bb/100**: 每百手大盲盈利（衡量技术水平的指标）
- **Insurance**: GGPoker 的 All-in Insurance 功能

