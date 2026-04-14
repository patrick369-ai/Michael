"""MCP Collector — 直接 JSON-RPC 2.0 调用 TradingView MCP"""

from __future__ import annotations

import json
import subprocess
import logging
from pathlib import Path

from michael.config import Config, TIMEFRAMES
from michael.types import BarData, DataManifest, SymbolData
from michael.ingestion.manifest import evaluate_integrity

logger = logging.getLogger(__name__)


class MCPError(Exception):
    """MCP 通信错误"""
    def __init__(self, code: int, message: str, data: dict | None = None):
        self.code = code
        self.message = message
        self.data = data or {}
        super().__init__(f"MCP Error {code}: {message}")


class CollectorError(Exception):
    """数据采集错误"""
    pass


class Collector:
    """TradingView MCP 数据采集器

    通过 stdin/stdout 与 MCP 服务器通信 JSON-RPC 2.0。
    不使用 Claude CLI，直接调用，零成本。
    """

    def __init__(self, config: Config):
        self._config = config
        self._server_path = config.mcp_server_dir / "src" / "server.js"
        self._process: subprocess.Popen | None = None
        self._request_id = 0

    def _start_server(self) -> None:
        """启动 MCP 服务器子进程"""
        if self._process and self._process.poll() is None:
            return

        if not self._server_path.exists():
            raise CollectorError(f"MCP 服务器不存在: {self._server_path}")

        self._process = subprocess.Popen(
            ["node", str(self._server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        logger.info("MCP 服务器已启动")

    def _stop_server(self) -> None:
        """停止 MCP 服务器"""
        if self._process:
            self._process.terminate()
            self._process.wait(timeout=5)
            self._process = None

    def _rpc(self, method: str, params: dict) -> dict:
        """发送 JSON-RPC 2.0 请求并接收响应"""
        if not self._process or self._process.poll() is not None:
            self._start_server()

        assert self._process and self._process.stdin and self._process.stdout

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

        request_line = json.dumps(request) + "\n"
        self._process.stdin.write(request_line)
        self._process.stdin.flush()

        response_line = self._process.stdout.readline()
        if not response_line:
            raise MCPError(-1, "MCP 服务器无响应")

        response = json.loads(response_line)

        if "error" in response:
            err = response["error"]
            raise MCPError(err.get("code", -1), err.get("message", "Unknown"))

        return response.get("result", {})

    def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        """调用 MCP 工具"""
        result = self._rpc("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        # 提取 content 中的文本
        content = result.get("content", [])
        for item in content:
            if item.get("type") == "text":
                try:
                    return json.loads(item["text"])
                except json.JSONDecodeError:
                    return {"raw": item["text"]}
        return result

    def collect_ohlcv(self, symbol: str, timeframe: str, bars: int = 100) -> list[BarData]:
        """采集单品种单时间框架的 OHLCV 数据"""
        try:
            data = self._call_tool("get_bars", {
                "symbol": symbol,
                "timeframe": timeframe,
                "count": bars,
            })
            raw_bars = data.get("bars", data.get("data", []))
            return [
                BarData(
                    timestamp=b.get("time", b.get("timestamp", "")),
                    open=float(b.get("open", 0)),
                    high=float(b.get("high", 0)),
                    low=float(b.get("low", 0)),
                    close=float(b.get("close", 0)),
                    volume=float(b.get("volume", 0)),
                )
                for b in raw_bars
            ]
        except MCPError as e:
            logger.error(f"采集 {symbol}/{timeframe} 失败: {e}")
            return []
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"解析 {symbol}/{timeframe} 数据失败: {e}")
            return []

    def collect_for_report(
        self,
        report_type: str,
        symbols: list[str],
        timeframes: list[str] | None = None,
        bars_per_tf: int = 100,
        data_dir: Path | None = None,
    ) -> DataManifest:
        """为指定报告类型采集所有需要的数据"""
        if timeframes is None:
            timeframes = TIMEFRAMES

        manifest = DataManifest(report_type=report_type)

        try:
            self._start_server()

            for symbol in symbols:
                manifest.symbols[symbol] = {}
                for tf in timeframes:
                    logger.info(f"采集 {symbol}/{tf}...")
                    bars = self.collect_ohlcv(symbol, tf, bars_per_tf)

                    sym_data = SymbolData(symbol=symbol, timeframe=tf, bars=bars)

                    # 保存到文件
                    if data_dir and bars:
                        file_path = data_dir / f"{symbol.replace('!', '')}_{tf}.json"
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
            self._stop_server()

        manifest.integrity = evaluate_integrity(manifest)
        return manifest
