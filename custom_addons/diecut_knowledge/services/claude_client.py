# -*- coding: utf-8 -*-
"""Claude API 客户端

使用 Anthropic 官方 Python SDK 调用 Claude Messages API。
与 DifyClient 并存，提供独立的 Claude 大模型调用能力。

本客户端只做 *薄封装*：
- 不抛 Odoo 自身的异常（让上层服务统一处理）
- 所有阻塞方法返回 (ok: bool, payload: dict, error: str|None, duration_ms: int) 四元组
- 流式方法 yield (event_type: str, data: dict, error: str|None) 三元组
"""

import json
import logging
import time
from typing import Optional

_logger = logging.getLogger(__name__)


class ClaudeClient:
    """Claude API 客户端。

    使用 Anthropic 官方 Python SDK 调用 Claude Messages API。
    与 DifyClient 并存，提供独立的 Claude 大模型调用能力。

    用法：
        client = ClaudeClient(api_key="sk-ant-xxx")
        ok, payload, error, duration_ms = client.chat(
            system="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
        )
    """

    DEFAULT_MODEL = "claude-opus-4-7"
    DEFAULT_MAX_TOKENS = 4096
    DEFAULT_TIMEOUT = 60

    def __init__(
        self,
        api_key: str,
        *,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
    ):
        if not api_key:
            raise ValueError("Claude api_key is required")
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS
        self.timeout = timeout or self.DEFAULT_TIMEOUT

        # 延迟导入，避免未安装 anthropic 时阻塞整个 Odoo 模块加载
        import anthropic as _anthropic

        self._anthropic = _anthropic
        kwargs: dict = {"api_key": api_key, "max_retries": 0}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = _anthropic.Anthropic(**kwargs)

    # ------------------------------------------------------------------
    # Blocking Chat
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list,
        *,
        system: str = "",
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs,
    ):
        """Blocking chat. Returns (ok, payload, error, duration_ms)."""
        t0 = time.monotonic()
        try:
            response = self._client.messages.create(
                model=model or self.model,
                max_tokens=max_tokens or self.max_tokens,
                system=system or self._anthropic.NOT_GIVEN,
                messages=messages,
                temperature=temperature if temperature is not None else self._anthropic.NOT_GIVEN,
                **kwargs,
            )
        except self._anthropic.APIError as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            _logger.warning("Claude chat failed: %s", exc)
            return False, {}, self._format_api_error(exc), duration_ms

        duration_ms = int((time.monotonic() - t0) * 1000)
        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        payload = {
            "answer": text,
            "model": response.model,
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens if response.usage else 0,
                "output_tokens": response.usage.output_tokens if response.usage else 0,
            },
        }
        return True, payload, None, duration_ms

    # ------------------------------------------------------------------
    # Streaming Chat
    # ------------------------------------------------------------------

    def chat_stream(
        self,
        messages: list,
        *,
        system: str = "",
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs,
    ):
        """SSE 流式调用 Claude Messages API，yield (event_type, data_dict, error) 三元组。

        Event types: "token", "done", "error"
        """
        try:
            with self._client.messages.stream(
                model=model or self.model,
                max_tokens=max_tokens or self.max_tokens,
                system=system or self._anthropic.NOT_GIVEN,
                messages=messages,
                temperature=temperature if temperature is not None else self._anthropic.NOT_GIVEN,
                **kwargs,
            ) as stream:
                full_answer = ""
                for token in stream.text_stream:
                    full_answer += token
                    yield ("token", {"token": token, "full_answer": full_answer}, None)

                final = stream.get_final_message()
                payload = {
                    "full_answer": full_answer,
                    "model": final.model,
                    "stop_reason": final.stop_reason,
                    "usage": {
                        "input_tokens": final.usage.input_tokens if final.usage else 0,
                        "output_tokens": final.usage.output_tokens if final.usage else 0,
                    },
                }
                yield ("done", payload, None)
        except self._anthropic.APIError as exc:
            _logger.warning("Claude chat_stream failed: %s", exc)
            yield ("error", {}, self._format_api_error(exc))

    # ------------------------------------------------------------------
    # Dify-compatible Adapters
    # ------------------------------------------------------------------

    def chat_messages(
        self,
        query: str,
        *,
        user: str = "",
        conversation_id: str = "",
        inputs: Optional[dict] = None,
        response_mode: str = "blocking",
        files: Optional[list] = None,
    ):
        """DifyClient.chat_messages() 兼容适配器。
        返回 (ok, payload, error, duration_ms)，payload 含 answer / conversation_id。
        """
        inputs = inputs or {}
        system = inputs.pop("system", "")
        history = self._parse_conversation_history(conversation_id)
        context = self._build_inputs_context(inputs)
        user_content = f"{context}\n\n{query}" if context else query
        history.append({"role": "user", "content": user_content})

        ok, payload, error, duration_ms = self.chat(
            messages=history,
            system=system,
        )
        if ok:
            payload["conversation_id"] = self._serialize_conversation(
                history, payload.get("answer", "")
            )
        return ok, payload, error, duration_ms

    def chat_messages_stream(
        self,
        query: str,
        *,
        user: str = "",
        conversation_id: str = "",
        inputs: Optional[dict] = None,
        files: Optional[list] = None,
    ):
        """DifyClient.chat_messages_stream() 兼容适配器。
        yield (event_type, data, error) 三元组。
        """
        inputs = inputs or {}
        system = inputs.pop("system", "")
        history = self._parse_conversation_history(conversation_id)
        context = self._build_inputs_context(inputs)
        user_content = f"{context}\n\n{query}" if context else query
        history.append({"role": "user", "content": user_content})

        for event_type, data, error in self.chat_stream(
            messages=history,
            system=system,
        ):
            if event_type == "done":
                data["conversation_id"] = self._serialize_conversation(
                    history, data.get("full_answer", "")
                )
            yield event_type, data, error

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_inputs_context(inputs: dict) -> str:
        """将 Dify 的 inputs 中非 system 字段转为上下文文本。"""
        if not inputs:
            return ""
        parts = []
        for key, value in inputs.items():
            if value and key != "system":
                parts.append(f"[{key}]: {value}")
        return "\n".join(parts)

    @staticmethod
    def _parse_conversation_history(conversation_id: str) -> list:
        """解析 conversation_id 为消息历史列表。"""
        if not conversation_id:
            return []
        try:
            parsed = json.loads(conversation_id)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    @staticmethod
    def _format_api_error(exc) -> str:
        text = str(exc)
        lowered = text.lower()
        if "invalid x-api-key" in lowered or "authentication_error" in lowered or "401" in lowered:
            return "Claude API Key 无效或已过期，请在「大模型档案」中更新 Claude 的 API Key，或先禁用 Claude 并选择其他模型。"
        if "not_found_error" in lowered or "model" in lowered and "not found" in lowered:
            return "Claude 模型名称不可用，请检查「大模型档案」中的模型名。"
        return text

    @staticmethod
    def _serialize_conversation(history: list, answer: str) -> str:
        """将消息历史序列化为 conversation_id。"""
        history.append({"role": "assistant", "content": answer})
        return json.dumps(history, ensure_ascii=False)
