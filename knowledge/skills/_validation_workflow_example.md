# Skill 工作流验证示例：daily_bias 报告

> 本文档演示样本 Skill（`bias.md`、`pda_scan.md`）如何在 daily_bias 报告中协同工作，验证模块化框架的可行性。

---

## 报告类型：daily_bias

**触发：** 每日 6:00 PM ET
**使用模式：** SCHEDULED 合并调用（1 次 LLM 调用完成 Layer 1-3）

---

## 数据流模拟

### Step 1: Ingestion（代码）

```
MCP 采集：
- NQ1! × [W, D, H4, H1, M15] × 50 bars
- DXY × D × 10 bars
- ES1! × D × 10 bars
```

### Step 2: Calculator（代码，< 1 秒）

```python
calc_output = {
    "current_price": 21463,
    "pdh": 21520, "pdl": 21380,
    "pwh": 21650, "pwl": 21320,
    "equilibrium_pdr": 21450,
    "ipda_20d": {"high": 21820, "low": 21180, "eq": 21500},
    "ipda_40d": {...},
    "ipda_60d": {...},
    "fvgs_h4": [
        {"type": "SIBI", "price_high": 21495, "price_low": 21472, "bar_index": 8, "filled": false}
    ],
    "fvgs_h1": [
        {"type": "SIBI", "price_high": 21480, "price_low": 21468, "bar_index": 15, "filled": false},
        {"type": "BISI", "price_high": 21425, "price_low": 21410, "bar_index": 22, "filled": true}
    ],
    "fvgs_m15": [...],
    "fvgs_m5": [...],
    "eqh_list": [21458, 21460],  # Equal Highs around 21458-21460
    "eql_list": [21340, 21342],
    "nwog": {"high": 21415, "low": 21400, "ce": 21407},
    "equilibrium_pwr": 21485
}
```

### Step 3: 组装 Prompt（代码）

PromptBuilder 根据 daily_bias 报告类型加载 Skills：

```
加载的 Skills（daily_bias 需要）:
- framing/context.md
- framing/narrative.md
- framing/bias.md         ← 本次验证的样本
- profiling/weekly_profile.md（引用周度结果）
- profiling/daily_profile.md
- targeting/pda_scan.md    ← 本次验证的样本
- targeting/dol_framework.md

Prompt 结构：
1. [System] 你是 ICT 交易分析师。严格按 Skill 指令执行。
2. [Skills 拼接] 上面 7 个 Skill 的完整内容
3. [Calculator 输出] calc_output 作为 $calc.* 变量注入
4. [历史数据] 昨日的 bias/key_levels（从 SQLite 读取）
5. [当前时间] 2026-04-14 18:00 ET
6. [输出 Schema] 完整的多段 JSON Schema
7. [任务] "按以上 Skill 顺序分析，输出完整 JSON"
```

### Step 4: LLM 调用（1 次，~80 秒）

LLM 按 Skill 顺序输出：

```json
{
  "context": {
    "ipda_position": "discount",
    "htf_order_flow": "bearish",
    "cisd_status": "confirmed_bearish",
    "erl_irl_cycle": "IRL targeting ERL (PWL 21320)"
  },
  "narrative": {
    "po3_phase": "distribution",
    "mmxm_phase": "distribution",
    "sequence_stage": "Sequence 2 underway: Weekly target = PWL",
    "story": "本周已从高位回落，Daily CISD 确认，IPDA 进入 Discount 但继续下探。"
  },
  "bias": {
    "direction": "SHORT",
    "confidence": "HIGH",
    "signal_breakdown": {
      "s1_ipda_position": "bearish",      // Discount 但 HTF 仍空
      "s2_htf_order_flow": "bearish",
      "s3_po3_sequence": "bearish",        // Distribution 顺势
      "s4_cisd": "bearish"                 // CISD 确认
    },
    "confirmations": {
      "dxy_alignment": "confirmed",         // DXY 上涨
      "smt_divergence": "bearish",          // NQ 创新高但 ES 没有
      "candle_closure": "bearish_confirmed" // 日线在 21480 下方收盘
    },
    "reasoning": "4 维度全部看空 + DXY 反向确认 + SMT 背离 = HIGH 置信度看空。",
    "reversal_from_previous": false,
    "gate_status": "PASS"
  },
  "weekly_profile": {
    "matched_template": "Classic Expansion (Bearish)",
    "key_reversal_day": "Tuesday (已过)"
  },
  "daily_profile": {
    "matched_type": "London Reversal → NY Continuation (bearish)"
  },
  "pda_scan": {
    "pda_zones": [
      {
        "zone_id": "Z1",
        "price_range": [21468, 21495],
        "constituents": [
          {"type": "FVG", "timeframe": "H4", "price_range": [21472, 21495], "source": "calculator"},
          {"type": "FVG", "timeframe": "H1", "price_range": [21468, 21480], "source": "calculator"},
          {"type": "OB", "timeframe": "H1", "price_range": [21470, 21488], "source": "llm",
           "identification_reason": "H4 SIBI 形成前的最后 up-closed bar"}
        ],
        "zone_grade": "S",
        "alignment_with_bias": "aligned",       // 在 Premium 区，Bias SHORT
        "weighted_score": 12,
        "notes": "H4+H1 FVG 重叠 + H1 OB，S 级共振"
      },
      {
        "zone_id": "Z2",
        "price_range": [21455, 21462],
        "constituents": [
          {"type": "EQH", "timeframe": "M15", "price_range": [21458, 21460]},
          {"type": "PDH", "price_range": [21520, 21520]}  // 非精确值
        ],
        "zone_grade": "A",
        "alignment_with_bias": "aligned",
        "weighted_score": 7
      }
    ],
    "pda_3_fail_check": {"triggered": false},
    "gate_status": "PASS"
  },
  "dol_framework": {
    "q1_where_from": "Weekly top @21650",
    "q2_where_now": "IPDA Discount, below EQ 21500",
    "q3_where_to": "PWL 21320 (primary target) / PDL 21380 (intermediate)",
    "path": "经 Z1 (21468-21495) 反弹回测 → 延续向下 → 先到 PDL → 最终 PWL"
  },
  "gate_status": "PASS"
}
```

