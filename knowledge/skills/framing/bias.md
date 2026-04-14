# Bias — 方向判断

> **Layer：** Framing
> **依赖 Skills：** `framing/context.md`, `framing/narrative.md`
> **可选 Skills：** `targeting/pda_scan.md`（如果有 HTF PDA 扫描结果可加强判断）

---

## 1. 目的

在已有 Context（宏观环境）和 Narrative（市场故事）的基础上，产出明确的方向判断（LONG / SHORT / NEUTRAL）和置信度。

Bias 不是独立的"感觉"，而是多个独立信号**交叉确认**的产物。

---

## 2. 输入要求

### 数据
- NQ1! 的 D/H4 数据（最近 20 根 bars）
- DXY 的 D 数据（最近 10 根 bars）
- ES1! 的 D 数据（最近 10 根 bars，用于 SMT 确认）

### Calculator 输出
```
$calc.pdh, $calc.pdl                    # 前日高低
$calc.pwh, $calc.pwl                    # 前周高低
$calc.ipda_20d, $calc.ipda_40d, $calc.ipda_60d  # IPDA 三周期范围
$calc.current_price                     # 当前 NQ 价格
$calc.equilibrium_pdr                   # 前日范围均衡点
```

### 前置 Skill 结果
```
$context.ipda_position          # "premium" | "discount" | "equilibrium"
$context.htf_order_flow         # "bullish" | "bearish" | "neutral"
$context.cisd_status            # "confirmed_bullish" | "confirmed_bearish" | "none"
$narrative.po3_phase            # "accumulation" | "manipulation" | "distribution"
$narrative.mmxm_phase           # 同上或 "reversal"
$narrative.sequence_stage       # 当前 Sequence 阶段
```

---

## 3. 执行步骤

### Step 1: 收集独立方向信号

从 4 个独立维度收集信号，每个维度独立打分（Bullish / Bearish / Neutral）：

| 信号维度 | 判断方法 |
|---------|---------|
| **S1: IPDA 位置** | 价格在 Discount 区（<50%）→ Bullish 倾向；Premium 区（>50%）→ Bearish 倾向 |
| **S2: HTF 订单流** | 直接使用 `$context.htf_order_flow` |
| **S3: PO3/Sequence** | Distribution 阶段顺势；Manipulation 阶段逆势；Accumulation 阶段中性 |
| **S4: CISD** | `$context.cisd_status` 为 confirmed_bullish/bearish 则强信号 |

### Step 2: DXY 反向过滤

DXY 与指数反向相关：
- DXY 看空 + NQ 信号看多 → **确认看多**
- DXY 看多 + NQ 信号看空 → **确认看空**
- DXY 与 NQ 同向 → **信号降权**（相关性异常）

检查方法：比较 DXY 最近 5 根 D bars 的 close 趋势与 NQ 的方向。

### Step 3: SMT 背离检查

比较 NQ 和 ES 在相同时间点的高低点：
- NQ 创新低但 ES 没有 → NQ 的 SSL 已扫，**看多信号加强**
- NQ 创新高但 ES 没有 → NQ 的 BSL 已扫，**看空信号加强**
- 无背离 → 无额外信号

### Step 4: Candle Closure 确认

检查最近 1-2 根日线 K 线的关键行为：
- 在关键位（PDH/PDL/IPDA 边界）**上方收盘** → 看多确认
- 在关键位 **下方收盘** → 看空确认
- 长上影 + 小实体 + 在 Premium 区 → 看空确认
- 长下影 + 小实体 + 在 Discount 区 → 看多确认

### Step 5: 综合评分

将 S1-S4 的信号按方向合计：
- ≥ 3 个信号看多 + DXY/SMT 确认 → `LONG` 高置信
- ≥ 3 个信号看多但无 DXY/SMT 确认 → `LONG` 中置信
- 2 个信号看多 + 2 个看空/中性 → `NEUTRAL` 低置信
- 信号混乱（无清晰方向）→ `NEUTRAL` 低置信 + 触发门控

