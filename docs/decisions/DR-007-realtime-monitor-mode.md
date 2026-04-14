# DR-007：双模式运行 + 分阶段实施

**日期：** 2026-04-14
**状态：** 已接受
**决策者：** Patrick

---

## 背景

Patrick 提出两个关键需求：
1. 老版本分析效率低，行情推进快时赶不上
2. 希望系统同时支持定时分析（默认）和实时监控（可开启）

同时表达了对 Monitor 模式信心不大的顾虑。

---

## 决策

### 1. 双模式共存

| 模式 | 默认 | 触发 | LLM 调用 | 输出 |
|------|------|------|---------|------|
| **SCHEDULED** | ✅ 默认开启 | cron 定时 | 每次都调 | 完整报告 |
| **MONITOR** | ❌ 默认关闭 | 定时轮询（默认 M5） | 仅触发条件命中时 | 即时告警 |

两种模式共用 Ingestion / Calculator / Confluence Scorer / Dispatch / SQLite。Monitor 的分析结果也写入 SQLite，供 SCHEDULED 模式引用。

### 2. 完整的 9 种报告类型覆盖

| 报告类型 | 触发时间 (ET) | 模式 | 预估耗时 |
|----------|-------------|------|---------|
| weekly_prep | 周日 | SCHEDULED | ~70s |
| daily_bias | 6:00 PM | SCHEDULED | ~80s |
| asia_pre | 6:30 PM | SCHEDULED | ~70s |
| london_pre | 1:30 AM | SCHEDULED | ~70s |
| nyam_pre | 8:00 AM | SCHEDULED | ~150s（两阶段） |
| nyam_open | 9:15 AM | SCHEDULED | ~70s |
| nypm_pre | 1:00 PM | SCHEDULED | ~70s |
| daily_review | 收盘后 | SCHEDULED | **< 10s**（纯代码 Audit） |
| weekly_review | 周五/六 | SCHEDULED | **< 10s**（纯代码 Audit） |
| **日均（SCHEDULED）** | | | ~660s / 7次LLM + 2次代码 |
| **盘中告警（MONITOR）** | 条件触发 | MONITOR | **< 3s** (纯代码) |
| **盘中补充分析（MONITOR）** | 告警后可选 | MONITOR | ~90s |

老版本日均 ~81min / 9 次 LLM 调用 → Michael SCHEDULED 日均 ~11min / 7 次 LLM 调用，**效率提升约 87%**。

### 3. Monitor 模式触发条件

**不是每周期都推送，有事发生才推送：**

| 触发条件 | 需要 LLM |
|----------|---------|
| 价格进入 S/A 级共振区 | 否 |
| 新 FVG 形成在共振区内 | 否 |
| Key Level 被突破（PDH/PDL/PWH/PWL） | 否 |
| EQH/EQL 被扫（流动性事件） | 否 |
| 共振区域等级变化（B→A 或 A→S） | 否 |
| 触发后补充完整分析 | 是（用户配置 auto_analyze=true） |

### 4. Monitor 配置

```python
@dataclass
class MonitorConfig:
    enabled: bool = False              # 默认关闭
    interval: str = "M5"               # 轮询周期：M1/M5/M15
    symbols: list[str] = ["NQ1!"]

    # 触发条件
    confluence_threshold: str = "A"    # 最低推送等级
    alert_on_level_break: bool = True
    alert_on_liquidity_sweep: bool = True
    alert_on_new_fvg: bool = True

    # LLM 补充
    auto_analyze: bool = False         # 触发后自动调 LLM

    # 推送
    push_channel: str = "feishu"
    cooldown_minutes: int = 15         # 同区域重复告警冷却
```

---

## 分阶段实施

考虑到 Monitor 模式的不确定性（Patrick 明确表达信心不大），分两个 Phase：

### Phase 1：SCHEDULED 模式（确定交付）

**目标：** 替代老版本，效率提升 80%+

**交付内容：**
- 9 种报告的完整 SCHEDULED 流水线
- Calculator + Confluence Scorer（纯代码）
- LLM 分析引擎（Skill 模块 + 自适应调用）
- Guardian 验证层
- 飞书推送 + SQLite 持久化
- Audit 异步反馈闭环

**成功标准：**
- 9 种报告全部正常运行
- 每日累计 LLM 调用时间 < 15 分钟
- Guardian 幻觉检测准确率 > 95%
- 连续运行 5 个交易日无故障

### Phase 2：MONITOR 模式（基于 Phase 1 验证后增强）

**目标：** 盘中实时告警

**前置条件（必须在 Phase 1 验证后才能做）：**
- Calculator 的 FVG 识别准确率已通过实际数据验证
- Confluence Scorer 的权重已通过 Audit 数据迭代
- MCP 轮询稳定性已测试

**交付内容：**
- Monitor Loop（定时轮询）
- 触发条件引擎
- 即时告警推送
- 冷却机制

**Phase 2 的主要风险：**

| 风险 | 应对 |
|------|------|
| MCP 长时间轮询断线 | 重试 + 健康检查，断线告警 |
| Calculator FVG 识别不准 | Phase 1 积累真实案例，Phase 2 前做回测 |
| 共振权重不合理 | Phase 1 的 Audit 数据用于权重调优 |
| 告警噪音太多 | cooldown + 等级阈值 + 实际运行迭代 |
| LLM 补充 90s 时效性差 | 承认局限：告警立即推，LLM 补充作为后续参考 |

---

## 为什么 Monitor 放到 Phase 2

1. **SCHEDULED 是必须品，MONITOR 是增强品。** 先把基础做稳。
2. **Phase 1 的运行数据是 Phase 2 的输入。** Calculator 准确率、权重合理性都需要真实数据验证。
3. **减少一次性工程风险。** 一次做太多容易哪里都不稳。

---

## 架构兼容性

双模式共用同一套基础模块，这是设计的隐含要求。Phase 1 的代码必须考虑 Phase 2 的扩展：

```
共用模块（Phase 1 就必须做好）：
  ├── Ingestion
  ├── Calculator
  ├── Confluence Scorer
  ├── Analysis Engine
  ├── Guardian
  ├── Dispatch
  └── Store (SQLite)

Phase 1 独占：
  └── Scheduler（cron 触发）

Phase 2 新增：
  ├── Monitor Loop（轮询调度）
  ├── Trigger Engine（触发条件）
  └── Alert Dispatcher（即时推送）
```

这意味着 Phase 1 的代码接口设计要考虑 Phase 2 会复用——不是写到 Phase 2 才改架构。
