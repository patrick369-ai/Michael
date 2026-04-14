# DR-005：Calculator 模块 — 代码级价格计算

**日期：** 2026-04-14
**状态：** 已接受
**决策者：** Patrick

---

## 问题

LLM 处理几百行 OHLCV 数字序列时准确性差。它不是在"读图"，而是在处理数字文本。让 LLM 既算价格又做判断，两边都不可靠。

重构版没有计算模块——所有 Key Levels 都由 LLM 自己从原始数据中识别，Guardian 只能事后验证 PDH/PDL 等少数指标。

## 决策

新增 Calculator 模块，在 LLM 分析之前完成所有确定性价格计算。

### 设计原则

**代码是眼睛（精确看数据），LLM 是大脑（判断意义）。**

| 类型 | 谁做 | 理由 |
|------|------|------|
| 确定性计算（有公式的） | 代码 | 100% 准确，LLM 做这个不可靠 |
| 模式识别（有规则的） | 代码 | FVG 的 3-bar 模式是确定性规则 |
| 优先级判断（需要理解上下文的） | LLM | 哪个 FVG 更重要需要结合叙事 |
| 方向判断（需要综合分析的） | LLM | Bias、DOL、Profile 等 |

### Calculator 计算清单

**Key Levels（确定性计算）：**

| 指标 | 计算方法 | 复杂度 |
|------|----------|--------|
| PDH / PDL | 前日 bars 的 max(high) / min(low) | 1 行 |
| PWH / PWL | 前周 bars 的 max(high) / min(low) | 1 行 |
| PMH / PML | 前月 bars 的 max(high) / min(low) | 1 行 |
| Equilibrium of PDR | (PDH + PDL) / 2 | 1 行 |
| Equilibrium of PWR | (PWH + PWL) / 2 | 1 行 |
| NWOG | Friday close vs Sunday open | 几行 |
| NDOG | 5PM close vs 6PM open | 几行 |
| ORG | 4PM close vs 9:30AM open | 几行 |
| NMO | Midnight opening price | 1 行 |
| 8:30 Open | 8:30 AM opening price | 1 行 |
| EQH / EQL | 相近的多个高/低点（容差阈值内） | ~10 行 |
| Session H/L | Asia/London/NY 各 Session 的 high/low | 几行 |
| 1st Hour DR | 9:30-10:30 的 high/low + equilibrium | 几行 |
| CBDR | 2PM-8PM 范围 + 标准差投射 | ~10 行 |

**PDA 扫描（模式识别）：**

| PDA 类型 | 代码能否识别 | 方法 |
|----------|-------------|------|
| FVG (BISI/SIBI) | ✅ | 3-bar: bar[i].low > bar[i+2].high 或反之 |
| Volume Imbalance | ✅ | 2-bar: 相邻 bar bodies 之间有 gap |
| BPR | ✅ | 找重叠的 BISI + SIBI |
| Implied FVG | ⚠️ 部分 | 重叠 wicks 之间的 CE，规则明确但需要精确判定 |
| OB | ❌ | 需要判断"位移"，定义主观 |
| Breaker | ❌ | 需要判断"流动性扫荡 + 结构转换" |
| Mitigation Block | ❌ | 需要判断 step-like 结构 |

### 两个用途

**1. 注入 Prompt（减少幻觉来源）：**

Calculator 的输出直接注入 LLM 的 prompt，LLM 不需要自己从原始数据中算这些值：

```
已计算的 Key Levels：
- PDH: 21520, PDL: 21380, Eq: 21450
- PWH: 21650, PWL: 21320
- NWOG: 21400-21415 (CE: 21407)
- NMO: 21460, 8:30 Open: 21475
- Asia H: 21490, Asia L: 21440

已识别的 FVGs（代码扫描）：
- M15 Bearish: 21495-21472 (14:30-15:00 bars)
- M5 Bullish: 21425-21440 (15:05-15:15 bars)

请基于以上数据进行分析...
```

**2. 给 Guardian 验证（增强验证能力）：**

Guardian 用 Calculator 的输出验证 LLM 声称的值：
- LLM 说"PDH 是 21525" → Calculator 算出 21520 → 差 5 点 → WARN
- LLM 说"M5 有 FVG 在 21460-21470" → Calculator 找不到 → FAIL（幻觉）
- LLM 算的 R:R = 3.5 → 代码验算 = 2.8 → 用代码的值

### 在架构中的位置

```
Ingestion → DataManifest
                ↓
         Calculator（代码算 Key Levels + FVGs）
                ↓
         PromptBuilder（注入 Calculator 输出 + Skill 模块）
                ↓
         LLM 分析（专注判断，不做数学）
                ↓
         Guardian 验证（用 Calculator 输出比对 LLM 输出）
                ↓
         Dispatch
```

Calculator 在 Ingestion 之后、LLM 之前运行，不调用 LLM，纯代码，耗时 < 1 秒。
