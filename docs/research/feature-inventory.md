# 功能点对照清单

> 两个前身项目的完整功能对比，按业务域分组

## 1. 报告生成（9 种报告类型）

| 报告类型 | 触发时间 | 原版 | 重构版 | 差异说明 |
|----------|----------|------|--------|----------|
| weekly_prep | 周日 | ✅ mega-prompt 单次生成 | ✅ WeeklyNarrative 步骤 | 重构版分步执行，有门控 |
| daily_bias | 每日 6PM ET | ✅ mega-prompt | ✅ Weekly 引用 + DailyBias 步骤 | 重构版自动引用周分析结果 |
| asia_pre | 每日 6:30PM ET | ✅ mega-prompt | ✅ Daily 引用 + Session 步骤 | 同上 |
| london_pre | 每日 1:30AM ET | ✅ mega-prompt | ✅ Daily 引用 + Session 步骤 | 同上 |
| nyam_pre | 每日 8AM ET | ✅ mega-prompt | ✅ Daily 引用 + Session + LTF + Signal | 重构版完整 5 步流水线 |
| nyam_open | 每日 9:15AM ET | ✅ mega-prompt | ✅ Session 更新 | 同上 |
| nypm_pre | 每日 1PM ET | ✅ mega-prompt | ✅ Daily 引用 + Session 步骤 | 同上 |
| daily_review | 收盘后 | ✅ Claude 自评 | ✅ Audit 层 4 维评分 | 重构版代码级评分 |
| weekly_review | 周五/周六 | ✅ Claude 自评 | ✅ Audit 聚合 | 重构版聚合历史数据 |

---

## 2. 数据采集

| 能力 | 原版 | 重构版 | 说明 |
|------|------|--------|------|
| TradingView MCP 采集 | ✅ 通过 Claude CLI（$0.19/次，~9 分钟） | ✅ 直接 JSON-RPC（免费，秒级） | 重构版性能/成本完胜 |
| 多品种支持 | ✅ 6 期货 + DXY | ✅ 6 期货 + DXY | 相同 |
| 多时间框架 | ✅ 7 个（W/D/H4/H1/M15/M5/M1） | ✅ 7 个 | 相同 |
| 按报告类型配置需求 | ❌ 每次全量采集 | ✅ REPORT_DATA_REQUIREMENTS | 重构版按需采集 |
| 增量更新 | ❌ 每次全量 | ✅ bootstrap/incremental/auto | 重构版支持 |
| 断点续传 | ❌ | ✅ resume-from-checkpoint | 重构版支持 |
| OHLCV 持久化 | ✅ full_collect.sh 批量写入 | ✅ MarketStore 完整实现 | 重构版更完善 |
| 数据完整性校验 | ✅ python3 JSON 验证 | ✅ DataManifest PASS/PARTIAL/FAIL | 重构版更结构化 |

---

## 3. ICT 分析能力

| 分析维度 | 原版 | 重构版 | 说明 |
|----------|------|--------|------|
| IPDA 3 周期分析（20D/40D/60D） | ✅ | ✅ | 相同 |
| HTF 订单流 | ✅ | ✅ | 相同 |
| Weekly Profile（12 模板） | ✅ | ✅ | 相同 |
| PO3 / The Sequence | ✅ | ✅ | 相同 |
| DOL 三问分析 | ✅ | ✅ | 相同 |
| DXY/SMT 背离 | ✅ | ✅ | 相同 |
| Seek & Destroy 过滤 | ✅ | ✅ | 相同 |
| CBDR | ✅ | ✅ | 相同 |
| PD Array 分析（22 种） | ✅ | ✅ 14 种（spec 定义） | 原版 Playbook 覆盖更全 |
| 入场模型匹配 | ✅ 4 层 17 模型 | ✅ 4 层 20 模型 | 重构版略多 |
| A+ Checklist（8 项） | ✅ | ✅ | 相同 |
| 红旗禁止交易条件 | ✅ 9 条 | ❌ 无独立列表 | 原版更明确 |
| TradingView 图表标注 | ✅ 水平线+矩形+文字+截图 | ❌ 无 | 原版独有 |

---

## 4. 质量保证

