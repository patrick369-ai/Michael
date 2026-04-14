# PDA Scan — Premium/Discount Array 扫描与优先级排序

> **Layer：** Targeting
> **依赖 Skills：** `framing/bias.md`
> **可选 Skills：** `framing/context.md`（用于 IPDA 区域参考）

---

## 1. 目的

在给定时间框架的数据中识别所有 PD Array（FVG, OB, Breaker, MB, RB, BPR 等），按与当前 Bias 和市场结构的对齐度进行优先级排序，输出 Top-N 的 PDA 列表。

**注意：** Calculator 已经扫描了确定性 PDA（FVG、BPR、VI、EQH/EQL）并注入 Prompt。本 Skill 的任务是：
1. 识别 Calculator 无法识别的 PDA（OB、Breaker、MB、Mitigation Block、Reaper FVG 等需要结构理解的）
2. 对所有 PDA（含 Calculator 提供的）做优先级排序
3. 应用 3 PDA 失败规则

---

## 2. 输入要求

### 数据
- NQ1! 的 H4/H1/M15/M5 数据（每个 TF 50 根 bars）

### Calculator 输出（注入 Prompt）
```
$calc.fvgs_h4, $calc.fvgs_h1, $calc.fvgs_m15, $calc.fvgs_m5
  # 每个 FVG: {type: "BISI|SIBI", price_high, price_low, bar_index, filled}
$calc.eqh_list, $calc.eql_list        # Equal Highs/Lows 点位
$calc.key_levels                       # PDH/PDL/PWH/PWL/NWOG/NDOG 等
$calc.ipda_20d, $calc.ipda_40d, $calc.ipda_60d
$calc.equilibrium_pdr, $calc.equilibrium_pwr
```

### 前置 Skill 结果
```
$bias.direction                        # "LONG" | "SHORT" | "NEUTRAL"
$bias.confidence                       # "HIGH" | "MEDIUM" | "LOW"
$context.ipda_position                 # "premium" | "discount"
```

### 历史数据（用于 3 PDA 失败规则）
```
$history.last_3_pda_predictions        # 过去 3 次预测的 PDA + 是否反应
```

---

## 3. 执行步骤

### Step 1: 引用 Calculator 已识别的 PDA

Calculator 已扫描出 FVG / BPR / VI / EQH / EQL，直接引用，不重新判断。
LLM 的任务是**评估重要性**，不是**重新找**。

### Step 2: 识别 Calculator 无法识别的 PDA

在每个时间框架（H4/H1/M15/M5）扫描以下 PDA 类型（需要结构理解）：

| PDA 类型 | 识别特征 |
|---------|---------|
| **Order Block (OB)** | 位移前的最后反向 K 线（bullish OB = 位移向上前的最后 down-closed bar） |
| **Breaker Block** | 流动性扫荡后的结构反转点（先扫 SSL 后反转，扫荡前的 swing low 成为 Breaker） |
| **Mitigation Block** | MSS 前的最后反向 K 线，在 step-like 结构中 |
| **Rejection Block** | 在深度回撤中带长上影/下影的 K 线 |
| **Inversion Breaker** | 已失败的 Breaker，被位移穿透后反转为对立 PDA |
| **Reaper FVG** | Breaker 内部形成的 FVG，必须在正确的 Premium/Discount 区 |
| **Propulsion Block** | 续行入场的 OB，MT=80% 而非 50% |

对每个识别出的 PDA，给出：
- 时间框架
- 价格范围 [high, low]
- 类型
- 识别理由（哪些 K 线位置触发了识别）

### Step 3: 优先级排序

按以下规则排序（由高到低）：

**规则 A: 时间框架优先级**
```
H4 PDA (权重 3) > H1 PDA (权重 2) > M15 PDA (权重 1) > M5 PDA (权重 0.5)
```

**规则 B: 方向对齐加权**
- PDA 在 Premium 区 + Bias = SHORT → 加权 ×1.5
- PDA 在 Discount 区 + Bias = LONG → 加权 ×1.5
- PDA 在错误区域（如 Discount 区但要做空） → 加权 ×0.3（降权不丢弃）

**规则 C: PDA 强度等级**（来自 All ICT PD Arrays）
```
S 级（必须关注）: FVG + OB 重叠（Unicorn）, Breaker + FVG 重叠, HTF 级 PDA
A 级（重点）:     单独的 HTF FVG/OB, 未填充的 NWOG/NDOG
B 级（辅助）:     M15/M5 FVG, MTF Breaker 未回测
C 级（参考）:     LTF PDA, 已接近填充的 FVG
```

