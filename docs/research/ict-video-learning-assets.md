# ICT 视频学习资料概念提取

> 来源：/home/patrick/ict_trading_learning/
> 生成日期：2026-04-14
> 扫描范围：全部目录结构、所有 .md/.json/.txt 内容文件

---

## 一、目录总览

### 1.1 项目性质

`ict_trading_learning/` 是一个基于 Gemini API 的 ICT 视频自动解析项目。通过 `parse_youtube.py` 工具对 YouTube 公开课程视频进行结构化分析，产出中文 Markdown（人类阅读）+ JSON（机器索引）双层输出。

### 1.2 目录结构

```
ict_trading_learning/
├── CLAUDE.md                              # 项目上下文说明
├── docs/
│   ├── content-plan.md                    # 内容梳理方案（概念框架+Pipeline）
│   ├── content-schema.md                  # 标准化输出格式设计
│   ├── full-directory.md                  # 591 视频完整目录
│   ├── 2016-2017-mentorship-overview.md   # 68 课内容体系总览
│   └── progress.md                        # 进度追踪
├── data/
│   ├── processed/
│   │   ├── 2016-2017-mentorship/          # 114 md + 114 json（12 个月）
│   │   └── charter-models/               # 34 md + 34 json（13 个模型）
│   ├── raw/
│   │   ├── wiki/course-index.json         # 课程索引（含中英标题）
│   │   └── subtitles/                     # 原始字幕文件
│   └── index/                             # 知识图谱索引（schema 已初始化，数据为空）
├── output/                                # 早期解析输出（3 个文件，预标准化）
├── scripts/                               # 批处理脚本
├── tools/parse_youtube.py                 # 核心：Gemini 视频解析器
├── site/                                  # Astro 静态站（开发中）
└── prototype/                             # UI 原型（暂停）
```

### 1.3 文件统计

| 类别 | 文件数 | 说明 |
|------|--------|------|
| 2016-2017 Mentorship .md | 114 | M01-M12，12 个月，114/115 课已完成 |
| 2016-2017 Mentorship .json | 114 | 结构化概念数据 |
| Charter Models .md | 34 | 13 个价格行为模型 |
| Charter Models .json | 34 | 结构化概念数据 |
| 文档 .md | 5 | 内容方案、schema、进度等 |
| 早期输出 .txt/.md | 3 | Frank369 市场回顾 + ICT 2026 评论 |
| Wiki 索引 .json | 1 | 完整课程目录（中英） |
| 知识图谱索引 .json | 4 | Schema 已建，数据待填充 |
| **合计内容文件** | **~310** | 不含 node_modules/prototypes |

### 1.4 已计划但尚未处理的系列

根据 `docs/full-directory.md`，项目已完整规划以下系列（591 视频），但仅 2016-2017 Mentorship 和 Charter Models 已完成解析：

| 系列 | 视频数 | 处理状态 |
|------|--------|----------|
| 2016-2017 Mentorship | 107 (114 done) | 99.1% 完成 |
| Charter Price Action Models | 34 | 已完成（部分失败因 token 限制） |
| 2022 Mentorship | 45 | 目录已建，待处理 |
| 2023 Mentorship | 105 | 目录已建，待处理 |
| 2024 Mentorship | 51 | 目录已建，待处理 |
| Market Maker Primer Course | 24 | 目录已建，待处理 |
| OTE Pattern Recognition | 20 | 目录已建，待处理 |
| Scout Sniper Field Guide | 8 | 目录已建，待处理 |
| Trading Plan Development | 7 | 目录已建，待处理 |
| Precision Trading Concepts | 3 | 目录已建，待处理 |
| High Probability Scalping | 3 | 目录已建，待处理 |
| WENT (新交易者须知) | 5 | 目录已建，待处理 |
| Market Maker Series 2014 | 5 | 目录已建，待处理 |
| If I Could Go Back | 4 | 目录已建，待处理 |
| Micro-Market Structure | 2 | 目录已建，待处理 |

---

## 二、2016-2017 Mentorship 课程体系概念提取

> 基于 114 个已解析视频的 Markdown + JSON 文件。本系列是 ICT 方法论的系统性教学，共 12 个月，从基础到高级。

### 2.1 月度课程主题与核心概念群

#### M01 - 交易设置基础（Sep 2016）| 8 课 | 入门-中级

**核心主题：** 建立 ICT 方法论的基本认知框架

**课程递进：**
1. 交易设置的要素 - 四种市场状态 + 四种机构订单流参考点
2. 做市商如何操控市场 - Market Efficiency Paradigm, IPDA
3. 当前应关注什么 - 学习路径指导
4. 均衡 vs 折价 - Equilibrium + Discount + Fibonacci
5. 均衡 vs 溢价 - Premium + OTE
6. 公允估值 - Fair Valuation, Liquidity Void 回补
7. 流动性清除 - 高阻力 vs 低阻力 Liquidity Run
8. 冲击性价格摆动与市场延伸 - Impulse Price Swing, Market Protraction

**核心概念：** Equilibrium(63次), Liquidity(22), Discount(21), Consolidation(20), Fair Valuation(20), Smart Money(19), Expansion(17), OTE(16)

---

#### M02 - 风险管理与账户增长（Oct 2016）| 8 课 | 中级

**核心主题：** 从概念认知过渡到实战交易

