# DR-003：分析效率策略 — 自适应调用模式

**日期：** 2026-04-14
**状态：** 已接受
**决策者：** Patrick（授权自主执行）

---

## 问题

重构版 5 步流水线的效率问题：

| 报告类型 | 步骤数 | Claude CLI 调用次数 | 估算时间 |
|----------|--------|---------------------|----------|
| weekly_prep | 1 | 1 | ~79s |
| daily_bias | 2 | 2 | ~158s |
| asia_pre | 2 | 2 | ~158s |
| nyam_pre | 5 | 5 | ~393s |

**核心矛盾：** 步骤分离提供了门控和验证能力，但 5 次串行调用的开销巨大。原版单次 mega-prompt 虽然上下文大，但对于简单报告反而更快。

---

## 决策：自适应调用模式（Adaptive Call Strategy）

不固定"N 步 = N 次调用"，而是根据报告复杂度选择调用策略：

### 策略 1：单步合并模式（Simple Reports）

**适用：** weekly_prep, daily_bias, asia_pre, london_pre, nypm_pre

这些报告不产生交易信号，不需要 LTF Execution 和 Signal Output。将多个分析维度合并到一次 Claude CLI 调用中，通过 prompt 结构引导输出的分段性。

```
数据 → [单次 Claude 调用，prompt 含多段分析指令] → 结构化 JSON → Guardian → Dispatch
```

**效率目标：** 1 次调用 / 报告，耗时 ~60-90s

**prompt 设计：**
```
你是 ICT 交易分析师。请按照以下步骤分析，每步输出到对应 JSON 字段：

## Step 1: Weekly Context（仅当需要时）
[weekly narrative 指令...]

## Step 2: Daily Bias
[daily bias 指令...]

## Step 3: Session Analysis（仅当需要时）
[session 指令...]

请输出以下 JSON 格式：
{
  "weekly_context": { ... },  // 如果适用
  "daily_bias": { ... },
  "session": { ... },         // 如果适用
  "gate_status": "PASS|FAIL|NO_TRADE|CAUTION",
  "caution_flags": [...]
}
```

**关键：** 虽然是单次调用，但 prompt 保持分步结构。模型的分析逻辑仍然是分层的（先 weekly → 再 daily → 再 session），只是不再拆成多次调用。

### 策略 2：两阶段模式（Signal Reports）

**适用：** nyam_pre, nyam_open

这些报告可能产生交易信号，需要精确的入场/止损/止盈。分两次调用：

```
数据 → [调用 1: 分析 + 方向判断] → 门控检查 → [调用 2: 精确执行信号] → Guardian → Dispatch
```

**Stage 1（分析阶段）：** 合并 Weekly Context + Daily Bias + Session Analysis → 方向判断 + 门控状态
- 如果 FAIL/NO_TRADE → 停止，不进入 Stage 2
- 如果 PASS/CAUTION → 进入 Stage 2

**Stage 2（执行阶段）：** LTF Execution + Signal Output → 精确入场位
- 输入：Stage 1 的方向和关键位 + 低时间框架数据
- 输出：入场/止损/止盈/A+ 清单评分

**效率目标：** 1-2 次调用 / 报告（FAIL 时仅 1 次），耗时 ~60-150s

### 策略 3：审计模式（Review Reports）

**适用：** daily_review, weekly_review

不调用 Claude CLI，纯代码执行：
- 从 SQLite 读取当日预测
- 从 MCP 获取实际价格
- Scorer 代码级评分
- FeedbackGenerator 生成反馈

**效率目标：** 0 次 Claude 调用，耗时 <10s

---

## 效率对比

| 报告类型 | 重构版（5步） | Michael（自适应） | 节省 |
|----------|:---:|:---:|:---:|
| weekly_prep | 1 次 / ~79s | 1 次 / ~70s | ~10% |
| daily_bias | 2 次 / ~158s | 1 次 / ~80s | **~50%** |
| asia_pre | 2 次 / ~158s | 1 次 / ~70s | **~56%** |
| london_pre | 2 次 / ~158s | 1 次 / ~70s | **~56%** |
| nyam_pre | 5 次 / ~393s | 2 次 / ~150s | **~62%** |
| nypm_pre | 2 次 / ~158s | 1 次 / ~70s | **~56%** |
| daily_review | 1 次 / ~79s | 0 次 / ~5s | **~94%** |
| **日均总计** | ~14 次 / ~1263s | ~7 次 / ~535s | **~58%** |

---

## Token 预算策略

不是简单的"按类别过滤"，而是按报告类型精确配置 token 预算：

| 报告类型 | 知识预算 | 数据预算 | 历史预算 | 总预算 |
|----------|----------|----------|----------|--------|
| weekly_prep | 8K（IPDA/框架） | 6K（全 TF） | 2K（上周回顾） | ~16K |
| daily_bias | 6K（PO3/DOL） | 4K（D/H4/H1） | 2K（周分析引用） | ~12K |
| asia_pre | 4K（Session） | 3K（H1/M15） | 2K（日分析引用） | ~9K |
| nyam_pre Stage 1 | 6K（Session+执行） | 4K（H1/M15/M5） | 3K（日+前 Session） | ~13K |
| nyam_pre Stage 2 | 4K（入场模型） | 3K（M5/M1） | 2K（Stage 1 结果） | ~9K |

**实现方式：** PromptBuilder 接收 token_budget 参数，按优先级裁剪知识上下文。

---

## Guardian 在自适应模式下的工作方式

合并模式不改变 Guardian 的检查逻辑——Guardian 检查的是输出结构，不关心产生输出的调用次数。

| 检查 | 合并模式 | 两阶段模式 |
|------|----------|-----------|
| 一致性 | 检查输出 JSON 中各段之间的一致性 | Stage 1 和 Stage 2 之间的一致性 |
| 幻觉 | 同现有逻辑 | 同现有逻辑 |
| 规则合规 | 同现有逻辑 | 同现有逻辑 |
| 模板合规 | 验证合并后的 JSON 结构 | 分别验证两阶段 |

**中间门控（两阶段模式独有）：** Stage 1 输出 gate_status，代码检查后决定是否进入 Stage 2。这是代码级门控，不是模型自判。

---

## 对 Harness 原则的影响

| 原则 | 影响 | 应对 |
|------|------|------|
| 验证独立 | 无影响，Guardian 仍然代码级检查 | — |
| 门控控制 | 合并模式下门控在调用后而非步骤间 | 通过 JSON 输出的 gate_status 字段实现 |
| 错误恢复 | 调用次数减少 = 失败点减少 | 正面影响 |
| 上下文预算 | token 预算精确到报告类型 | 正面影响 |

**关键结论：** 自适应模式不牺牲 Harness 纪律，反而因为减少了调用次数而降低了系统复杂度和失败概率。
