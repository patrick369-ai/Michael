"""Confluence Scorer 模块 — 双源共振评分

设计（见 DR-006）：
- Calculator 和 LLM 并行找位点，Confluence Scorer 汇合
- 9 维度加权评分 + 来源加成（Calculator + LLM 双重确认 × 1.5）
- 输出 Top-N 共振区域（S/A/B/C 等级）
"""

from michael.scorer.confluence import (
    ConfluenceZone,
    ConfluenceComponent,
    ConfluenceGrade,
    SourceType,
    score_confluence,
    merge_sources,
)

__all__ = [
    "ConfluenceZone",
    "ConfluenceComponent",
    "ConfluenceGrade",
    "SourceType",
    "score_confluence",
    "merge_sources",
]
