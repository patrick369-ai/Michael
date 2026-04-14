# Context — 宏观环境判断

> **Layer：** Framing
> **依赖 Skills：** 无（起点 Skill）
> **可选 Skills：** 无

---

## 1. 目的

判断当前市场所处的宏观环境：价格在 IPDA 范围内的位置、HTF 订单流方向、CISD 状态，以及 ERL↔IRL 循环当前阶段。

Context 是所有分析的起点。错误的 Context 会导致整个分析链失效。

---

## 2. 输入要求

### 数据
- NQ1! 的 Monthly/Weekly/Daily 数据（最近 60 根 bars）

### Calculator 输出
```
$calc.current_price
$calc.pdh, $calc.pdl, $calc.equilibrium_pdr
$calc.pwh, $calc.pwl, $calc.equilibrium_pwr
$calc.ipda_20d, $calc.ipda_40d, $calc.ipda_60d
$calc.ipda_position   # "premium" | "discount" | "equilibrium"
```

---

## 3. 执行步骤

### Step 1: 确认 IPDA 位置

Calculator 已提供 `ipda_position`，基于 20 日范围。补充分析：

- 在 40 日范围中是什么位置？
- 在 60 日范围中是什么位置？
- 三个周期是否一致？（一致 = 高置信）

### Step 2: 判断 HTF 订单流方向

在 Weekly 和 Daily 时间框架观察：

- **Bullish：** 连续更高的 HH 和 HL（Higher Highs + Higher Lows）
- **Bearish：** 连续更低的 LH 和 LL（Lower Highs + Lower Lows）
- **Neutral：** 区间震荡、混合结构

### Step 3: 检查 CISD（Change in State of Delivery）

CISD 是市场结构转换的核心确认：

- **Bullish CISD：** 一个 BISI（Bullish FVG）被价格穿透并收盘下方 → 说明之前的看多分发失效
- **Bearish CISD：** 一个 SIBI（Bearish FVG）被价格穿透并收盘上方 → 说明之前的看空分发失效
- **检查时间框架：** 优先 Daily，其次 H4

如果最近 5 日内有 CISD 发生，标记 `cisd_status`。

### Step 4: 识别 ERL↔IRL 循环阶段

ICT 方法论的核心循环：价格从外部流动性（ERL）→ 内部流动性（IRL）→ 回到 ERL。

- **扫 ERL 后回撤到 IRL：** 价格先扫了外部流动性（旧高/旧低），现在回撤填充内部流动性（FVG）
- **从 IRL 出发指向 ERL：** 当前在 IRL 区域，目标是外部流动性

这决定了 DOL 的类型和路径。

---

## 4. 判断规则

### IPDA 位置的含义

| 位置 | 倾向 | 注意事项 |
|------|------|----------|
| Premium（>50%） | 寻找做空机会 | HTF 订单流若为看空则加强，若为看多则谨慎 |
| Discount（<50%） | 寻找做多机会 | 同上反向 |
| Equilibrium（接近 50%） | 等待确认 | 方向不明，需要 HTF 订单流 + CISD 配合 |

### 三周期一致性

- 20/40/60 日三个 IPDA 位置全部一致 → **HIGH** 置信度
- 两个一致 → **MEDIUM**
- 混乱 → **LOW**，Context 标记不清晰

---

## 5. 输出 Schema

```json
{
  "ipda_position": "premium | discount | equilibrium",
  "ipda_consistency": "high | medium | low",
  "ipda_details": {
    "20d": "premium | discount | equilibrium",
    "40d": "premium | discount | equilibrium",
    "60d": "premium | discount | equilibrium"
  },
  "htf_order_flow": "bullish | bearish | neutral",
  "htf_structure_notes": "observations about HH/HL or LH/LL",
  "cisd_status": "confirmed_bullish | confirmed_bearish | none",
  "cisd_details": "which timeframe, which FVG inverted, when",
  "erl_irl_cycle": "swept_erl_now_irl | in_irl_targeting_erl | deep_in_irl | external_expansion",
  "narrative_summary": "一段话概括当前宏观环境",
  "gate_status": "PASS | CAUTION"
}
```

---

## 6. 门控条件

| 情况 | gate_status |
|------|------------|
| `ipda_consistency=low` + `htf_order_flow=neutral` | **CAUTION**（宏观环境不清晰） |
| 清晰的 HTF 订单流 + CISD 确认 | **PASS** |
| 其他 | **PASS** |

---

## 7. 红旗条件

- Context Skill 不直接触发红旗，但 `ipda_consistency=low` 会传导到下游 Bias Skill 降低置信度。

---

## 8. 知识来源

- **MMXMTrader_Handbook**: LTP 框架（Monthly/Weekly/Daily）
- **Bias_to_Execution**: IPDA 20 日范围应用
- **Advanced ICT Concepts Explained**: HTF 订单流识别
- **All ICT PD Arrays**: CISD 定义与识别
- **Mastering Institutional Orderflow**: IOF 作为 HTF 方向确认工具

对应审计：`ict-knowledge-audit.md` Layer 1 Framing - Context
