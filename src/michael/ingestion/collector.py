"""MCP Collector — 直接 JSON-RPC 2.0 调用 TradingView MCP

MCP 协议流程：
1. 启动 node server.js 子进程（通过 CDP_HOST/CDP_PORT 环境变量）
2. 发送 initialize 请求 + initialized 通知
3. 调用工具：chart_set_symbol → chart_set_timeframe → data_get_ohlcv
4. 工具名参考 /home/patrick/tradingview-mcp/src/tools/data.js
"""

from __future__ import annotations

import json
import os
import subprocess
import logging
import time
from pathlib import Path
from typing import Optional

from michael.config import Config, TIMEFRAMES
from michael.types import BarData, DataManifest, SymbolData
from michael.ingestion.manifest import evaluate_integrity

logger = logging.getLogger(__name__)


# MCP 协议常量
MCP_PROTOCOL_VERSION = "2024-11-05"
CLIENT_INFO = {"name": "michael", "version": "0.1.0"}

# TradingView Desktop CDP 默认值（WSL 中 Windows host）
DEFAULT_CDP_HOST = "172.19.32.1"
DEFAULT_CDP_PORT = "9223"

# Timeframe 映射：内部表示 → TradingView 格式
TIMEFRAME_MAP: dict[str, str] = {
    "W": "W",
    "D": "D",
    "H4": "240",
    "H1": "60",
    "M15": "15",
    "M5": "5",
    "M1": "1",
}


class MCPError(Exception):
    def __init__(self, code: int, message: str, data: Optional[dict] = None):
        self.code = code
        self.message = message
        self.data = data or {}
        super().__init__(f"MCP Error {code}: {message}")


class CollectorError(Exception):
    pass


