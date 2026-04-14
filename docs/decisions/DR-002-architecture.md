# DR-002：Michael 架构设计

**日期：** 2026-04-14
**状态：** 已接受
**决策者：** Patrick（授权自主执行）

---

## 设计目标

基于五维度评估结论，Michael 需要：

1. **Harness ★★★★** — 五子系统完整实现
2. **性能 ★★★★** — 继承直接 MCP + prompt 按需加载
3. **效率 ★★★★** — 原版的简洁性 + 重构版的结构性
4. **业务成熟度 ★★★★** — 继承原版知识积累 + 重构版知识图谱
5. **业务一致性 ★★★★★** — 代码级保障，零幻觉容忍

---

## 架构决策

### 决策 1：语言选择 — Python

沿用重构版的 Python 选择。理由：
- 零外部依赖的实践已验证可行
- 知识图谱、数据处理、subprocess 调用都在 Python 舒适区
- Patrick 已有重构版的 Python 经验

### 决策 2：五层分析框架 + Execution 开关

基于 ICT 方法论的决策链和 Patrick 的设计输入，Michael 采用 **5 层分析框架**，外加可选的 Execution 层：

**分析框架（5 层）：**

```
Layer 1: FRAMING（定框架）
│  Context → Narrative → Bias
│  输入：IPDA 20/40/60D, HTF 订单流, PO3, DXY/SMT
│  输出：方向（LONG/SHORT/NEUTRAL）+ 置信度
│  门控：Bias=NEUTRAL 且低置信 → 停止
│
Layer 2: PROFILING（画轮廓）
│  Weekly Profile → Daily Profile → Session Role
│  输入：Bias + 周初/日内行为 + London 表现
│  输出：周型 + 日型 + 当前 Session 角色
│  门控：Seek & Destroy 周型 → CAUTION
│
Layer 3: TARGETING（找目标）
│  PDA Scan → DOL Framework → Key Levels
│  输入：HTF 结构 + 知识库
│  输出：PDA 优先列表 + DOL 目标 + 关键价位
│  门控：无明确 DOL → 停止
│
Layer 4: PLANNING（做计划）
│  Market State → Entry Model 匹配 →
│  Plan Entry/SL/TP/R:R/Position Size →
│  A+ Checklist（8项，含时间窗口）→ Red Flags
│  输入：Layer 1-3 全部输出 + LTF 数据
│  输出：完整 Trade Plan（JSON 结构）
│  门控：A+ < 7 或 R:R < 2 或红旗 → NO_TRADE
│
Layer 5: EXECUTION（做执行）—— 默认关闭
   模拟交易（config.execution_enabled = false）
   未来阶段启用
```

**设计依据：**

1. **来自 ICT 方法论本身的决策链**：精读 24 份资料后发现，所有 ICT 教学者都遵循 Bias → Profile → DOL → Plan → Execute 的顺序。这不是人为分层，是方法论的天然结构。

2. **来自 8 步通用执行序列的验证**：所有 ICT 入场模型共享同一个序列（HTF Bias → DOL → 流动性扫荡 → 位移确认 → PDA 入场 → 目标流动性 → 风控），自然映射到 5 层。

3. **来自 Harness 门控需求**：每一层都能独立产生"停止"信号，实现 Harness 第四原则（范围控制）。

4. **Time 是 A+ Checklist 的一个评分项**，不单独成层。分析阶段（Layer 1-3）不需要管时间；时间只在 Planning 层作为入场条件之一参与 A+ 评分。

5. **Planning 是 Phase A 的终点**。Michael 当前只做分析和计划，不做交易。Execution 默认关闭，未来启用模拟交易。

**系统架构（围绕分析框架的支撑层）：**

```
┌──────────────────────────────────────────────────┐
│                   Scheduler                       │
│            (cron 触发 + CLI 入口)                  │
└──────────────┬───────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────┐
│              Ingestion                            │
│    直接 MCP 采集 → DataManifest → MarketStore     │
└──────────────┬───────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────┐
│              Calculator（代码，不调 LLM，<1秒）    │
│    Key Levels + FVG 扫描 + Equilibrium + NWOG     │
└──────────────┬───────────────────────────────────┘
               │
    ┌──────────┴──────────┐
    ▼                     ▼
┌────────────┐  ┌─────────────────────────────────┐
│ Calculator │  │   Analysis Engine (Layer 1-4)    │
│ 位点输出    │  │   Framing→Profiling→Targeting→   │
│ (注入prompt │  │   Planning                       │
│  同时保留)  │  │   (Skill 驱动 + 门控)            │
└──────┬─────┘  │   LLM 独立发现 OB/Breaker/MSS   │
       │        └──────────┬──────────────────────┘
       │                   │
    ┌──┴───────────────────┘
    ▼
┌──────────────────────────────────────────────────┐
│    Confluence Scorer（双源交叉验证 + 联合加权）    │
│    Calculator 位点 × LLM 位点 → 来源加成 →        │
│    共振区域 Top-N 排序（S/A/B/C 等级）             │
└──────────────┬───────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────┐
│              Guardian                             │
│    幻觉检测（Calculator 输出 vs LLM 输出）         │
│    一致性 + 规则合规 + 红旗检查                    │
│    (PASS/WARN/FAIL → 阻断或放行)                  │
└──────────────┬───────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────┐
│              Dispatch                             │
│    飞书卡片 + 本地 Markdown + SQLite 持久化        │
└──────────────────────────────────────────────────┘

          ┌─────────────────────┐
          │   Audit (异步)       │
          │ 收盘后独立运行       │
          │ 评分 → 反馈 → 回注   │
          └─────────────────────┘
```

**报告类型与分析深度：**

