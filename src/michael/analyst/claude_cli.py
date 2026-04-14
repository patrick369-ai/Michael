"""Claude CLI 包装器 — subprocess 调用 + JSON 提取 + 失败重试"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

from michael.config import Config

logger = logging.getLogger(__name__)


class ClaudeCLIError(Exception):
    """Claude CLI 调用错误"""
    pass


class ClaudeCLI:
    """Claude CLI 包装器

    特性：
    - subprocess 调用 claude -p <prompt>
    - 从输出中提取 JSON（支持围栏块和裸大括号）
    - JSON Schema 验证（可选）
    - 失败重试一次（追加错误信息到 prompt）
    - 超时控制 + max_turns 控制
    """

    def __init__(self, config: Config, enable_retry: bool = True):
        self._config = config
        self._bin = config.claude_bin
        self._default_timeout = config.claude_timeout
        self._default_max_turns = config.claude_max_turns
        self._enable_retry = enable_retry

    def call(
        self,
        prompt: str,
        schema: Optional[dict] = None,
        timeout: Optional[int] = None,
        max_turns: Optional[int] = None,
        allowed_tools: Optional[list[str]] = None,
    ) -> tuple[str, dict]:
        """调用 Claude CLI 并返回解析结果

        Args:
            prompt: 完整的 prompt 文本
            schema: 可选的 JSON Schema（用于验证）
            timeout: 超时秒数（默认 config 值）
            max_turns: 最大轮次（默认 config 值）
            allowed_tools: 允许的工具列表

        Returns:
            (raw_text, parsed_json) 元组
            如果解析失败，parsed_json 可能是空 dict

        Raises:
            ClaudeCLIError: CLI 执行失败或超时
        """
        timeout = timeout or self._default_timeout
        max_turns = max_turns or self._default_max_turns

        # 第一次调用
        try:
            raw_text = self._run_subprocess(prompt, timeout, max_turns, allowed_tools)
        except subprocess.TimeoutExpired as e:
            raise ClaudeCLIError(f"Claude CLI 超时（{timeout}s）") from e
        except subprocess.CalledProcessError as e:
            raise ClaudeCLIError(f"Claude CLI 失败: {e.stderr}") from e

        parsed = self._extract_json(raw_text)

        # Schema 验证失败时重试一次（仅当 enable_retry=True 时）
        if (schema and parsed and self._enable_retry
                and not self._validate_schema(parsed, schema)):
            logger.warning("第一次 Schema 验证失败，重试")
            retry_prompt = (
                prompt
                + "\n\n⚠️ 上次输出不符合 Schema，请严格按照给定的 JSON Schema 输出：\n"
                + json.dumps(schema, ensure_ascii=False, indent=2)
            )
            try:
                raw_text = self._run_subprocess(retry_prompt, timeout, max_turns, allowed_tools)
                parsed = self._extract_json(raw_text)
            except Exception as e:
                logger.error(f"重试也失败: {e}")

        return raw_text, parsed or {}

    def _run_subprocess(
        self,
        prompt: str,
        timeout: int,
        max_turns: int,
        allowed_tools: Optional[list[str]],
    ) -> str:
        """实际调用 subprocess"""
        cmd = [self._bin, "-p", prompt]

        if allowed_tools:
            cmd.extend(["--allowedTools", ",".join(allowed_tools)])

        # max_turns via --max-turns (如果 Claude CLI 支持)
        # 这里暂不强加，因为不同版本的 CLI 标志可能不同

        logger.info(f"Claude CLI 调用（prompt {len(prompt)} chars, timeout {timeout}s）")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )

        return result.stdout

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从文本中提取 JSON

        尝试顺序：
        1. 围栏代码块 ```json ... ```
        2. 围栏代码块 ``` ... ```（无语言标记）
        3. 首个 { 到最后一个 } 之间的内容
        """
        if not text:
            return {}

        # 尝试 ```json ... ```
        match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError as e:
                logger.debug(f"```json``` 解析失败: {e}")

        # 尝试 ``` ... ```
        match = re.search(r"```\s*\n(\{.*?\})\n```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试裸大括号
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace:last_brace + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError as e:
                logger.debug(f"裸大括号解析失败: {e}")

        logger.warning("无法从输出中提取 JSON")
        return {}

    @staticmethod
    def _validate_schema(data: dict, schema: dict) -> bool:
        """简化的 Schema 验证（检查 required 字段存在性）"""
        required = schema.get("required", [])
        for field in required:
            if field not in data:
                logger.warning(f"Schema 验证：缺少字段 {field}")
                return False
        return True


class MockClaudeCLI(ClaudeCLI):
    """Mock ClaudeCLI（用于测试，不真实调用 subprocess）"""

    def __init__(self, config: Config, mock_responses: Optional[list[str]] = None,
                 enable_retry: bool = False):
        super().__init__(config, enable_retry=enable_retry)
        self._responses = mock_responses or []
        self._call_count = 0

    def _run_subprocess(self, prompt, timeout, max_turns, allowed_tools):
        if self._call_count < len(self._responses):
            response = self._responses[self._call_count]
        else:
            # 默认 mock 响应
            response = '```json\n{"gate_status": "PASS"}\n```'
        self._call_count += 1
        return response
