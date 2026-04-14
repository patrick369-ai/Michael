# ict-advisor-refactory 重构版系统分析

> 仓库：https://github.com/patrick369-ai/ict-advisor-refactory

## 1. 架构概览

### 1.1 核心定位

原版系统的工程化重构。用 Python 替代 Bash，引入 5 层流水线架构，消除了"用 LLM 当 API 客户端"的高成本做法。

### 1.2 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.10+，type hints，dataclasses |
| 分析引擎 | Claude CLI (`claude -p`) via subprocess |
| 数据采集 | TradingView MCP（JSON-RPC 2.0 over stdio） |
| 数据库 | SQLite3（2 个库） |
| 消息推送 | 飞书 REST API |
| 测试 | pytest（2 个测试文件） |
| 知识库 | 自定义 JSON 图（kb.json，~20K 行，300+ 节点） |
| 异步 | asyncio |
| HTTP | urllib.request（stdlib） |

**关键特征：零外部 Python 运行时依赖**，全部使用 stdlib。只有知识构建工具链需要 pymupdf / easyocr / pyyaml。

### 1.3 代码规模

- 31 个 Python 源文件
- ~6,500 行代码
- ~1,000 行测试

---

## 2. 五层流水线架构

```
定时触发
    │
 [1. Ingestion]  ──→ DataManifest
    │
 [2. Analyst]    ──→ AnalysisResult（5 步 ICT 工作流）
    │
 [5. Guardian]   ──→ SupervisionReport（可阻断发布）
    │
 [3. Dispatch]   ──→ 飞书卡片 + SQLite 持久化
    │
 [4. Audit]      ──→ AuditResult ──→ FeedbackPayload（回注 Analyst）
```

---

### 2.1 Ingestion 层（数据采集）

**核心文件：** collector.py (586行), manifest.py (204行), config.py (176行), market_store.py (482行)

**Collector：**
- 直接生成 TradingView MCP 子进程，通过 stdin/stdout 说 JSON-RPC 2.0
- 替代原版用 Claude CLI 调 MCP 的方式（$0.19/次 → 免费，9 分钟 → 秒级）

**DataManifest：**
- Dataclass 描述采集结果：文件路径、bar 数量、完整性状态（PASS/PARTIAL/FAIL）
- NQ1! 数据为关键（critical），其他为非关键

**MarketStore：**
- SQLite 持久化 OHLCV 数据
- 支持 bootstrap（全量）、incremental（增量）、auto（自动检测）模式
- 断点续传（resume-from-checkpoint）

**数据需求配置：**
- 7 个品种（NQ, ES, YM, GC, SI, CL, DXY）× 7 个时间框架（W/D/H4/H1/M15/M5/M1）
- 按报告类型配置不同的数据需求

---

### 2.2 Analyst 层（分析引擎）

**核心文件：** engine.py (401行), claude_cli.py (250行), prompt_builder.py (226行), 5 个步骤模块, 5 个输出模板, 5 个规范文件

**5 步工作流（按报告类型映射不同步骤组合）：**

| 步骤 | 名称 | 核心分析内容 |
|------|------|-------------|
| 1 | Weekly Narrative | IPDA 3 周期（20D/40D/60D）、HTF 订单流、Weekly Profile（12 模板）、CBDR |
| 2 | Daily Bias | The Sequence (PO3)、DOL 三问分析、DXY/SMT 背离、Seek & Destroy 过滤 |
| 3 | Session Analysis | 每 Session 角色预测、前一 Session 回顾、流动性映射 |
| 4 | LTF Execution | 流动性扫荡、MSS/CISD 确认、PDA 排序、入场模型匹配（4 层 20 模型） |
| 5 | Signal Output | 入场/止损/止盈、R:R、仓位、置信度 |

**ClaudeCLI 包装器：**
- subprocess 调用，timeout 600s，max_turns 5
- 从 Claude 文本输出中提取 JSON（正则：先尝试围栏块，再尝试裸 `{}`）
- JSON Schema 验证
- 失败时追加错误信息重试一次

**PromptBuilder：**
- 从知识库按类别过滤上下文
- 组装前序步骤结果、市场数据路径、最近审计教训、规范指令、输出 Schema
- 中文 prompt，ICT 英文术语保留

**门控控制：**
- 每步输出 PASS/FAIL/NO_TRADE/CAUTION
- FAIL 或 NO_TRADE 终止后续步骤（不发布部分坏结果）

---

### 2.3 Guardian 层（质量守护）

