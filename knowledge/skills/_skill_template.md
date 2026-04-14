# Skill 模板规范

> 本文档定义所有 ICT Skill 文件的标准结构。每个 Skill 是一个可被 LLM 调用的分析能力模块。

---

## Skill 文件命名规范

- 位置：`knowledge/skills/{layer}/{skill_name}.md`
- 层级目录：`framing/` `profiling/` `targeting/` `planning/` `entry_models/`
- 命名：小写下划线（`snake_case`），无空格

## 标准结构（8 个区块）

```markdown
# Skill 名称（中文 + 英文）

> **Layer：** Framing / Profiling / Targeting / Planning / Entry Models
> **依赖 Skills：** 前置 Skill 列表（必须先执行）
> **可选 Skills：** 可选的参考 Skill

## 1. 目的

一句话说明这个 Skill 要判断/识别什么。

## 2. 输入要求

- **数据：** 需要哪些 OHLCV 数据（品种 × 时间框架 × bar 数）
- **Calculator 输出：** 依赖哪些代码已算好的指标（PDH/FVG/EQ 等）
- **前置 Skill 结果：** 依赖哪些上游 Skill 的输出（以 JSON 字段形式引用）
- **外部引用：** 知识图谱节点、历史记录等

## 3. 执行步骤

编号步骤，明确、无歧义。每步应该是可检查的判断或计算。

## 4. 判断规则

硬性规则和条件分支。用 if-then 或决策表形式。必要时给出例外情况。

## 5. 输出 Schema

```json
{
  "field_name": "type (enum | number | string | array)",
  "description": "每个字段的含义",
  "gate_status": "PASS | CAUTION | FAIL | NO_TRADE"
}
```

## 6. 门控条件

明确什么情况下输出 FAIL / NO_TRADE / CAUTION。这些条件代码可以验证。

## 7. 红旗条件

导致立即终止的条件（来自 24 份资料的 9 红旗 + 11 S&D 条件）。

## 8. 知识来源

列出这个 Skill 的内容来自哪些原始资料文件（如 "ICT 5 ENTRY MODELS p.4-9"）。
```

---

## 设计原则

### 原则 1：Skill 是"指令型"不是"信息型"

- ✅ "执行以下步骤判断方向"
- ❌ "方向的定义是..."

Skill 告诉 LLM **怎么做**，不只是**是什么**。

### 原则 2：最小必要输入

只列出这个 Skill 真正需要的输入。LLM 的上下文窗口有限，冗余输入 = token 浪费 + 注意力分散。

### 原则 3：结构化输出

每个 Skill 输出都是 JSON，Schema 明确。这样：
- 下游 Skill 可以精确引用字段
- Guardian 可以代码级验证
- 数据库可以结构化存储

### 原则 4：门控优先

先判断"能不能做"（红旗/门控），再做具体分析。避免在无效前提下的浪费。

### 原则 5：引用而非重复

依赖的前置 Skill 结果用 `$upstream.field` 引用，不在本 Skill 中重述。比如 Bias Skill 不重新定义 Context，而是引用 `$context.ipda_position`。

---

## 参考的样本 Skill

- `framing/bias.md` — Framing 层样本（判断型 Skill）
- `targeting/pda_scan.md` — Targeting 层样本（枚举扫描型 Skill）

---

## Token 预算

每个 Skill 文件建议控制在：
- **核心 Skill：** 500-1500 tokens（~2-6KB）
- **简单 Skill：** 300-600 tokens（~1-2KB）
- **复杂 Skill（如 entry_model_matching）：** 最多 2500 tokens（~10KB）

超过这个限制说明 Skill 太大了，应该拆分。
