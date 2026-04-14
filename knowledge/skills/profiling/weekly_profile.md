# Weekly Profile — 周度行为模板识别

> **Layer：** Profiling
> **依赖 Skills：** `framing/bias.md`
> **可选 Skills：** `framing/narrative.md`

---

## 1. 目的

基于周内已发生的价格行为，匹配到 ICT 的周度模板之一，预测本周剩余交易日的走势。

来源于 `Mastering Weekly Profiles` 的 3 种高概率 Profile + `ICT_Advisor Playbook` 的扩展版 12 模板。

---

## 2. 输入要求

### 数据
- NQ1! 的 Daily 数据（本周 + 前周共 10 根 bars）
- NQ1! 的 Weekly 数据（最近 4 根）

### Calculator 输出
```
$calc.pwh, $calc.pwl, $calc.equilibrium_pwr
$calc.current_price
$calc.ipda_20d
```

### 前置 Skill
```
$bias.direction            # 本周大方向
$bias.confidence
$narrative.sequence_type   # 用于判断 Profile 的匹配
```

### 上下文
```
current_day_of_week        # Monday / Tuesday / Wednesday / Thursday / Friday
weekly_open_price          # 本周一开盘价
```

---

## 3. 执行步骤

### Step 1: 标记本周关键事件

统计本周已发生的关键事件：
- 周高形成时间？周低形成时间？
- 是否已触及 PWH/PWL？
- 周一是否有 Judas Swing？
- DXY 是否同向？

### Step 2: 匹配 3 种高概率 Profile（优先）

这是最常见且可操作的 3 种：

#### Profile 1: Classic Expansion Week
- **Bullish 版本：** 周一/二形成周低，周三-五扩张向上。OLHC 结构。
- **Bearish 版本：** 周一/二形成周高，周三-五扩张向下。OHLC 结构。
- **识别：** 周一/二有明确的高/低形成，后续天数延续方向
- **含义：** 周三-五是主要交易日，顺势

#### Profile 2: Mid-Week Reversal
- **Bullish 版本：** 周一/二走低（Judas Swing），周三触及折价 PDA 反转，周四-五上涨
- **Bearish 版本：** 周一/二走高，周三触及溢价 PDA 反转，周四-五下跌
- **识别：** 周一/二方向与大方向相反，周三出现 4H+ PDA 反应
- **含义：** 周三是关键反转日

#### Profile 3: Consolidation Reversal
- **识别：** 周一至周三紧窄震荡，周四/五突破
- **含义：** 周四/五是唯一方向性天

### Step 3: 扩展 12 模板匹配（次要）

如果 3 种高概率 Profile 都不匹配，检查扩展模板：

4. Classic Tuesday Low / High
5. Wednesday Low / High
6. Thursday Reversal
7. Midweek Rally / Decline
8. Seek & Destroy
9. Friday Profile
10. Wednesday Weekly Reversal
11. Consolidation（整周窄幅）
12. Expansion（周一跳空 + 单向运行全周）

### Step 4: 预测本周剩余天数

基于匹配的 Profile，预测：
- 剩余天数的方向倾向
- 关键反转/扩张日
- 本周目标价位（PWH/PWL/更远）

---

## 4. 判断规则

### Profile 匹配的置信度

| 条件 | 置信度 |
|------|--------|
| 周内行为完全符合 Profile 定义 | HIGH |
| 大致符合但有 1-2 个偏差 | MEDIUM |
| 只符合部分特征 | LOW |
| 多个 Profile 都可能 | UNCLEAR |

### Seek & Destroy 特殊处理

如果识别为 Seek & Destroy Profile（整周双边扫荡、无方向）：
- 直接触发 `gate_status = CAUTION`
- Bias 可能需要重新评估
- 不推荐交易

---

## 5. 输出 Schema

```json
{
  "matched_profile": "Classic Expansion | Mid-Week Reversal | Consolidation Reversal | ... | Seek & Destroy",
  "direction": "bullish | bearish | neutral",
  "confidence": "HIGH | MEDIUM | LOW | UNCLEAR",
  "matching_reasoning": "why this profile matches",
  "key_observations": {
    "weekly_open": "price",
    "weekly_high_day": "Monday | Tuesday | ... | pending",
    "weekly_low_day": "Monday | Tuesday | ... | pending",
    "pwh_touched": true/false,
    "pwl_touched": true/false
  },
  "remaining_days_forecast": {
    "direction": "bullish | bearish | neutral",
    "key_reversal_day": "Wednesday | Thursday | ... | null",
    "target_levels": ["PWH", "PWL", "xxx"]
  },
  "gate_status": "PASS | CAUTION"
}
```

---

## 6. 门控条件

| 情况 | gate_status |
|------|------------|
| 匹配 Seek & Destroy | **CAUTION** |
| `confidence=UNCLEAR` | **CAUTION**（可继续但降低仓位倾向） |
| 其他匹配 | **PASS** |

---

## 7. 红旗条件

- `RF-SEEK-DESTROY`: 识别为 Seek & Destroy 周

---

## 8. 知识来源

- **Mastering Weekly Profiles to Determine Your Daily Bias** (主要来源)
- **ICT_Advisor Playbook**: 12 模板扩展
- **Unlocking Success in ICT 2022**: Ch.12 Weekly Profile
- **ict_trading_learning**: M04 周 Profile 相关视频

对应审计：`ict-knowledge-audit.md` Layer 2 Profiling - Weekly Profile