**课程递进：**
1. 无高风险增长小账户 - 1-2% 风险比例
2. 构建低风险交易设置 - HTF 方向 + LTF 精准入场
3. 每月赚取 10% - Bullish OB 入场 + R 倍数管理
4. 亏损不影响盈利能力 - 交易心理
5. 有效减少亏损交易 - Mean Threshold 精细化入场
6. 选择高回报设置的秘密 - "七点共识"三层视角体系
7. 做市商陷阱：假旗形 - False Flag 识别
8. 做市商陷阱：假突破 - False Breakout 识别

**核心概念：** Buy Stops(20), Intermediate Perspective(20), Short-Term Perspective(20), Big Picture(18), Market Maker Trap(16), False Breakouts(15), Reward to Risk Ratio(13)

---

#### M03 - 机构机制（Nov 2016）| 8 课 | 中级

**核心主题：** 深化机构交易视角

**课程递进：**
1. 时间框架选择与定义设置
2. 机构订单流 (Institutional Order Flow)
3. 机构赞助 (Institutional Sponsorship)
4. 预判能力发展
5. 机构市场结构 (Institutional Market Structure)
6. 宏观经济到微观技术
7. 做市商陷阱：趋势线幻影
8. 做市商陷阱：头肩形态

**核心概念：** Position Trader/Swing Trader/Short Term Trader/Day Trader 分类, 时间框架层次 (Monthly/Weekly/Daily/4H), HTF 主导 LTF 原则, 价格行为核心分析

---

#### M04 - 订单块理论深化（Dec 2016）| 14 课 | 中级-高级 [概念密度最高月份]

**核心主题：** ICT 方法论的技术核心 - Block 体系完整体系

**课程递进：**
1. 利率对货币交易的影响 - 30Y/10Y/5Y 利率三元组
2. 强化流动性概念与价格传递 - Internal vs External Liquidity, LRLR
3. 强化 Orderblock 理论 - Bullish OB 识别/验证/入场
4. Mitigation Block - 缓解块
5. Breaker Block - 突破块（假突破→MSS→回测 = Breaker）
6. Rejection Block - 拒绝块
7. Reclaimed Block - 回收块
8. Propulsion Block - FVG 内嵌推进块
9. Vacuum Block - 流动性真空缺口
10. 流动性空缺 (Liquidity Voids)
11. 流动性池 (Liquidity Pools)
12. 强化 Fair Value Gaps
13. 做市商陷阱：动量背离幽灵
14. 做市商陷阱：双顶与双底

**核心概念：** Gap(50), FVG(31), Order Block(27), Breaker Block(27), Liquidity(23), Sell Stops(18), Liquidity Void(16), Propulsion Block(15)

**六大 Block 类型体系：**
| Block 类型 | 英文名 | 定义 |
|-----------|--------|------|
| 订单块 | Order Block | 扩张前做市商在均衡附近留下的最后反向 K 线 |
| 缓解块 | Mitigation Block | 机构缓解/对冲不利头寸的回测区域 |
| 突破块 | Breaker Block | 假突破→MSS 后形成的支撑/阻力区域 |
| 拒绝块 | Rejection Block | 主要高低点反转处的 K 线实体 |
| 回收块 | Reclaimed Block | Market Maker Buy/Sell Model 中的回收块 |
| 推进块 | Propulsion Block | FVG 内嵌的续行推进块 |
| 真空块 | Vacuum Block | 波动事件引起的流动性真空缺口 |

---

#### M05 - 宏观分析与长期交易（Jan 2017）| 18 课 | 中级-高级 [课程数量最多]

**核心主题：** 从技术分析上升到宏观分析

**课程递进：**
1. 季度性转变与 IPDA 数据范围
2. 季度转换与 Open Float
3. 使用 IPDA Data Ranges
4. IPDA Data Ranges 与 Open Float 应用
5. 定义机构摆动点 - Breaker + Failure Swing
6. 10 年期国债收益率在 HTF 分析中的应用
7. 用 10 年期国债收益率限定交易条件 - SMT 分歧
8. 利率差异 - 央行利率差异识别强弱货币
9. 跨市场分析 - 全球市场互联互通
10-12. 季节性趋势应用 (看涨/看跌/理想)
13. 资金管理和 HTF 分析
14. 定义高时间框架 PD Arrays
15. 交易条件与设置进展
16. 止损入场技术
17. 限价入场技术
18. 持仓交易管理

**核心概念：** Seasonal Tendencies(57), Intermarket Analysis(33), Stop Order(32), PD Array(27), Institutional Order Flow(26), Commodities(22), Bonds(20), Open Float, IPDA Data Ranges (20/40/60 天)

---

#### M06 - 波段交易（Feb 2017）| 8 课 | 中级-高级

**课程递进：**
1. 理想波段交易条件
2. 成功波段交易的要素 - HTF + 机构订单流 + 利率 + COT
3. 经典波段交易方法
4. 牛市高概率波段设置 - HTF PD Array 嵌套
5. 熊市高概率波段设置 - PD Array Matrix 熊市应用
6. 降低风险最大化回报 - 4H 入场紧密止损
7. 选择爆发性市场的关键 - 八大特征 (Hallmarks)
8. 百万美元摆动设置 - 完整 Swing Trade 执行流程

