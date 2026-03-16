# -*- coding: utf-8 -*-

import uuid

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..tools import OpenClawAdapter, OpenClawError


class DiecutAiSettingsWizard(models.TransientModel):
    _name = "diecut.ai.settings.wizard"
    _description = "AI/TDS 设置"

    _PROVIDER_LABELS = {
        "disabled": "禁用",
        "openai": "OpenAI",
        "deepseek": "DeepSeek",
        "qwen": "通义千问(Qwen)",
        "openclaw": "OpenClaw（本地）",
    }

    _ROLE_DEFAULTS = {
        "vision": {
            "disabled": {"api_url": "", "model": ""},
            "openai": {
                "api_url": "https://api.openai.com/v1/chat/completions",
                "model": "gpt-4.1-mini",
            },
            "deepseek": {
                "api_url": "https://api.deepseek.com/chat/completions",
                "model": "deepseek-chat",
            },
            "qwen": {
                "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                "model": "qwen-vl-max-latest",
            },
            "openclaw": {
                "api_url": "",
                "model": "openai-codex/gpt-5.4",
                "gateway_url": "ws://host.docker.internal:18789",
                "agent_id": "odoo-diecut-dev",
                "session_mode": "main",
            },
        },
        "struct": {
            "disabled": {"api_url": "", "model": ""},
            "openai": {
                "api_url": "https://api.openai.com/v1/chat/completions",
                "model": "gpt-4.1-mini",
            },
            "deepseek": {
                "api_url": "https://api.deepseek.com/chat/completions",
                "model": "deepseek-chat",
            },
            "qwen": {
                "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                "model": "qwen3.5-plus",
            },
            "openclaw": {
                "api_url": "",
                "model": "openai-codex/gpt-5.4",
                "gateway_url": "ws://host.docker.internal:18789",
                "agent_id": "odoo-diecut-dev",
                "session_mode": "main",
            },
        },
    }

    vision_provider = fields.Selection(
        [
            ("disabled", "禁用视觉模型"),
            ("openai", "OpenAI 兼容接口"),
            ("deepseek", "DeepSeek 兼容接口"),
            ("qwen", "通义千问(Qwen) 兼容接口"),
            ("openclaw", "OpenClaw（本地）"),
        ],
        string="视觉模型提供商",
        default="qwen",
        required=True,
    )
    vision_api_key = fields.Char(string="视觉 API Key")
    vision_api_url = fields.Char(string="视觉接口地址")
    vision_model = fields.Char(string="视觉模型")
    vision_gateway_url = fields.Char(string="视觉网关地址")
    vision_gateway_token = fields.Char(string="视觉网关 Token")
    vision_agent_id = fields.Char(string="视觉 Agent ID")
    vision_session_mode = fields.Selection(
        [("main", "共享主会话"), ("isolated", "按文档隔离会话")],
        string="视觉会话模式",
        default="main",
        required=True,
    )

    struct_provider = fields.Selection(
        [
            ("disabled", "禁用结构化模型"),
            ("openai", "OpenAI 兼容接口"),
            ("deepseek", "DeepSeek 兼容接口"),
            ("qwen", "通义千问(Qwen) 兼容接口"),
            ("openclaw", "OpenClaw（本地）"),
        ],
        string="结构化模型提供商",
        default="qwen",
        required=True,
    )
    struct_api_key = fields.Char(string="结构化 API Key")
    struct_api_url = fields.Char(string="结构化接口地址")
    struct_model = fields.Char(string="结构化模型")
    struct_gateway_url = fields.Char(string="结构化网关地址")
    struct_gateway_token = fields.Char(string="结构化网关 Token")
    struct_agent_id = fields.Char(string="结构化 Agent ID")
    struct_session_mode = fields.Selection(
        [("main", "共享主会话"), ("isolated", "按文档隔离会话")],
        string="结构化会话模式",
        default="main",
        required=True,
    )

    extraction_note = fields.Text(
        string="说明",
        readonly=True,
        default=(
            "推荐双模型分工：视觉模型负责 PDF、图片、图表和方法区块理解；结构化模型负责系列、型号、"
            "参数和值草稿生成。若选择 OpenClaw，本地网关会作为模型执行后端，继续复用系统现有的 "
            "TDS Skill、参数字典和主字段路由规则。"
        ),
    )

    @api.model
    def _provider_defaults(self, role, provider):
        return dict(self._ROLE_DEFAULTS.get(role, {}).get(provider or "disabled", {"api_url": "", "model": ""}))

    @api.model
    def _provider_label(self, provider):
        return self._PROVIDER_LABELS.get(provider or "disabled", provider or "AI")

    @api.model
    def _normalize_secret(self, value):
        secret = (value or "").strip()
        if not secret:
            return ""
        half = len(secret) // 2
        if len(secret) % 2 == 0 and half and secret[:half] == secret[half:]:
            return secret[:half]
        return secret

    @api.model
    def _normalize_openclaw_model_name(self, model_name):
        value = (model_name or "").strip()
        if "/" in value:
            return value.split("/")[-1]
        return value

    @api.model
    def _load_role_values(self, icp, role):
        provider = icp.get_param(f"diecut.ai_tds_{role}_provider", default="")
        api_key = icp.get_param(f"diecut.ai_tds_{role}_api_key", default="")
        api_url = icp.get_param(f"diecut.ai_tds_{role}_api_url", default="")
        model = icp.get_param(f"diecut.ai_tds_{role}_model", default="")
        gateway_url = icp.get_param(f"diecut.ai_tds_{role}_gateway_url", default="")
        gateway_token = icp.get_param(f"diecut.ai_tds_{role}_gateway_token", default="")
        agent_id = icp.get_param(f"diecut.ai_tds_{role}_agent_id", default="")
        session_mode = icp.get_param(f"diecut.ai_tds_{role}_session_mode", default="")

        old_provider = icp.get_param("diecut.ai_tds_provider", default="qwen")
        old_api_key = icp.get_param("diecut.ai_tds_openai_api_key", default="")
        old_api_url = icp.get_param("diecut.ai_tds_openai_api_url", default="")
        old_model = icp.get_param("diecut.ai_tds_openai_model", default="")

        provider = provider or old_provider or "qwen"
        defaults = self._provider_defaults(role, provider)
        api_key = api_key or old_api_key
        api_url = api_url or old_api_url or defaults.get("api_url", "")
        model = model or (old_model if role == "struct" else "") or defaults.get("model", "")
        gateway_url = gateway_url or defaults.get("gateway_url", "")
        agent_id = agent_id or defaults.get("agent_id", "")
        session_mode = session_mode or defaults.get("session_mode", "main")

        return {
            f"{role}_provider": provider,
            f"{role}_api_key": api_key,
            f"{role}_api_url": api_url,
            f"{role}_model": model,
            f"{role}_gateway_url": gateway_url,
            f"{role}_gateway_token": gateway_token,
            f"{role}_agent_id": agent_id,
            f"{role}_session_mode": session_mode,
        }

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        icp = self.env["ir.config_parameter"].sudo()
        values.update(self._load_role_values(icp, "vision"))
        values.update(self._load_role_values(icp, "struct"))
        return values

    @api.onchange("vision_provider")
    def _onchange_vision_provider(self):
        defaults = self._provider_defaults("vision", self.vision_provider)
        self.vision_api_url = defaults.get("api_url", "")
        self.vision_model = defaults.get("model", "")
        self.vision_gateway_url = defaults.get("gateway_url", "")
        self.vision_agent_id = defaults.get("agent_id", "")
        self.vision_session_mode = defaults.get("session_mode", "main")

    @api.onchange("struct_provider")
    def _onchange_struct_provider(self):
        defaults = self._provider_defaults("struct", self.struct_provider)
        self.struct_api_url = defaults.get("api_url", "")
        self.struct_model = defaults.get("model", "")
        self.struct_gateway_url = defaults.get("gateway_url", "")
        self.struct_agent_id = defaults.get("agent_id", "")
        self.struct_session_mode = defaults.get("session_mode", "main")

    def _role_payload(self, role):
        return {
            "provider": getattr(self, f"{role}_provider"),
            "api_key": self._normalize_secret(getattr(self, f"{role}_api_key")),
            "api_url": (getattr(self, f"{role}_api_url") or "").strip(),
            "model": (getattr(self, f"{role}_model") or "").strip(),
            "gateway_url": (getattr(self, f"{role}_gateway_url") or "").strip(),
            "gateway_token": self._normalize_secret(getattr(self, f"{role}_gateway_token")),
            "agent_id": (getattr(self, f"{role}_agent_id") or "").strip(),
            "session_mode": getattr(self, f"{role}_session_mode") or "main",
        }

    def action_save(self):
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        for role in ("vision", "struct"):
            payload = self._role_payload(role)
            defaults = self._provider_defaults(role, payload["provider"])
            icp.set_param(f"diecut.ai_tds_{role}_provider", payload["provider"])
            icp.set_param(f"diecut.ai_tds_{role}_api_key", payload["api_key"])
            icp.set_param(f"diecut.ai_tds_{role}_api_url", payload["api_url"] or defaults.get("api_url", ""))
            icp.set_param(f"diecut.ai_tds_{role}_model", payload["model"] or defaults.get("model", ""))
            icp.set_param(f"diecut.ai_tds_{role}_gateway_url", payload["gateway_url"] or defaults.get("gateway_url", ""))
            icp.set_param(f"diecut.ai_tds_{role}_gateway_token", payload["gateway_token"])
            icp.set_param(f"diecut.ai_tds_{role}_agent_id", payload["agent_id"] or defaults.get("agent_id", ""))
            icp.set_param(f"diecut.ai_tds_{role}_session_mode", payload["session_mode"] or defaults.get("session_mode", "main"))

        struct_payload = self._role_payload("struct")
        icp.set_param("diecut.ai_tds_provider", struct_payload["provider"])
        icp.set_param("diecut.ai_tds_openai_api_key", struct_payload["api_key"])
        icp.set_param("diecut.ai_tds_openai_api_url", struct_payload["api_url"])
        icp.set_param("diecut.ai_tds_openai_model", struct_payload["model"])
        return {"type": "ir.actions.client", "tag": "reload"}

    def _test_http_role_connection(self, role, payload):
        role_label = "视觉模型" if role == "vision" else "结构化模型"
        if not payload["api_key"]:
            raise UserError(f"{role_label}未填写 API Key。")
        request_payload = {
            "model": payload["model"],
            "messages": [{"role": "user", "content": "请只返回 OK"}],
            "temperature": 0.1,
            "max_tokens": 16,
        }
        try:
            response = requests.post(
                payload["api_url"],
                timeout=90,
                headers={
                    "Authorization": f"Bearer {payload['api_key']}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            code = ""
            detail = ""
            try:
                data = exc.response.json()
                error = data.get("error") or {}
                code = error.get("code") or ""
                detail = error.get("message") or ""
            except Exception:
                detail = exc.response.text[:300] if exc.response is not None else str(exc)
            summary = f"{role_label}测试失败：{self._provider_label(payload['provider'])} / {payload['model']} / HTTP {status}"
            if code:
                summary += f" / {code}"
            if detail:
                summary += f"\n{detail}"
            raise UserError(summary) from exc
        except Exception as exc:
            raise UserError(f"{role_label}测试失败：{exc}") from exc

        if "OK" not in (content or "").upper():
            raise UserError(f"{role_label}已连通，但返回内容异常，请检查接口兼容性。")
        return f"{role_label} 连通成功：{self._provider_label(payload['provider'])} / {payload['model']}"

    def _test_openclaw_role_connection(self, role, payload):
        role_label = "视觉模型" if role == "vision" else "结构化模型"
        if not payload["gateway_url"]:
            raise UserError(f"{role_label}未填写 OpenClaw 网关地址。")
        if not payload["gateway_token"]:
            raise UserError(f"{role_label}未填写 OpenClaw 网关 Token。")
        if not payload["agent_id"]:
            raise UserError(f"{role_label}未填写 OpenClaw Agent ID。")

        normalized_model = self._normalize_openclaw_model_name(payload["model"])
        try:
            with OpenClawAdapter(
                gateway_url=payload["gateway_url"],
                token=payload["gateway_token"],
                timeout=120,
            ) as adapter:
                adapter.status()
                models_payload = adapter.models_list()
                model_ids = {
                    self._normalize_openclaw_model_name(model.get("id") or "")
                    for model in models_payload
                    if isinstance(model, dict) and (model.get("id") or "")
                }
                if normalized_model and model_ids and normalized_model not in model_ids:
                    raise UserError(
                        f"{role_label}测试失败：OpenClaw 已连接，但模型 {payload['model']} 不在可用模型列表中。"
                    )
                result = adapter.agent(
                    message="Reply with OK only",
                    agent_id=payload["agent_id"],
                    session_key=f"settings-test:{payload['agent_id']}:{uuid.uuid4()}",
                    timeout=90,
                    extra={
                        "model": payload["model"],
                        "sessionMode": "isolated",
                    },
                )
        except UserError:
            raise
        except OpenClawError as exc:
            raise UserError(f"{role_label}测试失败：{exc}") from exc

        return (
            f"{role_label} 连通成功：{self._provider_label(payload['provider'])}"
            f" / {payload['agent_id']} / {normalized_model or payload['model']}"
        )

    def _test_role_connection(self, role):
        payload = self._role_payload(role)
        role_label = "视觉模型" if role == "vision" else "结构化模型"
        if payload["provider"] == "disabled":
            return f"{role_label}：已禁用"
        if payload["provider"] == "openclaw":
            return self._test_openclaw_role_connection(role, payload)
        return self._test_http_role_connection(role, payload)

    def action_test_connection(self):
        self.ensure_one()
        messages = [self._test_role_connection("vision"), self._test_role_connection("struct")]
        raise UserError("\n".join(messages))
