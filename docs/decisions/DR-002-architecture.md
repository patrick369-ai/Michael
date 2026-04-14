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

### 决策 2：四层架构（简化重构版的五层为四层）

重构版五层的问题：Audit 层与 Guardian 层职责重叠（都是验证），且 Audit 是异步后置的，与实时流水线混在一起增加复杂度。

**Michael 四层：**

```
┌──────────────────────────────────────────────────┐
│                   Scheduler                       │
│            (cron 触发 + CLI 入口)                  │
└──────────────┬───────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────┐
│              Layer 1: Ingestion                   │
│    直接 MCP 采集 → DataManifest → MarketStore     │
└──────────────┬───────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────┐
│              Layer 2: Analyst                     │
│    PromptBuilder → Claude CLI → StepResult        │
│    (5 步工作流 + 门控 + JSON Schema 验证)          │
└──────────────┬───────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────┐
│              Layer 3: Guardian                    │
│    一致性 + 幻觉检测 + 规则合规 + 红旗检查         │
│    (PASS/WARN/FAIL → 阻断或放行)                  │
└──────────────┬───────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────┐
│              Layer 4: Dispatch                    │
│    飞书卡片 + 本地 Markdown + SQLite 持久化        │
└──────────────────────────────────────────────────┘

          ┌─────────────────────┐
          │   Audit (异步)       │
          │ 收盘后独立运行       │
          │ 评分 → 反馈 → 回注   │
          └─────────────────────┘
```

**关键改变：** Audit 从流水线中独立出来，作为异步后处理。理由：
- Audit 需要"实际市场结果"，在分析时不可用
- Audit 的反馈是给下一次分析用的，不影响当前流水线
- 分离后流水线更简洁，四层各司其职

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