**核心概念：** Premium Array(20), PD Array Matrix(18), Seasonal Tendency(17), Swing Trading(16), Bearish OB(12), MWD 三级框架(Monthly-Weekly-Daily)

---

#### M07 - 短线交易（Mar 2017）| 8 课 | 中级-高级

**课程递进：**
1. 结合 HTF 月线和周线区间
2. 定义周度区间形态 - 12 种 Weekly Range Profile
3. 市场操纵者操纵模板 - 周二/周三高低点规律
4. 融合 IPDA 数据范围与 PD Arrays
5-6. 低阻力流动性运行 (Part 1 & 2) - 4H PD Array Matrix
7. 周内市场反转与叠加模型
8. 一击必杀交易模型 (OSOK) - COT 对冲程序 + 时间价格精准交易

**核心概念：** PD Array Matrix(20), Equilibrium(16), HTF Discount/Premium Array(15), FVG(13), One Shot One Kill(12), Manipulation(12), Weekly Range Profiles (12 种模板), Market Maker Manipulation Templates

---

#### M08 - 日内交易模型（Apr 2017）| 8 课 | 入门-中级

**课程递进：**
1. ICT 日内交易精要
2. 定义日内区间 - IPDA True Day (0 GMT), Killzone 时间
3. 央行交易员区间 (CBDR) - 计算方法与 Standard Deviation
4. 预测每日高点与低点 - CBDR + SD 投射 HOD/LOD
5. 盘中市场形态 - 4 种伦敦盘形态
6. 何时避免伦敦交易时段 - ADR 异常规则
7. 高概率日内交易设置
8. 日内交易与 HTF 入场结合 - Power of Three

**核心概念：** CBDR(36), Asian Range(23), Standard Deviation(23), London Killzone(13), Judas Swing(13), IPDA True Day(13), Power of Three (PO3)

---

#### M09 - 日内交易进阶（May 2017）| 8 课 | 高级

**课程递进：**
1. 情绪效应 - Smart Money 利用散户情绪
2. 填补数字 - IPDA 零售枢轴点/CBDR/Asian Range 作为流动性诱饵
3. 每日 20 点 - 小目标策略
4. 整合中的交易 - 机构在盘整中积累/分配订单的行为
5. 交易市场反转
6-7. Bread & Butter 买入/卖出设置
8. ICT 日内交易例程

**核心概念：** Asian Range(32), Pivot Points(18), Opening Price(13), CBDR(11), Bread & Butter Setups, Open Float 在盘整中的作用

---

#### M10 - 多资产交易（Jun 2017）| 19 课 | 中级-高级

**课程递进：**
1. COT 报告分析 - 商业交易者对冲程序
2. 相对强度分析与积累/分配
3. 商品季节性趋势
4. 溢价 vs Carrying Charge 市场
5. Open Interest 秘密与 Smart Money 足迹
6-9. 债券交易（基础/分仓/盘整/趋势）
10-14. 指数期货（基础/AM趋势/PM趋势/投射/设置）
15-18. 股票交易（季节性/看涨看盘/看跌看盘/期权）
19. 多资产分析的重要性

**核心概念：** COT Report, Hedging Programs, Net Zero Basis, Commercials/Non-Commercials/Small Speculators, Relative Strength Analysis, Open Interest, Bond Trading (30Y ZB), Index Futures (ES/NQ/YM), Opening Range, AM Trend/PM Trend, Split Session Rules, Stock Seasonals, Options Trading

---

#### M11 - 巨额交易 Mega-Trades（Jul 2017）| 4 课 | 高级

**课程递进：**
1. 商品巨额交易 - 季节性 + COT + SMT 三重确认
2. 外汇巨额交易
3. 股票巨额交易
4. 债券巨额交易 - 利率 SMT 背离确认

**核心概念：** Megatrade, Seasonal Tendencies 主导作用, SMT Divergence (利率), Terminus (时间+价格目标融合), 5:1-8:1 风险回报比

---

#### M12 - 自上而下分析综合回顾（Aug 2017）| 4 课 | 高级

**课程递进：**
1. 长期自上而下分析 (Monthly→Weekly)
2. 中期自上而下分析 (Weekly→Daily)
3. 短期自上而下分析 (Daily→4H)
4. 日内自上而下分析 (4H→M15→M5)

**核心概念：** Top-Down Analysis 四层级, 时间框架对齐方法, 宏观→微观递进, 综合模型整合

---

### 2.2 核心概念频次排行（Top 30）