**核心文件：** supervisor.py (213行), consistency.py (220行), hallucination.py (327行), report.py (98行)

**5 类检查：**

| 检查类别 | 内容 | 严重性 |
|----------|------|--------|
| 工作流合规 | 步骤按正确顺序执行 | FAIL |
| 数据完整性 | DataManifest 状态验证 | FAIL |
| 模板合规 | 步骤输出符合 JSON Schema | FAIL |
| 一致性检查 | Session bias vs Daily bias 矛盾检测、DOL 与 bias 对齐、信号方向一致 | WARN/FAIL |
| 幻觉检测 | PDH/PDL/PWH/PWL 与实际 OHLCV 比对（1-2 点容差）、PDA 名称存在性、入场模型存在性、价格偏离检查（>5% 标记） | WARN/FAIL |

**整体状态：** 任一 FAIL → 阻断发布（严格模式）。WARN → 发布但附加标注。

---

### 2.4 Dispatch 层（消息分发）

**核心文件：** feishu.py (~450行), publisher.py (72行), 9 个展示模板 JSON

- Publisher 协议接口，支持多通道
- 飞书交互卡片 + 文本回退（卡片失败时自动降级）
- 9 个模板 JSON 定义每种报告的节区顺序和标签
- 颜色编码：绿=看多、红=看空、灰=中性
- 本地 Markdown 报告生成

---

### 2.5 Audit 层（审计反馈）

**核心文件：** reviewer.py (352行), scorer.py (192行), feedback.py (237行)

**4 维评分（满分 10 分）：**

| 维度 | 分值 | 评估内容 |
|------|------|----------|
| 方向准确性 | 0-3 | 预测 vs 实际方向 |
| 关键位准确性 | 0-3 | 精确/接近/部分阈值（10/25/50 NQ 点） |
| 叙事质量 | 0-2 | 分析逻辑质量 |
| 可操作性 | 0-2 | 实际可执行程度 |

**反馈闭环：**
- FeedbackGenerator 将审计结果转化为 FeedbackPayload（偏差警告、Session 调整、知识强化、位点提醒、近期准确率）
- 检测跨历史的系统性弱点
- FeedbackStore 持久化到 `audit_feedback` SQLite 表
- PromptBuilder 在下一次分析中注入这些教训

---

## 3. 知识系统

### 3.1 KnowledgeBrain 图数据库

**文件：** brain.py (461行), schema.py (157行), kb.json (20,320行), aliases.json (1,823行), by_category.json (390行)

全量加载到内存。所有查找 O(1) 或 O(邻居数)。初始化后零 I/O。

**索引结构：**
- Primary: ID → 节点字典
- Alias: 小写字符串 → 规范 ID
- Category: 类别 → [节点 ID]（8 类：concept, pd_array, model, framework, session, rule, pattern, glossary）
- Tag: 标签 → {节点 ID}
- Reverse edges: target_id → {边类型 → [源 ID]}
- Search corpus: node_id → [可搜索 token]

**12 种边类型：** requires, triggers, part_of, validates, invalidated_by, strengthened_by, weakened_by, precedes, follows, children, parent, related

**核心 API：**
- `get(name)` — O(1) 别名解析查找
- `by_category(cat)` — 类别下所有节点
- `search(query)` — 关键词搜索
- `decision_context(name)` — 节点 + 所有边 + 规则 + 相关（单次调用获取完整决策上下文）
- `export_context(categories, max_chars)` — 批量文本导出用于 prompt 注入

### 3.2 知识构建工具链（5 个工具）

| 工具 | 来源 | 输出 |
|------|------|------|
| pdf_extractor.py | ICT PDF 文档 | 文本提取（pymupdf + easyocr 回退） |
| memory_importer.py | Claude auto-memory ict_*.md | 解析 YAML frontmatter |
| wiki_importer.py | ict_onepiece/wiki/ | 448 概念 + 35 模型 |
| transcript_importer.py | 68 节指导课程转录 | 结构化概念 |
| classifier.py (760行) | 去重、分类、建边 | kb.json + aliases.json |

### 3.3 知识统计

- 210+ 概念
- 15 框架
- 55+ 模型
- 21 模式
- 42+ PD Array
- 6 规则
- 25+ Session 相关

---

## 4. 配置系统

