# Session Role — Session 角色判断

> **Layer：** Profiling
> **依赖 Skills：** `framing/bias.md`, `profiling/daily_profile.md`
> **可选 Skills：** `profiling/weekly_profile.md`

---

## 1. 目的

判断当前分析的 Session 在日内扮演什么角色（建范围/冲击/续行/反转/分发），以及在 NY PM 特殊情况下匹配 T1/T2/T3 模板。

---

## 2. 输入要求

### 数据
- NQ1! 的 M15/M5 数据（当前 Session + 前序 Session）

### Calculator 输出
```
$calc.asia_range, $calc.london_range, $calc.ny_am_range, $calc.ny_pm_range
$calc.current_price
```

### 前置 Skill
```
$bias.direction
$daily_profile.matched_profile
$daily_profile.ny_expected_role
```

### 上下文
```
current_session: "asia | london_open | ny_am | ny_pm"
```

---

## 3. 执行步骤

### Step 1: 确认当前 Session

基于 `current_session` 上下文确定正在分析的 Session。

### Step 2: 查看前序 Session 结果

检查前序 Session 的实际行为（是否与预期一致）：

- **Asia**：建立了范围？方向如何？
- **London**：扫荡了 Asia 高/低？创建了日极值？
- **NY AM**（分析 NY PM 时）：方向如何？是否到达 HTF 目标？

### Step 3: 匹配 Session 角色

#### Asia Session 角色
- **Range Building**（最常见）：窄幅震荡，为 London 制造流动性
- **Continuation**：延续前日方向
- **Breakout Day**：前日是 Inside Day，Asia 可能是突破 Session

#### London Session 角色
基于 Daily Profile 预期：
- **Reversal（创建日极值）**：London 在关键位反转
- **Expansion**：London 直接扩张 Daily Bias 方向
- **Failure**：London 未完成预期工作，NY 接手

#### NY AM Session 角色
- **Continuation**：延续 London 方向
- **Reversal**：NY 创建日极值（Profile 2）
- **Manipulation + Expansion**：扫 London 范围后扩张（Profile 3）

#### NY PM Session 角色（特殊：T1/T2/T3）

NY PM 的角色匹配 3 种模板：

| 模板 | AM 表现 | HTF 目标 | PM 行为 |
|------|---------|----------|---------|
| **T1** | 强方向性 | **已达到** | 反转 |
| **T2** | 强方向性 | **未达到** | 延续 |
| **T3** | 震荡无方向 | - | 发起方向性移动 |

---

## 4. 判断规则

### 角色与 Bias 对齐检查

Session 角色应该与 Daily Bias 方向一致。如果偏离：
- 必须有明确理由（如 CISD 刚发生、Profile 1 的 Reversal 结构）
- 否则标记 `CAUTION: session_bias_conflict`

### T3 的特殊判断（NY PM）

T3 是 NY PM 唯一创造方向的场景，条件严苛：
- AM 必须真正震荡（不只是慢速趋势）
- AM 未触及任何 HTF 关键位
- PM 开盘（1:30 PM ET）附近有流动性扫荡

---

## 5. 输出 Schema

```json
{
  "session": "asia | london_open | ny_am | ny_pm",
  "role": "range_building | continuation | reversal | manipulation_expansion | expansion | failure",
  "bias_alignment": "aligned | deviation_justified | conflicting",
  "prior_session_review": {
    "session_name": "...",
    "actual_behavior": "...",
    "met_expectation": true/false
  },
  "pm_template_match": "T1 | T2 | T3 | null (仅 NY PM)",
  "key_levels_formed": ["list of new key levels"],
  "expected_behavior": "one-sentence summary",
  "gate_status": "PASS | CAUTION"
}
```

---

## 6. 门控条件

| 情况 | gate_status |
|------|------------|
| Session 角色与 Bias 严重冲突且无合理理由 | **CAUTION** |
| T3 但条件不满足 | **CAUTION** |
| 正常匹配 | **PASS** |

---

## 7. 红旗条件

- `RF-SESSION-CONFLICT`: Session 角色与 Bias 无理由冲突

---

## 8. 知识来源

- **ICT Daily Profiles**: 3 种 Profile 的 Session 角色
- **Unlocking Success in ICT 2022**: Ch.28 Hours of Operation
- **ICT_Advisor Playbook**: Session 角色与 T1/T2/T3
- **ict_trading_learning**: 4 种 London Profile 的变体

对应审计：`ict-knowledge-audit.md` Layer 2 - Session Role
