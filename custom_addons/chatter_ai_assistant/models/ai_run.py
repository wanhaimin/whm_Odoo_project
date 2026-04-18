# -*- coding: utf-8 -*-

import base64
import json
import logging
import os
import re
import tempfile
import uuid
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


_logger = logging.getLogger(__name__)


class ChatterAiRun(models.Model):
    _name = "chatter.ai.run"
    _description = "Chatter AI Run"
    _order = "create_date desc, id desc"

    name = fields.Char(string="Name", required=True, default=lambda self: _("New AI Run"))
    run_id = fields.Char(string="Run ID", required=True, copy=False, readonly=True, index=True)
    state = fields.Selection(
        [
            ("queued", "Queued"),
            ("running", "Running"),
            ("succeeded", "Succeeded"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        required=True,
        default="queued",
        index=True,
    )
    conversation_type = fields.Selection(
        [
            ("record", "Business Record"),
            ("private_chat", "Private Chat"),
        ],
        string="Conversation Type",
        required=True,
        default="record",
        index=True,
    )
    task_type = fields.Selection(
        [
            ("chat", "Chat"),
            ("document", "Document"),
        ],
        string="Task Type",
        required=True,
        default="chat",
        index=True,
    )
    document_action = fields.Selection(
        [
            ("extract_source", "Extract Source"),
            ("identify_handbook", "Identify Handbook"),
            ("parse", "Parse"),
            ("summarize", "Summarize"),
            ("extract_params", "Extract Parameters"),
            ("reparse", "Reparse"),
        ],
        string="Document Action",
        default=False,
        index=True,
    )
    source_kind = fields.Selection(
        [
            ("pdf", "PDF"),
            ("image", "Image"),
            ("webpage", "Webpage"),
            ("text", "Text"),
            ("mixed", "Mixed"),
        ],
        string="Source Kind",
        default=False,
        index=True,
    )
    model = fields.Char(string="Model", required=True, index=True)
    res_id = fields.Integer(string="Record ID", required=True, index=True)
    channel_id = fields.Many2one("discuss.channel", string="Discuss Channel", ondelete="cascade", index=True)
    record_display_name = fields.Char(string="Record Name", readonly=True)
    trigger_message_id = fields.Many2one("mail.message", string="Trigger Message", required=True, ondelete="cascade", index=True)
    status_message_id = fields.Many2one("mail.message", string="Status Message", ondelete="set null")
    requesting_partner_id = fields.Many2one("res.partner", string="Requesting Partner", required=True, ondelete="restrict")
    requesting_user_id = fields.Many2one("res.users", string="Requesting User", ondelete="set null")
    prompt_html = fields.Html(string="Prompt HTML", readonly=True)
    prompt_text = fields.Text(string="Prompt Text", readonly=True)
    context_payload = fields.Text(string="Context Payload", readonly=True)
    result_summary = fields.Text(string="Summary", readonly=True)
    reply_text = fields.Html(string="Reply", readonly=True)
    source_attachment_ids = fields.Many2many(
        "ir.attachment",
        "chatter_ai_run_source_attachment_rel",
        "run_id",
        "attachment_id",
        string="Source Attachments",
        readonly=True,
    )
    generated_attachment_ids = fields.Many2many(
        "ir.attachment",
        "chatter_ai_run_generated_attachment_rel",
        "run_id",
        "attachment_id",
        string="Generated Attachments",
        readonly=True,
    )
    temp_directory = fields.Char(string="Temp Directory", readonly=True)
    trace_path = fields.Char(string="Trace Log", readonly=True)
    error_message = fields.Text(string="Error", readonly=True)
    started_at = fields.Datetime(string="Started At", readonly=True)
    finished_at = fields.Datetime(string="Finished At", readonly=True)

    @api.constrains("trigger_message_id")
    def _check_trigger_message_id(self):
        for run in self:
            if not run.trigger_message_id:
                continue
            duplicate = self.search(
                [("trigger_message_id", "=", run.trigger_message_id.id), ("id", "!=", run.id)],
                limit=1,
            )
            if duplicate:
                raise ValidationError(_("The same chatter message can only trigger one AI run."))

    @api.model
    def _config(self):
        icp = self.env["ir.config_parameter"].sudo()
        aliases = (icp.get_param("chatter_ai_assistant.mention_aliases") or "@OdooBot,@odoobot,@bot").strip()
        allowlist = (icp.get_param("chatter_ai_assistant.enabled_model_allowlist") or "").strip()
        group_xmlids = (icp.get_param("chatter_ai_assistant.allowed_group_xmlids") or "base.group_user").strip()
        return {
            "bot_name": (icp.get_param("chatter_ai_assistant.bot_name") or "OdooBot").strip(),
            "aliases": [item.strip() for item in aliases.split(",") if item.strip()],
            "allowlist": [item.strip() for item in allowlist.split(",") if item.strip()],
            "group_xmlids": [item.strip() for item in group_xmlids.split(",") if item.strip()],
            "private_chat_enabled": (icp.get_param("chatter_ai_assistant.private_chat_enabled") or "True").strip().lower() in ("1", "true", "yes", "on"),
            "cli_command": (
                icp.get_param("chatter_ai_assistant.openclaw_cli_command") or "/opt/openclaw-cli/bin/openclaw"
            ).strip(),
            "node_bin_path": (
                icp.get_param("chatter_ai_assistant.openclaw_node_bin_path") or "/opt/node-v22.16.0-linux-x64/bin"
            ).strip(),
            "general_agent_id": (
                icp.get_param("chatter_ai_assistant.openclaw_general_agent_id")
                or icp.get_param("chatter_ai_assistant.openclaw_agent_id")
                or "odoo-diecut-dev"
            ).strip(),
            "tds_agent_id": (
                icp.get_param("chatter_ai_assistant.openclaw_tds_agent_id")
                or icp.get_param("chatter_ai_assistant.openclaw_agent_id")
                or "odoo-diecut-dev"
            ).strip(),
            "thinking": (icp.get_param("chatter_ai_assistant.openclaw_thinking") or "low").strip(),
            "timeout_seconds": int(icp.get_param("chatter_ai_assistant.job_timeout_seconds") or 240),
            "max_context_messages": int(icp.get_param("chatter_ai_assistant.max_context_messages") or 12),
            "max_attachment_size_mb": int(icp.get_param("chatter_ai_assistant.max_attachment_size_mb") or 15),
            "worker_shared_secret": (
                icp.get_param("chatter_ai_assistant.worker_shared_secret") or "chatter-ai-local-dev"
            ).strip(),
            "worker_stale_seconds": int(icp.get_param("chatter_ai_assistant.worker_stale_seconds") or 300),
            "worker_poll_seconds": float(icp.get_param("chatter_ai_assistant.worker_poll_seconds") or 0.5),
        }

    @api.model
    def _odoobot_partner(self):
        return self.env.ref("base.partner_root", raise_if_not_found=False)

    @api.model
    def _worker_secret_is_valid(self, token):
        secret = self._config()["worker_shared_secret"]
        return bool(secret and token and token == secret)

    @api.model
    def _extract_plain_text(self, html):
        text = re.sub(r"<[^>]+>", " ", html or "")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @api.model
    def _document_action_from_text(self, model_name, plain_text):
        text = (plain_text or "").strip().lower()
        if model_name not in ("diecut.catalog.source.document", "chatter.ai.handbook.review") or not text:
            return False
        if any(token in text for token in ("识别手册结构", "手册结构", "系列总览", "handbook", "catalog review", "catalog structure")):
            return "identify_handbook"
        if any(token in text for token in ("提取原文", "提取正文", "抽取原文", "extract source", "extract text")):
            return "extract_source"
        if any(token in text for token in ("重新解析", "重解析", "重新整理", "重新生成草稿", "reparse")):
            return "reparse"
        if any(token in text for token in ("总结", "摘要", "概括", "summary", "summarize")):
            return "summarize"
        if any(token in text for token in ("参数", "规格")) and any(
            token in text for token in ("提取", "抽取", "整理", "解析", "extract")
        ):
            return "extract_params"
        if any(
            token in text
            for token in ("解析", "整理", "草稿", "结构化", "parse", "analyze", "analyse")
        ):
            return "parse"
        return False

    @api.model
    def _user_is_allowed(self, user):
        if not user:
            return False
        if user._is_admin():
            return True
        allowed_groups = []
        for xmlid in self._config()["group_xmlids"]:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                allowed_groups.append(group)
        if not allowed_groups:
            return True
        return any(group in user.groups_id for group in allowed_groups)

    @api.model
    def _private_chat_channel(self, message):
        if message.model != "discuss.channel" or not message.res_id:
            return self.env["discuss.channel"]
        return self.env["discuss.channel"].sudo().browse(message.res_id).exists()

    @api.model
    def _is_odoobot_private_chat(self, message):
        if not self._config()["private_chat_enabled"]:
            return False
        channel = self._private_chat_channel(message)
        odoobot = self._odoobot_partner()
        if not channel or not odoobot:
            return False
        if channel.channel_type != "chat":
            return False
        return odoobot in channel.channel_member_ids.partner_id

    @api.model
    def _should_trigger_from_message(self, message):
        if not message.model or not message.res_id:
            return False
        if message.message_type not in ("comment", "email"):
            return False
        user = message.author_id.user_ids[:1]
        if not self._user_is_allowed(user):
            return False
        if self._is_odoobot_private_chat(message):
            odoobot = self._odoobot_partner()
            if odoobot and message.author_id == odoobot:
                return False
            plain = self._extract_plain_text(message.body)
            return bool(plain or message.attachment_ids)
        config = self._config()
        if config["allowlist"] and message.model not in config["allowlist"]:
            return False
        plain = self._extract_plain_text(message.body)
        if self._document_action_from_text(message.model, plain):
            return True
        return bool(plain and any(alias.lower() in plain.lower() for alias in config["aliases"]))

    @api.model
    def _collect_source_attachments(self, message):
        attachments = self.env["ir.attachment"]
        for attachment in message.attachment_ids:
            attachments |= attachment
        return self._validate_attachments(attachments)

    @api.model
    def _validate_attachments(self, attachments):
        config = self._config()
        max_bytes = config["max_attachment_size_mb"] * 1024 * 1024
        for attachment in attachments:
            if attachment.file_size and attachment.file_size > max_bytes:
                raise UserError(
                    _("Attachment %s exceeds the %s MB limit.")
                    % (attachment.name, config["max_attachment_size_mb"])
                )
        return attachments

    @api.model
    def _prepare_context_messages(self, message):
        config = self._config()
        siblings = self.env["mail.message"].sudo().search(
            [
                ("model", "=", message.model),
                ("res_id", "=", message.res_id),
                ("message_type", "in", ("comment", "email")),
            ],
            order="id desc",
            limit=config["max_context_messages"],
        )
        payload = []
        for sibling in reversed(siblings):
            payload.append(
                {
                    "message_id": sibling.id,
                    "author": sibling.author_id.display_name,
                    "body_text": self._extract_plain_text(sibling.body),
                    "date": fields.Datetime.to_string(sibling.date or sibling.create_date),
                }
            )
        return payload

    @api.model
    def _status_body(self, state, extra_text=False):
        labels = {
            "queued": "已排队",
            "running": "处理中",
            "succeeded": "已完成",
            "failed": "失败",
            "cancelled": "已取消",
        }
        body = "<p><strong>%s</strong>：%s</p>" % (self._config()["bot_name"], labels.get(state, state))
        if extra_text:
            body += "<p>%s</p>" % extra_text
        return body

    @api.model
    def create_run_from_message(self, message):
        existing = self.search([("trigger_message_id", "=", message.id)], limit=1)
        if existing:
            return existing
        user = message.author_id.user_ids[:1]
        if not self._user_is_allowed(user):
            raise AccessError(_("You do not have permission to use the AI assistant."))
        source_attachments = self._collect_source_attachments(message)
        message_record = self.env[message.model].sudo().browse(message.res_id).exists()
        if not message_record:
            raise UserError(_("The target conversation record does not exist."))
        record = message_record
        if message.model == "chatter.ai.handbook.review":
            record = message_record.source_document_id.sudo().exists()
            if not record:
                raise UserError(_("The source document for this handbook review no longer exists."))
        plain_text = self._extract_plain_text(message.body)
        document_action = self._document_action_from_text(message.model, plain_text)
        if document_action and hasattr(record, "_chatter_ai_resolve_source_attachments"):
            source_attachments = record._chatter_ai_resolve_source_attachments(source_attachments)
        source_attachments = self._validate_attachments(source_attachments)
        conversation_type = "private_chat" if self._is_odoobot_private_chat(message) else "record"
        bot_partner = self._odoobot_partner()
        status_message = self.env["mail.message"]
        if conversation_type == "record":
            status_message = message_record.message_post(
                body=self._status_body("queued"),
                author_id=bot_partner.id if bot_partner else False,
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        values = {
            "name": "%s/%s" % (record._name, record.id),
            "run_id": str(uuid.uuid4()),
            "conversation_type": conversation_type,
            "task_type": "document" if document_action else "chat",
            "document_action": document_action or False,
            "model": record._name,
            "res_id": record.id,
            "record_display_name": getattr(record, "display_name", False) or getattr(record, "name", False),
            "trigger_message_id": message.id,
            "requesting_partner_id": message.author_id.id,
            "requesting_user_id": user.id,
            "prompt_html": message.body,
            "prompt_text": plain_text,
            "context_payload": json.dumps(self._prepare_context_messages(message), ensure_ascii=False),
            "source_attachment_ids": [(6, 0, source_attachments.ids)],
        }
        if document_action and hasattr(record, "_chatter_ai_source_kind"):
            values["source_kind"] = record._chatter_ai_source_kind(
                attachments=source_attachments,
                message_text=plain_text,
            )
        if conversation_type == "record" and status_message:
            values["status_message_id"] = status_message.id
        if conversation_type == "private_chat":
            values["channel_id"] = record.id
        return self.sudo().create(values)

    @api.model
    def create_document_run(self, record, *, document_action, prompt_text=False, requesting_user=False):
        record = record.sudo().exists()
        if not record:
            raise UserError(_("The target conversation record does not exist."))
        user = (requesting_user or self.env.user).sudo()
        if not self._user_is_allowed(user):
            raise AccessError(_("You do not have permission to use the AI assistant."))
        prompt_text = (prompt_text or "").strip()
        if not prompt_text:
            prompt_map = {
                "extract_source": _("提取原文"),
                "identify_handbook": _("识别手册结构"),
                "parse": _("AI生成草稿"),
                "extract_params": _("参数提取"),
                "reparse": _("重新识别"),
                "summarize": _("总结"),
            }
            prompt_text = prompt_map.get(document_action) or _("AI document task")
        trigger_message = self.env["mail.message"].sudo().create(
            {
                "model": record._name,
                "res_id": record.id,
                "body": "<p>%s</p>" % prompt_text,
                "author_id": user.partner_id.id,
                "message_type": "comment",
                "subtype_id": self.env.ref("mail.mt_note").id,
            }
        )
        source_attachments = self.env["ir.attachment"]
        if hasattr(record, "_chatter_ai_resolve_source_attachments"):
            source_attachments = record._chatter_ai_resolve_source_attachments(source_attachments)
        source_attachments = self._validate_attachments(source_attachments)
        bot_partner = self._odoobot_partner()
        status_message = record.message_post(
            body=self._status_body("queued"),
            author_id=bot_partner.id if bot_partner else False,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        values = {
            "name": "%s/%s" % (record._name, record.id),
            "run_id": str(uuid.uuid4()),
            "conversation_type": "record",
            "task_type": "document",
            "document_action": document_action,
            "model": record._name,
            "res_id": record.id,
            "record_display_name": getattr(record, "display_name", False) or getattr(record, "name", False),
            "trigger_message_id": trigger_message.id,
            "status_message_id": status_message.id if status_message else False,
            "requesting_partner_id": user.partner_id.id,
            "requesting_user_id": user.id,
            "prompt_html": "<p>%s</p>" % prompt_text,
            "prompt_text": prompt_text,
            "context_payload": json.dumps([], ensure_ascii=False),
            "source_attachment_ids": [(6, 0, source_attachments.ids)],
        }
        if hasattr(record, "_chatter_ai_source_kind"):
            values["source_kind"] = record._chatter_ai_source_kind(
                attachments=source_attachments,
                message_text=prompt_text,
            )
        run = self.sudo().create(values)
        run._trigger_processing()
        return run

    def _trigger_processing(self):
        cron = self.env.ref("chatter_ai_assistant.ir_cron_process_chatter_ai_runs", raise_if_not_found=False)
        if cron:
            cron._trigger()
        return True

    @api.model
    def _cron_process_pending_runs(self):
        stale_seconds = self._config()["worker_stale_seconds"]
        deadline = fields.Datetime.now() - timedelta(seconds=stale_seconds)
        stale_runs = self.search([("state", "=", "running"), ("started_at", "!=", False), ("started_at", "<", deadline)])
        for run in stale_runs:
            run._handle_failure(_("The external OpenClaw worker timed out or stopped unexpectedly."))
        return True

    def _build_execution_message(self):
        self.ensure_one()
        if self.task_type == "document":
            return self._build_document_execution_message()
        return self._build_chat_execution_message()

    def _build_chat_execution_message(self):
        self.ensure_one()
        context_rows = json.loads(self.context_payload or "[]")
        lines = [
            "You are the AI assistant inside Odoo. Reply in concise Chinese unless the user clearly asks otherwise.",
            "Return JSON only.",
            'The final JSON format must be {"reply_text":"...","summary":"...","generated_files":[{"path":"...","name":"...","mimetype":"..."}]}.',
            "If you create files, write them into output_dir and list them in generated_files.",
            "",
            "conversation_type: %s" % self.conversation_type,
            "record_model: %s" % self.model,
            "record_id: %s" % self.res_id,
            "record_name: %s" % (self.record_display_name or ""),
            "channel_id: %s" % (self.channel_id.id if self.channel_id else ""),
            "trigger_user: %s" % (self.requesting_partner_id.display_name or ""),
            "output_dir: %s" % (self.temp_directory or ""),
            "",
            "message_text:",
            self.prompt_text or "",
            "",
            "context_messages:",
            json.dumps(context_rows, ensure_ascii=False, indent=2),
            "",
            "attachments:",
            json.dumps(self._attachment_prompt_payload(), ensure_ascii=False, indent=2),
        ]
        return "\n".join(lines)

    def _selected_agent_id(self):
        self.ensure_one()
        config = self._config()
        if self.task_type == "document":
            return config["tds_agent_id"] or config["general_agent_id"]
        return config["general_agent_id"]

    def _build_document_execution_message(self):
        self.ensure_one()
        context_rows = json.loads(self.context_payload or "[]")
        record = self.env[self.model].sudo().browse(self.res_id).exists()
        runtime_payload = {}
        if record and hasattr(record, "_chatter_ai_runtime_payload"):
            runtime_payload = record._chatter_ai_runtime_payload(
                attachments=self.source_attachment_ids,
                message_text=self.prompt_text,
            )
        lines = [
            "You are the multimodal document assistant inside Odoo.",
            "Use OpenClaw tools to inspect the provided files or webpage when needed.",
            "Reply in concise Chinese unless the user clearly asks otherwise.",
            "Return JSON only.",
            "When dictionary_index or dictionary_candidates are provided, treat them as the only reliable parameter dictionary context for naming normalization.",
            "Only claim that a field was normalized to an existing dictionary item when you can match it confidently against dictionary_index or dictionary_candidates.",
            "If a requested field cannot be confirmed against the provided dictionary context, keep the current naming or place it into unmatched and explain that it remains unconfirmed.",
            "Always prefer main_field_rules for thickness, color, adhesive type, base material, thickness_std, and other declared main fields before using params/spec_values.",
        ]
        include_raw_text_hint = True
        include_runtime_context = True
        include_current_draft = True
        if self.document_action == "summarize":
            lines.append(
                'The final JSON format must be {"reply_text":"...","summary":"...","generated_files":[]}.'
            )
        elif self.document_action == "identify_handbook":
            include_raw_text_hint = False
            include_runtime_context = False
            include_current_draft = False
            lines.extend(
                [
                    'The final JSON format must be {"reply_text":"...","summary":"...","handbook_review":{"family_name":"...","document_outline":"...","confidence":0.0,"series_groups":[{"series_display_name":"...","series_long_name":"...","page_range":"...","series_description":"...","series_features":"...","series_applications":"...","confidence":0.0,"evidence":"...","models":[{"material_code":"...","display_name":"...","page_range":"...","confidence":0.0,"evidence":"...","param_total":0,"reused_param_count":0,"pending_param_count":0,"issue_count":0,"main_field_hits":0}]}]},"generated_files":[]}.',
                    "Treat the source as a handbook, sample book, or product catalog instead of a single TDS.",
                    "First identify the document outline and page roles, then identify series groups, then list model candidates under each series.",
                    "Prefer grouped sub-series inside a page over broad page-level family titles when both are visible.",
                    "Do not try to produce full parameter extraction for the whole handbook in this step.",
                    "Read the attached PDF directly. Use only compact business rules; ignore detailed current draft and raw text unless absolutely necessary.",
                    "Do not return draft_payload for identify_handbook.",
                ]
            )
        elif self.document_action == "extract_source":
            lines.extend(
                [
                    'The final JSON format must be {"reply_text":"...","summary":"...","raw_text":"...","generated_files":[{"path":"...","name":"...","mimetype":"..."}]}.',
                    "Extract readable text from the provided source.",
                    "Export as many useful images from the TDS/PDF as possible into generated_files.",
                    "Prefer extracting product photos, structure diagrams, charts, methods, tables, and page images when they carry business value. When in doubt, prefer exporting the image instead of skipping it.",
                    "Do not generate draft_payload for extract_source.",
                ]
            )
        else:
            lines.extend(
                [
                    'The final JSON format must be {"reply_text":"...","summary":"...","draft_payload":{"series":[],"items":[],"params":[],"category_params":[],"spec_values":[],"unmatched":[]},"generated_files":[]}.',
                    "draft_payload must stay compatible with the Odoo source document buckets.",
                ]
            )
        lines.extend(
            [
                "",
                "task_type: document",
                "document_action: %s" % (self.document_action or "parse"),
                "source_kind: %s" % (self.source_kind or "mixed"),
                "record_model: %s" % self.model,
                "record_id: %s" % self.res_id,
                "record_name: %s" % (self.record_display_name or ""),
                "trigger_user: %s" % (self.requesting_partner_id.display_name or ""),
                "source_url: %s" % (runtime_payload.get("source_url") or ""),
                "message_text:",
                self.prompt_text or "",
                "",
                "context_messages:",
                json.dumps(context_rows, ensure_ascii=False, indent=2),
            ]
        )
        if include_raw_text_hint:
            lines.extend(
                [
                    "",
                    "raw_text_hint:",
                    runtime_payload.get("raw_text") or "",
                ]
            )
        if include_runtime_context:
            lines.extend(
                [
                    "",
                    "record_runtime_context:",
                    json.dumps(runtime_payload.get("copilot_context") or {}, ensure_ascii=False, indent=2),
                ]
            )
        if include_current_draft:
            lines.extend(
                [
                    "",
                    "current_draft_payload:",
                    json.dumps(runtime_payload.get("current_draft_payload") or {}, ensure_ascii=False, indent=2),
                ]
            )
        lines.extend(
            [
                "",
                "attachments:",
                json.dumps(self._attachment_prompt_payload(), ensure_ascii=False, indent=2),
            ]
        )
        return "\n".join(lines)

    def _session_id(self):
        self.ensure_one()
        if self.conversation_type == "private_chat" and self.channel_id:
            user_key = self.requesting_user_id.id or self.requesting_partner_id.id or 0
            return "discuss-channel-%s-%s" % (self.channel_id.id, user_key)
        model_key = (self.model or "record").replace(".", "_")
        user_key = self.requesting_user_id.id or self.requesting_partner_id.id or 0
        return "chatter-%s-%s-%s" % (model_key, self.res_id, user_key)

    def _attachment_prompt_payload(self):
        self.ensure_one()
        payload = []
        for attachment in self.source_attachment_ids:
            filename = os.path.basename(attachment.name or ("attachment-%s" % attachment.id))
            payload.append(
                {
                    "name": attachment.name,
                    "mimetype": attachment.mimetype,
                    "path": os.path.join(self.temp_directory or "", filename),
                }
            )
        return payload

    def _prepare_temp_directory(self):
        self.ensure_one()
        tempdir = self.temp_directory
        if not tempdir or not os.path.isdir(tempdir):
            tempdir = tempfile.mkdtemp(prefix="odoo-chatter-ai-%s-" % self.run_id)
        for attachment in self.source_attachment_ids:
            filename = os.path.basename(attachment.name or ("attachment-%s" % attachment.id))
            target_path = os.path.join(tempdir, filename)
            with open(target_path, "wb") as handle:
                handle.write(base64.b64decode(attachment.datas or b""))
        self.write({"temp_directory": tempdir, "trace_path": os.path.join(tempdir, "openclaw.log")})
        return tempdir

    def _mark_worker_started(self):
        self.ensure_one()
        if self.state == "queued":
            self.write({"state": "running", "started_at": fields.Datetime.now()})
        if self.conversation_type == "record":
            self._update_status_message("running")
            record = self.env[self.model].sudo().browse(self.res_id).exists()
            if record and hasattr(record, "_chatter_ai_mark_run_started"):
                record._chatter_ai_mark_run_started(self)

    def _worker_payload(self):
        self.ensure_one()
        config = self._config()
        tempdir = self._prepare_temp_directory()
        message = self._build_execution_message()
        self._mark_worker_started()
        return {
            "run_db_id": self.id,
            "run_id": self.run_id,
            "conversation_type": self.conversation_type,
            "task_type": self.task_type,
            "document_action": self.document_action or False,
            "source_kind": self.source_kind or False,
            "channel_id": self.channel_id.id if self.channel_id else False,
            "record_model": self.model,
            "record_id": self.res_id,
            "session_id": self._session_id(),
            "message": message,
            "working_directory": tempdir,
            "trace_path": self.trace_path,
            "cli_command": config["cli_command"],
            "node_bin_path": config["node_bin_path"],
            "agent_id": self._selected_agent_id(),
            "thinking": config["thinking"],
            "timeout_seconds": config["timeout_seconds"],
        }

    @api.model
    def claim_next_run_for_worker(self, token):
        if not self._worker_secret_is_valid(token):
            raise AccessError(_("Invalid worker token."))
        self.flush_model(["state"])
        self.env.cr.execute(
            """
            SELECT id
              FROM chatter_ai_run
             WHERE state = 'queued'
             ORDER BY id ASC
             FOR UPDATE SKIP LOCKED
             LIMIT 1
            """
        )
        row = self.env.cr.fetchone()
        if not row:
            return False
        run = self.browse(row[0]).sudo()
        try:
            return run._worker_payload()
        except Exception as exc:  # pylint: disable=broad-except
            _logger.exception("Failed to prepare worker payload for AI run %s", run.run_id)
            if run.state not in ("failed", "succeeded", "cancelled"):
                run._handle_failure(_("Failed to prepare OpenClaw payload: %s") % exc)
            return False

    @api.model
    def complete_run_from_worker(self, token, run_id, payload):
        if not self._worker_secret_is_valid(token):
            raise AccessError(_("Invalid worker token."))
        run = self.sudo().search([("run_id", "=", run_id)], limit=1)
        if not run or run.state not in ("running", "queued"):
            return False
        run._handle_success(payload or {})
        return True

    @api.model
    def fail_run_from_worker(self, token, run_id, error_message):
        if not self._worker_secret_is_valid(token):
            raise AccessError(_("Invalid worker token."))
        run = self.sudo().search([("run_id", "=", run_id)], limit=1)
        if not run or run.state in ("succeeded", "failed", "cancelled"):
            return False
        run._handle_failure(error_message)
        return True

    def _post_final_message(self, body, attachments=False):
        self.ensure_one()
        target = self.env[self.model].sudo().browse(self.res_id).exists()
        if self.trigger_message_id and self.trigger_message_id.model and self.trigger_message_id.res_id:
            trigger_target = self.env[self.trigger_message_id.model].sudo().browse(self.trigger_message_id.res_id).exists()
            if trigger_target:
                target = trigger_target
        if not target:
            return False
        bot_partner = self._odoobot_partner()
        values = {
            "body": body,
            "attachment_ids": (attachments or self.env["ir.attachment"]).ids,
            "author_id": bot_partner.id if bot_partner else False,
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_note" if self.conversation_type == "record" else "mail.mt_comment",
        }
        return target.message_post(**values)

    def _handle_success(self, payload):
        self.ensure_one()
        attachments = self._import_generated_attachments(payload.get("generated_files") or [])
        record = self.env[self.model].sudo().browse(self.res_id).exists()
        if self.task_type == "document" and record and hasattr(record, "_chatter_ai_apply_result"):
            applied = record._chatter_ai_apply_result(self.document_action, payload)
            if applied:
                payload = dict(payload, **applied)
        if (
            self.task_type == "document"
            and self.document_action == "extract_source"
            and record
            and attachments
            and hasattr(record, "_chatter_ai_sync_preview_image")
        ):
            record._chatter_ai_sync_preview_image(attachments)
        reply_text = payload.get("reply_text") or payload.get("text") or _("The AI assistant finished without text output.")
        summary = payload.get("summary") or reply_text[:500]
        self.write(
            {
                "state": "succeeded",
                "finished_at": fields.Datetime.now(),
                "reply_text": reply_text,
                "result_summary": summary,
                "generated_attachment_ids": [(6, 0, attachments.ids)],
                "error_message": False,
            }
        )
        if record and hasattr(record, "_chatter_ai_mark_run_success"):
            record._chatter_ai_mark_run_success(self, payload)
        self._post_final_message(reply_text, attachments)
        self._clear_status_message()

    def _handle_failure(self, error):
        self.ensure_one()
        message = self._format_user_error_message(str(error))
        self.write(
            {
                "state": "failed",
                "finished_at": fields.Datetime.now(),
                "error_message": message,
            }
        )
        record = self.env[self.model].sudo().browse(self.res_id).exists()
        if record and hasattr(record, "_chatter_ai_mark_run_failure"):
            record._chatter_ai_mark_run_failure(self, message)
        self._post_final_message(self._status_body("failed", message))
        self._clear_status_message()

    def _format_user_error_message(self, raw_message):
        self.ensure_one()
        message = raw_message or _("OpenClaw execution failed.")
        if "WebAssembly.instantiate(): Out of memory" in message and "undici" in message:
            return _(
                "OpenClaw CLI failed while initializing its network runtime inside the current process."
                " The chatter trigger worked, but the local Node runtime still needs isolation."
            )
        return message

    def _update_status_message(self, state, extra_text=False):
        self.ensure_one()
        if self.status_message_id:
            self.status_message_id.sudo().write({"body": self._status_body(state, extra_text=extra_text)})

    def _clear_status_message(self):
        self.ensure_one()
        if self.status_message_id:
            status_message = self.status_message_id.sudo()
            self.sudo().write({"status_message_id": False})
            status_message.unlink()

    @api.model
    def frontend_status_snapshot(self):
        recent_runs = self.search(
            [("requesting_user_id", "=", self.env.user.id)],
            order="id desc",
            limit=10,
        )
        pending_runs = recent_runs.filtered(lambda run: run.state in ("queued", "running") and run.conversation_type == "record")
        latest_finished = recent_runs.filtered(lambda run: run.finished_at and run.conversation_type == "record")[:1]
        latest_finished_action = False
        latest_finished_model = False
        latest_finished_res_id = False
        latest_finished_run_id = False
        handbook_review_id = False
        redirect_url = False
        if latest_finished:
            latest_finished_action = latest_finished.document_action or latest_finished.task_type or False
            latest_finished_model = latest_finished.model
            latest_finished_res_id = latest_finished.res_id
            latest_finished_run_id = latest_finished.run_id
            if latest_finished.model == "diecut.catalog.source.document":
                record = self.env[latest_finished.model].sudo().browse(latest_finished.res_id).exists()
                if record and getattr(record, "handbook_review_id", False):
                    handbook_review_id = record.handbook_review_id.id
                    if latest_finished_action == "identify_handbook":
                        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "").rstrip("/")
                        redirect_url = (
                            "%s/odoo/action-594/%s/diecut.catalog.source.document/%s#handbook-review"
                            % (base_url, record.id, record.id)
                        )
        return {
            "has_pending": bool(pending_runs),
            "pending_run_ids": pending_runs.mapped("run_id"),
            "latest_finished_at": fields.Datetime.to_string(latest_finished.finished_at) if latest_finished else False,
            "latest_finished_state": latest_finished.state if latest_finished else False,
            "latest_finished_action": latest_finished_action,
            "latest_finished_model": latest_finished_model,
            "latest_finished_res_id": latest_finished_res_id,
            "latest_finished_run_id": latest_finished_run_id,
            "handbook_review_id": handbook_review_id,
            "redirect_url": redirect_url,
        }

    def _import_generated_attachments(self, generated_files):
        self.ensure_one()
        attachments = self.env["ir.attachment"]
        for item in generated_files:
            path = (item or {}).get("path")
            if not path or not os.path.exists(path):
                continue
            with open(path, "rb") as handle:
                raw = handle.read()
            attachment = self.env["ir.attachment"].sudo().create(
                {
                    "name": (item or {}).get("name") or os.path.basename(path),
                    "datas": base64.b64encode(raw),
                    "mimetype": (item or {}).get("mimetype") or "application/octet-stream",
                    "res_model": self.model,
                    "res_id": self.res_id,
                    "type": "binary",
                }
            )
            attachments |= attachment
        return attachments
