# 讨论记录：入场模型精细化设计

**日期：** 2026-04-14
**参与者：** Patrick, Claude

---

## Patrick 的需求

1. 现有系统入场模型推荐**过于笼统**——几乎每次都推荐 2022 Entry Model 或 Silver Bullet
2. 希望增加更多 ICT 模型：
   - **分型模型（Fractal Model）**
   - **MMXM 模型（Market Maker Model）**
   - **其他 ICT 模型**
3. 需要基于市场上下文精确匹配，不能"一招打天下"
4. 模型应提供入场参考，不是信号执行

---

## 问题分析：为什么现有系统总是推荐 2022 / Silver Bullet？

### 根因 1：模型定义缺少触发条件

原版 Playbook 虽然定义了 4 层 17 个入场模型，但大部分定义是"这个模型是什么"，不是"什么条件下应该用这个模型"。Claude 在缺少明确触发条件时，倾向于选择它最"熟悉"的模型。

### 根因 2：没有市场状态分类

不同模型适用于不同的市场状态。但现有系统没有"当前市场处于什么状态"的显式分类步骤。没有状态判断，就无法做条件匹配。

### 根因 3：模型之间没有排他/互补关系

系统不知道"如果 MMXM 正在展开 Manipulation，不应该用 OTE，应该等 Distribution 阶段"这类关系。

---

## 设计方向：上下文感知的模型匹配引擎

### 核心思路：Market State → Model Eligibility → Ranking

```
市场数据 → [市场状态分类] → [模型资格过滤] → [排序 + 推荐]
```

### Step 1：市场状态分类（新增 Skill）

在做入场模型匹配之前，先用一个独立 Skill 判断当前市场状态：

```
market_state_classifier.md

输入：多时间框架数据、Session 信息、Daily Bias 结果
输出：
{
  "macro_state": "trending | ranging | transitioning",
  "micro_state": "impulse | retracement | consolidation | sweep",
  "mmxm_phase": "accumulation | manipulation | distribution | reversal | none",
  "volatility": "low | normal | high | extreme",
  "session_context": "asia_range | london_impulse | ny_continuation | ..."
}
```

### Step 2：模型资格过滤（条件匹配）

每个入场模型有明确的**触发条件**和**排除条件**：

| 模型 | 触发条件 | 排除条件 |
|------|----------|----------|
| **2022 Entry** | MSS 确认 + FVG 存在于折价/溢价区 | 无 MSS、FVG 被填充 |
| **Silver Bullet** | 时间窗口内（10-11 或 14-15 ET）+ FVG | 窗口外、大新闻时段 |
| **OTE** | 趋势确认 + 回撤到 62-79% Fib + FVG/OB | 无明确趋势、浅回撤 |
| **Turtle Soup** | 流动性扫荡（突破前高/低后反转） | 无明显流动性池、趋势延续中 |
| **Judas Swing** | Session 开盘假突破 | 非 Session 开盘时段 |
| **MMXM** | 完整 MMXM 周期识别、当前处于可入场阶段 | 无完整周期、处于 Accumulation |
| **分型入场** | 特定分型结构完成 + 与 HTF 方向一致 | 分型未完成、与 HTF 矛盾 |
| **Breaker** | 旧 OB 失败后价格回测 | 无失败 OB、回测太深 |
| **Mitigation** | 之前未填充的 FVG 被回测 | FVG 已完全填充 |

### Step 3：模型排序（上下文优先级）

通过市场状态和模型特性的匹配度排序：

```
if macro_state == "trending":
    优先：OTE, 2022 Entry, Breaker
    降权：Turtle Soup, MMXM (等反转)

if micro_state == "sweep":
    优先：Turtle Soup, Judas Swing
    降权：OTE (可能被扫)

if mmxm_phase == "distribution":
    优先：MMXM 入场
    降权：顺趋势模型

if session == "silver_bullet_window":
    优先：Silver Bullet
    同时保留其他符合条件的模型

if volatility == "extreme":
    全部降权，红旗：考虑不交易
```

---

## 讨论待续

### 开放问题
1. Patrick 具体想增加哪些分型模型？（经典分型？ICT 特有的分型定义？Williams 分型？）
2. MMXM 模型的具体入场时机定义？（Distribution 结束后？还是 Manipulation 阶段的特定点？）
3. 模型推荐是给出 Top-N 排序还是只给 Top-1？
4. 模型推荐需要附带置信度和理由吗？

### 下一步
- 待 Patrick 确认方向后，编写各模型的 Skill 文件
- 设计 market_state_classifier Skill
- 更新 DR-004 知识架构