| 排名 | 频次 | 英文名 | 中文名 | 类别 |
|------|------|--------|--------|------|
| 1 | 100 | Equilibrium | 均衡点 | 价格结构 |
| 2 | 90 | Order Block | 订单块 | 价格结构 |
| 3 | 84 | Fair Value Gap (FVG) | 公平价值缺口 | 流动性 |
| 4 | 69 | Liquidity Void | 流动性空隙 | 流动性 |
| 5 | 60 | Liquidity | 流动性 | 流动性 |
| 6 | 59 | Seasonal Tendencies | 季节性趋势 | 时间周期 |
| 7 | 57 | Asian Range | 亚洲区间 | 时间周期 |
| 8 | 50 | Gap | 缺口 | 价格结构 |
| 9 | 48 | Institutional Order Flow | 机构订单流 | 订单流 |
| 10 | 48 | Discount | 折扣区 | 价格结构 |
| 11 | 46 | Sell Stops | 止损卖单 | 流动性 |
| 12 | 46 | Buy Stops | 买入止损 | 订单流 |
| 13 | 46 | Intermarket Analysis | 跨市场分析 | 框架 |
| 14 | 45 | Consolidation | 盘整 | 价格结构 |
| 15 | 44 | PD Array Matrix | PDA 矩阵 | 框架 |
| 16 | 42 | Premium | 溢价区 | 价格结构 |
| 17 | 36 | CBDR | 央行交易员区间 | 价格结构 |
| 18 | 35 | Premium Array | 溢价数组 | 价格结构 |
| 19 | 34 | Bearish Order Block | 看跌订单块 | 订单流 |
| 20 | 33 | Top Down Analysis | 自上而下分析 | 框架 |
| 21 | 33 | Breaker Block | 突破块 | 价格结构 |
| 22 | 33 | Rejection Block | 拒绝块 | 模型 |
| 23 | 32 | Stop Order | 止损挂单 | 执行 |
| 24 | 30 | Smart Money | 聪明钱 | 订单流 |
| 25 | 29 | PDA (Price Delivery Array) | 价格交付数组 | 框架 |
| 26 | 28 | Bullish Orderblock | 看涨订单块 | 订单流 |
| 27 | 27 | Reward to Risk Ratio | 盈亏比 | 风险管理 |
| 28 | 27 | Premium Market | 溢价市场 | 价格结构 |
| 29 | 24 | Bullish Order Block | 看涨订单块 | 订单流 |
| 30 | 23 | Standard Deviation | 标准差 | 价格结构 |

---

## 三、Charter Price Action Models 概念提取

> 基于 34 个已解析视频。13 个独立价格行为模型，每个包含核心讲座 + 放大讲座 + Trade Plan & Algorithmic Theory。

### 3.1 模型清单

| # | 模型名 | 中文名 | 课程数 | 核心逻辑 |
|---|--------|--------|--------|----------|
| 1 | Intraday Scalping | 日内剥头皮 | 3 | PDH/PDL + NYKZ + OTE 62% + 20 点管理 |
| 2 | Short Term Model | 短期模型 | 2 | （token 限制未完成） |
| 3 | Swing Trading | 波段交易 | 2 | （token 限制未完成） |
| 4 | Position Trading | 仓位交易 | 3 | 季度转换 + COT 对冲 + SMT 背离 + 日线入场 |
| 5 | Day Trading - Volatility Expansions | 日内波动率扩张 | 4 | IPDA + MSS + Breaker/OB + Killzone |
| 6 | Universal Trading Model I | 通用交易模型 I | 6 | PD Array + FVG + OB 多 TF 框架 |
| 7 | Universal Trading Model II | 通用交易模型 II | 3 | UTM 进阶 |
| 8 | Targeting 6% Per Month | 月目标 6% | 2 | 每周 25 点 + IOFED + 纪律优先 |
| 9 | One Shot One Kill | 一击必杀 | 2 | COT + IPDA + PDA Matrix + 精准单笔 |
| 10 | Swing Trading II | 波段交易 II | 2 | PDA Matrix 波段进阶 |
| 11 | Day Trading II | 日内交易 II | 2 | 日内进阶模型 |
| 12 | Scalping Intraday Model | 剥头皮日内模型 | 2 | 微观时间框架剥头皮 |
| 13 | 2022 YouTube Model | 2022 YouTube 模型讲座 | 1 | 指数期货 + LR→SMS→FVG 框架 |

### 3.2 Charter Models 独特概念

| 概念 | 来源模型 | 说明 |
|------|----------|------|
| IPDA 20-Day Data Range | CPM 1 | 最近 20 个交易日的高低点构成的流动性区间 |
| Symmetrical Price Swing | CPM 1 | 对称价格摆动目标设定 |
| IOFED | CPM 8 | 机构订单流入场演练（5 分钟图） |
| Weekly Range Bias | CPM 8 | 周度范围偏差判断 |
| Volatility Injection | CPM 8 | 经济日历事件引发的波动注入 |
| Quarterly Shift | CPM 4 | 季度性转换（机构季度资产重配） |
| Terminus | CPM 4 | 时间+价格目标的融合点 |
| Liquidity Raid (LR) | CPM 13 | 流动性掠夺 - 快速突破触发止损 |
| Market Structure Shift (SMS) | CPM 13 | 市场结构转移（与 MSS 同义） |
| Price is Fractal | CPM 13 | 分形原则 - 同样逻辑适用于任何时间框架 |

---

## 四、概念分类体系（完整版）

### 4.1 市场结构概念 (Market Structure)

| 概念 | 英文名 | 定义 |
|------|--------|------|
| 扩张 | Expansion | 价格从均衡水平快速移动 |
| 回撤 | Retracement | 价格回移到最近创建的价格区间内 |
| 反转 | Reversal | 价格朝当前方向相反的方向移动 |
| 盘整 | Consolidation | 价格在明确交易区间内无方向移动 |
| 市场结构转变 | Market Structure Shift (MSS) | 价格突破关键 Swing H/L 确认趋势转变 |
| 摆动高点 | Swing High | 两侧有更低高点的 K 线高点 |
| 摆动低点 | Swing Low | 两侧有更高低点的 K 线低点 |
| 冲击性价格摆动 | Impulse Price Swing | 快速强劲的价格运动 |
| 市场延伸 | Market Protraction | 价格运动的时间维度延展 |
| 位移 | Displacement | 强力价格运动创造 FVG/Imbalance |
| 交易区间 | Dealing Range | 价格操作的范围区间 |
| 重新定价 | Repricing | 市场快速大幅价格调整 |

