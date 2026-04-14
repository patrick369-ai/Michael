# DOL Framework — Draw on Liquidity 三问框架

> **Layer：** Targeting
> **依赖 Skills：** `framing/bias.md`, `targeting/pda_scan.md`
> **可选 Skills：** `framing/context.md`

---

## 1. 目的

用 Q1 / Q2 / Q3 三问框架系统地判断价格目标（DOL）：价格从哪来？现在在哪？要去哪？

DOL 是决定 Entry Model 和 TP 的核心。没有 DOL 就没有交易。

---

## 2. 输入要求

### Calculator 输出
```
$calc.current_price
$calc.pdh, $calc.pdl, $calc.pwh, $calc.pwl
$calc.ipda_20d, $calc.ipda_40d, $calc.ipda_60d
$calc.eqh_list, $calc.eql_list      # 流动性池
$calc.fvgs_by_tf                    # 所有 FVG
```

### 前置 Skill
```
$bias.direction
$context.ipda_position
$context.erl_irl_cycle
$pda_scan.pda_zones                 # 已扫描的 PDA 列表
```

---

## 3. 执行步骤

### Q1: Where from? — 价格从哪来？

回答最近的结构起点：

- 当前行情的最近高点/低点是什么？
- 那个点是扫了什么流动性形成的（旧高/旧低/EQH/EQL）？
- 从那里到现在发生了什么（扫荡/位移/CISD）？

输出一段简短的"来源故事"。

### Q2: Where now? — 价格现在在哪？

用多个维度定位当前价：

- 在 IPDA 20D 范围的什么位置？（Premium / Discount / Equilibrium）
- 在 PWR（前周范围）的什么位置？
- 在 PDR（前日范围）的什么位置？
- 附近有什么 PDA/Key Levels？（距离 5% 内）

### Q3: Where to? — 价格要去哪？

基于 Q1、Q2 和 Bias 判断：

- **ERL（外部流动性）候选：**
  - PWH / PWL
  - PDH / PDL
  - IPDA 20D 范围边界
  - EQH / EQL 集群
  - 未填充的 NWOG / NDOG

- **IRL（内部流动性）候选：**
  - HTF FVG（未填充）
  - 关键 PDA 区域

**选择 DOL 的原则：**

1. **与 Bias 一致**：如果 Bias = LONG，DOL 应在上方
2. **ERL↔IRL 循环**：如果刚扫了 ERL，下一步目标通常是 IRL；在 IRL 中应指向 ERL
3. **最近的未完成目标**：优先选择最近未被触及的流动性池
4. **层级原则**：Weekly 目标 > Daily 目标 > Session 目标（HTF 优先）

### Step 4: 确定路径

DOL 不只是终点，还包括路径：

- 会经过哪些中间 PDA？
- 哪些中间点可能有阻力/支撑？
- 预估路径的时间尺度（当日/本周）

---

## 4. 判断规则

### DOL 优先级

当有多个候选 DOL 时，按以下规则：

1. **Unclaimed Liquidity 优先**：多次触及未真正扫荡的 EQH/EQL，或明显的 PMH/PML
2. **距离合理**：太近（<10 点）不算目标；太远（>5%）优先级低
3. **HTF 强度**：Weekly 级 DOL > Daily 级 > H4 级

### 冲突处理

如果存在多个符合条件的 DOL：
- 主要 DOL：最重要的那个
- 次要 DOL：作为分段目标（TP1/TP2 参考）

---

## 5. 输出 Schema

```json
{
  "q1_where_from": {
    "recent_high_or_low": "price (swing type)",
    "liquidity_swept": "what was taken (PDH/PWH/EQH/etc)",
    "story": "one-sentence description"
  },
  "q2_where_now": {
    "ipda_20d_position": "premium | discount | equilibrium",
    "in_pwr": "premium | discount | equilibrium",
    "in_pdr": "premium | discount | equilibrium",
    "nearby_pdas": ["list"]
  },
  "q3_where_to": {
    "primary_dol": {
      "type": "ERL | IRL",
      "level_name": "PWL | PDH | IPDA 60D High | etc",
      "price": 21320,
      "distance_points": 143,
      "priority": "S | A | B"
    },
    "secondary_dols": [
      {
        "type": "ERL | IRL",
        "level_name": "...",
        "price": 21380,
        "priority": "..."
      }
    ]
  },
  "path": {
    "intermediate_pdas": ["list of expected reactions along the way"],
    "time_horizon": "intraday | multi-day | weekly"
  },
  "erl_irl_stage": "in_irl_targeting_erl | swept_erl_retracing_irl | deep_expansion",
  "gate_status": "PASS | CAUTION | FAIL"
}
```

---

## 6. 门控条件

| 情况 | gate_status |
|------|------------|
| 无可识别的 DOL（价格在"空白区"） | **FAIL** |
| 主 DOL 与 Bias 方向矛盾 | **FAIL** |
| 多个候选 DOL 优先级模糊 | **CAUTION** |
| 清晰 DOL + 路径明确 | **PASS** |

---

## 7. 红旗条件

- `RF-NO-DOL`: 没有合理距离内的 DOL
- `RF-DOL-CONFLICT`: 最近的流动性池在 Bias 反方向

---

## 8. 知识来源

- **ICT_Advisor Playbook**: DOL 三问框架
- **ict-advisor-refactory specs**: DOL 多维度判断
- **MMXMTrader_Handbook**: ERL↔IRL 循环
- **Bias_to_Execution**: DOL 实战案例
- **Mastering Institutional Orderflow**: IOF 与 DOL 的关系

对应审计：`ict-knowledge-audit.md` Layer 3 - DOL Framework
