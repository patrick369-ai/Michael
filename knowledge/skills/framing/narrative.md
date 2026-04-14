# Narrative — 市场叙事构建

> **Layer：** Framing
> **依赖 Skills：** `framing/context.md`
> **可选 Skills：** `profiling/weekly_profile.md`（可选，如果已有）

---

## 1. 目的

基于 Context 推导当前市场的"故事"——通过 PO3 / The Sequence / MMXM 三个视角，判断市场正在执行什么算法程序，当前处于什么阶段。

Narrative 回答的是"为什么价格会这样走"，而不是"价格下一步去哪"。方向判断在 Bias Skill。

---

## 2. 输入要求

### 数据
- NQ1! 的 Weekly/Daily 数据（最近 20 根）
- NQ1! 的 H4/H1 数据（最近 30 根，用于 Sequence 识别）

### Calculator 输出
```
$calc.pdh, $calc.pdl, $calc.pwh, $calc.pwl
$calc.equilibrium_pdr, $calc.equilibrium_pwr
$calc.ipda_20d
$calc.current_price
$calc.fvgs_by_tf    # 各 TF 的 FVG（用于 CISD 确认）
```

### 前置 Skill
```
$context.ipda_position
$context.htf_order_flow
$context.cisd_status
$context.erl_irl_cycle
```

---

## 3. 执行步骤

### Step 1: PO3 日线阶段识别

对最近的 Daily candle 分析 PO3 (Power of Three)：

- **Accumulation：** 开盘附近窄幅震荡，无明显方向
- **Manipulation：** 价格反向 Judas Swing（假突破），目的是扫流动性
- **Distribution：** 真实方向性移动，朝向 DOL

判断当前日线在哪个阶段。如果今日尚未结束，基于已有 bars 判断。

### Step 2: The Sequence 识别

选择适用的 Sequence 类型：

**Sequence 1（Monthly → Weekly → H4）**：
- 条件：当前在接近 Monthly 级别关键位
- 判断：是否已发生 PMH/PML 扫荡？Weekly 是否已确认 CISD？

**Sequence 2（Weekly → Daily → Session → M15/H1）**：
- 条件：日内分析场景（大多数情况）
- 判断：周级关键位 → 日级扫荡 → Session 扫荡 → LTF 入场

识别当前处于 Sequence 的哪一步。

### Step 3: MMXM 阶段识别

MMXM 的 4 阶段（从 HTF 角度）：

| 阶段 | 特征 |
|------|------|
| **Original Consolidation** | 大区间震荡，建仓阶段 |
| **Engineering Liquidity** | 故意制造高/低，吸引反向仓位 |
| **Smart Money Reversal (SMR)** | 在关键位反转 |
| **Distribution/Re-accumulation** | 真实方向移动，到达 DOL |

### Step 4: 综合叙事

将 PO3 + Sequence + MMXM 编织成一段连贯的叙事：

- "市场上周在 IPDA Premium 区创新高（Engineering Liquidity），本周一 Judas Swing 继续向上扫 PWH，然后日线 CISD 确认反转，现在处于 Sequence 2 的 Daily Distribution 阶段，Session 级别正在构建扫荡..."

---

## 4. 判断规则

### PO3 阶段推导

| 当前日 Open 位置 | Session 行为 | 可能 PO3 阶段 |
|-----------------|-------------|--------------|
| 接近昨日高 | Asia 继续上行 | Distribution 向上 |
| 接近昨日高 | Asia 下探后反弹 | Manipulation（向下 Judas） |
| 昨日范围中间 | Asia 窄幅 | Accumulation |
| 接近昨日低 | Asia 继续下行 | Distribution 向下 |

### Sequence 完整性检查

一个完整的 Sequence 要求：
1. HTF 目标明确（Draw on Liquidity）
2. 一级扫荡（如 PWH）+ Candle Closure 确认
3. 可能的 Session 扫荡
4. LTF 入场触发

如果只有步骤 1 和 2，是"Sequence 进行中"；全部完成则"Sequence 完成"。

### MMXM 与 PO3 的对应

- MMXM Engineering ≈ PO3 Manipulation
- MMXM Distribution ≈ PO3 Distribution
- MMXM SMR 是 Engineering 的结束点

---

## 5. 输出 Schema

```json
{
  "po3_phase": "accumulation | manipulation | distribution | unclear",
  "po3_reasoning": "why this phase based on daily candle behavior",
  "sequence_type": "sequence_1 | sequence_2 | none",
  "sequence_stage": "draw_identified | liquidity_swept | closure_confirmed | session_setup | ltf_entry | completed",
  "sequence_details": "step-by-step description",
  "mmxm_phase": "consolidation | engineering | smr | distribution | reversal | none",
  "narrative_summary": "综合故事（2-3 句话）",
  "next_likely_action": "市场最可能的下一步（非 Bias 判断）",
  "gate_status": "PASS | CAUTION"
}
```

---

## 6. 门控条件

| 情况 | gate_status |
|------|------------|
| 无清晰叙事（三个视角都 `unclear`） | **CAUTION** |
| 至少 PO3 或 Sequence 清晰 | **PASS** |

---

## 7. 红旗条件

- 如果 Narrative 识别为"Market Maker Trap 特征"（多次假突破 + 无明确方向），标记 `RF-TRAP`

---

## 8. 知识来源

- **MMXMTrader_The Sequence**: Sequence 1/2 完整流程
- **MMXMTrader_Handbook**: MMXM 4 阶段
- **Advanced ICT Concepts**: PO3 详解
- **Unlocking Success in ICT 2022**: Ch.13 PO3 日内框架
- **Bias_to_Execution**: 叙事实战演示
- **ICT 2022 Mentorship Notes**: PO3 简化版（accumulation/manipulation/distribution）

对应审计：`ict-knowledge-audit.md` Layer 1 - Narrative
