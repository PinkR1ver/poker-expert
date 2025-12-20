---
description: "Development rules, environment management, code standards, and documentation maintenance requirements"
alwaysApply: true
---

# Development Rules

## 环境管理

### 1. 虚拟环境规则
- **禁止使用 venv**：不要创建或使用 Python 虚拟环境 (venv)
- **使用 Conda 环境**：项目使用 `.conda` 环境，通过 `conda activate` 激活
- **依赖管理**：所有需要的 Python 包都写入 `requirements.txt`，用户会自行使用 `pip install -r requirements.txt` 安装

### 2. 依赖管理
- 所有新增的 Python 包必须添加到 `requirements.txt`
- 不要使用 `pip freeze` 生成 requirements，手动维护依赖列表
- 保持依赖版本简洁，除非有特殊需求，否则不指定具体版本号

## 代码规范

### 1. 文件组织
- GUI 相关代码放在 `gui/` 目录
- 核心业务逻辑（parser, db_manager）放在项目根目录
- 工具类（equity_calculator）放在项目根目录

### 2. 命名规范
- 类名使用 `PascalCase`（如 `PokerHand`, `DBManager`）
- 函数和变量使用 `snake_case`（如 `parse_hand`, `hero_name`）
- 常量使用 `UPPER_SNAKE_CASE`（如 `PROFIT_GREEN`, `DARK_THEME_QSS`）

### 3. 数据库操作
- 每个线程使用独立的 `DBManager` 实例（SQLite 线程安全要求）
- 使用参数化查询防止 SQL 注入
- 数据库迁移通过 `ALTER TABLE` 或表重建实现

## 文档维护规则

### 📚 项目文档结构

本项目使用四个核心文档管理项目上下文（位于 `.cursor/rules/` 目录）：

- **`project-context`**: 项目背景、目标、当前状态
  - **用途**: 了解项目整体情况、已完成功能、待实现功能
  - **何时查阅**: 开始新功能开发、更新项目状态时

- **`dev-rules`**: 开发规则、环境管理、代码规范（本文档，alwaysApply: true）
  - **用途**: 开发规范、环境配置、文档维护规则
  - **何时查阅**: 每次代码变更时自动应用

- **`architecture`**: 系统架构、模块设计、数据流
  - **用途**: 了解系统架构、模块职责、数据流向
  - **何时查阅**: 修改架构、添加新模块、理解数据流时

- **`glossary`**: 术语表、概念定义
  - **用途**: 查找专业术语、概念定义
  - **何时查阅**: 遇到不熟悉的术语时

**重要**: AI 助手在执行任务前应查阅相关文档，特别是 `@project-context` 和 `@architecture`，以确保理解项目上下文。

### ⚠️ 重要：文档同步要求（精简版）

- 文档只记录**当前已经实现的模块和功能**，不要在规则里堆积还没做、已经废弃的想法。
- 每次完成一段代码改动后：
  1. 如果新增/调整了模块或类结构 → 更新 `@architecture` 中对应部分
  2. 如果新增/调整了可见功能或页面 → 在 `@project-context` 的“已完成功能”中补充，必要时精简“待实现”
  3. 如果新增/调整了开发流程或约定 → 更新本文件 `@dev-rules`
  4. 如果引入了新的专业术语 → 在 `@glossary` 中补充

### 文档优先级

当文档内容与代码不一致时：
- **代码为准**：文档需要更新以反映实际实现
- **设计文档为准**：如果是有计划的变更，先更新设计文档再实现

### 文档更新检查清单

在提交代码前，确认：
- [ ] 相关文档已更新
- [ ] 文档内容与实际代码一致
- [ ] 新增功能已在 `@project-context` 中记录
- [ ] 架构变更已在 `@architecture` 中反映

## Git 工作流

- 主分支：`main`
- 功能开发：创建功能分支
- 提交信息：使用清晰的中文或英文描述

## 测试要求

- 导入功能：测试重复导入检测
- 解析功能：测试各种边界情况（空文件、格式异常等）
- GUI 功能：确保多线程操作不阻塞界面

## 性能要求

- 文件导入使用后台线程（`QThread`）
- 大数据量图表渲染使用适当的数据采样
- 数据库查询使用索引优化（hand_id 为主键）