| 能力 | 原版 | 重构版 | 说明 |
|------|------|--------|------|
| A/B 测试基础设施 | ✅ 完整（双 worktree + 版本标记 + 双飞书群） | ❌ | 原版独有 |
| 三层验证（System B） | ✅ rules/preflight/validation | ❌ | 原版独有 |
| Guardian 发布阻断 | ❌ | ✅ 5 类检查，FAIL 阻断发布 | 重构版独有 |
| 幻觉检测 | ❌ | ✅ 价格与 OHLCV 比对 | 重构版独有 |
| 一致性检查 | ❌ | ✅ 跨步骤 bias/DOL/信号对齐 | 重构版独有 |
| 门控（停止后续步骤） | ❌ | ✅ FAIL/NO_TRADE 终止流水线 | 重构版独有 |
| 反馈闭环 | ❌ | ✅ audit lessons 注入下次分析 | 重构版独有 |
| 日度自评 | ✅ 10 分制（方向错=0） | ✅ 4 维评分（方向 0-3 + 位点 0-3 + 叙事 0-2 + 可操作 0-2） | 重构版更结构化 |
| 周度总结 | ✅ | ✅ | 相同 |

---

## 5. 知识管理

| 能力 | 原版 | 重构版 | 说明 |
|------|------|--------|------|
| 知识表示 | Markdown（Playbook 22K tokens + 7 知识文件 77KB） | JSON 图（kb.json 20K 行，300+ 节点，12 种边） | 重构版结构化程度高 |
| 知识加载方式 | 全量注入 Prompt | 按类别过滤，O(1) 查找 | 重构版 token 效率好 |
| 知识构建 | 手工整理 | 5 个自动化工具（PDF/memory/wiki/transcript/classifier） | 重构版自动化 |
| 反馈记忆 | ✅ 10 个反馈文件（真实修正） | ✅ FeedbackStore（SQLite 持久化） | 原版积累更多 |
| 别名解析 | ❌ | ✅ aliases.json（1823 行） | 重构版支持 |
| 决策链查询 | ❌ | ✅ decision_context() | 重构版支持 |
| ICT 术语表 | ✅ Playbook 50+ 术语 | ✅ glossary 类别节点 | 相同 |

---

## 6. 消息推送

| 能力 | 原版 | 重构版 | 说明 |
|------|------|--------|------|
| 飞书交互卡片 | ✅ 内联构建 | ✅ 模板驱动（9 个 JSON 模板） | 重构版更可维护 |
| 颜色编码 | ✅ 绿/红/蓝/橙/紫 | ✅ 绿/红/灰 | 原版颜色更丰富 |
| 多群推送 | ✅ | ✅ | 相同 |
| 文本回退 | ❌ | ✅ 卡片失败自动降级 | 重构版更健壮 |
| 本地 Markdown 报告 | ❌ | ✅ | 重构版支持 |

---

## 7. 运维

| 能力 | 原版 | 重构版 | 说明 |
|------|------|--------|------|
| 定时调度 | ✅ crontab 25 条 | ✅ crontab 26 条 | 相同 |
| 日志 | ✅ stdout 文件捕获 | ✅ logging 模块（console + file） | 重构版更结构化 |
| CLI 参数 | ❌ report_type + system_version 仅 | ✅ --dry-run, --no-push, --no-guardian, --verbose | 重构版更灵活 |
| 错误恢复 | ❌ 无重试/告警 | ✅ Claude CLI 重试一次 + 门控 + 超时 | 重构版更好但仍有限 |
| 健康监控 | ❌ | ❌ | 两者都无 |
| Docker | ❌ | ❌ | 两者都无 |
| CI/CD | ❌ | ❌ | 两者都无 |
| 自动化测试 | ❌ | ✅ pytest（330 + 685 行） | 重构版有 |

---

## 8. 功能差集总结

### 仅原版有（Michael 应考虑继承）

1. **A/B 测试基础设施** —— 双系统对比评估的能力
2. **三层验证（rules/preflight/validation）** —— 结构化的预检查和后验证
3. **TradingView 图表标注** —— 水平线、矩形、文字标注、截图
4. **9 条红旗禁止交易条件** —— 明确的不交易判断
5. **完整 SOP（424 行）** —— 集中可查的操作流程
6. **10 个反馈记忆** —— Patrick 真实修正的积累
7. **丰富颜色编码（5 色）** —— 更细的飞书卡片区分
8. **7 个决策记录** —— 设计决策的完整追溯

### 仅重构版有（Michael 应继承）

1. **直接 MCP 采集** —— 免费、秒级
2. **DataManifest 完整性跟踪** —— 数据质量可见
3. **5 步流水线 + 门控** —— 步骤级质量控制
4. **Guardian 发布阻断** —— 独立于模型的质量守门
5. **幻觉检测** —— 价格数据验证
6. **一致性检查** —— 跨步骤逻辑对齐
7. **反馈闭环** —— 审计教训自动回注
8. **知识图谱 + 按需加载** —— token 效率
9. **CLI 参数** —— dry-run / no-push / no-guardian
10. **自动化测试** —— pytest 覆盖主要路径
11. **文本回退 + 本地 Markdown** —— 推送健壮性
