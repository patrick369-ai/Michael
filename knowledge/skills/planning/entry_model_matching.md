# Entry Model Matching — 入场模型条件匹配引擎

> **Layer：** Planning
> **依赖 Skills：** `framing/bias.md`, `targeting/pda_scan.md`, `targeting/dol_framework.md`, `planning/market_state.md`
> **可选 Skills：** `profiling/session_role.md`

---

## 1. 目的

**解决"每次都推荐 2022/Silver Bullet"的核心痛点。** 基于当前 Market State、PDA、DOL、Bias、时间窗口，从 25 个 ICT 入场模型中匹配最合适的 Top-3。

**这不是让 LLM 选一个模型，而是条件匹配引擎：** 每个模型有明确的触发条件和排除条件，先代码过滤掉不适用的，再让 LLM 从剩下的候选中排序。

---

## 2. 输入要求

### 前置 Skill
```
$bias.direction, $bias.confidence
$pda_scan.pda_zones             # 已扫描的 PDA 列表
$dol_framework.primary_dol
$market_state.macro_state, $market_state.micro_state, $market_state.mmxm_phase_current
$market_state.volatility
$session_role.session, $session_role.role
```

### 上下文
```
current_time_et              # 当前 ET 时间
calendar_events              # 当日经济日历
```

---

## 3. 执行步骤

### Step 1: 时间窗口资格检查

根据 `current_time_et` 确定可用的时间敏感模型：

| 时间窗口（ET） | 可用模型 |
|--------------|---------|
| 3:00-4:00 AM | Silver Bullet (London) |
| 8:30-11:00 AM | 2022 Entry, 1st Presented FVG (9:31-10:00), Judas Swing (8:30) |
| 10:00-11:00 AM | Silver Bullet (NY AM), 2022 Entry |
| 9:50-10:10 AM | Macro Window（所有模型加成） |
| 1:30 PM | NY PM Judas Swing |
| 2:00-3:00 PM | Silver Bullet (NY PM) |
| 非以上时段 | 无时间敏感模型，通用模型可用 |

### Step 2: Market State 过滤

基于 `market_state` 排除不适合的模型：

| Macro State | 优先模型 | 排除模型 |
|------------|---------|---------|
| Trending + Retracement | OTE, 2022, Breaker | Turtle Soup（趋势中不做反转） |
| Trending + Impulse | 不入场（等回撤） | - |
| Ranging + Sweep | Turtle Soup, Judas Swing, 2025 Model | OTE（无明确趋势） |
| Ranging + Post-Sweep | Turtle Soup, Failure Swing | 顺势模型 |
| MMXM SMR | MMXM Entry, 2nd Stage Distribution | - |
| MMXM Distribution | 顺势入场模型 | 反转模型 |
| MMXM Engineering（进行中） | 等待，不入场 | 所有 |

### Step 3: PDA/DOL 资格检查

每个模型需要特定的结构：

| 模型 | 必需结构 |
|------|----------|
| **2022 Entry** | 流动性扫荡 + MSS + 位移 + FVG |
| **Silver Bullet** | 同 2022，外加时间窗口 |
| **Unicorn** | Breaker + FVG 重叠 |
| **IFVG Model** | FVG 被 body close 穿透 |
| **OTE** | 明确趋势 + 62-79% 回撤区有 FVG/OB |
| **Breaker Model** | 流动性扫荡 + Breaker 形成 + 回测 |
| **1st Presented FVG** | 9:31 后第一个 FVG，必须在扫荡后 |
| **Turtle Soup** | 旧高/低刚被突破 + V 型反转 |
| **Judas Swing** | Session 开盘假突破（MNO/8:30/1:30） |
| **NY Continuation** | London 有明确冲击 + NY 回撤 London PDA |
| **MMXM Entry** | 完整 MMXM 周期 + 当前处于可入场阶段 |
| **Venom Model** | 8:00-9:30 AM 盘前操纵完成 |
| **Propulsion Block** | 前序 OB 回测 + 即时暴力反应 |

代码级过滤：如果必需结构缺失，从候选移除。

### Step 4: Bias 对齐过滤

- 做多模型需要 PDA 在 Discount 区，做空模型需要 PDA 在 Premium 区
- 如果 PDA 在错误区域，模型不输出（或输出但置信度极低）

### Step 5: 综合评分

对剩余候选模型，基于以下维度打分（0-10）：

| 维度 | 分值 |
|------|------|
| 时间窗口完美匹配（如 10-11 AM 的 Silver Bullet） | +3 |
| Market State 完美匹配 | +2 |
| 高质量 PDA 结构（S 级共振区内） | +2 |
| MSS/CISD 已确认 | +2 |
| Bias 高置信度对齐 | +1 |

