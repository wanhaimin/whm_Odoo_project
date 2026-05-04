# -*- coding: utf-8 -*-

import time

from odoo import api, fields, models
from odoo.exceptions import UserError


class DiecutLlmModelProfile(models.Model):
    _name = "diecut.llm.model.profile"
    _description = "大模型配置档案"
    _order = "sequence, name"

    name = fields.Char(string="名称", required=True)
    sequence = fields.Integer(string="序号", default=10)
    active = fields.Boolean(string="启用", default=False, index=True)
    provider = fields.Selection(
        [
            ("dify", "Dify"),
            ("anthropic", "Claude / Anthropic"),
            ("deepseek", "DeepSeek"),
            ("qwen", "通义千问"),
            ("kimi", "Kimi / Moonshot"),
            ("openclaw", "OpenClaw"),
            ("openai_compatible", "OpenAI 兼容"),
        ],
        string="供应商",
        required=True,
        default="openai_compatible",
        index=True,
    )
    protocol = fields.Selection(
        [
            ("dify_chat", "Dify Chat"),
            ("anthropic_messages", "Anthropic Messages"),
            ("openai_chat_compatible", "OpenAI Chat Compatible"),
            ("openclaw_worker", "OpenClaw Worker"),
        ],
        string="协议",
        required=True,
        default="openai_chat_compatible",
    )
    base_url = fields.Char(string="Base URL / 命令")
    api_key = fields.Char(string="API Key", groups="base.group_system")
    model_name = fields.Char(string="模型名 / Agent")
    max_tokens = fields.Integer(string="最大输出 Token", default=4096)
    temperature = fields.Float(string="Temperature", default=0.2)
    support_stream = fields.Boolean(string="支持流式", default=True)
    use_ai_advisor = fields.Boolean(string="AI 顾问", default=True)
    use_wiki_compile = fields.Boolean(string="Wiki 编译", default=False)
    use_source_parse = fields.Boolean(string="资料解析", default=False)
    use_graph_fix = fields.Boolean(string="图谱修正", default=False)
    is_default_advisor = fields.Boolean(string="默认 AI 顾问模型", default=False)
    is_default_wiki_compile = fields.Boolean(string="默认 Wiki 编译模型", default=False)
    last_test_at = fields.Datetime(string="最近测试时间", readonly=True)
    last_test_state = fields.Selection(
        [("success", "成功"), ("failed", "失败")],
        string="最近测试结果",
        readonly=True,
    )
    last_test_message = fields.Text(string="最近测试消息", readonly=True)

    @api.model
    def ensure_builtin_profiles(self):
        Profile = self.with_context(active_test=False).sudo()
        openclaw_cli = self._param("chatter_ai_assistant.openclaw_cli_command") or "/opt/openclaw-cli/bin/openclaw"
        configs = [
            {
                "provider": "dify",
                "protocol": "dify_chat",
                "name": "Dify Chat",
                "sequence": 10,
                "base_url": self._param("diecut_knowledge.dify_chat_app_url") or self._param("diecut_knowledge.dify_base_url"),
                "api_key": self._param("diecut_knowledge.dify_chat_api_key"),
                "model_name": "dify-chat",
                "active": bool(self._param("diecut_knowledge.dify_chat_api_key")),
            },
            {
                "provider": "anthropic",
                "protocol": "anthropic_messages",
                "name": "Claude",
                "sequence": 20,
                "base_url": self._param("diecut_knowledge.claude_base_url"),
                "api_key": self._param("diecut_knowledge.claude_api_key"),
                "model_name": self._param("diecut_knowledge.claude_model") or "claude-opus-4-7",
                "active": bool(self._param("diecut_knowledge.claude_api_key")),
            },
            {
                "provider": "deepseek",
                "protocol": "openai_chat_compatible",
                "name": "DeepSeek",
                "sequence": 30,
                "base_url": "https://api.deepseek.com",
                "model_name": "deepseek-v4-flash",
            },
            {
                "provider": "qwen",
                "protocol": "openai_chat_compatible",
                "name": "通义千问",
                "sequence": 40,
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model_name": "qwen-plus",
            },
            {
                "provider": "kimi",
                "protocol": "openai_chat_compatible",
                "name": "Kimi",
                "sequence": 50,
                "base_url": "https://api.moonshot.ai/v1",
                "model_name": "kimi-k2.5",
            },
            {
                "provider": "openclaw",
                "protocol": "openclaw_worker",
                "name": "OpenClaw",
                "sequence": 60,
                "base_url": openclaw_cli,
                "model_name": self._param("chatter_ai_assistant.openclaw_general_agent_id") or "main",
                "active": bool(openclaw_cli),
                "support_stream": False,
            },
        ]
        profiles = Profile.browse()
        for vals in configs:
            profile = Profile.search([("provider", "=", vals["provider"]), ("protocol", "=", vals["protocol"])], limit=1)
            create_vals = {
                "name": vals["name"],
                "provider": vals["provider"],
                "protocol": vals["protocol"],
                "sequence": vals.get("sequence", 10),
                "base_url": vals.get("base_url") or "",
                "model_name": vals.get("model_name") or "",
                "active": bool(vals.get("active", False)),
                "support_stream": bool(vals.get("support_stream", True)),
                "use_ai_advisor": True,
                "use_wiki_compile": vals["provider"] in {"anthropic", "deepseek", "qwen", "kimi"},
                "max_tokens": int(self._param("diecut_knowledge.claude_max_tokens") or 4096) if vals["provider"] == "anthropic" else 4096,
            }
            if vals.get("api_key"):
                create_vals["api_key"] = vals["api_key"]
            if profile:
                update_vals = {}
                for key in ("base_url", "api_key", "model_name"):
                    if not profile[key] and create_vals.get(key):
                        update_vals[key] = create_vals[key]
                if profile.protocol == "openclaw_worker":
                    update_vals["support_stream"] = False
                if vals.get("active") and not profile.active:
                    update_vals["active"] = True
                if update_vals:
                    profile.write(update_vals)
            else:
                profile = Profile.create(create_vals)
            profiles |= profile
        Profile._ensure_default_flags()
        return profiles

    @api.model
    def advisor_options(self):
        self.sudo().ensure_builtin_profiles()
        profiles = self.sudo().search(self._available_domain("advisor"))
        default_profile = self.sudo().get_default_profile("advisor")
        return {
            "default_id": default_profile.id if default_profile else False,
            "profiles": [
                {
                    "id": profile.id,
                    "name": profile.name,
                    "provider": profile.provider,
                    "protocol": profile.protocol,
                    "model": profile.model_name or "",
                    "support_stream": bool(profile.support_stream),
                    "is_default": profile == default_profile,
                }
                for profile in profiles
            ],
        }

    @api.model
    def get_default_profile(self, purpose="advisor"):
        self.sudo().ensure_builtin_profiles()
        domain = self._available_domain("wiki_compile" if purpose == "wiki_compile" else "advisor")
        default_field = "is_default_wiki_compile" if purpose == "wiki_compile" else "is_default_advisor"
        profile = self.sudo().search(domain + [(default_field, "=", True)], limit=1)
        if profile:
            return profile
        return self.sudo().search(domain, limit=1)

    def build_client(self):
        self.ensure_one()
        if self.protocol == "openclaw_worker":
            from ..services.openclaw_worker_client import OpenClawWorkerClient

            return OpenClawWorkerClient(env=self.env)
        if not self.api_key:
            raise UserError("模型档案 [%s] 未配置 API Key。" % self.name)
        if self.protocol == "dify_chat":
            from ..services.dify_client import DifyClient

            if not self.base_url:
                raise UserError("模型档案 [%s] 未配置 Base URL。" % self.name)
            return DifyClient(base_url=self.base_url, api_key=self.api_key, timeout=120, retries=1)
        if self.protocol == "anthropic_messages":
            from ..services.claude_client import ClaudeClient

            kwargs = {
                "api_key": self.api_key,
                "model": self.model_name or None,
                "max_tokens": self.max_tokens or 4096,
                "timeout": 120,
            }
            if self.base_url:
                kwargs["base_url"] = self.base_url
            return ClaudeClient(**kwargs)
        from ..services.openai_compatible_client import OpenAICompatibleClient

        return OpenAICompatibleClient(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model_name,
            max_tokens=self.max_tokens or 4096,
            temperature=self.temperature,
            timeout=120,
        )

    def action_test_profile(self):
        self.ensure_one()
        t0 = time.monotonic()
        try:
            client = self.build_client()
            if self.protocol == "openclaw_worker":
                ok, payload, error, duration = client.test_connection()
            else:
                ok, payload, error, duration = client.chat_messages(
                    query="请用一句话回复：模型连接测试成功。",
                    user=self.env.user.display_name or "Odoo User",
                    inputs={"system": "你是一个连接测试助手，只需要简短回复。"},
                )
        except Exception as exc:
            ok, payload, error, duration = False, {}, str(exc), int((time.monotonic() - t0) * 1000)
        self.write(
            {
                "last_test_at": fields.Datetime.now(),
                "last_test_state": "success" if ok else "failed",
                "last_test_message": (payload.get("answer") if ok else error or "调用失败")[:1000],
            }
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "模型连接测试",
                "message": "连接成功，用时 %sms。" % duration if ok else "连接失败：%s" % (error or "未知错误"),
                "type": "success" if ok else "danger",
                "sticky": not ok,
            },
        }

    @api.constrains("is_default_advisor", "is_default_wiki_compile")
    def _check_single_default(self):
        for record in self:
            if record.is_default_advisor:
                self.search([("id", "!=", record.id), ("is_default_advisor", "=", True)]).write({"is_default_advisor": False})
            if record.is_default_wiki_compile:
                self.search([("id", "!=", record.id), ("is_default_wiki_compile", "=", True)]).write({"is_default_wiki_compile": False})

    def _ensure_default_flags(self):
        advisor = self.search(self._available_domain("advisor") + [("is_default_advisor", "=", True)], limit=1)
        if not advisor:
            advisor = self.search(self._available_domain("advisor"), limit=1)
            if advisor:
                advisor.is_default_advisor = True
        wiki = self.search(self._available_domain("wiki_compile") + [("is_default_wiki_compile", "=", True)], limit=1)
        if not wiki:
            wiki = self.search(self._available_domain("wiki_compile"), limit=1)
            if wiki:
                wiki.is_default_wiki_compile = True

    def _available_domain(self, purpose):
        domain = [
            ("active", "=", True),
            "|",
            ("api_key", "!=", False),
            ("protocol", "=", "openclaw_worker"),
        ]
        if purpose == "wiki_compile":
            domain.append(("use_wiki_compile", "=", True))
        else:
            domain.append(("use_ai_advisor", "=", True))
        return domain

    @api.model
    def _param(self, key):
        return (self.env["ir.config_parameter"].sudo().get_param(key) or "").strip()