**规则 D: 流动性关联加成**
- PDA 附近有 EQH/EQL（容差 5 点内）→ 加权 ×1.3
- PDA 恰好在 Key Level（PDH/PDL/NWOG CE）→ 加权 ×1.2

### Step 4: 3 PDA 失败规则检查

检查 `$history.last_3_pda_predictions`：
- 如果过去 3 次预测的 PDA 全部"价格到达但没反应"（即 PDA 失效） → **触发 CAUTION**
- 本次 Bias 应标记为"可能需要翻转"
- 输出 `red_flag: "RF-PDA-FAIL"`

### Step 5: 输出 Top-N

默认输出 Top-5 PDA（可配置）。每个 PDA 包含完整评分依据。

---

## 4. 判断规则

### 规则汇总

1. **PDA 必须在价格合理范围内** — 距离当前价 ≥ 5% 的 PDA 不输出（不会短期内到达）
2. **已填充的 FVG 不输出** — 但保留未完全填充的（留有未测区域）
3. **与 Bias 冲突的 S/A 级 PDA 也要输出** — 但明确标记"与 Bias 冲突"，给 LLM 在 Planning 层判断
4. **同一价格区域的多个 PDA 合并** — 如 H1 OB 和 M15 FVG 重叠，输出为一个 Zone，内含多个 PDA

### 冲突处理

- 如果识别到的 PDA 与 Calculator 的 FVG 位置矛盾（如 LLM 说 M15 有个 bearish FVG 在 21450，但 Calculator 没扫到） → **以 Calculator 为准，该 PDA 不输出**（防幻觉）
- 如果 LLM 识别了 OB 但 Calculator 无法验证（正常情况，代码算不了 OB） → 保留但标记 `source: llm_only`，由 Confluence Scorer 降权

---

## 5. 输出 Schema

```json
{
  "pda_zones": [
    {
      "zone_id": "Z1",
      "price_range": [21450, 21460],
      "constituents": [
        {
          "type": "OB",
          "timeframe": "H1",
          "price_range": [21448, 21462],
          "identification_reason": "2024-01-15 14:00 K线前最后反向 bar",
          "source": "llm"
        },
        {
          "type": "FVG",
          "timeframe": "M5",
          "price_range": [21452, 21458],
          "identification_reason": "Calculator 扫描",
          "source": "calculator"
        }
      ],
      "zone_grade": "S | A | B | C",
      "alignment_with_bias": "aligned | conflicting | neutral",
      "distance_from_price": 15,
      "weighted_score": 8.5,
      "notes": "Unicorn 形态（OB + FVG 重叠）"
    }
  ],
  "pda_3_fail_check": {
    "triggered": false,
    "details": null
  },
  "gate_status": "PASS | CAUTION",
  "red_flags": []
}
```

---

## 6. 门控条件

| 情况 | gate_status |
|------|------------|
| 无 S/A 级 PDA 在合理距离内 | **CAUTION**（可继续但信号弱） |
| 3 PDA 失败规则触发 | **CAUTION** + 红旗 |
| 所有识别的 PDA 都与 Bias 冲突 | **CAUTION**（Bias 可能错） |
| 有至少 1 个 S 级 PDA 且与 Bias 对齐 | **PASS** |

---

## 7. 红旗条件

1. **RF-PDA-FAIL**：3 PDA 连续失败（来自 2023 GEMS）
2. **RF-PDA-SPARSE**：合理范围内无 A 级以上 PDA（"价格在空白区"）

---

## 8. 知识来源

- **All ICT PD Arrays Explained** (32 页)：15 种 PDA 完整定义
- **ICT_Advisor Playbook** + **DR-005 PDA 完整性**：22 种 PDA 分类（含反转变体）
- **2023 ICT Mentorship GEMS**：3 PDA 失败规则
- **Advanced ICT Market Structure**：OB 识别的"位移前最后反向 K 线"定义
- **ICT 5 Entry Models**：Unicorn (FVG+Breaker), Reaper FVG, Propulsion Block
- **Mastering Institutional Orderflow**：OB 在 Premium/Discount 区的应用

对应审计文档：`docs/research/ict-knowledge-audit.md` 的 Layer 3: TARGETING 部分，以及"完整入场模型清单"中的精确工具类。
