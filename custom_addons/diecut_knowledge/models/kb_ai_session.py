# -*- coding: utf-8 -*-

import json

from odoo import api, fields, models


class DiecutKbAiSession(models.Model):
    _name = "diecut.kb.ai.session"
    _description = "AI 顾问会话"
    _order = "last_message_at desc, write_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(string="会话名称", required=True, default="AI 顾问会话")
    mode = fields.Selection(
        [
            ("ai", "AI 顾问"),
            ("wiki", "Wiki 顾问"),
            ("selection", "AI 选型助手"),
            ("source", "AI 资料助手"),
            ("qa", "AI 辅助答复"),
            ("global", "知识 AI"),
        ],
        string="模式",
        required=True,
        default="ai",
        index=True,
    )
    res_model = fields.Char(string="业务模型", index=True)
    res_id = fields.Integer(string="业务记录 ID", index=True)
    record_name = fields.Char(string="业务记录名称")
    dify_conversation_id = fields.Char(string="会话 ID", index=True)
    model_profile_id = fields.Many2one("diecut.llm.model.profile", string="当前模型", ondelete="set null")
    last_message_at = fields.Datetime(string="最后消息时间", index=True)
    active = fields.Boolean(string="启用", default=True, index=True)
    message_ids = fields.One2many("diecut.kb.ai.message", "session_id", string="消息")
    message_count = fields.Integer(string="消息数", compute="_compute_message_count")
    create_uid = fields.Many2one("res.users", string="创建人", default=lambda self: self.env.user, index=True)

    @api.depends("message_ids")
    def _compute_message_count(self):
        grouped = self.env["diecut.kb.ai.message"].read_group(
            [("session_id", "in", self.ids)],
            ["session_id"],
            ["session_id"],
        )
        counts = {row["session_id"][0]: row["session_id_count"] for row in grouped}
        for record in self:
            record.message_count = counts.get(record.id, 0)

    @api.model
    def open_session(self, mode="ai", res_model="", res_id=0, record_name="", model_profile_id=False):
        mode = mode or "ai"
        res_id = int(res_id or 0)
        domain = [
            ("active", "=", True),
            ("mode", "=", mode),
            ("res_model", "=", res_model or ""),
            ("res_id", "=", res_id),
            ("create_uid", "=", self.env.user.id),
        ]
        session = self.search(domain, limit=1)
        if not session:
            label = record_name or self._mode_label(mode)
            session = self.create(
                {
                    "name": "%s - %s" % (self._mode_label(mode), label),
                    "mode": mode,
                    "res_model": res_model or "",
                    "res_id": res_id,
                    "record_name": record_name or "",
                    "model_profile_id": model_profile_id or False,
                    "last_message_at": fields.Datetime.now(),
                }
            )
            if record_name:
                session.add_message("system", "当前: %s" % record_name)
        elif record_name and session.record_name != record_name:
            session.record_name = record_name
        if model_profile_id and session.model_profile_id.id != int(model_profile_id):
            session.model_profile_id = int(model_profile_id)
        return session

    def clear_messages(self):
        for session in self:
            session.message_ids.unlink()
            session.write({"dify_conversation_id": False, "last_message_at": fields.Datetime.now()})
            if session.record_name:
                session.add_message("system", "当前: %s" % session.record_name)
        return True

    def add_message(self, role, content, **kwargs):
        self.ensure_one()
        vals = {
            "session_id": self.id,
            "role": role,
            "content": content or "",
            "question": kwargs.get("question") or "",
            "source_layer": kwargs.get("source_layer") or False,
            "compile_job_id": kwargs.get("compile_job_id") or False,
            "openclaw_run_id": kwargs.get("openclaw_run_id") or False,
            "async_state": kwargs.get("async_state") or False,
            "can_save": bool(kwargs.get("can_save")),
            "saved_article_id": kwargs.get("saved_article_id") or False,
            "model_profile_id": kwargs.get("model_profile_id") or self.model_profile_id.id or False,
        }
        source_refs = kwargs.get("source_refs")
        if source_refs is not None:
            vals["source_refs_json"] = json.dumps(source_refs, ensure_ascii=False)
        articles = kwargs.get("articles")
        if articles is not None:
            vals["articles_json"] = json.dumps(articles, ensure_ascii=False)
        citations = kwargs.get("citations")
        if citations is not None:
            vals["citations_json"] = json.dumps(citations, ensure_ascii=False)
        message = self.env["diecut.kb.ai.message"].create(vals)
        self.last_message_at = fields.Datetime.now()
        return message

    def to_client_payload(self, limit=80):
        self.ensure_one()
        messages = self.message_ids.sorted(key=lambda message: (message.create_date, message.id))
        if limit:
            messages = messages[-limit:]
        return {
            "session_id": self.id,
            "mode": self.mode,
            "conversation_id": self.dify_conversation_id or "",
            "model_profile_id": self.model_profile_id.id or False,
            "messages": [message.to_client_dict() for message in messages],
        }

    def _mode_label(self, mode):
        return dict(self._fields["mode"].selection).get(mode, "AI 顾问")


