# -*- coding: utf-8 -*-

import re
from html import escape

from odoo import api, fields, models
from odoo.exceptions import UserError


class DiecutKbArticle(models.Model):
    _name = "diecut.kb.article"
    _description = "知识库文章"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _parent_name = "parent_id"
    _parent_store = True
    _order = "parent_path, sequence, id desc"

    name = fields.Char(string="标题", required=True, index=True, tracking=True)
    active = fields.Boolean(string="启用", default=True)
    sequence = fields.Integer(string="排序", default=10)

    parent_id = fields.Many2one(
        "diecut.kb.article",
        string="上级文章",
        index=True,
        ondelete="set null",
    )
    child_ids = fields.One2many("diecut.kb.article", "parent_id", string="子文章")
    parent_path = fields.Char(index=True)

    category_id = fields.Many2one(
        "diecut.kb.category",
        string="知识分类",
        required=True,
        index=True,
        tracking=True,
        ondelete="restrict",
    )
    category_code = fields.Char(
        string="分类编码",
        related="category_id.code",
        store=True,
        readonly=True,
    )

    state = fields.Selection(
        [
            ("draft", "草稿"),
            ("review", "评审中"),
            ("published", "已发布"),
            ("archived", "已归档"),
        ],
        string="状态",
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )

    summary = fields.Text(string="摘要", help="一句话概括文章核心要点，会同步到 Dify 作为元数据。")
    content_html = fields.Html(string="正文", sanitize=True)
    content_text = fields.Text(
        string="正文纯文本",
        compute="_compute_content_text",
        store=True,
        help="去除 HTML 标签后的纯文本，用于 Dify 同步与全文检索。",
    )
    content_length = fields.Integer(string="正文字数", compute="_compute_content_text", store=True)

    keywords = fields.Char(string="关键词", help="逗号分隔，用于 Dify 检索过滤。")
    source_url = fields.Char(string="来源 URL")
    author_name = fields.Char(string="作者/来源")
    publish_date = fields.Date(string="发布日期")

    related_brand_ids = fields.Many2many(
        "diecut.brand",
        "diecut_kb_article_brand_rel",
        "article_id",
        "brand_id",
        string="关联品牌",
    )
    related_categ_ids = fields.Many2many(
        "product.category",
        "diecut_kb_article_categ_rel",
        "article_id",
        "categ_id",
        string="关联材料分类",
    )
    related_item_ids = fields.Many2many(
        "diecut.catalog.item",
        "diecut_kb_article_item_rel",
        "article_id",
        "item_id",
        string="关联型号",
    )
    related_article_ids = fields.Many2many(
        "diecut.kb.article",
        "diecut_kb_article_related_rel",
        "article_id",
        "related_article_id",
        string="相关文章",
    )

    attachment_ids = fields.One2many(
        "diecut.kb.attachment",
        "article_id",
        string="附件",
    )
    attachment_count = fields.Integer(string="附件数", compute="_compute_attachment_count")

    is_favorite = fields.Boolean(string="收藏", default=False)
    last_edited_uid = fields.Many2one("res.users", string="最后编辑人", readonly=True)
    last_edited_at = fields.Datetime(string="最后编辑时间", readonly=True)

    sync_status = fields.Selection(
        [
            ("pending", "待同步"),
            ("synced", "已同步"),
            ("failed", "同步失败"),
            ("skipped", "已跳过"),
        ],
        string="同步状态",
        default="pending",
        index=True,
        tracking=True,
    )
    dify_dataset_id = fields.Char(string="Dify 知识库ID", readonly=True)
    dify_document_id = fields.Char(string="Dify 文档ID", readonly=True)
    last_sync_at = fields.Datetime(string="最近同步时间", readonly=True)
    sync_error = fields.Text(string="同步错误", readonly=True)
    sync_log_ids = fields.One2many(
        "diecut.kb.sync.log",
        "article_id",
        string="同步日志",
    )

    compile_source = fields.Selection(
        [
            ("manual", "手工编写"),
            ("catalog_item", "产品编译"),
            ("comparison", "对比分析"),
            ("source_document", "资料编译"),
            ("faq", "FAQ 编译"),
            ("qa_compile", "问答编译"),
            ("ai_answer", "AI 对话沉淀"),
            ("lint_note", "治理补充"),
            ("brand_overview", "品牌综述"),
        ],
        string="内容来源",
        default="manual",
        index=True,
    )
    compile_source_item_id = fields.Many2one(
        "diecut.catalog.item",
        string="编译源产品",
        index=True,
        ondelete="set null",
    )
    compile_source_document_id = fields.Many2one(
        "diecut.catalog.source.document",
        string="编译源资料",
        index=True,
        ondelete="set null",
    )
    compile_source_brand_id = fields.Many2one(
        "diecut.brand",
        string="编译源品牌",
        index=True,
        ondelete="set null",
    )
    compiled_at = fields.Datetime(string="编译时间", readonly=True, copy=False)
    compiled_hash = fields.Char(string="编译哈希", readonly=True, copy=False)
    compile_confidence = fields.Float(string="编译置信度", readonly=True, copy=False)
    compile_risk_level = fields.Selection(
        [
            ("low", "低风险"),
            ("medium", "中风险"),
            ("high", "高风险"),
        ],
        string="编译风险",
        default="medium",
        readonly=True,
        copy=False,
    )
    source_page_refs = fields.Char(string="来源页码", readonly=True, copy=False)
    source_file_name = fields.Char(string="来源文件", readonly=True, copy=False)
    xref_enriched_at = fields.Datetime(string="交叉引用更新时间", readonly=True, copy=False)
    last_linted_at = fields.Datetime(string="最近治理检查时间", readonly=True, copy=False)
    lint_issue_count = fields.Integer(string="治理问题数", readonly=True, copy=False)

    @api.depends("attachment_ids")
    def _compute_attachment_count(self):
        for record in self:
            record.attachment_count = len(record.attachment_ids)

    @api.depends("content_html")
    def _compute_content_text(self):
        for record in self:
            text = self._html_to_text(record.content_html or "")
            record.content_text = text
            record.content_length = len(text)

    @staticmethod
    def _html_to_text(html_value):
        if not html_value:
            return ""
        text = re.sub(r"<br\s*/?>", "\n", html_value, flags=re.I)
        text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
        text = re.sub(r"</li\s*>", "\n", text, flags=re.I)
        text = re.sub(r"<li[^>]*>", "- ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;", " ", text, flags=re.I)
        text = re.sub(r"&amp;", "&", text, flags=re.I)
        text = re.sub(r"&lt;", "<", text, flags=re.I)
        text = re.sub(r"&gt;", ">", text, flags=re.I)
        text = re.sub(r"&quot;", '"', text, flags=re.I)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("last_edited_uid", self.env.user.id)
            vals.setdefault("last_edited_at", fields.Datetime.now())
        records = super().create(vals_list)
        records._auto_enrich_if_needed(vals_list)
        return records

    def write(self, vals):
        meaningful_fields = {
            "name",
            "summary",
            "content_html",
            "category_id",
            "state",
            "keywords",
            "source_url",
            "author_name",
            "publish_date",
            "related_brand_ids",
            "related_categ_ids",
            "related_item_ids",
            "related_article_ids",
            "compile_source_brand_id",
        }
        is_meaningful = bool(meaningful_fields & set(vals.keys()))
        if is_meaningful:
            vals.setdefault("last_edited_uid", self.env.user.id)
            vals.setdefault("last_edited_at", fields.Datetime.now())
        result = super().write(vals)
        if is_meaningful and not vals.get("state") == "archived":
            to_pending = self.filtered(lambda r: r.sync_status == "synced")
            if to_pending:
                super(DiecutKbArticle, to_pending).write({"sync_status": "pending"})
        if not self.env.context.get("skip_auto_enrich"):
            self._auto_enrich_if_needed([vals] * len(self))
        return result

    def action_submit_review(self):
        for record in self:
            if record.state != "draft":
                raise UserError("只有草稿状态的文章可以提交评审。")
        self.write({"state": "review"})
        return True

    def action_publish(self):
        for record in self:
            if record.state not in ("draft", "review"):
                raise UserError("只有草稿或评审中的文章可以发布。")
            if not record.content_html or record.content_length < 10:
                raise UserError(f"文章 [{record.name}] 正文为空或过短，无法发布。")
        self._run_enrichment()
        self.write({
            "state": "published",
            "publish_date": fields.Date.context_today(self),
            "sync_status": "pending",
        })
        return True

    def action_archive_article(self):
        self.write({
            "state": "archived",
            "active": False,
            "sync_status": "pending",
        })
        return True

    def action_back_to_draft(self):
        self.write({"state": "draft"})
        return True

    def action_fill_content_from_attachments(self):
        """把附件中已解析的 markdown/纯文本拼接成 HTML 写入 content_html。"""
        for record in self:
            attachments = record.attachment_ids.filtered(lambda a: a.parse_state == "parsed")
            if not attachments:
                raise UserError(f"文章 [{record.name}] 没有已解析的附件，请先解析附件。")

            sections = []
            for att in attachments.sorted(key=lambda a: (a.sequence, a.id)):
                body_md = att.parsed_markdown or att.parsed_text or ""
                if not body_md.strip():
                    continue
                body_html = self._markdown_to_simple_html(body_md)
                sections.append(
                    f"<h2>{escape(att.name or att.file_name or '未命名附件')}</h2>\n{body_html}"
                )

            if not sections:
                raise UserError("所选附件均无可用的提取文本。")

            new_block = "\n\n".join(sections)
            existing = record.content_html or ""
            record.content_html = (existing + "\n\n" + new_block).strip() if existing else new_block

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "已填充正文",
                "message": "附件提取文本已追加到正文末尾，请检查后再发布。",
                "type": "success",
                "sticky": False,
            },
        }

    @staticmethod
    def _markdown_to_simple_html(md_text: str) -> str:
        lines = (md_text or "").splitlines()
        out = []
        in_list = False
        for line in lines:
            stripped = line.rstrip()
            if not stripped:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                out.append("")
                continue
            if stripped.startswith("### "):
                if in_list:
                    out.append("</ul>")
                    in_list = False
                out.append(f"<h3>{escape(stripped[4:].strip())}</h3>")
            elif stripped.startswith("## "):
                if in_list:
                    out.append("</ul>")
                    in_list = False
                out.append(f"<h3>{escape(stripped[3:].strip())}</h3>")
            elif stripped.startswith("# "):
                if in_list:
                    out.append("</ul>")
                    in_list = False
                out.append(f"<h2>{escape(stripped[2:].strip())}</h2>")
            elif stripped.startswith(("- ", "* ", "• ")):
                if not in_list:
                    out.append("<ul>")
                    in_list = True
                out.append(f"<li>{escape(stripped[2:].strip())}</li>")
            else:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                out.append(f"<p>{escape(stripped)}</p>")
        if in_list:
            out.append("</ul>")
        return "\n".join(filter(None, out))

    def action_view_attachments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "附件",
            "res_model": "diecut.kb.attachment",
            "view_mode": "list,form",
            "domain": [("article_id", "=", self.id)],
            "context": {"default_article_id": self.id},
        }

    def action_request_sync(self):
        from ..services.dify_sync import DifyKnowledgeSync

        sync_service = DifyKnowledgeSync(self.env)
        ok_count, fail_count = 0, 0
        for record in self:
            result = sync_service.sync_article(record)
            if result.get("ok"):
                ok_count += 1
            else:
                fail_count += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "知识库同步",
                "message": f"成功 {ok_count} 篇 / 失败 {fail_count} 篇",
                "type": "success" if fail_count == 0 else "warning",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def action_mark_pending(self):
        self.write({"sync_status": "pending"})
        return True

    def action_recompile(self):
        self.ensure_one()
        from ..services.kb_compiler import KbCompiler

        if self.compile_source_document_id:
            result = KbCompiler(self.env).compile_from_source_document(self.compile_source_document_id, force=True)
        elif self.compile_source_item_id:
            result = KbCompiler(self.env).compile_from_item(self.compile_source_item_id, force=True)
        else:
            raise UserError("当前文章没有关联编译源资料或编译源产品，无法重新编译。")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "AI 编译",
                "message": "重新编译成功" if result.get("ok") else result.get("error", "重新编译失败"),
                "type": "success" if result.get("ok") else "warning",
                "sticky": not result.get("ok"),
            },
        }

    def action_run_lint(self):
        from ..services.kb_linter import KbLinter

        total = 0
        for article in self:
            total += KbLinter(self.env).lint_article(article).get("total", 0)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "知识治理检查",
                "message": f"已完成检查，发现 {total} 个问题。",
                "type": "success" if total == 0 else "warning",
                "sticky": False,
            },
        }

    @api.model
    def cron_sync_pending_articles(self):
        from ..services.dify_sync import DifyKnowledgeSync

        return DifyKnowledgeSync(self.env).sync_pending()

    @api.model
    def cron_lint_published_articles(self):
        from ..services.kb_linter import KbLinter

        limit = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "diecut_knowledge.lint_batch_limit", default="20"
            )
            or 20
        )
        return KbLinter(self.env).lint_pending(limit=limit)

    def action_open_ai_advisor(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "diecut_ai_advisor",
            "params": {
                "model": self._name,
                "record_id": self.id,
                "record_name": self.name or "",
            },
        }

    def action_view_sync_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "同步日志",
            "res_model": "diecut.kb.sync.log",
            "view_mode": "list,form",
            "domain": [("article_id", "=", self.id)],
            "context": {"default_article_id": self.id},
        }

    def _auto_enrich_if_needed(self, vals_list):
        if self.env.context.get("skip_auto_enrich"):
            return
        trigger_fields = {
            "content_html",
            "summary",
            "name",
            "related_brand_ids",
            "related_categ_ids",
            "related_item_ids",
        }
        should_run = any(trigger_fields & set(vals.keys()) for vals in vals_list)
        if should_run:
            self._run_enrichment()

    def _run_enrichment(self):
        from ..services.kb_enricher import KbEnricher

        enricher = KbEnricher(self.env)
        for record in self.filtered(lambda rec: rec.state != "archived" and rec.content_html):
            enricher.enrich_article(record)
