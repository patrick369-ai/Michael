# Daily Profile — 日内行为模板识别

> **Layer：** Profiling
> **依赖 Skills：** `framing/bias.md`, `profiling/weekly_profile.md`
> **可选 Skills：** `profiling/session_role.md`（反向引用）

---

## 1. 目的

基于 Daily Bias 和 London Session 的行为，预测 NY Session 的角色。来源于 `ICT Daily Profiles` 的 3 种高概率 Profile。

**关键前提：** Daily Profile 不创建 bias，它确认 bias。必须先有明确的 Daily Bias。

---

## 2. 输入要求

### 数据
- NQ1! 的 H1/M15 数据（最近 24 小时）
- Calculator 已计算的 Session 范围

### Calculator 输出
```
$calc.asia_range
$calc.london_range
$calc.pdh, $calc.pdl
$calc.current_price
```

### 前置 Skill
```
$bias.direction           # 必须为 LONG 或 SHORT（NEUTRAL 时不运行此 Skill）
$bias.confidence          # 至少 MEDIUM
$weekly_profile.matched_profile
```

---

## 3. 执行步骤

### Step 1: 验证 Bias 前提

如果 `$bias.direction == NEUTRAL`，跳过此 Skill，输出 `profile_applicable: false`。

### Step 2: 分析 London Session 行为

检查 London Session (2-5 AM ET) 已发生的行为：

- **London 是否创建了日高/日低？**
- **London 是否在 1H 关键位形成反转？**
- **London 是否与 Daily Bias 一致？**
- **London 范围大小？（窄 = 可能是 consolidation，宽 = 已发生 impulse）**

### Step 3: 匹配 3 种高概率 Profile

#### Profile 1: London Reversal → NY Continuation

**Bullish 版本（Daily Bias = LONG）：**
- London 在日内开盘下方创建 LOW（1H 关键位或之上）
- SMT/CISD 确认
- London LOW 成为"受保护的低点"，NY 不应跌破
- NY 回撤到 London 期间的 PDA，然后继续上涨

**Bearish 版本（Daily Bias = SHORT）：**
- London 在日内开盘上方创建 HIGH
- SMT/CISD 确认
- London HIGH 受保护，NY 回撤后继续下跌

**识别特征：** London 完成反转工作，NY 只需延续

#### Profile 2: NY Reversal

**Bullish 版本：**
- Daily Bias = LONG
- London 尝试下探到 1H 关键位但**未到达**（London 只是震荡或未触及）
- NY 开盘后创建日低（到达 1H 关键位）
- CISD 确认
- NY 余下时间上涨分发

**Bearish 版本：** 反之

**识别特征：** London 没完成反转，NY 接手完成

#### Profile 3: NY Manipulation

- London 形成 **consolidation range**（无方向性扩张）
- NY 扫荡 London 范围（做多 Bias 时扫下方，做空时扫上方）
- SMT/CISD 在关键位确认
- 价格向 Daily Bias 方向扩张

**识别特征：** London 横盘，NY 来做"真事"

### Step 4: 确定 NY Session 的角色

基于匹配的 Profile，NY 的角色：

| Profile | NY 角色 |
|---------|---------|
| Profile 1 | **Continuation**（延续 Daily Bias） |
| Profile 2 | **Reversal**（NY 创建日内极值后反转） |
| Profile 3 | **Manipulation + Expansion**（先扫荡后扩张） |

---

## 4. 判断规则

### Profile 失效条件

**如果 London 已经朝 Daily Bias 方向大幅扩张**：
- 标记为 "High-Resistance Liquidity Run"
- 当天概率低，不推荐交易
- 等待次日或 Consolidation Reversal

### 关键位识别

1H 关键位指：
- PDH/PDL
- PWH/PWL
- HTF FVG/OB/Breaker
- IPDA 范围边界

---

## 5. 输出 Schema

```json
{
  "profile_applicable": true,
  "matched_profile": "London Reversal -> NY Continuation | NY Reversal | NY Manipulation | Low Probability",
  "bullish_or_bearish": "bullish | bearish",
  "confidence": "HIGH | MEDIUM | LOW",
  "london_behavior": {
    "created_daily_extreme": true/false,
    "extreme_type": "high | low | none",
    "touched_1h_key_level": true/false,
    "range_size_category": "narrow | normal | wide"
  },
  "ny_expected_role": "continuation | reversal | manipulation_expansion | low_probability",
  "protected_level": "price level NY should not break",
  "key_levels_to_watch": ["price1", "price2"],
  "gate_status": "PASS | CAUTION | FAIL"
}
```

---

## 6. 门控条件

| 情况 | gate_status |
|------|------------|
| `profile_applicable=false` (Bias NEUTRAL) | **FAIL** |
| `matched_profile=Low Probability` | **CAUTION** |
| London 已大幅扩张 DOL 方向 | **CAUTION** |
| 正常匹配 | **PASS** |

---

## 7. 红旗条件

- `RF-HRLR`: High-Resistance Liquidity Run（London 已完成 DOL 方向的大部分工作）

---

## 8. 知识来源

- **ICT Daily Profiles** (主要来源，由 @murutrades 撰写)
- **Unlocking Success in ICT 2022**: Ch.26 Daily Templates
- **PRE-MARKET-PLAN (Lumi Trader)**: Asia-London 规则

对应审计：`ict-knowledge-audit.md` Layer 2 - Daily Profile