### Step 6: 输出 Top-3

按综合分排序，输出前 3 名候选模型，附带：
- 触发条件满足状态
- 建议的入场区域（价格范围）
- 建议的 SL / TP 位置（由模型特定规则推导）

---

## 4. 判断规则

### 模型冲突处理

如果多个模型同时满足（如 Silver Bullet 时间窗口内 + OTE 回撤到位）：
- **保留多个候选**，由 LLM 在叙事中选择最契合的
- 不强制唯一

### 默认策略

如果所有专门模型都不适用：
- 回退到 **2025 Model**（最通用的短期模型，规则简单）
- 如果 2025 Model 也不适用 → 标记 NO_TRADE

### 排除常见误用

**避免"什么都推荐 2022"：**
- 2022 Entry 必须有完整的"流动性扫荡 + MSS + 位移 + FVG"四要素
- 缺任何一个 → 2022 不合格，寻找其他模型

---

## 5. 输出 Schema

```json
{
  "eligible_models_count": 5,
  "top_candidates": [
    {
      "rank": 1,
      "model_name": "Silver Bullet",
      "score": 9,
      "reasoning": "在 10:00-11:00 窗口 + M5 FVG 在 Discount + MSS 确认",
      "triggers_met": {
        "time_window": true,
        "mss_confirmed": true,
        "fvg_in_zone": true,
        "liquidity_swept": true
      },
      "suggested_entry": {
        "zone_high": 21455,
        "zone_low": 21448,
        "pda_reference": "M5 FVG"
      },
      "suggested_sl": 21467,
      "suggested_tp1": 21400,
      "suggested_tp2": 21320
    },
    {
      "rank": 2,
      "model_name": "2022 Entry",
      "score": 7,
      "reasoning": "...",
      ...
    },
    {
      "rank": 3,
      "model_name": "Unicorn",
      "score": 6,
      ...
    }
  ],
  "rejected_models": [
    {"model": "Turtle Soup", "reason": "当前是 Trending 而非 Sweep"},
    {"model": "OTE", "reason": "回撤位无 FVG"}
  ],
  "gate_status": "PASS | CAUTION | NO_TRADE"
}
```

---

## 6. 门控条件

| 情况 | gate_status |
|------|------------|
| 无合格模型（所有都被过滤） | **NO_TRADE** |
| 只有低分候选（最高分 < 5） | **CAUTION** |
| 至少 1 个高分候选（≥ 7） | **PASS** |

---

## 7. 红旗条件

- `RF-NO-MODEL-FIT`: 当前市场状态无任何 ICT 模型适用
- `RF-MODEL-TIME-MISS`: 强依赖时间窗口的模型（如 Silver Bullet）在窗口外被选中

---

## 8. 完整模型条件表

详细的 25 个模型触发条件见 `knowledge/skills/entry_models/` 目录下各个子 Skill 文件。本 Skill 仅负责**匹配引擎**逻辑。

核心 10 个模型的条件速查：

```
2022 Entry:         流动性扫荡 → MSS → 位移 → FVG（4 要素全齐）
Silver Bullet:      同 2022 + 时间窗口（3-4AM / 10-11AM / 2-3PM）
OTE:                位移后回撤 62-79% + FVG/OB 在区内
Unicorn:            Breaker + FVG 重叠
IFVG Model:         FVG 被 body close 穿透 + 反转
Breaker Model:      流动性扫荡 + MSS + Breaker 形成 + 回测
Judas Swing:        Session 开盘价假突破后反转
Turtle Soup:        旧高/低被扫 + V 型反转
NY Continuation:    London 冲击 + NY 回撤 London PDA
MMXM Entry:         完整 MMXM 周期 + 当前在可入场阶段（SMR 后或 Distribution）
```

---

## 9. 知识来源

- **ICT 5 ENTRY MODELS**: 2022/Unicorn/IFVG/OTE/Breaker
- **ICT 2025 Model Masterclass**: 2025 Model
- **MMXMTrader_Handbook + The Sequence**: MMXM Entry
- **ICT_Advisor Playbook DR-004**: 4 层入场模型分类
- **ict-advisor-refactory entry-model-spec**: 20 模型清单
- **2023 ICT Mentorship GEMS**: Silver Bullet 时间窗口
- **PRE-MARKET-PLAN**: Venom, Asia-London Entry
- **ICT 2022 Mentorship Notes**: Gold Standard = FVG+OB+OTE+MSS

对应审计：`ict-knowledge-audit.md` 完整入场模型清单（25 个模型）
