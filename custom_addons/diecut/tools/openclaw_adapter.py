# -*- coding: utf-8 -*-

import json
import os
import socket
import sys
import time
import uuid
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parents[1]
_VENDOR_DIR = _MODULE_ROOT / "_vendor"
if _VENDOR_DIR.exists():
    vendor_path = str(_VENDOR_DIR)
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)

from websocket import create_connection  # type: ignore
from websocket import WebSocketConnectionClosedException  # type: ignore
from websocket import WebSocketTimeoutException  # type: ignore


class OpenClawError(Exception):
    """Raised when OpenClaw gateway calls fail."""


class OpenClawTimeoutError(OpenClawError):
    """Raised when OpenClaw gateway calls time out."""


class OpenClawGatewayError(OpenClawError):
    """Raised for structured gateway errors."""


class OpenClawAdapter:
    _DEFAULT_SCOPES = [
        "operator.admin",
        "operator.read",
        "operator.write",
        "operator.approvals",
        "operator.pairing",
    ]

    def __init__(self, gateway_url, token, timeout=60, display_name="Odoo Diecut", platform_name=None):
        self.gateway_url = self._normalize_gateway_url(gateway_url)
        self.token = (token or "").strip()
        self.timeout = timeout
        self.display_name = display_name
        self.platform_name = platform_name or ("windows" if os.name == "nt" else "linux")
        self._ws = None

    @staticmethod
    def _normalize_gateway_url(url):
        value = (url or "").strip()
        if not value:
            raise OpenClawError("未配置 OpenClaw 网关地址。")
        if value.startswith("http://"):
            return "ws://" + value[len("http://") :].rstrip("/")
        if value.startswith("https://"):
            return "wss://" + value[len("https://") :].rstrip("/")
        return value.rstrip("/")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    def connect(self):
        try:
            self._ws = create_connection(
                self.gateway_url,
                timeout=self.timeout,
                suppress_origin=True,
            )
        except OSError as exc:
            raise OpenClawGatewayError(f"OpenClaw 网关不可达：{exc}") from exc
        except Exception as exc:
            raise OpenClawGatewayError(f"无法连接 OpenClaw 网关：{exc}") from exc

        challenge = self._recv_json(deadline=time.time() + self.timeout)
        if challenge.get("type") != "event" or challenge.get("event") != "connect.challenge":
            raise OpenClawGatewayError(f"OpenClaw 握手失败：{challenge}")

        response = self._request(
            "connect",
            {
                "minProtocol": 3,
                "maxProtocol": 3,
                "client": {
                    "id": "cli",
                    "displayName": self.display_name,
                    "version": "1.0",
                    "platform": self.platform_name,
                    "mode": "cli",
                    "instanceId": str(uuid.uuid4()),
                },
                "caps": [],
                "auth": {"token": self.token},
                "role": "operator",
                "scopes": list(self._DEFAULT_SCOPES),
            },
            expect_final=False,
            timeout=self.timeout,
        )
        if response.get("ok") is False:
            raise OpenClawGatewayError(response.get("message") or "OpenClaw 握手被拒绝。")
        return response

    def status(self):
        return self.call("status", {}, expect_final=False, timeout=self.timeout)

    def models_list(self):
        payload = self.call("models.list", {}, expect_final=False, timeout=self.timeout)
        result = payload.get("result")
        if isinstance(result, dict):
            return result.get("items") or result.get("models") or []
        if isinstance(result, list):
            return result
        return payload.get("items") or []

    def agent(self, message, agent_id, session_key, timeout=120, extra=None, attachments=None):
        params = {
            "message": message,
            "agentId": agent_id,
            "sessionKey": session_key,
            "idempotencyKey": str(uuid.uuid4()),
            "timeout": int(timeout),
        }
        if attachments:
            params["attachments"] = attachments
        if extra:
            params.update(extra)
        payload = self.call("agent", params, expect_final=True, timeout=timeout)
        result = payload.get("result") or {}
        texts = []
        for item in result.get("payloads") or []:
            if isinstance(item, dict) and item.get("text"):
                texts.append(item["text"])
        return {
            "payload": payload,
            "text": "\n".join(texts).strip(),
            "meta": result.get("meta") or {},
        }

    def call(self, method, params=None, expect_final=False, timeout=None):
        return self._request(method, params or {}, expect_final=expect_final, timeout=timeout or self.timeout)

    def _send_json(self, payload):
        if self._ws is None:
            raise OpenClawGatewayError("OpenClaw 连接尚未建立。")
        self._ws.send(json.dumps(payload, ensure_ascii=False))

    def _recv_json(self, deadline):
        if self._ws is None:
            raise OpenClawGatewayError("OpenClaw 连接尚未建立。")
        while True:
            remaining = max(deadline - time.time(), 0.1)
            try:
                self._ws.settimeout(remaining)
                raw = self._ws.recv()
            except (WebSocketTimeoutException, socket.timeout) as exc:
                raise OpenClawTimeoutError("OpenClaw 调用超时。") from exc
            except WebSocketConnectionClosedException as exc:
                raise OpenClawGatewayError("OpenClaw 网关连接已关闭。") from exc
            except Exception as exc:
                raise OpenClawGatewayError(f"OpenClaw 网关读取失败：{exc}") from exc
            if not raw:
                continue
            try:
                return json.loads(raw)
            except Exception:
                continue

    def _request(self, method, params, expect_final=False, timeout=60):
        request_id = str(uuid.uuid4())
        self._send_json({"type": "req", "id": request_id, "method": method, "params": params})
        deadline = time.time() + timeout
        while True:
            message = self._recv_json(deadline=deadline)
            if message.get("id") != request_id:
                continue
            if message.get("type") == "err":
                payload = message.get("payload") or {}
                raise OpenClawGatewayError(payload.get("message") or payload.get("code") or str(payload))
            if message.get("type") != "res":
                continue
            payload = message.get("payload") or {}
            if not expect_final:
                return payload
            status = (payload.get("status") or "").lower()
            if status in {"accepted", "queued", "running", "streaming"} and "result" not in payload:
                continue
            return payload
