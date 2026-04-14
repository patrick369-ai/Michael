"""Layer 4: Dispatch 消息分发

设计：
- 飞书 5 色交互卡片（绿/红/蓝/橙/紫）
- 文本回退（卡片失败时）
- 本地 Markdown 报告归档
- SQLite 持久化（结构化数据）
- Publisher 协议支持多通道
"""

from michael.dispatch.publisher import Publisher, MultiPublisher
from michael.dispatch.feishu import FeishuPublisher, CardColor
from michael.dispatch.local_md import LocalMarkdownPublisher
from michael.dispatch.persist import persist_analysis_result

__all__ = [
    "Publisher",
    "MultiPublisher",
    "FeishuPublisher",
    "CardColor",
    "LocalMarkdownPublisher",
    "persist_analysis_result",
]