class Collector:
    """TradingView MCP 数据采集器"""

    def __init__(
        self,
        config: Config,
        cdp_host: Optional[str] = None,
        cdp_port: Optional[str] = None,
        response_timeout: float = 30.0,
    ):
        self._config = config
        self._server_path = config.mcp_server_dir / "src" / "server.js"
        self._cdp_host = cdp_host or os.environ.get("CDP_HOST", DEFAULT_CDP_HOST)
        self._cdp_port = cdp_port or os.environ.get("CDP_PORT", DEFAULT_CDP_PORT)
        self._timeout = response_timeout

        self._process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._initialized = False

    # ─── 生命周期 ───

    def connect(self) -> None:
        """启动 MCP 服务器并完成握手"""
        if self._process and self._process.poll() is None and self._initialized:
            return

        if not self._server_path.exists():
            raise CollectorError(f"MCP 服务器不存在: {self._server_path}")

        env = {
            **os.environ,
            "CDP_HOST": self._cdp_host,
            "CDP_PORT": self._cdp_port,
        }

        logger.info(f"启动 MCP 服务器: node {self._server_path}（CDP {self._cdp_host}:{self._cdp_port}）")
        self._process = subprocess.Popen(
            ["node", str(self._server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        # MCP initialize 握手
        resp = self._rpc("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": CLIENT_INFO,
        })
        server_name = resp.get("serverInfo", {}).get("name", "unknown")
        logger.info(f"MCP initialized: {server_name}")

        # 发送 initialized 通知（无响应）
        self._send_notification("notifications/initialized", {})
        self._initialized = True

    def disconnect(self) -> None:
        """关闭 MCP 服务器"""
        if self._process:
            try:
                if self._process.stdin:
                    self._process.stdin.close()
            except Exception:
                pass
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        self._initialized = False
        self._request_id = 0

    def __enter__(self) -> "Collector":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.disconnect()

    # ─── 低层 JSON-RPC ───

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _rpc(self, method: str, params: dict) -> dict:
        """发送 JSON-RPC 2.0 请求"""
        if not self._process or not self._process.stdin:
            raise CollectorError("MCP 服务器未启动")

        req_id = self._next_id()
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        raw = json.dumps(request) + "\n"
        try:
            self._process.stdin.write(raw.encode())
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise CollectorError(f"写入 MCP stdin 失败: {e}") from e

        response_line = self._read_response(req_id)
        resp = json.loads(response_line)

        if "error" in resp:
            err = resp["error"]
            raise MCPError(err.get("code", -1), err.get("message", "unknown"), err.get("data"))

        return resp.get("result", {})

    def _read_response(self, expected_id: int) -> str:
        """读取指定 id 的响应，跳过非 JSON / 通知消息"""
        assert self._process and self._process.stdout

        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            line = self._process.stdout.readline()
            if not line:
                if self._process.poll() is not None:
                    stderr = ""
                    if self._process.stderr:
                        stderr = self._process.stderr.read().decode(errors="replace")
                    raise CollectorError(
                        f"MCP 服务器退出 code={self._process.returncode}: {stderr[:500]}"
                    )
                continue

            line_str = line.decode().strip()
            if not line_str:
                continue

            try:
                obj = json.loads(line_str)
            except json.JSONDecodeError:
                logger.debug(f"MCP 非 JSON 输出: {line_str[:200]}")
                continue

            if "id" not in obj:
                continue  # 通知

            if obj["id"] == expected_id:
                return line_str

            logger.warning(f"MCP 响应 id 不匹配: 期望 {expected_id}, 收到 {obj.get('id')}")

        raise CollectorError(f"等待 MCP 响应超时 (id={expected_id}, timeout={self._timeout}s)")

    def _send_notification(self, method: str, params: dict) -> None:
        if not self._process or not self._process.stdin:
            return
        notification = {"jsonrpc": "2.0", "method": method, "params": params}
        raw = json.dumps(notification) + "\n"
        try:
            self._process.stdin.write(raw.encode())
            self._process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    # ─── 工具调用 ───

    def _call_tool(self, tool_name: str, arguments: dict) -> str:
        """调用 MCP 工具，返回 content[].text 文本"""
        result = self._rpc("tools/call", {"name": tool_name, "arguments": arguments})
        for item in result.get("content", []):
            if item.get("type") == "text":
                return item.get("text", "")
        return json.dumps(result)

    def set_symbol(self, symbol: str) -> None:
        logger.info(f"切换品种: {symbol}")
        self._call_tool("chart_set_symbol", {"symbol": symbol})

    def set_timeframe(self, tf: str) -> None:
        tv_tf = TIMEFRAME_MAP.get(tf, tf)
        logger.info(f"切换时间框架: {tf} → {tv_tf}")
        self._call_tool("chart_set_timeframe", {"timeframe": tv_tf})

    def collect_ohlcv(self, symbol: str, timeframe: str, bars: int = 100) -> list[BarData]:
        """采集单品种单时间框架的 OHLCV"""
        try:
            self.set_symbol(symbol)
            self.set_timeframe(timeframe)
            raw = self._call_tool("data_get_ohlcv", {"count": bars, "summary": False})
        except (MCPError, CollectorError) as e:
            logger.error(f"采集 {symbol}/{timeframe} 失败: {e}")
            return []

        # 解析 OHLCV 数据
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"OHLCV 返回非 JSON: {raw[:200]}")
            return []

        raw_bars: list = []
        if isinstance(data, list):
            raw_bars = data
        elif isinstance(data, dict):
            for key in ("bars", "data", "ohlcv"):
                if key in data and isinstance(data[key], list):
                    raw_bars = data[key]
                    break

        return self._parse_bars(raw_bars)

    @staticmethod
    def _parse_bars(raw_bars: list) -> list[BarData]:
        bars: list[BarData] = []
        for b in raw_bars:
            if not isinstance(b, dict):
                continue
            try:
                bars.append(BarData(
                    timestamp=str(b.get("time") or b.get("timestamp") or ""),
                    open=float(b.get("open", 0)),
                    high=float(b.get("high", 0)),
                    low=float(b.get("low", 0)),
                    close=float(b.get("close", 0)),
                    volume=float(b.get("volume", 0)),
                ))
            except (KeyError, TypeError, ValueError) as e:
                logger.debug(f"bar 解析失败: {e}, bar={b}")
        return bars

    # ─── 高层聚合 ───

    def collect_for_report(
        self,
        report_type: str,
        symbols: list[str],
        timeframes: Optional[list[str]] = None,
        bars_per_tf: int = 100,
        data_dir: Optional[Path] = None,
    ) -> DataManifest:
        """为指定报告采集所有需要的数据"""
        if timeframes is None:
            timeframes = TIMEFRAMES

        manifest = DataManifest(report_type=report_type)

        try:
            self.connect()

            for symbol in symbols:
                manifest.symbols[symbol] = {}
                for tf in timeframes:
                    logger.info(f"采集 {symbol}/{tf}...")
                    bars = self.collect_ohlcv(symbol, tf, bars_per_tf)

                    sym_data = SymbolData(symbol=symbol, timeframe=tf, bars=bars)

                    if data_dir and bars:
                        file_path = data_dir / f"{symbol.replace('!', '').replace(':', '_')}_{tf}.json"
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(file_path, "w") as f:
                            json.dump(
                                {"symbol": symbol, "timeframe": tf, "bars": [
                                    {"timestamp": b.timestamp, "open": b.open,
                                     "high": b.high, "low": b.low,
                                     "close": b.close, "volume": b.volume}
                                    for b in bars
                                ]},
                                f, indent=2,
                            )
                        sym_data.file_path = str(file_path)

                    manifest.symbols[symbol][tf] = sym_data

        except CollectorError:
            raise
        except Exception as e:
            manifest.errors.append(str(e))
            logger.error(f"采集过程错误: {e}")
        finally:
            self.disconnect()

        manifest.integrity = evaluate_integrity(manifest)
        return manifest