### 4.2 PD Arrays（价格交付数组）

| 概念 | 英文名 | 定义 |
|------|--------|------|
| 订单块 | Order Block (OB) | 扩张前做市商留下的最后反向 K 线 |
| 看涨订单块 | Bullish OB | 上涨扩张前的最后下跌 K 线 |
| 看跌订单块 | Bearish OB | 下跌扩张前的最后上涨 K 线 |
| 缓解块 | Mitigation Block | 机构对冲不利头寸的回测区域 |
| 突破块 | Breaker Block | 假突破→MSS 后的支撑/阻力区域 |
| 拒绝块 | Rejection Block | 主要反转点的 K 线实体分析 |
| 回收块 | Reclaimed Block | MM Buy/Sell Model 中的回收块 |
| 推进块 | Propulsion Block | FVG 内嵌的续行推进块 |
| 真空块 | Vacuum Block | 波动事件引起的流动性真空 |
| 公允价值缺口 | Fair Value Gap (FVG) | 快速移动造成的未交易价格区域 |
| 流动性空白 | Liquidity Void | HTF 的 FVG 在 LTF 的表现 |
| 结果性侵蚀 | Consequent Encroachment (CE) | FVG 的 50% 中点 |
| 均衡 | Equilibrium | 买卖双方力量平衡的中间价位 |
| 溢价区 | Premium | 均衡之上的价格区域 |
| 折扣区 | Discount | 均衡之下的价格区域 |
| PD Array Matrix | PDA 矩阵 | 所有 PDA 元素的系统化矩阵框架 |
| Mean Threshold | 均值阈值 | OB 的 50% 位置，精细化入场点 |

### 4.3 入场模型 (Entry Models)

| 模型 | 英文名 | 核心序列 |
|------|--------|----------|
| 最优入场点 | Optimal Trade Entry (OTE) | 位移→回撤 62-79% Fib→FVG/OB 入场 |
| 一击必杀 | One Shot One Kill (OSOK) | COT + IPDA + PDA Matrix + 多维共振 |
| 乌龟汤做多 | Turtle Soup Long | 旧低被突破→即时反转做多 |
| 乌龟汤做空 | Turtle Soup Short | 旧高被突破→即时反转做空 |
| 犹大摆动 | Judas Swing | Session 开盘假突破参考价→反转 |
| Bread & Butter 买入 | B&B Buy Setup | 标准扫荡→OB 入场（多种 Session 变体） |
| Bread & Butter 卖出 | B&B Sell Setup | 标准扫荡→OB 入场（卖出变体） |
| 日内剥头皮模型 | Intraday Scalping | PDH/PDL + NYKZ + OTE + 20 点管理 |
| 仓位交易模型 | Position Trading | 季度转换 + COT + SMT 背离 |
| 通用交易模型 | Universal Trading Model (UTM) | PD Array + FVG + OB 多 TF 框架 |
| 每周 25 点模型 | 25 Pips Per Week | 每周一单 + IOFED + 纪律优先 |
| 百万美元摆动设置 | Million Dollar Swing Setup | 完整波段交易执行流程 |
| 低阻力流动性运行 | Low Resistance Liquidity Run (LRLR) | PDA 到 PDA 的顺势交易 |
| 指数期货模型 (CPM 13) | Charter Model 13 | LR→SMS→FVG 日内框架 |

### 4.4 时间与交易时段 (Time & Sessions)

| 概念 | 英文名 | 定义/时间 |
|------|--------|-----------|
| 亚洲击杀区 | Asian Killzone | 8:00 PM - 12:00 AM ET |
| 伦敦击杀区 | London Killzone | 2:00 AM - 5:00 AM ET |
| 纽约击杀区 | New York Killzone | 7:00 AM - 10:00 AM ET |
| 伦敦收盘击杀区 | London Close Killzone | 10:00 AM - 12:00 PM ET |
| IPDA 真日 | IPDA True Day | 以 0:00 GMT 为日线分割 |
| 央行交易员区间 | CBDR | 2:00 PM - 8:00 PM ET |
| 三力法则 | Power of 3 (PO3) | Accumulation→Manipulation→Distribution |
| AMD 周期 | Accumulation-Manipulation-Distribution | 价格的三阶段周期（任何时间框架） |
| 季度转换 | Quarterly Shift | 季度初期机构资产重配导致的趋势转变 |
| IPDA 数据范围 | IPDA Data Ranges | 过去 20/40/60 个交易日的高低点范围 |
| 标准差投射 | Standard Deviation Projection | 基于 CBDR 的 1-4 SD 投射 HOD/LOD |
| 周度区间形态 | Weekly Range Profiles | 12 种周度价格形态模板 |
| 做市商操纵模板 | MM Manipulation Templates | 周二/周三高低点规律 |
| 伦敦盘形态 | London Session Profiles | 4 种伦敦盘形态（正常/延迟/诱导） |

