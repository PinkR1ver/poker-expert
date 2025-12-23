---
description: "Glossary of poker terms, data analysis terminology, and technical concepts"
alwaysApply: false
---

# Glossary

## 扑克术语

### 基础概念

- **Hero**: 玩家自己，手牌历史记录中的主角
- **Villain**: 对手玩家
- **Hand**: 一手牌，从发牌到结算的完整过程
- **Street**: 游戏阶段
  - **Preflop**: 翻牌前
  - **Flop**: 翻牌圈（3张公共牌）
  - **Turn**: 转牌圈（第4张公共牌）
  - **River**: 河牌圈（第5张公共牌）
- **Showdown**: 摊牌，所有玩家都亮牌比较大小
- **Pot**: 底池，当前轮所有玩家投入的筹码总和
- **Rake**: 抽水，平台从底池中抽取的费用

### 位置术语

- **Button (BTN)**: 按钮位，最后行动的位置（最有利）
- **Small Blind (SB)**: 小盲位
- **Big Blind (BB)**: 大盲位
- **Cutoff (CO)**: 按钮前一位
- **Middle Position (MP)**: 中位
- **Early Position (EP)**: 前位

### 动作术语

- **Fold**: 弃牌
- **Check**: 过牌（不下注）
- **Call**: 跟注
- **Bet**: 下注（第一个行动）
- **Raise**: 加注
- **All-in**: 全下（投入所有筹码）

### 手牌术语

- **Hole Cards**: 底牌，玩家手中的两张牌
- **Board**: 公共牌
- **Hand Strength**: 手牌强度（高牌、一对、两对、三条、顺子、同花、葫芦、四条、同花顺）

## 数据分析术语

### 盈利指标

- **Net Won**: 净盈利 = Collected - Wagered
- **bb/100**: 每百手大盲盈利，衡量技术水平的核心指标
  - 公式: `(Net Won / Big Blind) / (Hands / 100)`
- **All-in EV**: 全下时的期望值
  - 使用 Monte Carlo 模拟计算 equity
  - `EV = (Total Pot × Equity) - Hero投入`
- **Luck**: 运气成分 = Actual Profit - EV
  - 正数 = 运气好（赢得比期望多）
  - 负数 = 运气差（赢得比期望少）

### 分类盈利

- **Showdown Won**: 摊牌盈利，到摊牌的手牌盈亏
- **Non-Showdown Won**: 非摊牌盈利，未到摊牌的手牌盈亏（对手弃牌赢/Hero弃牌输）

### 统计指标

- **VPIP** (Voluntarily Put $ In Pot): 主动入池率，自愿投入底池的手数比例（除盲注外有 call/raise/bet 的手数 / 总手数）
- **PFR** (Pre-Flop Raise): 翻牌前加注率，翻前有 raise 的手数 / 总手数
- **3Bet**: 三倍加注率，面对 open raise 后 re-raise 的次数 / 面对 open raise 的次数
- **WTSD%** (Went To ShowDown): 摊牌率，到摊牌的手数 / 看到 flop 的手数
- **W$SD%** (Won $ at ShowDown): 摊牌胜率，摊牌赢钱的手数 / 到摊牌的手数
- **Postflop Agg%** (Postflop Aggression): 翻后激进度，(bet + raise 次数) / (bet + raise + call + check 次数)
- **AF** (Aggression Factor): 攻击性因子 = (Bet次数 + Raise次数) / Call次数

### 行动线术语

- **Line**: Hero 的行动线，记录各街（包括 Preflop）的行动缩写
  - **B** = Bet (下注)
  - **R** = Raise (加注)
  - **C** = Call (跟注)
  - **X** = Check (过牌)
  - **F** = Fold (弃牌)
  - **A** = All-in (全下)
  - 格式：各街用逗号分隔
  - 例如：`RC,XB,XC,XF` = Preflop Raise-Call, Flop Check-Bet, Turn Check-Call, River Check-Fold
  - 注：只记录实际行动，排除盲注（post blind）、底池操作（collected, uncalled_bet_returned）等
- **PF Line**: Hero 翻前行动类型（简化显示）
  - **Raiser** = Open raise (开池加注)
  - **3B** = 3-bet (对 open raise 再加注)
  - **C** = Call (跟注)
  - **F** = Fold (弃牌)

## 技术术语

### 数据库

- **SQLite**: 轻量级关系型数据库，单文件存储
- **Schema**: 数据库表结构定义
- **Migration**: 数据库迁移，更新表结构

### GUI

- **QWidget**: Qt 基础窗口组件
- **QDialog**: 对话框窗口
- **QTableView**: 表格视图
- **QGraphicsView**: 图形视图（用于绘制牌桌）
- **QStackedWidget**: 堆叠窗口，用于多页面切换
- **Signal/Slot**: Qt 的事件通信机制

### 数据处理

- **Regex**: 正则表达式，用于文本模式匹配
- **Monte Carlo**: 蒙特卡洛模拟，通过随机采样估算概率
- **Equity**: 胜率，在当前情况下获胜的概率

## GGPoker 特定术语

- **Rush and Cash**: GGPoker 的快节奏现金游戏模式
- **Insurance**: All-in Insurance，全下保险功能
  - 玩家可以购买保险，如果全下后输掉，可以获得部分补偿
  - 保险费用计入 `insurance_premium`
- **Hand ID**: 手牌唯一标识符，格式如 `RC4122279318`

## 项目特定术语

- **Parser**: 解析器，`poker_parser.py` 中的解析逻辑
- **DBManager**: 数据库管理器，`db_manager.py` 中的数据库操作类
- **Replayer**: 手牌回放器，可视化重现手牌过程（已实现）
- **Dashboard**: 概览页面，显示核心统计和图表
- **Sessions**: 会话页面，按时间分组显示 session 统计和手牌详情
- **Session**: 连续打牌的时间段，间隔超过 30 分钟算作不同 session