| 报告类型 | 走到哪一层 | 说明 |
|----------|-----------|------|
| weekly_prep | Layer 1-3 | Framing + Profiling + Targeting |
| daily_bias | Layer 1-3 | 同上 |
| asia_pre / london_pre / nypm_pre | Layer 1-3 + Planning 的 Session Plan 部分 | 含 Session 计划但不含 Trade Plan |
| nyam_pre / nyam_open | Layer 1-4 完整 | 含完整 Trade Plan |
| daily_review / weekly_review | Audit 流程 | 独立异步运行 |

**Audit 独立于流水线。** 理由：
- Audit 需要"实际市场结果"，在分析时不可用
- Audit 的反馈是给下一次分析用的，不影响当前流水线
- 分离后流水线更简洁

### 决策 3：知识系统 — 双轨制

| 轨道 | 内容 | 加载方式 |
|------|------|----------|
| 知识图谱 (KnowledgeBrain) | 300+ ICT 概念节点，结构化关系 | 按类别/步骤过滤加载 |
| 业务文档 (Playbook + SOP) | 完整方法论 + 操作流程 | 按报告类型选择性引用 |

不丢弃原版 Playbook 和 SOP——它们是人类可读的业务参考，知识图谱替代不了。但加载方式从"全量注入"改为"按需引用"。

### 决策 4：配置系统 — 环境变量 + 配置类

```python
@dataclass
class Config:
    # 路径（全部通过环境变量或自动检测，无硬编码）
    project_dir: Path        # 自动检测
    claude_bin: str           # 环境变量 CLAUDE_BIN 或 which claude
    mcp_server_dir: Path      # 环境变量 MCP_SERVER_DIR

    # 飞书
    feishu_app_id: str        # 环境变量 FEISHU_APP_ID
    feishu_app_secret: str    # 环境变量 FEISHU_APP_SECRET
    feishu_chat_ids: list     # 环境变量 FEISHU_CHAT_IDS

    # 交易参数
    primary_symbol: str = "NQ1!"
    max_sl_points: int = 30
    system_version: str = "A"

    # 运行时控制
    dry_run: bool = False
    no_push: bool = False
    no_guardian: bool = False
    verbose: bool = False
```

### 决策 5：Guardian 增强 — 红旗规则引擎

将原版的 9 条红旗禁止交易条件 + 40+ 条硬性规则编码为 Guardian 的规则引擎：

```python
@dataclass
class Rule:
    id: str              # e.g. "RF-001"
    category: str        # time, structure, pda, ipda, risk, report
    condition: str       # 人类可读的条件描述
    check: Callable      # 代码级检查函数
    severity: str        # FAIL / WARN
    source: str          # "原版rules.md" / "SOP" / "反馈"
```

### 决策 6：飞书卡片 — 5 色模板驱动

恢复原版的 5 色方案（比重构版的 3 色信息量更大）：

| 颜色 | 含义 | 使用场景 |
|------|------|----------|
| 绿色 | 看多 | 多头报告 |
| 红色 | 看空 | 空头报告 |
| 蓝色 | 信息 | 周报、日报 |
| 橙色 | 修正 | 更新/修正报告 |
| 紫色 | 周度 | 周度总结 |

### 决策 7：Harness 文件体系

```
Michael/
├── CLAUDE.md                    # 入口路由（<100 行）
├── init.sh                      # 标准化启动
├── feature_list.json            # 功能追踪
├── docs/
│   ├── sop/
│   │   └── analysis-sop.md      # 集中 SOP（继承原版 424 行）
│   ├── specs/                   # 业务规范
│   ├── decisions/               # 决策记录
│   └── research/                # 调研文档
├── src/michael/
│   ├── config.py                # 配置中心
│   ├── ingestion/               # Layer 1
│   ├── analyst/                 # Layer 2
│   ├── guardian/                # Layer 3
│   ├── dispatch/                # Layer 4
│   ├── audit/                   # 异步审计
│   ├── knowledge/               # 知识系统
│   └── store/                   # SQLite 存储
├── tests/
├── scripts/
│   └── run.py                   # CLI 入口
└── knowledge/
    ├── kb.json                  # 知识图谱
    ├── playbook.md              # ICT Playbook
    └── build/                   # 知识构建工具
```

---

## 实施顺序

遵循 Harness 构建顺序（先权限后能力、先验证后交付）：

```
Phase 1: 骨架 + 指令系统
  ├── 项目结构
  ├── CLAUDE.md（路由入口）
  ├── init.sh
  ├── Config 类
  └── CLI 入口（run.py）

Phase 2: 数据层
  ├── MCP Collector（继承重构版）
  ├── DataManifest
  ├── MarketStore
  └── 测试

Phase 3: 知识系统
  ├── KnowledgeBrain（继承重构版）
  ├── Playbook + SOP 集成
  └── 知识构建工具迁移

Phase 4: 分析引擎
  ├── Claude CLI 包装器
  ├── PromptBuilder（按需知识加载）
  ├── 5 步工作流
  ├── 门控控制
  └── 测试

Phase 5: Guardian
  ├── 规则引擎（40+ 规则 + 9 红旗）
  ├── 一致性检查
  ├── 幻觉检测
  └── 测试

Phase 6: Dispatch
  ├── 飞书 5 色卡片
  ├── 文本回退
  ├── 本地 Markdown
  ├── SQLite 持久化
  └── 测试

Phase 7: Audit（异步）
  ├── Scorer
  ├── FeedbackGenerator
  ├── FeedbackStore
  └── 测试

Phase 8: 集成 + 运维
  ├── E2E 测试
  ├── Crontab 配置
  ├── 健康检查
  └── 文档完善
```