### 4.5 流动性概念 (Liquidity)

| 概念 | 英文名 | 定义 |
|------|--------|------|
| 流动性池 | Liquidity Pool | 止损订单大量聚集的区域 |
| 买方流动性 | Buy Side Liquidity (BSL) | 旧高点上方的买入止损聚集区 |
| 卖方流动性 | Sell Side Liquidity (SSL) | 旧低点下方的卖出止损聚集区 |
| 内部区间流动性 | Internal Range Liquidity (IRL) | 交易范围内部的 FVG/LV |
| 外部区间流动性 | External Range Liquidity (ERL) | 交易范围外部的流动性池 |
| 流动性猎杀 | Liquidity Run | 价格快速扫过流动性区域 |
| 止损猎杀 | Stop Hunt / Stop Run | 做市商推动价格触发止损 |
| 假突破 | False Break | 价格短暂突破关键位后迅速反转 |
| 开放浮动 | Open Float | 未平仓合约/未执行订单聚集 |
| 流动性掠夺 | Liquidity Raid | 快速突破触发大量止损订单 |
| 高阻力流动性运行 | High Resistance Liquidity Run | 逆趋势的流动性运行 |
| 低阻力流动性运行 | Low Resistance Liquidity Run (LRLR) | 顺趋势的流动性运行 |
| 工程师设定的流动性 | Engineered Liquidity | 机构主动构造的流动性目标 |

### 4.6 风险管理规则 (Risk Management)

| 规则 | 来源 | 说明 |
|------|------|------|
| 1-2% 最大风险 | M02 | 每笔交易不超过账户 1-2% |
| 盈亏比 ≥ 2:1 | M02, M06 | 最低 2:1，理想 3:1-5:1 |
| 分批止盈 | M02 | 多个目标分批平仓 |
| 每周一单纪律 | CPM 8 | 25 点模型强制每周一笔 |
| 连胜后减小仓位 | CPM 8 | 避免过度自信 |
| 连败后减小仓位 | CPM 8 | 保护心理资本 |
| 止损移动规则 | CPM 1 | 20 点利润后移动止损保护 |
| 不惧亏损心态 | M02-L04 | 亏损是交易成本，低胜率仍可盈利 |
| 七点共识选择体系 | M02-L06 | Big Picture + Intermediate + Short-Term 三层视角 |
| 何时不交易 | M08-L06 | ADR 异常、连续单边日、重大新闻前后 |
| 50/50 概率 = 不交易 | 2026 Commentary | 市场两方向等概率时不进场 |

### 4.7 分析框架 (Frameworks)

| 框架 | 英文名 | 核心逻辑 |
|------|--------|----------|
| 市场效率范式 | Market Efficiency Paradigm | Smart Money vs Speculative Uninformed Money |
| IPDA | Interbank Price Delivery Algorithm | 银行间算法驱动四种市场状态循环 |
| 自上而下分析 | Top-Down Analysis | Monthly→Weekly→Daily→4H→M15 逐层递进 |
| PD Array Matrix | PDA 矩阵框架 | 溢价/折扣区内所有 PDA 元素的系统矩阵 |
| COT 对冲程序 | COT Hedging Program | 商业交易者净头寸的零线基准分析 |
| SMT 背离 | Smart Money Technique Divergence | 相关资产走势背离揭示机构意图 |
| 跨市场分析 | Intermarket Analysis | DXY + 债券 + 股指 + 商品联动 |
| 季节性趋势 | Seasonal Tendencies | 年度/季度可预测的价格模式 |
| MWD 三级框架 | Monthly-Weekly-Daily | 波段交易的三层级分析 |
| 做市商买卖模型 | Market Maker Buy/Sell Model | 做市商的四阶段操作周期 |

### 4.8 多资产概念 (Multi-Asset，M10-M11 独有)

| 概念 | 英文名 | 说明 |
|------|--------|------|
| COT 报告 | Commitment of Traders | CFTC 每周发布的持仓数据 |
| 商业交易者 | Commercials | 对冲型参与者（生产商/消费者） |
| 非商业交易者 | Non-Commercials | 投机型大型基金 |
| 小型投机者 | Small Speculators | 散户 |
| Open Interest | 未平仓合约 | Smart Money 足迹 |
| 相对强度分析 | Relative Strength Analysis | 跨资产强弱比较 |
| Carrying Charge | 持有成本 | 期货溢价 vs Carrying Charge 市场 |
| Opening Range (债券) | 开盘范围 | 债券交易的开盘范围概念 |
| Split Session (债券) | 分仓规则 | 债券交易的分仓日规则 |
| AM Trend / PM Trend | 上午/下午趋势 | 指数期货的日内趋势分段 |
| Projected Range | 投射范围 | 指数期货的范围投射 |
| 股票季节性 | Stock Seasonals | 个股的月度季节性摆动 |
| 期权交易 | Options Trading | 使用期权执行 ICT 模型 |
| Megatrade | 巨额交易 | 捕捉多月级别大趋势 |
| Terminus | 终点 | 季节性+价格目标的融合终点 |

---

## 五、概念关联网络

### 5.1 核心概念前置依赖链

