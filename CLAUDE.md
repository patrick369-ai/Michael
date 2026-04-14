# Michael — ICT 交易分析系统

## 项目概览

基于 Harness Engineering 哲学构建的 ICT 交易分析系统。四层架构：Ingestion → Analyst → Guardian → Dispatch，外加异步 Audit。

## 运行命令

```bash
# 初始化环境
./init.sh

# 运行分析
python3 scripts/run.py <report_type> [--dry-run] [--no-push] [--no-guardian] [--verbose]

# 报告类型
# weekly_prep | daily_bias | asia_pre | london_pre | nyam_pre | nyam_open | nypm_pre | daily_review | weekly_review

# 测试
python3 -m pytest tests/ -v
```

## 验证

```bash
python3 -m pytest tests/ -v && python3 scripts/run.py daily_bias --dry-run
```

## 架构

```
src/michael/
├── config.py          # 配置中心（环境变量驱动）
├── ingestion/         # Layer 1: MCP 数据采集 → DataManifest
├── analyst/           # Layer 2: Claude CLI 分析 → StepResult（5步+门控）
├── guardian/          # Layer 3: 独立验证（一致性+幻觉+规则+红旗）
├── dispatch/          # Layer 4: 飞书推送 + SQLite 持久化
├── audit/             # 异步审计（评分+反馈闭环）
├── knowledge/         # 知识系统（KnowledgeBrain 图数据库）
└── store/             # SQLite 数据存储
```

## 硬性约束

- 零外部 Python 运行时依赖（纯 stdlib）
- 所有路径通过环境变量或自动检测，禁止硬编码 `/home/patrick/`
- Guardian 检查不调用 LLM，纯代码验证
- 飞书 App Secret 只从环境变量读取，不提交到 git
- 每个 commit 必须通过 `python3 -m pytest tests/ -v`

## 规范文件索引

- [架构设计](docs/decisions/DR-002-architecture.md)
- [分析 SOP](docs/sop/analysis-sop.md)（待迁移）
- [功能清单](feature_list.json)

## 协作规范

- 决策用 ADR 记录（docs/decisions/DR-NNN-*.md）
- 变更用 conventional commits（feat/fix/docs/chore/perf）
- 每步实现后运行测试
