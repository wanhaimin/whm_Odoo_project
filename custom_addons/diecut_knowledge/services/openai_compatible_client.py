# -*- coding: utf-8 -*-
"""OpenAI-compatible chat client for DeepSeek, Qwen, Kimi, and similar providers."""

import json
import logging
import time
from typing import Optional

import requests

_logger = logging.getLogger(__name__)


class OpenAICompatibleClient:
    DEFAULT_MAX_TOKENS = 4096
    DEFAULT_TIMEOUT = 120

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout: Optional[int] = None,
    ):
        if not api_key:
            raise ValueError("API key is required")
        if not base_url:
            raise ValueError("Base URL is required")
        if not model:
            raise ValueError("Model name is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS
        self.temperature = temperature
        self.timeout = timeout or self.DEFAULT_TIMEOUT

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
        t0 = time.monotonic()
        inputs = dict(inputs or {})
        system = inputs.pop("system", "")
        messages = self._parse_conversation_history(conversation_id)
        context = self._build_inputs_context(inputs)
        if system:
            messages.insert(0, {"role": "system", "content": system})
        messages.append({"role": "user", "content": f"{context}\n\n{query}" if context else query})
        body = self._chat_body(messages, stream=False)
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=self.timeout,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            return False, {}, f"Connection failed: {exc}", int((time.monotonic() - t0) * 1000)

        duration_ms = int((time.monotonic() - t0) * 1000)
        try:
            payload = response.json()
        except ValueError:
            payload = {"_raw": response.text[:1000]}
        if not (200 <= response.status_code < 300):
            error = payload.get("error") or payload.get("message") or response.text[:500]
            if isinstance(error, dict):
                error = error.get("message") or json.dumps(error, ensure_ascii=False)
            return False, payload, f"HTTP {response.status_code}: {error}", duration_ms

        answer = self._extract_answer(payload)
        assistant_history = self._conversation_messages(messages)
        assistant_history.append({"role": "assistant", "content": answer})
        return (
            True,
            {
                "answer": answer,
                "conversation_id": json.dumps(assistant_history, ensure_ascii=False),
                "model": payload.get("model") or self.model,
                "usage": payload.get("usage") or {},
                "retriever_resources": [],
            },
            None,
            duration_ms,
        )

    def chat_messages_stream(
        self,
        query: str,
        *,
        user: str = "",
        conversation_id: str = "",
        inputs: Optional[dict] = None,
        files: Optional[list] = None,
    ):
        inputs = dict(inputs or {})
        system = inputs.pop("system", "")
        messages = self._parse_conversation_history(conversation_id)
        context = self._build_inputs_context(inputs)
        if system:
            messages.insert(0, {"role": "system", "content": system})
        messages.append({"role": "user", "content": f"{context}\n\n{query}" if context else query})
        body = self._chat_body(messages, stream=True)
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                stream=True,
                timeout=self.timeout,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            yield ("error", {}, f"Connection failed: {exc}")
            return

        if response.status_code != 200:
            try:
                payload = response.json()
                error = payload.get("error") or payload.get("message") or response.text[:500]
                if isinstance(error, dict):
                    error = error.get("message") or json.dumps(error, ensure_ascii=False)
            except ValueError:
                error = response.text[:500]
            yield ("error", {}, f"HTTP {response.status_code}: {error}")
            return

        full_answer = ""
        try:
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if raw == "[DONE]":
                    break
                if not raw:
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                token = self._extract_stream_token(event)
                if token:
                    full_answer += token
                    yield ("token", {"token": token, "full_answer": full_answer}, None)
        except requests.RequestException as exc:
            _logger.warning("OpenAI-compatible stream failed: %s", exc)
            yield ("error", {}, str(exc))
            return

        assistant_history = self._conversation_messages(messages)
        assistant_history.append({"role": "assistant", "content": full_answer})
        yield (
            "done",
            {
                "conversation_id": json.dumps(assistant_history, ensure_ascii=False),
                "full_answer": full_answer,
                "citations": [],
            },
            None,
        )

    def _chat_body(self, messages, stream=False):
        body = {
            "model": self.model,
            "messages": messages,
            "stream": bool(stream),
            "max_tokens": self.max_tokens,
        }
        if self.temperature is not None:
            body["temperature"] = self.temperature
        return body

    @staticmethod
    def _extract_answer(payload):
        choices = payload.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        if isinstance(content, list):
            return "".join(block.get("text", "") if isinstance(block, dict) else str(block) for block in content)
        return content

    @staticmethod
    def _extract_stream_token(event):
        choices = event.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        content = delta.get("content") or ""
        if isinstance(content, list):
            return "".join(block.get("text", "") if isinstance(block, dict) else str(block) for block in content)
        return content

    @staticmethod
    def _build_inputs_context(inputs: dict) -> str:
        parts = []
        for key, value in (inputs or {}).items():
            if value and key != "system":
                parts.append(f"[{key}]: {value}")
        return "\n".join(parts)

    @staticmethod
    def _parse_conversation_history(conversation_id: str) -> list:
        if not conversation_id:
            return []
        try:
            parsed = json.loads(conversation_id)
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(parsed, list):
            return []
        return [
            {"role": row.get("role"), "content": row.get("content") or ""}
            for row in parsed
            if isinstance(row, dict) and row.get("role") in {"user", "assistant", "system"}
        ]

    @staticmethod
    def _conversation_messages(messages):
        return [row for row in messages if row.get("role") in {"user", "assistant"}]