### Step 5: Guardian 验证（代码）

```
幻觉检测：
  - LLM 说 "SMT 背离看空" → 代码检查 NQ vs ES 最近 bars：✅ 确认
  - LLM 说 "PDH=21520" → Calculator 算出 PDH=21520：✅ 一致
  - LLM 说 "H1 OB @21470-21488" → Calculator 算不出，但在 H1 SIBI 附近，合理：保留
  - Z1 的所有 constituents 都在合理价格范围内：✅

一致性检查：
  - bias.direction=SHORT vs dol_framework.q3=PWL（下方）：✅ 一致
  - pda_scan.zones 全部标注 aligned：✅
  - 与昨日 bias（也是 SHORT）一致：✅，无需翻转理由

规则合规：
  - 非 FOMC/NFP 日：✅
  - 未触发 3 PDA 失败：✅

最终：PASS
```

### Step 6: Dispatch

生成飞书红色卡片（SHORT Bias），推送。

---

## 验证结论

### 模块化框架可行 ✅

1. **Skill 作为指令型文档可用**：每个 Skill 告诉 LLM "执行什么步骤"，LLM 按顺序输出结构化结果
2. **Calculator + Skill 双源模式工作**：
   - Calculator 的确定性数据（FVG 位置、Key Levels）通过 `$calc.*` 注入
   - LLM 识别的结构性 PDA（OB）作为 `source: llm` 标记，供 Guardian 判断
3. **Skill 依赖链清晰**：`bias.md` 引用 `$context.*` 和 `$narrative.*`，`pda_scan.md` 引用 `$bias.*` 和 `$calc.*`
4. **门控机制有效**：每个 Skill 独立输出 `gate_status`，代码可组合判断

### 发现的问题与改进

1. **Prompt 长度管理**：7 个 Skill 拼接 + Calculator 输出 + 历史数据，估算 prompt ≈ 12K tokens。对于单次 Claude 调用仍在预算内，但需要在 PromptBuilder 中做精简（例如 Skill 的"知识来源"区块在实际注入时可以移除）。

2. **输出 Schema 合并问题**：当前每个 Skill 有自己的输出 Schema，合并调用时需要在 Prompt 最后组装一个"完整顶层 Schema"，引用各 Skill 的子 Schema。这是 PromptBuilder 的工作。

3. **LLM 的 Skill 切换成本**：LLM 要在一次响应中切换多个"角色"（分析 Context → 判断 Bias → 扫描 PDA），这对 Opus 4.6 问题不大，但对弱模型可能不行。建议坚持用 Opus 4.6。

4. **历史数据引用**：`$history.last_3_pda_predictions` 需要 Store 层实现，Phase 1 必须包含。

---

## 下一步

Step 1（样本 Skill 验证）完成。结构可行，可以进入 Step 2（Calculator 模块）。

批量写剩余 Skill 的工作放到 Step 4 进行——等 Calculator 完成后，Skill 的输入格式可以最终确定。
