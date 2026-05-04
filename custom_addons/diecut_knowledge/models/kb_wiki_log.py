# -*- coding: utf-8 -*-

from odoo import fields, models


class DiecutKbWikiLog(models.Model):
    _name = "diecut.kb.wiki.log"
    _description = "Wiki 演化日志"
    _order = "create_date desc, id desc"

    event_type = fields.Selection(
        [
            ("ingest", "资料入库"),
            ("compile", "Wiki 编译"),
            ("link", "图谱关联"),
            ("query", "查询沉淀"),
            ("lint", "治理检查"),
            ("publish", "发布"),
            ("sync", "同步"),
        ],
        string="事件类型",
        required=True,
        default="compile",
        index=True,
    )
    name = fields.Char(string="标题", required=True)
    article_id = fields.Many2one("diecut.kb.article", string="Wiki 页面", index=True, ondelete="set null")
    source_document_id = fields.Many2one(
        "diecut.catalog.source.document",
        string="来源资料",
        index=True,
        ondelete="set null",
    )
    link_id = fields.Many2one("diecut.kb.wiki.link", string="图谱关联", index=True, ondelete="set null")
    summary = fields.Text(string="摘要")
    details = fields.Text(string="详情")
    payload_json = fields.Text(string="JSON 载荷")
