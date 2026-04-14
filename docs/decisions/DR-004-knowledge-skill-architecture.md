# DR-004：知识系统 — Skill 模块化 + 图谱辅助

**日期：** 2026-04-14
**状态：** 草案（待 Patrick review）
**背景：** Patrick 提出将 ICT Concept 分解为模块化 Skill，以提高效率

---

## 问题

重构版 KnowledgeBrain 是"百科模式"——300+ 节点按类别存储，PromptBuilder 按类别过滤加载。问题：

1. **按类别过滤太粗**：加载"concept"类别可能包含 50+ 无关概念
2. **信息型而非指令型**：节点内容是"PO3 是什么"，不是"如何用 PO3 分析"
3. **更新成本高**：改一个概念需要重跑 5 步构建工具链
4. **组合逻辑在代码中**：哪些概念配合使用靠 PromptBuilder 硬编码

---

## 方案：双层知识架构

### Layer 1: ICT Skills（主层 — 工作流驱动）

15-20 个 Markdown 文件，每个是一个**可执行的分析技能**。

**Skill 结构标准：**
```markdown
# [Skill 名称]

## 输入要求
[需要的数据和前置 Skill 结果]

## 执行步骤
[编号步骤，明确、无歧义]

## 判断规则
[硬性规则和条件分支]

## 输出格式
[JSON Schema 或字段说明]

## 依赖
[前置 Skill 列表]

## 红旗条件
[触发 NO_TRADE 的条件]
```

**Skill 清单（初步）：**

| Skill | 文件 | 依赖 | 输出 |
|-------|------|------|------|
| IPDA 范围分析 | ipda_analysis.md | 无 | IPDA 20/40/60D 范围 |
| 周轮廓识别 | weekly_profile.md | ipda_analysis | 12 种模板之一 |
| 多品种扫描 | multi_instrument_scan.md | 无 | 6 品种强弱排序 |
| PO3 日方向 | po3_sequence.md | ipda_analysis | 方向 + 阶段 |
| DOL 三问 | dol_framework.md | po3_sequence | DOL + 目标位 |
| DXY/SMT 背离 | dxy_smt_divergence.md | 无 | 背离确认/否认 |
| Seek & Destroy 过滤 | seek_destroy_filter.md | dol_framework | 交易/等待 |
| Session 角色 | session_role.md | po3_sequence | 角色 + 预期 |
| 流动性映射 | liquidity_mapping.md | session_role | 扫荡位 + 池 |
| PDA 排序 | pda_ranking.md | liquidity_mapping | 优先 PDA 列表 |
| 入场模型匹配 | entry_model_matching.md | pda_ranking | 模型 + 条件 |
| A+ 清单 | aplus_checklist.md | entry_model_matching | 8 项评分 |
| CBDR 分析 | cbdr_analysis.md | 无 | CBDR 范围 |
| NDOG 分析 | ndog_analysis.md | 无 | NDOG 区间 |
| 红旗总检 | red_flag_check.md | 所有适用 skill | 9 条红旗扫描 |

### Layer 2: KnowledgeBrain（辅助层 — 查询驱动）

保留图数据库，但角色改变：

| 旧角色（重构版） | 新角色（Michael） |
|-----------------|------------------|
| prompt 注入的主要知识源 | Skill 引用的概念词典 |
| PromptBuilder 按类别批量加载 | Skill 按名字精确查询定义 |
| — | Guardian 验证名称存在性 |

### 报告类型 → Skill 映射

```python
REPORT_SKILLS: dict[ReportType, list[str]] = {
    ReportType.WEEKLY_PREP: [
        "ipda_analysis", "weekly_profile", "multi_instrument_scan", "cbdr_analysis",
    ],
    ReportType.DAILY_BIAS: [
        "po3_sequence", "dol_framework", "dxy_smt_divergence",
        "seek_destroy_filter", "red_flag_check",
    ],
    ReportType.ASIA_PRE: [
        "session_role", "ndog_analysis", "liquidity_mapping",
    ],
    ReportType.LONDON_PRE: [
        "session_role", "liquidity_mapping",
    ],
    ReportType.NYAM_PRE: [  # Stage 1
        "session_role", "liquidity_mapping", "dxy_smt_divergence",
    ],
    # NYAM_PRE Stage 2:
    # "pda_ranking", "entry_model_matching", "aplus_checklist"
    ReportType.NYAM_OPEN: [
        "session_role",
    ],
    ReportType.NYPM_PRE: [
        "session_role", "liquidity_mapping",
    ],
}
```

---

## 效率影响

| 指标 | 重构版 (KnowledgeBrain) | Michael (Skill) | 变化 |
|------|------------------------|-----------------|------|
| 知识上下文大小 | ~8-16K tokens | ~2-7K tokens | **-50~60%** |
| 知识加载方式 | 按类别过滤（可能含噪音） | 按 Skill 精确组合 | 零噪音 |
| Prompt 类型 | 信息型（"X 是什么"） | 指令型（"按步骤执行"） | 质量提升 |
| 更新方式 | 重跑 5 步构建工具 | 编辑 Markdown | 即时 |
| 调试透明度 | 不清楚加载了哪些节点 | 日志显示 Skill 列表 | 可追溯 |

---

## 风险

1. **Skill 之间重复内容**：多个 Skill 可能重复描述相同概念 → 用 KnowledgeBrain 引用解决
2. **Skill 粒度不当**：太细碎 → 组合复杂；太粗 → 失去按需加载的优势 → 目标 15-20 个
3. **Playbook 与 Skill 关系**：Playbook 是完整参考文档，Skill 是执行提取 → 两者共存，Skill 优先注入

---

## 与 Harness 原则的对齐

- **Prompt 是控制面** → Skill 就是结构化的控制块，有明确的输入/输出/步骤
- **上下文是工作记忆** → Skill 按需加载 = token 预算管理
- **工具是受管理接口** → Skill 类似于模型的"分析工具"，有预定义的接口
