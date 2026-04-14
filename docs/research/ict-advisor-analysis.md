# ICT_Advisor 原版系统分析

> 仓库：https://github.com/patrick369-ai/ICT_Advisor

## 1. 架构概览

### 1.1 核心定位

这是一个**"提示软件"（Promptware）**系统——没有传统应用代码（无 `.py`、`.ts`、`.js`），Claude Code CLI 即运行时。业务逻辑完全编码在 Bash 脚本的 prompt 文本和 Markdown 规范文件中。

### 1.2 数据流

```
Cron (25 任务)
     │
     ▼
data_collect.sh ──→ claude -p (MCP: TradingView) ──→ JSON 文件 (data/YYYY-MM-DD/)
     │
     ▼
run_analysis.sh ──→ claude -p (MCP + Read/Write/Edit/WebFetch)
     │                   │
     │                   ├── 读取：CLAUDE.md, memory/*.md, 知识文件, SOP 规范
     │                   ├── 读取：预采集 JSON 数据
     │                   ├── 读取：SQLite（历史分析记录）
     │                   ├── 写入：SQLite（新分析记录）
     │                   └── 发送：飞书 API 交互卡片
     │
     ▼
logs/ (stdout 捕获)
```

### 1.3 技术栈

| 组件 | 技术 |
|------|------|
| 运行时 | Claude Code CLI (`claude -p`)，Claude Opus 4.6 |
| 市场数据 | TradingView MCP 服务器（Node.js，CDP 连接 TradingView Desktop） |
| 数据库 | SQLite（2 个库） |
| 调度 | Linux crontab（25 条规则） |
| 消息推送 | 飞书/Lark Open API |
| 版本控制 | Git（main + system-b 分支，1 个 worktree） |
| 平台 | WSL2 Linux on Windows |

无传统应用框架。无 Docker。无 CI/CD。无 package.json / requirements.txt。

---

## 2. 核心文件分析

### 2.1 run_analysis.sh（337 行）—— 主编排脚本

系统的核心。接收 `report_type`（9 种）和 `system_version`（A/B）参数。

**结构：**
- `COMMON_CONTEXT` 变量（~75 行 ICT 交易规则，注入每个 prompt）
- `case` 语句分发 9 种报告类型，每种有独立的 mega-prompt
- 调用 `claude -p`，通过 `--allowedTools` 限制工具集

**工具白名单：** Bash, Read, Write, Edit, Glob, Grep, WebFetch, `mcp__tradingview__*`

**问题点：**
- COMMON_CONTEXT 与 CLAUDE.md、rules.md、SOP 部分内容重复，维护负担
- 每次调用加载 ~100KB+ 上下文（playbook + 7 知识文件 + SOP + 数据）

### 2.2 data_collect.sh（92 行）—— 数据采集

通过 Claude CLI 调用 TradingView MCP 预采集数据：
- NQ1! 跨 7 个时间框架（W/D/H4/H1/M15/M5/M1）
- DXY 日线
- JSON 输出验证（python3 校验），无效文件标记 `.invalid`

**成本问题：** 每次采集消耗一次 Claude CLI 调用（~$0.19，~9 分钟）。

### 2.3 CLAUDE.md（94 行）—— 会话启动指令

强制 Claude 在每次调用时读取 7 个知识文件 + Playbook + SOP 规范。包含：
- 飞书推送凭证和群 ID
- 行为规则（不重复确认已定事项、讨论记录、SOP 遵守）

### 2.4 ICT_Trading_Playbook.md（~22K tokens）

核心交付物。6 部分结构：
1. **Meta**：品种、时间框架、50+ ICT 术语
2. **PD Array Reference**：22 种 PDA 类型
3. **Weekly Prep Module**：周分析模块
4. **Daily Bias Module**：日偏差模块
5. **Execution Module**：执行模块
6. **Risk Management**：风险管理

兼作人类参考手册和 AI 系统提示。

---

## 3. 知识体系

### 3.1 层次结构