---

## 4. 判断规则

### 置信度定义

| 置信度 | 标准 |
|--------|------|
| HIGH | 4 个维度全部一致 + DXY 反向确认 + SMT 背离（或 Candle Closure 确认） |
| MEDIUM | 3 个维度一致 + 至少 1 个确认信号 |
| LOW | 2 个维度一致，但不足以否定对立信号 |
| NONE | 信号混乱或明显矛盾 |

### 关键规则

1. **5 日视野限制**（来自 2022 Mentorship）：Bias 的预测范围限制在未来 5 个交易日内。不预测更远。
2. **Bias 失效规则**：如果上一个 Bias 判断被明显违反（如看空时 ITH 被突破），必须承认错误，本次 Bias 重新判断。
3. **Seek & Destroy 避免**：如果 Narrative 识别为 Seek & Destroy 环境，Bias 直接设为 `NEUTRAL` 并触发 CAUTION。
4. **跨报告一致性**：Daily Bias 必须与 Weekly Bias 大方向一致。如果要逆转，必须给出明确的翻转理由（如 CISD 发生）。

---

## 5. 输出 Schema

```json
{
  "direction": "LONG | SHORT | NEUTRAL",
  "confidence": "HIGH | MEDIUM | LOW | NONE",
  "reasoning": "一段简短叙事，解释为什么是这个方向",
  "signal_breakdown": {
    "s1_ipda_position": "bullish | bearish | neutral",
    "s2_htf_order_flow": "bullish | bearish | neutral",
    "s3_po3_sequence": "bullish | bearish | neutral",
    "s4_cisd": "bullish | bearish | neutral"
  },
  "confirmations": {
    "dxy_alignment": "confirmed | neutral | conflicting",
    "smt_divergence": "bullish | bearish | none",
    "candle_closure": "bullish_confirmed | bearish_confirmed | none"
  },
  "reversal_from_previous": false,
  "reversal_reason": null,
  "gate_status": "PASS | CAUTION | FAIL"
}
```

---

## 6. 门控条件

| 情况 | gate_status | 后续 |
|------|------------|------|
| `direction=NEUTRAL` 且 `confidence=NONE` | **FAIL** | 流水线停止，不进入 Profiling |
| `direction=NEUTRAL` 且 `confidence=LOW` | **CAUTION** | 继续但后续 Skill 保守处理 |
| Seek & Destroy 环境 | **CAUTION** | 继续但标记"不建议执行" |
| 明确方向 + 置信度 ≥ MEDIUM | **PASS** | 正常推进 |

---

## 7. 红旗条件

以下情况 Bias 不做判断，直接输出 NEUTRAL + CAUTION：

1. **RF-001：FOMC 当日**（2PM 后高波动）
2. **RF-002：NFP 当日**（经济数据主导）
3. **RF-003：Inside Day 持续 3 天以上**（无方向性）
4. **RF-004：3 PDA 连续失败**（前序判断系统性失效）
5. **RF-005：DXY 与指数同向 3 天以上**（相关性断裂）

---

## 8. 知识来源

本 Skill 整合自以下原始资料：

- **ICT 2022 Mentorship Notes** (43 页)：5 日视野限制、Bias 失效规则
- **Mastering Institutional Orderflow**：DXY 反向过滤、IOF 确认
- **Bias_to_Execution** (15 页)：完整周的 Bias 演示、CISD 确认方法
- **MMXMTrader_The Sequence** (35 页)：Sequence 阶段对方向的影响
- **Advanced ICT Concepts Explained** (89 页)：IPDA 位置与方向
- **2023 ICT Mentorship GEMS**：3 PDA 失败规则、Event Horizon
- **Unlocking Success in ICT 2022 Mentorship** (407 页)：PO3 日内框架

对应审计文档：`docs/research/ict-knowledge-audit.md` 的 Layer 1: FRAMING 部分。
