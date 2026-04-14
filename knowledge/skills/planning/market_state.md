# Market State — 微观市场状态分类

> **Layer：** Planning
> **依赖 Skills：** `framing/bias.md`, `framing/narrative.md`, `targeting/pda_scan.md`, `targeting/dol_framework.md`
> **可选 Skills：** `profiling/session_role.md`

---

## 1. 目的

在 Planning 层的最前端，判断当前**微观市场状态**，用于入场模型匹配。这是 Entry Model 选择的关键前提——不同状态适合不同模型。

**没有 Market State 判断 → 入场模型推荐会退化成"推荐 2022/Silver Bullet"。** 这是前两个系统的核心痛点。

---

## 2. 输入要求

### 数据
- NQ1! 的 M15/M5/M1 数据（最近 100 根 bars）

### Calculator 输出
```
$calc.current_price
$calc.first_hour_dr             # 1st Hour Dealing Range
$calc.ny_am_range
$calc.fvgs_by_tf                # LTF FVG
$calc.eqh_list, $calc.eql_list
```

### 前置 Skill
```
$bias.direction
$narrative.po3_phase
$narrative.mmxm_phase
$dol_framework.primary_dol
$session_role.role
```

---

## 3. 执行步骤

### Step 1: 宏观状态分类（Macro State）

观察 M15 数据最近 3-5 小时的行为：

| 状态 | 特征 |
|------|------|
| **Trending** | 连续的 HH/HL（看多）或 LL/LH（看空），明显方向性位移 |
| **Ranging** | 在一个范围内反复震荡，无明显扩张 |
| **Transitioning** | 结构正在变化（如从 Trending 进入 Ranging，或反之） |

### Step 2: 微观状态分类（Micro State）

观察 M5/M1 最近 30-60 分钟：

| 状态 | 特征 |
|------|------|
| **Impulse** | 强势方向性移动，大实体 K 线，创建 FVG |
| **Retracement** | 回撤进入 FVG/OB，为下一波积累 |
| **Consolidation** | 窄幅整理，无明确方向 |
| **Sweep** | 正在扫荡流动性（EQH/EQL 或关键位被突破） |
| **Post-Sweep Reversal** | 扫荡刚完成，价格反向位移 |

### Step 3: MMXM 阶段映射

引用 Narrative 中的 MMXM 阶段，并在当前 Session 中细化：

| MMXM 阶段 | 当前可做什么 |
|-----------|-------------|
| Consolidation / Accumulation | 等待，不入场 |
| Engineering / Manipulation | 等待扫荡完成 + CISD |
| SMR | 精确入场机会 |
| Distribution | 顺势入场 |
| Reversal | 谨慎，需要确认 |

### Step 4: 波动率评估

观察 ATR 近似值（最近 10 根 M15 bars 的平均范围）：

- **Low**：窄幅（< 历史均值 0.5x）
- **Normal**：正常
- **High**：放大（> 1.5x）
- **Extreme**：异常（> 2x，通常是新闻事件）

### Step 5: 综合判断适配性

基于以上 4 个维度，给出"当前适合什么操作"：

- **适合入场**：Trending + Retracement + 正常波动 + MMXM Distribution
- **等待**：Ranging + Consolidation + Low volatility
- **不建议交易**：Extreme volatility、MMXM Consolidation 阶段

---

## 4. 判断规则

### 状态组合的典型场景

| Macro | Micro | MMXM | 推荐操作 |
|-------|-------|------|---------|
| Trending | Retracement | Distribution | **顺势入场**（最佳） |
| Trending | Impulse | Distribution | **等回撤**（不要追） |
| Ranging | Sweep | Engineering | **等 CISD**（反转入场） |
| Ranging | Post-Sweep Reversal | SMR | **精确入场**（Turtle Soup） |
| Transitioning | any | any | **谨慎**，等确认 |

### 波动率过滤

- **Extreme volatility** → 全部入场机会降权 50%，或直接 NO_TRADE
- **Low volatility** + Ranging → 等待，不交易

---

## 5. 输出 Schema

```json
{
  "macro_state": "trending | ranging | transitioning",
  "macro_reasoning": "observations from M15 recent 3-5 hours",
  "micro_state": "impulse | retracement | consolidation | sweep | post_sweep_reversal",
  "micro_reasoning": "observations from M5/M1 recent 30-60 min",
  "mmxm_phase_current": "consolidation | engineering | smr | distribution | reversal",
  "volatility": "low | normal | high | extreme",
  "volatility_context": "ATR 相对历史均值",
  "trading_suitability": "ideal | good | wait | avoid",
  "suitability_reason": "why",
  "gate_status": "PASS | CAUTION | NO_TRADE"
}
```

---

## 6. 门控条件

| 情况 | gate_status |
|------|------------|
| `volatility=extreme` | **NO_TRADE**（除非用户明确接受高风险） |
| `trading_suitability=avoid` | **NO_TRADE** |
| `trading_suitability=wait` | **CAUTION** |
| `trading_suitability in {ideal, good}` | **PASS** |

---

## 7. 红旗条件

- `RF-VOL-EXTREME`: 极端波动
- `RF-RANGE-LOCKED`: Ranging + Low volatility 持续 2 小时以上

---

## 8. 知识来源

- **Advanced ICT Concepts**: 市场结构与阶段
- **MMXMTrader_Handbook**: MMXM 阶段
- **ICT 2022 Mentorship Notes**: 市场状态判断
- **Mastering Institutional Orderflow**: IOF 工作的前提（Trending/Expansion vs Ranging）
- **ICT 2026 Mentorship**: 1st Hour Dealing Range 与状态识别

对应审计：`ict-knowledge-audit.md` Layer 4 - Market State