| 配置源 | 内容 |
|--------|------|
| `.env` | 飞书凭证和群 ID |
| `config.py: AppConfig` | 项目路径、MCP 目录、主品种（NQ1!）、扫描品种、最大止损（30 点）、系统版本 |
| `ingestion/config.py` | TIMEFRAME_MAP、SYMBOLS、按报告类型的数据需求 |
| `claude_cli.py` | Claude 二进制路径、允许的工具、超时/max_turns |

**问题：** `AppConfig.from_env()` 抛出 `NotImplementedError`，配置系统半成品。

---

## 5. 错误处理

- 自定义异常类：`MCPError(code, message, data)`、`CollectorError`、`AnalysisError`
- 边界处 try/except：MCP 调用、Claude CLI 子进程、飞书 HTTP、JSON 解析、文件 I/O
- 回退链：飞书卡片 → 文本回退；JSON 提取尝试围栏块 → 裸大括号
- Claude CLI 失败重试一次（追加错误信息到 prompt）
- 门控：FAIL/NO_TRADE 阻止后续步骤
- 超时：subprocess.run timeout

---

## 6. 测试

### test_ingestion.py (~330 行)
- 配置验证、Manifest 验证（PASS/PARTIAL/FAIL）、Collector 初始化、RPC 协议、完整采集流程 mock

### test_e2e.py (~685 行)
- Guardian 层（一致性/幻觉检测/Supervisor 完整检查）
- Audit 层（评分/反馈生成/反馈持久化）
- Dispatch 层（卡片构建/信号信息/多 Publisher）
- 数据库层（Schema 创建/保存各类记录）
- 端到端（manifest → analysis → guardian → db → card）

全部使用 mock，无真实外部连接。

---

## 7. 文档体系

| 文件 | 用途 |
|------|------|
| CLAUDE.md (158行) | 项目指令（但目录结构已过时） |
| CHANGELOG.md (21行) | 变更日志（未持续维护） |
| 改革计划 (663行) | 详细的现状分析 + 3 阶段计划 |
| ADR-001 (66行) | 语言、仓库、Schema 决策 |
| ADR-002 (174行) | 5 层流水线架构设计 |
| ADR-003 (29行) | 数据采集自动检测模式（待审查） |
| ADR-004 (48行) | 数据采集/分析解耦计划 |
| report-format-spec.md (127行) | 报告格式约束 |
| pda-analysis-spec.md (144行) | PDA 分析要求（14 类） |
| entry-model-spec.md (170行) | 入场模型匹配要求（20 模型 4 层级） |
| data-collection-spec.md (117行) | 数据采集规范 |

---

## 8. Git 历史

- 28 个 commit，6 天（2026-04-08 至 2026-04-13）
- 单分支 main（虽然 CLAUDE.md 定义了 main/develop/feature/* 策略，但未实际执行）
- 关键里程碑：
  - Apr 8：项目初始化 + 文档
  - Apr 9：全量实现（Knowledge Brain, 5 层流水线, E2E 测试, MarketStore）
  - Apr 13：性能优化（prompt 压缩 71%，E2E 时间减少 37%：635s→393s，max_turns 30→5，timeout 1800→600s）

---

## 9. 优势与不足总结

### 优势

- **架构清晰**：5 层分离，接口明确（DataManifest, AnalysisResult, SupervisionReport, AuditResult）
- **独立验证**：Guardian 层代码级检查，不依赖模型自觉
- **幻觉检测**：价格数据与 OHLCV 比对，模型名称存在性验证
- **性能显著优化**：数据采集免费、prompt 压缩 71%、E2E 时间减少 37%
- **反馈闭环**：审计教训自动注入下一次分析
- **零外部依赖**：运行时纯 stdlib
- **知识图谱**：300+ 节点图数据库，O(1) 查找，决策链支持

### 不足

- **业务积累不足**：仅 6 天开发，缺少生产运行验证数据
- **配置系统半成品**：`AppConfig.from_env()` 未实现
- **CLAUDE.md 过时**：文件目录结构与实际不符
- **步骤模块代码重复**：5 个步骤的 `validate_output()` 几乎相同，应抽取共享验证器
- **步骤类是空壳**：定义了类但没有方法，逻辑在模块级函数中
- **硬编码路径**：`/home/patrick/` 散布各处
- **分支策略未执行**：定义了 main/develop/feature/* 但只有 main
- **无 A/B 测试**：丢失了原版的 A/B 对比能力
- **无独立 SOP**：原版 424 行 SOP 的逻辑分散在步骤模块中，不再集中可查
- **datetime.utcnow() 已废弃**：应使用 `datetime.now(timezone.utc)`
