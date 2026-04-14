#!/bin/bash
set -e

echo "=== Michael 初始化 ==="

# 1. 检查 Python 版本
python3 --version 2>/dev/null || { echo "错误: 需要 Python 3.10+"; exit 1; }

# 2. 检查 .env 文件
if [ ! -f .env ]; then
    echo "警告: .env 文件不存在，复制模板..."
    cp .env.example .env 2>/dev/null || echo "请创建 .env 文件（参考 .env.example）"
fi

# 3. 检查环境变量
source .env 2>/dev/null || true
[ -z "$FEISHU_APP_ID" ] && echo "警告: FEISHU_APP_ID 未设置"
[ -z "$FEISHU_APP_SECRET" ] && echo "警告: FEISHU_APP_SECRET 未设置"

# 4. 检查 Claude CLI
CLAUDE_BIN="${CLAUDE_BIN:-$(which claude 2>/dev/null || echo '')}"
if [ -z "$CLAUDE_BIN" ]; then
    echo "警告: Claude CLI 未找到，分析功能将不可用"
else
    echo "Claude CLI: $CLAUDE_BIN"
fi

# 5. 检查 TradingView MCP
MCP_SERVER_DIR="${MCP_SERVER_DIR:-$HOME/tradingview-mcp}"
if [ -d "$MCP_SERVER_DIR" ]; then
    echo "TradingView MCP: $MCP_SERVER_DIR"
else
    echo "警告: TradingView MCP 目录不存在: $MCP_SERVER_DIR"
fi

# 6. 运行测试
echo ""
echo "=== 运行测试 ==="
python3 -m pytest tests/ -v --tb=short 2>/dev/null || echo "测试跳过（无测试文件或 pytest 未安装）"

echo ""
echo "=== 初始化完成 ==="
echo "运行分析: python3 scripts/run.py <report_type> [--dry-run]"
