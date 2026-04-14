# DR-006：Confluence Scorer — 双源交叉验证 + 多维共振评分

**日期：** 2026-04-14
**状态：** 已接受
**决策者：** Patrick

---

## 背景

Patrick 提出两个关键洞察：
1. 如果能找到不同维度的共振点并权重排序，也可能找准入场位置
2. 让 Calculator 和 LLM **各自独立找位点**，然后交叉验证 + 联合加权，比单靠任何一方更好

## 核心思路

**不是 Calculator 先算再让 LLM 评估，而是两条线并行，在 Confluence Scorer 汇合。**

| 来源 | 能找到 | 找不到 |
|------|--------|--------|
| Calculator | FVG、Key Levels、EQH/EQL、NWOG、Equilibrium、Fibonacci | OB、Breaker、MSS、市场结构判断 |
| LLM | OB、Breaker、MSS、结构判断、叙事、Bias | 容易算错 FVG 具体价格、Key Levels 数值 |

**互补关系：Calculator 找确定性位点，LLM 找需要"理解"的位点。两者交叉验证。**

### 双源并行架构

```
           Ingestion（市场数据）
                ↓
    ┌───────────┴───────────┐
    ▼                       ▼
Calculator                 LLM 分析
(确定性计算)              (结构理解)
  找到：                    找到：
  - FVG (各TF)             - OB (各TF)
  - Key Levels             - Breaker
  - EQH/EQL                - MSS 转换点
  - NWOG/NDOG/ORG          - 叙事 + Bias
  - Equilibrium            - Session Role
  - Fibonacci              - Market State
    ↓                       ↓
    └───────────┬───────────┘
                ▼
       Confluence Scorer
       (交叉验证 + 联合加权)
                ↓
         共振区域 Top-N 排序
```

**注意：Calculator 输出仍然注入 LLM 的 prompt**（帮 LLM 减少算数），但 LLM 也可以独立发现 Calculator 找不到的位点。两者最终在 Confluence Scorer 汇合。

### 交叉验证规则（来源加成）

| 情况 | 加成系数 | 理由 |
|------|---------|------|
| Calculator + LLM 都找到 | × 1.5 | 双重确认，最高可信度 |
| 仅 Calculator 找到 | × 1.0 | 位点真实存在，LLM 可能认为不重要或遗漏 |
| LLM 找到 + 代码可验证 | × 1.2 | LLM 识别 + 代码确认存在 |
| LLM 找到 + 代码不可验证 | × 0.8 | 可能是 OB/Breaker（代码算不了），保留但降权 |
| LLM 找到 + 代码算出矛盾 | × 0.0 | 幻觉，丢弃 |

### 共振维度与权重（基础分）

| 维度 | 权重 | Calculator | LLM | 说明 |
|------|------|-----------|-----|------|
| HTF PDA (H4/D) | 3 | ✅ FVG | ✅ OB/Breaker | 高时间框架权重最大 |
| MTF PDA (H1) | 2 | ✅ FVG | ✅ OB/Breaker | 中间框架 |
| LTF PDA (M15/M5) | 1 | ✅ FVG | ✅ OB/Breaker | 低时间框架 |
| Key Level 命中 | 2 | ✅ | ✅ | PDH/PWH/NWOG/NMO 等 |
| Fibonacci OTE 对齐 | 1 | ✅ | ✅ | 62-79% 区域与 PDA 重叠 |
| EQH/EQL 附近 | 2 | ✅ | ✅ | 流动性池 |
| 多品种确认 (SMT) | 2 | ✅ | ✅ | NQ/ES 对应位都有结构 |
| 时间窗口内 | 1 | ✅ | ✅ | KZ/Macro |
| Premium/Discount 正确 | 2 | ✅ | ✅ | 做空在 Premium，做多在 Discount |
| **最高基础分** | **16** | | | |
| **× 来源加成后最高** | **24** | | | 16 × 1.5 |

### 共振等级

| 得分 | 等级 | 含义 |
|------|------|------|
| 12-16 | S 级 | 极强共振，高置信度 |
| 8-11 | A 级 | 强共振，值得关注 |
| 5-7 | B 级 | 中等共振，需叙事支持 |
| < 5 | C 级 | 弱共振，不推荐 |

### 与叙事分析的结合

| 共振等级 | Bias 状态 | 结论 |
|----------|----------|------|
| S + Bias 一致 | 最强信号 | A+ 自然高分 |
| S + Bias 不明确 | 值得关注 | 谨慎小仓位 |
| A + Bias 一致 | 强信号 | 正常仓位 |
| B + Bias 强 | 可做 | 位点不精确但方向对 |
| C + 任何 | 不做 | 共振不够 |

### 输出格式

```json
{
  "confluence_zones": [
    {
      "price_range": [21450, 21460],
      "score": 15,
      "grade": "S",
      "components": [
        {"dimension": "H4 SIBI", "weight": 3, "detail": "21445-21465"},
        {"dimension": "H1 -OB", "weight": 2, "detail": "21448-21462"},
        {"dimension": "PDH", "weight": 2, "detail": "21455"},
        {"dimension": "OTE 79%", "weight": 1, "detail": "21452"},
        {"dimension": "EQH", "weight": 2, "detail": "21458"},
        {"dimension": "ES SMT", "weight": 2, "detail": "ES 对应位有 FVG"},
        {"dimension": "Premium zone", "weight": 2, "detail": "Above EQ 21450"},
        {"dimension": "Macro window", "weight": 1, "detail": "9:50-10:10 AM"}
      ]
    },
    {
      "price_range": [21380, 21390],
      "score": 10,
      "grade": "A",
      "components": [...]
    }
  ]
}
```

### 在架构中的位置

```
Ingestion → Calculator ──┐
                         ├→ Confluence Scorer → Guardian → Dispatch
         → LLM 分析 ────┘
           (Calculator 输出注入 prompt，但 LLM 独立发现额外位点)
```

### 权重迭代

初始权重基于 ICT 方法论的优先级设定。后续通过 Audit 数据迭代：
- 跑一段时间后统计各维度对实际准确率的贡献
- 提高准确率高的维度权重，降低低的
- 这是未来 Phase 的工作