```
Level 0 (基础认知)
  Smart Money ←对比→ Speculative Uninformed Money
  Market Efficiency Paradigm ──包含──> Smart Money
  IPDA ──被控制──> Smart Money

Level 1 (价格传递四状态)
  IPDA ──驱动──> Expansion / Retracement / Reversal / Consolidation

Level 2 (价格结构工具)
  Expansion ──共现──> Order Block
  Retracement ──共现──> Fair Value Gap / Liquidity Void
  Reversal ──共现──> Liquidity Pool / Stop Runs
  Consolidation ──共现──> Equilibrium
  Consolidation ──演变为──> Expansion

Level 3 (Block 体系)
  Order Block ──包含──> Bullish/Bearish OB
  Order Block ──衍生──> Breaker / Rejection / Reclaimed / Propulsion / Vacuum Block
  Bullish OB ──包含──> Mean Threshold

Level 4 (价格区间框架)
  Equilibrium ──划分──> Premium / Discount
  Discount ──包含──> OTE (62-79% Fib)
  PD Array Matrix ──包含──> Premium Array / Discount Array / FVG

Level 5 (宏观分析层)
  Top Down Analysis ──应用于──> Institutional Order Flow
  Macro Analysis ──包含──> Seasonal Tendencies / Intermarket Analysis
  IPDA Data Ranges ──融合──> PD Array Matrix

Level 6 (时间框架模型)
  CBDR ──应用──> Standard Deviation ──投射──> HOD/LOD
  Asian Range ──属于──> Consolidation
  Manipulation ──包含──> Judas Swing
  Power of 3 ──包含──> AMD (Accumulation→Manipulation→Distribution)
```

### 5.2 最重要的概念关系对

| 关系 | 类型 | 说明 |
|------|------|------|
| Smart Money <-> Speculative Uninformed Money | 对比 | 驱动者 vs 被利用者 |
| Institutional Order Flow -> Order Block | 包含 | OB 是机构订单流在图表的表现 |
| Order Block <-> Fair Value Gap | 共现 | 共同构成入场依据 |
| Fair Value Gap <-> Liquidity Void | 共现 | HTF FVG 在 LTF 表现为 LV |
| PD Array Matrix -> Premium / Discount | 包含 | 划分溢价和折扣区域 |
| Top Down Analysis -> Institutional Order Flow | 应用 | 通过 TDA 确定 IOF 方向 |
| CBDR -> Standard Deviation -> HOD/LOD | 投射 | 日内定价工具链 |
| Consolidation -> Expansion | 演变 | 盘整是蓄力，扩张是释放 |
| Seasonal Tendencies -> Quarterly Shift | 驱动 | 季节性驱动季度转变 |
| COT Hedging Program + SMT Divergence | 共振 | 多因素确认高概率设置 |

---

## 六、与现有知识审计的比对

> 对比文件：/home/patrick/Michael/docs/research/ict-knowledge-audit.md

### 6.1 视频资料中有但现有审计已覆盖的核心概念

以下概念在两处均有充分覆盖（验证现有审计的完整性）：
- 全部 Block 体系（7 种）
- FVG/LV/PD Array/PDA Matrix
- Equilibrium/Premium/Discount
- Killzones (4 个 Session)
- CBDR + SD 投射
- AMD / PO3
- Top-Down Analysis
- OTE / Judas Swing / Turtle Soup
- SMT Divergence
- COT Analysis
- Intermarket Analysis

### 6.2 视频资料中的概念在现有审计中缺失或不足的

| 概念/内容 | 视频资料中的深度 | 现有审计状态 | 建议 |
|-----------|-----------------|-------------|------|
| **12 种 Weekly Range Profiles** | M07-L02 完整定义 12 种周度形态 | 审计仅有 3 种高概率 Profile | 补充完整 12 种 |
| **4 种 London Session Profiles** | M08-L05 详细定义 | 审计仅有 3 种 Daily Profile | 补充 London 专属形态 |
| **Open Float** | M05 专课讲解，与 IPDA Data Ranges 配合 | 审计未提及 | 纳入 |
| **做市商陷阱系列 (6 种)** | M02(2种)+M03(2种)+M04(2种) | 审计未列为独立概念 | 纳入 |
| **利率分析三元组** | M04-L01 (30Y/10Y/5Y) + M05 深化 | 审计仅提及 SMT | 补充利率工具 |
| **Impulse Price Swing / Market Protraction** | M01-L08 专课 | 审计未提及 | 纳入 |
| **七点共识选择体系** | M02-L06 详细框架 | 审计未提及 | 纳入风险管理 |
| **八大特征 (Hallmarks)** | M06-L07 爆发性市场选择 | 审计未提及 | 纳入 |
| **M10 多资产体系** | 19 课完整覆盖 COT/债券/指数/股票 | 审计仅有 COT 基础 | 大幅补充 |
| **Megatrade 方法论** | M11 (4 课) 完整跨资产 Megatrade | 审计未提及 | 纳入 |
| **Terminus 概念** | CPM 4 时间+价格融合终点 | 审计未提及 | 纳入 |
| **IOFED** | CPM 8 机构订单流入场演练 | 审计列为补充模型 | 已覆盖但可深化 |
| **Bread & Butter 设置** | M09 (2 课) 买入/卖出标准设置 | 审计列为补充模型 | 已覆盖但可深化 |
| **盘整交易策略** | M09-L04 专课 | 审计未独立覆盖 | 纳入 |
| **情绪效应** | M09-L01 散户情绪逆向利用 | 审计未提及 | 纳入 |
| **填补数字** | M09-L02 IPDA 利用零售参考点 | 审计未提及 | 纳入 |
| **AM/PM Trend (指数期货)** | M10-L11/L12 | 审计未提及 | 纳入 |
| **Opening Range (债券/指数)** | M10-L06/L10 | 审计未提及 | 纳入 |
| **Stock Seasonals + Options** | M10-L15-18 | 审计未提及 | 纳入 |
| **何时避免交易** | M08-L06 具体条件 | 审计有红旗但不同源 | 补充 |