```
ICT_Trading_Playbook.md         ← 核心方法论（22K tokens）
├── memory/ict_*.md (7 个文件)  ← 结构化知识（~77KB）
│   ├── core_framework          ← ICT 核心框架
│   ├── pd_arrays               ← PD Array 详解
│   ├── entry_models            ← 入场模型
│   ├── time_sessions           ← 时间与 Session
│   ├── liquidity_structure     ← 流动性结构
│   ├── execution_rules         ← 执行规则
│   └── advanced_visual         ← 高级视觉细节
├── feedback/*.md (10 个文件)   ← Patrick 真实修正
│   ├── analysis_quality        ← 分析质量
│   ├── independence            ← 独立分析
│   ├── asia_sessions           ← 亚洲时段修正
│   └── ...                     ← 每个文件记录一类修正
└── docs/specs/ (4 个文件)      ← SOP 与规范
    ├── analysis-sop.md (424行) ← 完整 6 步 SOP
    └── report-format-spec.md (547行) ← 报告格式规范
```

### 3.2 知识来源

17 个 ICT 学习文档（PDF + 提取的 PNG 页面 + docx），包括：
- Advanced ICT Concepts（89 页）
- ICT 5 Entry Models（29 页）
- MMXMTrader Handbook
- Pre-Market Plan
- 等

### 3.3 SOP 亮点

`analysis-sop.md`（424 行）包含：
- TradingView MCP 工具调用表（按操作分类）
- PDA 标注颜色规范
- A+ Checklist（8 项入场条件）
- 9 条红旗禁止交易条件
- 20 种入场模型匹配条件（4 层级）

---

## 4. 数据存储

### 4.1 ict_advisor.db

| 表 | 用途 | 关键字段 |
|---|---|---|
| `weekly_prep` | 周分析记录 | IPDA 范围、bias、DOL、narrative、review 评分 |
| `daily_bias` | 日方向预测 | DOL 分析、key levels (JSON)、DXY/SMT、S&D 检查、review 评分 |
| `session_analysis` | 每 Session 预测 | 方向、入场模型、review 评分 |
| `trade_signals` | 交易信号 | A+ 清单评分、入场/止损/止盈、执行结果 |
| `daily_review` | 日绩效汇总 | P&L 追踪 |
| `v_accuracy_stats` | 准确率视图 | 跨表聚合 |

所有表含 `system_version` 列，支持 A/B 测试分离。

**已知问题：**
- `session_type` 值不一致（"Asia" vs "asia_pre"，"Long" vs "BULLISH"）
- 存在重复记录

### 4.2 market_data.db

- `ohlcv` 表：历史 OHLCV 数据
- `v_key_levels` 视图：计算 PDH/PDL/PWH/PWL/IPDA 范围

---

## 5. A/B 测试基础设施

| 维度 | System A（基线） | System B（三层验证） |
|------|------------------|---------------------|
| 分支 | main | system-b |
| 工作目录 | ICT_Advisor/ | ICT_Advisor_B/（worktree） |
| 数据 | 共享（symlink） | 共享（symlink） |
| 数据库 | 共享（system_version 列区分） | 共享 |
| 飞书群 | ICT 群 | 独立测试群 |
| 验证层 | 无额外验证 | rules.md + preflight.md + validation.md |

### System B 三层验证

1. **Rules（40+ 条硬性规则）：** 按类别组织（时间/Session、市场结构、PD Array、IPDA、风控纪律、报告、周一、周轮廓），每条有 ID、日期、精确定义
2. **Preflight（预分析检查）：** 5 项通用检查 + 报告类型特定检查
3. **Validation（后分析验证）：** 定义一致性、流程完整性、证据绑定、自相矛盾、规则合规

---

## 6. 决策记录

7 个决策记录（DR-001 至 DR-007）覆盖：项目阶段（A/B/C 路线图）、品种选择、语言格式、入场模型（4 层 17 模型分类）、PD Array 完整性（22 种）、Playbook 结构（单文件 6 部分）、文档要求。

---

## 7. 优势与不足总结

### 优势

- **业务深度极强**：Playbook 22K tokens，SOP 424 行，覆盖完整的 ICT 方法论
- **真实生产积累**：10 个反馈文件记录 Patrick 的修正，8+ 天生产数据
- **A/B 测试纪律**：完整的双系统对比基础设施
- **文档意识好**：7 个决策记录、讨论日志、执行示例

### 不足

- **无独立验证**：验证由 Claude 自己执行（"让被告当法官"）
- **性能问题**：每次采集 $0.19/9 分钟，每次分析加载 100KB+ 上下文
- **数据一致性差**：session_type 值混乱，有重复记录
- **无错误恢复**：无重试、无告警、无健康监控
- **密钥明文**：飞书 App Secret 在 .env 明文，bearer token 在 settings 中
- **硬编码路径**：PROJECT_DIR、CLAUDE_BIN 等硬编码
- **无自动化测试**：完全依赖生产运行验证
