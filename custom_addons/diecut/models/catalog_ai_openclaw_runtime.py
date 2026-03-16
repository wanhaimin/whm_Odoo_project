# -*- coding: utf-8 -*-

import base64
import re

from odoo import api, models
from odoo.exceptions import UserError

from ..tools import OpenClawAdapter, OpenClawError


class DiecutCatalogSourceDocumentOpenClawRuntime(models.Model):
    _inherit = "diecut.catalog.source.document"

    _OPENCLAW_DEFAULTS = {
        "vision": {
            "gateway_url": "ws://host.docker.internal:18789",
            "model": "openai-codex/gpt-5.4",
            "agent_id": "odoo-diecut-dev",
            "session_mode": "isolated",
        },
        "struct": {
            "gateway_url": "ws://host.docker.internal:18789",
            "model": "openai-codex/gpt-5.4",
            "agent_id": "odoo-diecut-dev",
            "session_mode": "isolated",
        },
    }

    @api.model
    def _get_role_defaults(self, role, provider):
        defaults = super()._get_role_defaults(role, provider)
        if provider == "openclaw":
            defaults.update(self._OPENCLAW_DEFAULTS.get(role, {}))
        return defaults

    @api.model
    def _get_ai_provider_label(self, provider):
        if provider == "openclaw":
            return "OpenClaw（本地）"
        return super()._get_ai_provider_label(provider)

    @api.model
    def _normalize_openclaw_model_name(self, model_name):
        value = (model_name or "").strip()
        if "/" in value:
            return value.split("/")[-1]
        return value

    @api.model
    def _flatten_messages_for_openclaw(self, messages):
        sections = []
        for message in messages or []:
            role = (message or {}).get("role") or "user"
            content = (message or {}).get("content")
            parts = []
            if isinstance(content, list):
                for chunk in content:
                    if not isinstance(chunk, dict):
                        continue
                    if chunk.get("type") == "text":
                        parts.append(chunk.get("text") or "")
                    elif chunk.get("type") == "image_url":
                        parts.append("[附带视觉输入图片，请结合附件理解页面、表格、图表和结构图。]")
            else:
                parts.append("" if content in (False, None) else str(content))
            text = "\n".join(part for part in parts if part).strip()
            if text:
                sections.append(f"{role.upper()}:\n{text}")
        return "\n\n".join(sections).strip()

    @api.model
    def _decode_openclaw_data_url(self, url):
        value = (url or "").strip()
        match = re.match(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$", value, re.S)
        if not match:
            return False
        try:
            return {
                "mimeType": match.group("mime"),
                "raw": base64.b64decode(match.group("data")),
            }
        except Exception:
            return False

    @api.model
    def _build_openclaw_attachments(self, messages):
        attachments = []
        image_index = 1
        for message in messages or []:
            content = (message or {}).get("content")
            if not isinstance(content, list):
                continue
            for chunk in content:
                if not isinstance(chunk, dict) or chunk.get("type") != "image_url":
                    continue
                image_url = (chunk.get("image_url") or {}).get("url")
                payload = self._decode_openclaw_data_url(image_url)
                if not payload:
                    continue
                mime_type = payload["mimeType"]
                extension = {
                    "image/jpeg": "jpg",
                    "image/png": "png",
                    "image/webp": "webp",
                }.get(mime_type, "bin")
                attachments.append(
                    {
                        "name": f"vision_input_{image_index}.{extension}",
                        "content": base64.b64encode(payload["raw"]).decode(),
                        "encoding": "base64",
                        "mimeType": mime_type,
                    }
                )
                image_index += 1
        return attachments

    @api.model
    def _extract_openclaw_text(self, agent_result):
        text = (agent_result or {}).get("text") or ""
        if text:
            return text.strip()
        payload = (agent_result or {}).get("payload") or {}
        result = payload.get("result") or {}
        parts = []
        for item in result.get("payloads") or []:
            if isinstance(item, dict) and item.get("text"):
                parts.append(item["text"])
        return "\n".join(parts).strip()

    @api.model
    def _get_ai_role_config(self, role):
        config = super()._get_ai_role_config(role)
        if config.get("provider") != "openclaw":
            return config
        icp = self.env["ir.config_parameter"].sudo()
        defaults = self._OPENCLAW_DEFAULTS.get(role, {})
        config.update(
            {
                "gateway_url": (
                    self.env.context.get(f"diecut_ai_{role}_gateway_url")
                    or icp.get_param(f"diecut.ai_tds_{role}_gateway_url")
                    or defaults.get("gateway_url")
                    or ""
                ),
                "gateway_token": (
                    self.env.context.get(f"diecut_ai_{role}_gateway_token")
                    or icp.get_param(f"diecut.ai_tds_{role}_gateway_token")
                    or ""
                ),
                "agent_id": (
                    self.env.context.get(f"diecut_ai_{role}_agent_id")
                    or icp.get_param(f"diecut.ai_tds_{role}_agent_id")
                    or defaults.get("agent_id")
                    or ""
                ),
                "session_mode": (
                    self.env.context.get(f"diecut_ai_{role}_session_mode")
                    or icp.get_param(f"diecut.ai_tds_{role}_session_mode")
                    or defaults.get("session_mode")
                    or "isolated"
                ),
                "model": config.get("model") or defaults.get("model") or "",
            }
        )
        if role == "vision" and config.get("session_mode") == "main":
            config["session_mode"] = "isolated"
        return config

    def _has_ai_role_config(self, role):
        config = self._get_ai_role_config(role)
        if config.get("provider") != "openclaw":
            return super()._has_ai_role_config(role)
        return bool(config.get("gateway_url") and config.get("gateway_token") and config.get("agent_id"))

    def _build_openclaw_session_key(self, role, config):
        self.ensure_one()
        agent_id = config.get("agent_id") or "odoo-diecut-dev"
        if (config.get("session_mode") or "isolated") == "isolated":
            return f"agent:{agent_id}:tds-{self.id or 'runtime'}-{role}"
        return f"agent:{agent_id}:main"

    def _openclaw_agent_extra(self, role, config):
        return {}

    def _ai_request(self, role, messages, max_tokens=4000, json_mode=False):
        config = self._get_ai_role_config(role)
        if config.get("provider") != "openclaw":
            return super()._ai_request(role, messages, max_tokens=max_tokens, json_mode=json_mode)

        if not self._has_ai_role_config(role):
            label = "视觉模型" if role == "vision" else "结构化模型"
            raise UserError(f"{label}未配置可用的 OpenClaw 网关。")

        prompt = self._flatten_messages_for_openclaw(messages)
        if json_mode:
            prompt = "请严格返回 JSON 对象，不要输出 Markdown、代码块围栏或解释。\n\n" + prompt
        timeout_seconds = int(self.env.context.get("diecut_ai_timeout_seconds") or 240)
        attachments = self._build_openclaw_attachments(messages)
        try:
            with OpenClawAdapter(
                gateway_url=config.get("gateway_url"),
                token=config.get("gateway_token"),
                timeout=timeout_seconds,
            ) as adapter:
                result = adapter.agent(
                    message=prompt,
                    agent_id=config.get("agent_id"),
                    session_key=self._build_openclaw_session_key(role, config),
                    timeout=timeout_seconds,
                    extra=self._openclaw_agent_extra(role, config),
                    attachments=attachments,
                )
        except OpenClawError as exc:
            raise UserError(f"OpenClaw 调用失败：{exc}") from exc

        content = self._extract_openclaw_text(result)
        if not content:
            raise UserError("OpenClaw 未返回可用内容。")
        return content

    def _generate_draft_with_openai(self):
        payload, parse_version = super()._generate_draft_with_openai()
        vision_config = self._get_ai_role_config("vision")
        struct_config = self._get_ai_role_config("struct")
        if vision_config.get("provider") == "openclaw" or struct_config.get("provider") == "openclaw":
            heuristic_match = re.search(r"(heuristic-v\d+)$", parse_version or "")
            heuristic_part = heuristic_match.group(1) if heuristic_match else "heuristic-v2"
            vision_part = (
                f"openclaw({self._normalize_openclaw_model_name(vision_config.get('model')) or 'default'})"
                if vision_config.get("provider") == "openclaw"
                else vision_config.get("model")
            )
            struct_part = (
                f"openclaw({self._normalize_openclaw_model_name(struct_config.get('model')) or 'default'})"
                if struct_config.get("provider") == "openclaw"
                else struct_config.get("model")
            )
            parse_version = f"vision:{vision_part} + struct:{struct_part} + {heuristic_part}"
        return payload, parse_version
