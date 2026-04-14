# Harness 工程实施落地指南

> 综合自三大知识源：[Harness Books](https://github.com/wquguru/harness-books)（理论体系）、[Learn Harness Engineering](https://github.com/walkinglabs/learn-harness-engineering)（实践课程）、[Archon](https://github.com/coleam00/Archon)（工程实现）

---

## 第一部分：核心认知 —— 什么是 Harness Engineering

### 1.1 一句话定义

**Harness Engineering（驾驭工程）是在不可靠模型外围构建可靠控制结构的工程学科。**

它不是 Prompt Engineering 的升级版，而是一个独立的系统工程领域。Prompt 决定模型「怎么说」，Harness 决定系统「怎么做」。

### 1.2 为什么需要 Harness

| 现象 | 根因 | Harness 的回应 |
|------|------|----------------|
| 同样的 Prompt，模型输出不一致 | 模型本质是概率性的 | 用确定性流程包裹概率性组件 |
| Agent 宣称完成但实际未通过测试 | 验证缺口（Verification Gap） | 独立于实现的验证门控 |
| 长对话后期 Agent 表现退化 | 上下文污染与衰减 | 上下文预算管理 + 受控压缩 |
| 多 Session 之间丢失进度 | 会话间状态断裂 | 持久化状态 + 会话交接协议 |
| 团队中个人技巧无法复用 | 缺乏制度化 | 标准化工作流 + 可复用 Skill |

### 1.3 核心原则（十条）

来自 Harness Books 提炼的十条设计原则：

1. **模型是不稳定组件，不是队友** —— 设计系统时假设模型会犯错
2. **Prompt 是控制面的一部分** —— 分层、有优先级、可缓存
3. **查询循环是心跳** —— 持续的、有状态的执行循环，不是一次性调用
4. **工具是受管理的执行接口** —— 能力与授权分离
5. **上下文是工作记忆** —— 有预算、有分层、有压缩策略
6. **错误路径是主路径** —— 恢复逻辑是一等公民
7. **恢复优化续行而非重来** —— 从断点继续，不重新开始
8. **多 Agent 的价值是分割不确定性** —— 职责分离，不是并行加速
9. **验证必须独立于实现** —— 写代码的 Agent 不能自己判定完成
10. **团队制度比个人技巧重要** —— 制度化 > 个人经验

---

## 第二部分：五子系统架构 —— Harness 的骨架

任何 Harness 系统都由五个子系统构成（来自 Learn Harness Engineering 课程的核心框架）：

```
┌─────────────────────────────────────────────────┐
│                  Harness 系统                     │
│                                                   │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │ 指令系统   │  │ 状态系统   │  │ 验证系统   │    │
│  │Instructions│  │   State   │  │Verification│    │
│  └───────────┘  └───────────┘  └───────────┘    │
│                                                   │
│  ┌───────────┐  ┌───────────┐                    │
│  │ 范围控制   │  │ 生命周期   │                    │
│  │   Scope   │  │ Lifecycle │                    │
│  └───────────┘  └───────────┘                    │
└─────────────────────────────────────────────────┘
```

### 2.1 指令系统（Instructions）

**目标：** 让 Agent 冷启动时能自主回答五个问题：
1. 这个项目是什么？
2. 代码怎么组织的？
3. 怎么运行？
4. 怎么验证？
5. 当前进展到哪了？

**实施要点：**

- **入口文件作路由，不作百科** —— CLAUDE.md / AGENTS.md 保持 50-200 行，链接到专题文档
- **分层优先级** —— override > coordinator > agent > custom > default，冲突时高优先级胜出
- **避免"迷失在中间"** —— 重要信息放头部或尾部，不放中间段
- **每条指令需标注三要素** —— 来源（为什么加）、适用条件（何时需要）、过期条件（何时移除）

**文件结构示例：**

```
CLAUDE.md                    # 入口路由（50-200 行）
├── docs/architecture.md     # 架构概览
├── docs/conventions.md      # 编码规范
├── docs/testing.md          # 测试策略
└── docs/deployment.md       # 部署流程
```

### 2.2 状态系统（State）

**目标：** 跨 Session 保持进度，新会话重建成本 < 3 分钟

**核心制品：**

| 文件 | 用途 | 更新时机 |
|------|------|----------|
| `feature_list.json` | 功能清单（行为描述 + 验证命令 + 当前状态） | 每完成一个功能 |
| `progress.md` | 会话进度日志 | 每个会话开始和结束 |
| `session-handoff.md` | 精简交接笔记 | 每个会话结束 |

**功能清单的四状态机：**

```
not_started → active → passing
                ↓
             blocked
```

**关键规则：** 只有验证通过才能将状态移至 `passing`（Pass-State Gating）。

**Agent 状态的 ACID 原则：**
- **原子性** —— 一次 commit 对应一个逻辑操作
- **一致性** —— 验证谓词必须可执行
- **隔离性** —— 每个 Agent 使用独立的状态文件或分支
- **持久性** —— 状态存在 git 跟踪的文件中

### 2.3 验证系统（Verification）

**目标：** 消除验证缺口，杜绝 Agent "自我宣告胜利"

**层次化验证：**

```
Level 1: 类型检查 + Lint（每次文件修改后）
Level 2: 单元测试（每个功能完成后）
Level 3: 集成 / E2E 测试（每个功能通过后）
Level 4: 冒烟测试 / 手动验证（交付前）
```

**实施规则：**
- 验证命令必须写在 CLAUDE.md 中，Agent 不需要猜
- "完成" = 行为实现 + 验证运行 + 证据记录 + 仓库可重启
- 验证必须独立于实现 —— 实现者与验证者不能是同一个 Agent
- 使用 Evaluator Rubric 进行结构化评分（正确性、验证覆盖、范围纪律、可靠性、可维护性、交接就绪度）

### 2.4 范围控制（Scope）

**目标：** 防止 Agent 过度扩展（开始太多）或不完成（完成太少）

**核心纪律：WIP = 1**
- 同一时间只处理一个功能
- 完成当前功能后，才开始下一个
- 数据支撑："小步前进"策略比大范围策略完成率高 37%

**完成证据必须可执行：**
- ✗ "代码看起来没问题"
- ✓ `npm test -- --grep "auth" && npm run e2e`

### 2.5 生命周期管理（Lifecycle）

**目标：** 标准化每个 Agent 会话的启动和关闭

**会话生命周期四阶段：**

```
START → SELECT → EXECUTE → WRAP UP
  │        │         │          │
  │        │         │          ├─ 更新 progress.md
  │        │         │          ├─ 更新 feature_list.json
  │        │         │          ├─ 提交干净状态
  │        │         │          └─ 写 session-handoff.md
  │        │         │
  │        │         ├─ 实现功能
  │        │         └─ 运行验证
  │        │
  │        └─ 从 feature_list 选一个功能（WIP=1）
  │
  ├─ 读取 progress.md
  ├─ 读取 feature_list.json
  ├─ 查看最近 commit
  └─ 运行 init.sh
```

**init.sh 标准内容：**
```bash
#!/bin/bash
set -e
# 1. 安装依赖
npm install  # 或 bun install / pip install -r requirements.txt
# 2. 运行验证
npm test
# 3. 打印启动命令
echo "Ready. Run: npm run dev"
```

**Clean-State Checklist（会话退出检查）：**
- [ ] 构建通过
- [ ] 测试通过
- [ ] 进度已记录
- [ ] feature_list 已更新
- [ ] 无未提交的半成品
- [ ] 启动路径可用

---

## 第三部分：控制面设计 —— 从 Prompt 到查询循环

### 3.1 Prompt 分层架构

Prompt 不是人设描述，而是分层组装的行为控制块：

```
┌─────────────────────────┐ 优先级最高
│   Override 层            │ ← 安全规则、强制行为
├─────────────────────────┤
│   Coordinator 层         │ ← 多 Agent 协调指令
├─────────────────────────┤
│   Agent 层               │ ← 角色定义、工具列表
├─────────────────────────┤
│   Custom 层              │ ← CLAUDE.md / AGENTS.md
├─────────────────────────┤
│   Default System Prompt  │ ← 基础行为         优先级最低
└─────────────────────────┘
```

**缓存优化：** 将稳定内容（系统提示、工具定义、项目规则）放在 Prompt 前部（可缓存段），将动态内容（当前对话、最新上下文）放在后部（缓存中断段）。

### 3.2 查询循环（Query Loop）

查询循环是 Agent 系统的心跳，维护显式的跨轮次状态：

```
while (not terminal_condition) {
    // 1. 输入治理：内存预取、消息裁剪、工具结果预算
    governance(context)

    // 2. 模型调用：消费事件流，不是最终文本
    stream = call_model(context)

    // 3. 工具调度：批量执行、并发安全分类
    results = execute_tools(stream.tool_calls)

    // 4. 状态更新：消息追加、上下文预算检查
    update_state(results)

    // 5. 终止判断：多种不同的停止条件
    check_stop_conditions()
}
```

**六种终止条件（各自语义不同）：**
1. 工具后续调用 → 继续循环
2. 用户中断 → 关闭未完成工具调用的账本
3. Prompt 过长 → 触发上下文压缩恢复
4. 输出超限 → 升级 token 上限，追加续行指令
5. Hook 阻断 → 触发停止 Hook 的死循环防护
6. API 错误 → 分级重试策略

### 3.3 上下文治理

**四层指令加载：**

```
组织级规则 → 用户级规则 → 项目级规则 → 本地规则
                                          ↑ 优先级最高
```

**上下文预算管理：**
- Autocompact 预留摘要预算（20K tokens）+ 缓冲（13K tokens）
- 连续压缩失败的熔断器（最多 3 次）
- 压缩是"受控重启" —— 恢复文件附件、计划状态、技能内容，不只是文本摘要

**MEMORY.md 管理规范：**
- 作为索引文件，不是内容容器
- 最大 200 行 / 25KB
- 两步保存：先写内容文件，再更新索引

---

## 第四部分：工具与权限 —— 能力 ≠ 授权

### 4.1 三态权限模型

```
Allow ──── 自动执行，无需确认
Ask   ──── 每次执行前请求用户确认
Deny  ──── 禁止执行
```

不是布尔的"可以/不可以"，而是三个独立状态。

### 4.2 高风险工具的高密度约束

以 Bash 为例（Claude Code 的实际实践）：

```yaml
高密度约束清单：
  - git 规则（不 force push、不 amend 除非明确要求）
  - 命令前缀分析（阻断危险前缀如 rm -rf /）
  - 子命令限制（限制特定工具的子命令集）
  - 超时控制（默认 2 分钟，最大 10 分钟）
  - 后台执行隔离（run_in_background 参数）
```

### 4.3 工具编排规则

- 无依赖的工具调用 → 并行批量执行
- 有依赖的工具调用 → 按拓扑序串行
- 上下文修改类工具 → 按原始顺序重放
- 中断时 → 为未完成调用生成合成结果（账本闭合）

### 4.4 Hooks（钩子）系统

Hooks 是自动化行为的载体，在事件驱动下执行：

```yaml
# 示例：每次写文件后自动类型检查
hooks:
  PostToolUse:
    - matcher: "Write|Edit"
      response:
        systemMessage: >
          你刚修改了文件。立即执行：
          1. 运行类型检查
          2. 重新读取文件确认修改正确
          3. 说明为什么这个修改是必要的

# 示例：PR 创建节点中禁止修改源码
hooks:
  PreToolUse:
    - matcher: "Write|Edit"
      response:
        hookSpecificOutput:
          permissionDecision: deny
          permissionDecisionReason: "PR 创建节点禁止修改源文件"
```

**部署时机：** Hooks 属于高级自动化，应在基线治理稳定之后再引入。

---

## 第五部分：错误与恢复 —— 错误路径是主路径

### 5.1 错误分级

| 级别 | 示例 | 策略 |
|------|------|------|
| FATAL | 认证失败、权限不足 | 不重试，报告用户 |
| TRANSIENT | 超时、限流 | 指数退避自动重试 |
| UNKNOWN | 未分类错误 | 追踪，连续 3 次后中止 |

### 5.2 分层恢复策略

```
prompt_too_long（上下文过长）
  ├─ 第一层：上下文折叠排空
  ├─ 第二层：响应式压缩（reactive compact）
  ├─ 第三层：截断头部（truncateHead，最后手段）
  └─ 防护：hasAttemptedReactiveCompact 防止盲目重试

max_output_tokens（输出超限）
  ├─ 第一层：升级 token 上限
  └─ 第二层：追加续行指令（不重述、不道歉、从截断点继续）

压缩本身失败
  └─ 熔断器：连续失败 3 次后停止压缩尝试
```

### 5.3 恢复设计原则

- **续行优先于重来** —— 从断点继续，不重新开始
- **恢复逻辑必须防循环** —— 使用计数器和熔断器
- **中断需要语义闭合** —— 为未完成的工具调用生成合成结果

---

## 第六部分：多 Agent 协作 —— 分割不确定性

### 6.1 三种协作模式

| 模式 | 特点 | 适用场景 |
|------|------|----------|
| **Coordinator**（协调者） | 零继承，最安全 | 复杂任务分解 |
| **Fork**（分叉） | 全继承，仅单层 | 并行同质任务 |
| **Swarm**（群组） | 点对点，共享任务列表 | 自组织松耦合任务 |

### 6.2 四阶段工作流

```
Research（调研）→ Synthesis（综合）→ Implementation（实现）→ Verification（验证）
```

**关键规则：**
- 协调者必须综合（消化、转换），不能转发原始结果
- 子 Agent 共享缓存参数但隔离所有可变状态
- 验证必须独立于实现 —— 两层检查
- 父 Agent 中止时必须传播到所有子 Agent

### 6.3 DAG 工作流编排（Archon 的实践）

Archon 用 YAML 定义 DAG 工作流，将 Agent 行为编码为确定性流程：

```yaml
# 示例：从 Issue 到 PR 的完整流程
name: fix-issue
nodes:
  - id: analyze
    prompt: "分析这个 issue，确定根因和修复方案"
    allowed_tools: [Read, Grep, Glob]  # 只读，不能修改

  - id: plan
    depends_on: [analyze]
    command: create-plan  # 引用 Markdown 命令文件
    output_format:
      type: object
      properties:
        tasks: { type: array }

  - id: implement
    depends_on: [plan]
    type: loop
    prompt: "按计划逐步实现，每步验证"
    until: "IMPLEMENTATION_COMPLETE"
    max_iterations: 10
    fresh_context: true  # 每轮清空上下文，通过磁盘文件传递状态

  - id: review
    depends_on: [implement]
    prompt: "审查所有变更"
    denied_tools: [Write, Edit, Bash]  # 只能看不能改

  - id: approval
    depends_on: [review]
    type: approval  # 人类审批门控
    gate_message: "审查完成，是否创建 PR？"

  - id: create-pr
    depends_on: [approval]
    prompt: "创建 Pull Request"
```

**DAG 节点类型：**

| 类型 | 说明 | 是否涉及 AI |
|------|------|-------------|
| `prompt:` | 内联 AI 提示 | 是 |
| `command:` | 引用 Markdown 命令文件 | 是 |
| `bash:` | Shell 脚本 | 否 |
| `script:` | TypeScript/Python 脚本 | 否 |
| `loop:` | 迭代 AI 提示直到完成信号 | 是 |
| `approval:` | 人类审批门控 | 否（人类） |

**条件执行：**
```yaml
- id: fix-bug
  when: "$classify.output.issue_type == 'bug'"
  depends_on: [classify]
```

### 6.4 Git Worktree 隔离

每个工作流运行获得独立的 Git Worktree，实现：
- 并行开发不冲突
- 失败时干净回滚
- 多 Agent 状态天然隔离

---

## 第七部分：团队落地 —— 从个人技巧到组织制度

### 7.1 落地顺序（严格按序）

```
第 1 步：定义可接受的使用范围
    ↓
第 2 步：定义审查和验证期望
    ↓
第 3 步：打包循环工作流（Skills）
    ↓
第 4 步：分级审批（按后果和环境敏感度）
    ↓
第 5 步：引入 Hooks 自动化
    ↓
第 6 步：建立可回放性（转录、Hook 事件、压缩摘要）
```

### 7.2 CLAUDE.md 管理原则

- 作为**稳定基石**，不作**公告板**
- 承载稳定规则，不堆积细节
- 定期审计，像管理技术债务一样管理指令膨胀
- 团队中标准化"完成定义"比增加 Skill 数量更重要

### 7.3 审批分级

按**后果严重性**和**环境敏感度**分级，不按工具名称分级：

| 级别 | 标准 | 示例 |
|------|------|------|
| 自动通过 | 本地、可逆 | 读文件、运行测试 |
| 需确认 | 共享或不可逆 | 推送代码、创建 PR |
| 禁止 | 破坏性 | Force push、删数据库 |

### 7.4 可观测性

**两层可观测性：**

| 层 | 信号 | 制品 |
|----|------|------|
| 运行时 | 日志、追踪、健康检查 | 工具调用记录、错误日志 |
| 流程 | Sprint 合同、评估量表 | 质量文档、评分卡 |

**无可观测性的代价：** Agent 在冗余诊断上浪费 30-50% 的会话时间。

---

## 第八部分：实施检查清单

### 8.1 快速启动（Day 1）

- [ ] 创建 CLAUDE.md / AGENTS.md（50-100 行），包含：项目概览、运行命令、硬性约束、专题链接
- [ ] 创建 init.sh：标准化依赖安装 + 验证 + 启动
- [ ] 创建 feature_list.json：行为/验证/状态三元组
- [ ] 创建 progress.md：会话进度日志

### 8.2 Agent 运行时设计检查

- [ ] 是否有显式查询循环？
- [ ] 是否维护跨轮次状态？
- [ ] 模型输出是否作为事件流消费？
- [ ] 中断时是否有账本闭合机制？
- [ ] 是否有明确不同的停止语义？
- [ ] 是否有上下文预算管理？

### 8.3 Prompt 设计检查

- [ ] 是否分层分段？
- [ ] 是否有显式优先级？
- [ ] 是否对危险操作有显式规则？
- [ ] 是否避免了职责过载？
- [ ] 团队是否可维护？

### 8.4 工具与权限检查

- [ ] 是否有统一的编排层？
- [ ] 是否有并发安全证明？
- [ ] 是否支持 allow/deny/ask 三态？
- [ ] 高风险工具是否有高密度约束？
- [ ] 中断时是否有语义闭合？

### 8.5 上下文治理检查

- [ ] 是否有分层规则？
- [ ] 是否有入口/正文分离？
- [ ] 是否有 token 预算？
- [ ] 是否为压缩预留空间？
- [ ] 压缩后是否恢复语义（不只是文本）？
- [ ] 压缩失败是否有恢复路径？

### 8.6 错误恢复检查

- [ ] 可恢复错误是否有路由？
- [ ] 恢复是否分层（低破坏到高破坏）？
- [ ] 是否有防循环守卫？
- [ ] 是否优先续行而非重述？
- [ ] 是否有计数器和熔断器？

### 8.7 多 Agent 检查

- [ ] 分叉是否共享缓存但隔离可变状态？
- [ ] 是否有明确的角色分离？
- [ ] 协调者是否综合而非转发？
- [ ] 验证是否独立？
- [ ] 生命周期是否可观测？
- [ ] 父 Agent 中止是否传播到子 Agent？

### 8.8 团队落地检查

- [ ] CLAUDE.md 是否作为稳定基石而非公告板？
- [ ] "完成"的定义是否标准化？
- [ ] 审批是否按后果分级？
- [ ] Hooks 是否在基线稳定后才引入？
- [ ] 是否有可回放的证据（git diff、PR 评论、CI）？
- [ ] 过期记忆是否有维护机制？

---

## 第九部分：两种 Harness 哲学 —— 选择你的路径

来自 Harness Books 第二册的比较分析：

| 维度 | Runtime Republic（Claude Code 路线） | Constitutional Control（Codex 路线） |
|------|-------------------------------------|-------------------------------------|
| 控制面 | 运行时动态组装 Prompt | 结构化指令片段 + 类型边界 |
| 连续性 | 压缩在查询循环中 | 分布在 Thread/Rollout/StateDB 中 |
| 权限 | 运行时情境审批 | Schema-first + 独立策略引擎 |
| 本地治理 | 经验吸收为现场记忆 | 结构化注入 + 事件系统 |
| 多 Agent | 运行时职责分离 | 工具中介的委托 |
| 比喻 | 值班经理现场决策 | 先写制度再执行 |

**你的系统更接近哪一种？**

- 如果你的控制逻辑主要在主循环和现场调度中 → **Runtime Republic**
- 如果你的控制逻辑主要写进类型、Fragment、策略、线程、事件中 → **Constitutional Control**
- 如果你主要是往 Prompt 里堆更多文本 → **第三条路（较弱）：先注入后补救**

**建议：** 认清自己的起点，再有意识地向目标架构演进。

---

## 第十部分：构建自己的 Harness —— 执行顺序

来自 Harness Books 第二册的实践指导：

```
Step 1: 定义高风险动作和最小权限模型
    "先设计权限，再设计能力"
        ↓
Step 2: 定义主循环或线程生命周期
    "先设计心跳，再设计功能"
        ↓
Step 3: 定义上下文治理和恢复路径
    "先设计预算，再开始对话"
        ↓
Step 4: 定义 Skills、本地规则和 Hooks
    "先设计制度，再期望熟练"
        ↓
Step 5: 扩展到多 Agent、平台能力、生态
    "先设计生命周期，再组建团队"
```

**六条设计先行原则：**

1. 先设计权限，再设计能力
2. 先设计回滚，再设计自主
3. 先设计验证，再设计交付
4. 先设计上下文预算，再开始长对话
5. 先设计生命周期，再搞多 Agent
6. 先设计制度，再期望团队熟练

---

## 附录 A：模板速查

| 模板 | 用途 | 来源 |
|------|------|------|
| CLAUDE.md / AGENTS.md | 入口指令文件 | Learn Harness Engineering |
| init.sh | 启动脚本 | Learn Harness Engineering |
| feature_list.json | 功能追踪器 | Learn Harness Engineering |
| progress.md | 会话进度日志 | Learn Harness Engineering |
| session-handoff.md | 会话交接笔记 | Learn Harness Engineering |
| clean-state-checklist.md | 会话退出检查 | Learn Harness Engineering |
| evaluator-rubric.md | 质量评分卡 | Learn Harness Engineering |
| quality-document.md | 模块健康度 | Learn Harness Engineering |
| workflow.yaml (DAG) | 工作流定义 | Archon |
| command.md | 详细提示模板 | Archon |

## 附录 B：故障诊断映射

| 故障现象 | 首要修复的子系统 | 具体制品 |
|----------|-----------------|----------|
| Agent 不知道做什么 | 指令系统 | CLAUDE.md + 专题文档 |
| Agent 每次从零开始 | 状态系统 | progress.md + feature_list.json |
| Agent 宣称完成但实际没完成 | 验证系统 | 验证命令 + evaluator rubric |
| Agent 开始太多完成太少 | 范围控制 | WIP=1 规则 + 功能清单 |
| Agent 长对话后表现退化 | 上下文治理 | 预算管理 + 压缩策略 |
| Agent 出错后无法恢复 | 错误恢复 | 分层恢复 + 熔断器 |

## 附录 C：关键数据点

| 指标 | 数据 | 来源 |
|------|------|------|
| 裸模型 vs 有 Harness | $9/20min 失败 vs $200/6hr 可玩游戏 | Anthropic 实验 |
| 分文件后成功率提升 | 45% → 72% | Learn HE L04 |
| "小步前进"完成率提升 | +37% | Learn HE L07 |
| 无可观测性浪费时间 | 30-50% 会话时间 | Learn HE L11 |
| 无清理 12 周后构建通过率 | 100% → 68% | Learn HE L12 |
| 有清理策略的构建通过率 | 97%，启动 < 9 分钟 | Learn HE L12 |

---

> **最后一句话（来自 Harness Books）：**
> "Harness Engineering 追问的是：当模型本身不可靠时，系统如何仍然像工程系统一样运行。"
