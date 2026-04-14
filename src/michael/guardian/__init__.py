"""Layer 3: Guardian 质量守护

设计（DR-002 + DR-005）：
- 不调用 LLM，纯代码验证
- 用 Calculator 输出验证 LLM 输出（防幻觉）
- 跨步骤一致性检查（Bias/DOL/Signal 方向对齐）
- 9 红旗 + 40+ 硬规则的代码级检查
- PASS / WARN / FAIL → 阻断或附加标注后发布
"""

from michael.guardian.supervisor import Supervisor, SupervisionReport
from michael.guardian.hallucination import HallucinationDetector
from michael.guardian.consistency import ConsistencyChecker
from michael.guardian.rules import RuleEngine, Rule, RuleResult

__all__ = [
    "Supervisor",
    "SupervisionReport",
    "HallucinationDetector",
    "ConsistencyChecker",
    "RuleEngine",
    "Rule",
    "RuleResult",
]