### 6.3 现有审计中有但视频资料中较少出现的

以下概念主要来自 2022-2025 年更新内容，在 2016-2017 Mentorship + Charter Models 中出现较少：

| 概念 | 现有审计中的来源 |
|------|-----------------|
| Silver Bullet 窗口 | 2023 GEMS |
| Macros (5 个时间窗口) | 2023 GEMS |
| 1st Hour Dealing Range | 2026 Notes |
| Octane Levels | 2026 Notes |
| MMXM (4 阶段完整模型) | MMXM Handbook |
| The Sequence (两种) | MMXM The Sequence |
| IFVG Model | 2022 五大入场模型 |
| Unicorn Model | 2022 五大入场模型 |
| 2025 Model (4 条规则) | 2025 Masterclass |
| Event Horizon | 2023 GEMS |
| Quarter of the Wick | 2023 GEMS |
| 3 PDA 失败规则 | 2023 GEMS |
| 11 条 S&D 条件 | 2023 GEMS |
| NMO 框架 | PRE-MARKET-PLAN |
| Goldbach 体系 | Goldbach Trading 2024 |
| HIPPO | Goldbach Trading 2024 |
| Venom Model | Refactory |
| MEP | 重构版 |
| 30-Second Model | 重构版 |

---

## 七、统计汇总

### 7.1 内容规模

| 指标 | 数值 |
|------|------|
| 项目规划总视频数 | ~591 |
| 已完成解析视频数 | ~148 (114 Mentorship + 34 Charter) |
| 已提取独立概念数 | ~803 个（去重约 350+） |
| 已提取概念关系数 | ~571 条 |
| 内容覆盖课程系列 | 2 个（2016-2017 Mentorship + Charter Models） |
| 待处理课程系列 | 13+ 个 |

### 7.2 课程体系覆盖

| 维度 | 已覆盖 | 待补充 |
|------|--------|--------|
| 基础概念 (M01) | 完整 | - |
| 风险管理 (M02) | 完整 | - |
| 机构机制 (M03) | 完整 | - |
| 技术核心 (M04) | 完整 | - |
| 宏观分析 (M05) | 17/18 课 | 1 课因 token 限制 |
| 波段交易 (M06) | 完整 | - |
| 短线交易 (M07) | 完整 | - |
| 日内交易 (M08) | 完整 | - |
| 日内进阶 (M09) | 完整 | - |
| 多资产 (M10) | 完整 | - |
| 巨额交易 (M11) | 完整 | - |
| 综合回顾 (M12) | 完整 | - |
| Charter Models | 完整 | 部分因 token 限制失败 |
| 2022-2025 Mentorship | 未处理 | 目录已建 |
| 免费系列 (7+ 套) | 未处理 | 目录已建 |

### 7.3 概念类别分布

| 类别 | 概念数（估计） | 代表 |
|------|---------------|------|
| 价格结构 | ~40 | Equilibrium, OB, FVG, Discount, Premium |
| 流动性 | ~20 | BSL, SSL, IRL, ERL, Liquidity Raid |
| 订单流 | ~15 | IOF, Smart Money, Buy/Sell Stops |
| 时间周期 | ~20 | Killzones, CBDR, Seasonals, Quarterly Shift |
| 分析框架 | ~15 | IPDA, Top-Down, PDA Matrix, Intermarket |
| 入场模型 | ~15 | OTE, OSOK, UTM, Turtle Soup, B&B |
| 风险管理 | ~10 | R:R, Position Sizing, Psychology |
| 多资产 | ~15 | COT, Bonds, Indices, Stocks, Options |
| 做市商陷阱 | ~8 | False Flag, False Breakout, Divergence Phantoms |

---

## 八、对 Michael 系统的建议

### 8.1 高优先级补充

1. **Multi-Asset 分析模块** -- M10 的 19 课内容（COT 深度分析、债券/指数交易规则、AM/PM Trend）在 Michael 系统中几乎空白
2. **完整 Weekly Range Profiles** -- 12 种模板 vs 当前 3 种
3. **London Session Profiles** -- 4 种形态
4. **做市商陷阱识别** -- 6 种具体陷阱作为红旗规则源

### 8.2 中优先级补充

5. **Megatrade 框架** -- 适用于长线信号识别
6. **利率分析工具** -- 30Y/10Y/5Y 三元组 + 利率差异
7. **Open Float 概念** -- 流动性分析的补充维度
8. **情绪效应 + 填补数字** -- 日内分析的微观补充

### 8.3 未来数据利用

该项目仍有 ~443 个视频待处理（2022-2025 Mentorship + 免费系列），处理完成后将极大丰富 2022+ 年代的新概念覆盖（Silver Bullet, MMXM, 2025 Model 等的原始教学内容）。
