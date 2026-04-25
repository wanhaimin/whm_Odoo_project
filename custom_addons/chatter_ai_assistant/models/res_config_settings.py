# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    chatter_ai_bot_name = fields.Char(string="Bot Name", config_parameter="chatter_ai_assistant.bot_name", default="OdooBot")
    chatter_ai_mention_aliases = fields.Char(
        string="Mention Aliases",
        config_parameter="chatter_ai_assistant.mention_aliases",
        default="@OdooBot,@odoobot,@bot",
        help="Comma-separated aliases, for example @OdooBot,@odoobot,@bot.",
    )
    chatter_ai_private_chat_enabled = fields.Boolean(
        string="Enable OdooBot Private Chat AI",
        config_parameter="chatter_ai_assistant.private_chat_enabled",
        default=True,
    )
    chatter_ai_enabled_model_allowlist = fields.Char(
        string="Enabled Models",
        config_parameter="chatter_ai_assistant.enabled_model_allowlist",
        help="Optional comma-separated model list, for example crm.lead,project.task,res.partner.",
    )
    chatter_ai_allowed_group_xmlids = fields.Char(
        string="Allowed Groups",
        config_parameter="chatter_ai_assistant.allowed_group_xmlids",
        default="base.group_user",
    )
    chatter_ai_openclaw_cli_command = fields.Char(
        string="OpenClaw CLI Command",
        config_parameter="chatter_ai_assistant.openclaw_cli_command",
        default="/opt/openclaw-cli/bin/openclaw",
    )
    chatter_ai_openclaw_node_bin_path = fields.Char(
        string="Node Bin Directory",
        config_parameter="chatter_ai_assistant.openclaw_node_bin_path",
        default="/opt/node-v22.16.0-linux-x64/bin",
    )
    chatter_ai_openclaw_general_agent_id = fields.Char(
        string="General Agent ID",
        config_parameter="chatter_ai_assistant.openclaw_general_agent_id",
        default="main",
    )
    chatter_ai_openclaw_tds_agent_id = fields.Char(
        string="TDS Agent ID",
        config_parameter="chatter_ai_assistant.openclaw_tds_agent_id",
        default="odoo-diecut-tds",
    )
    chatter_ai_openclaw_thinking = fields.Selection(
        [
            ("minimal", "minimal"),
            ("low", "low"),
            ("medium", "medium"),
            ("high", "high"),
            ("xhigh", "xhigh"),
        ],
        string="Thinking Level",
        config_parameter="chatter_ai_assistant.openclaw_thinking",
        default="low",
    )
    chatter_ai_job_timeout_seconds = fields.Integer(
        string="Job Timeout (seconds)",
        config_parameter="chatter_ai_assistant.job_timeout_seconds",
        default=240,
    )
    chatter_ai_max_attachment_size_mb = fields.Integer(
        string="Max Attachment Size (MB)",
        config_parameter="chatter_ai_assistant.max_attachment_size_mb",
        default=15,
    )
    chatter_ai_max_context_messages = fields.Integer(
        string="Context Message Limit",
        config_parameter="chatter_ai_assistant.max_context_messages",
        default=12,
    )
    chatter_ai_worker_shared_secret = fields.Char(
        string="Worker Shared Secret",
        config_parameter="chatter_ai_assistant.worker_shared_secret",
        default="chatter-ai-local-dev",
    )
    chatter_ai_worker_stale_seconds = fields.Integer(
        string="Worker Stale Timeout (seconds)",
        config_parameter="chatter_ai_assistant.worker_stale_seconds",
        default=1800,
    )
    chatter_ai_worker_poll_seconds = fields.Float(
        string="Worker Poll Interval (seconds)",
        config_parameter="chatter_ai_assistant.worker_poll_seconds",
        default=0.5,
    )