class DiecutKbAiMessage(models.Model):
    _name = "diecut.kb.ai.message"
    _description = "AI 顾问消息"
    _order = "create_date asc, id asc"

    session_id = fields.Many2one("diecut.kb.ai.session", string="会话", required=True, index=True, ondelete="cascade")
    role = fields.Selection(
        [
            ("system", "系统"),
            ("user", "用户"),
            ("assistant", "AI"),
        ],
        string="角色",
        required=True,
        index=True,
    )
    content = fields.Text(string="内容")
    question = fields.Text(string="对应问题")
    source_layer = fields.Selection(
        [
            ("wiki", "已编译 Wiki"),
            ("raw_source", "原始资料"),
            ("catalog", "材料目录"),
            ("mixed", "混合来源"),
            ("none", "未命中"),
        ],
        string="来源层级",
        index=True,
    )
    source_refs_json = fields.Text(string="来源 JSON")
    articles_json = fields.Text(string="Wiki 文章 JSON")
    citations_json = fields.Text(string="引用 JSON")
    compile_job_id = fields.Many2one("diecut.kb.compile.job", string="待编译任务", index=True, ondelete="set null")
    openclaw_run_id = fields.Many2one("chatter.ai.run", string="OpenClaw 任务", index=True, ondelete="set null")
    async_state = fields.Selection(
        [
            ("queued", "排队中"),
            ("running", "处理中"),
            ("done", "已完成"),
            ("failed", "失败"),
        ],
        string="异步状态",
        index=True,
    )
    can_save = fields.Boolean(string="可保存为知识", default=False)
    saved_article_id = fields.Many2one("diecut.kb.article", string="已保存文章", index=True, ondelete="set null")
    liked_article_id = fields.Many2one("diecut.kb.article", string="点赞沉淀文章", index=True, ondelete="set null")
    model_profile_id = fields.Many2one("diecut.llm.model.profile", string="使用模型", index=True, ondelete="set null")

    def to_client_dict(self):
        self.ensure_one()
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content or "",
            "question": self.question or "",
            "sourceLayer": self.source_layer or "",
            "sourceRefs": self._json_value(self.source_refs_json, []),
            "articles": self._json_value(self.articles_json, []),
            "citations": self._json_value(self.citations_json, []),
            "compileJobId": self.compile_job_id.id or False,
            "openclawRunId": self.openclaw_run_id.id or False,
            "asyncState": self.async_state or "",
            "canSave": bool(self.can_save),
            "savedArticleId": self.saved_article_id.id or False,
            "likedArticleId": self.liked_article_id.id or False,
            "modelProfileId": self.model_profile_id.id or False,
            "modelProfileName": self.model_profile_id.name or "",
        }

    def _json_value(self, value, default):
        if not value:
            return default
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default
