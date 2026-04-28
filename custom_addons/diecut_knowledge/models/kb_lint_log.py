# -*- coding: utf-8 -*-

from odoo import fields, models


class DiecutKbLintLog(models.Model):
    _name = "diecut.kb.lint.log"
    _description = "知识治理检查日志"
    _order = "create_date desc, id desc"
    _rec_name = "summary"

    article_id = fields.Many2one(
        "diecut.kb.article",
        string="文章",
        index=True,
        ondelete="cascade",
    )
    source_item_id = fields.Many2one(
        "diecut.catalog.item",
        string="源产品",
        index=True,
        ondelete="set null",
    )
    severity = fields.Selection(
        [
            ("info", "提示"),
            ("warning", "警告"),
            ("error", "错误"),
        ],
        string="严重级别",
        required=True,
        default="info",
        index=True,
    )
    issue_type = fields.Selection(
        [
            ("stale_compile", "编译内容过期"),
            ("missing_reference", "缺少关联"),
            ("sync_failed", "同步失败"),
            ("content_short", "内容过短"),
            ("duplicate_title", "标题重复"),
            ("weak_source_binding", "源数据映射偏弱"),
        ],
        string="问题类型",
        required=True,
        index=True,
    )
    state = fields.Selection(
        [
            ("open", "待处理"),
            ("resolved", "已处理"),
            ("dismissed", "已忽略"),
        ],
        string="状态",
        required=True,
        default="open",
        index=True,
    )
    summary = fields.Char(string="摘要", required=True)
    details = fields.Text(string="详细说明")
    suggestion = fields.Text(string="建议动作")
    detected_at = fields.Datetime(string="发现时间", default=fields.Datetime.now, required=True)

