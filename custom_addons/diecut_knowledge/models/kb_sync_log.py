# -*- coding: utf-8 -*-

from odoo import fields, models


class DiecutKbSyncLog(models.Model):
    _name = "diecut.kb.sync.log"
    _description = "知识库同步日志"
    _order = "create_date desc, id desc"
    _rec_name = "summary"

    article_id = fields.Many2one(
        "diecut.kb.article",
        string="文章",
        index=True,
        ondelete="cascade",
    )
    direction = fields.Selection(
        [
            ("push", "Odoo → Dify"),
            ("pull", "Dify → Odoo"),
        ],
        string="方向",
        required=True,
        default="push",
    )
    action = fields.Selection(
        [
            ("create", "创建"),
            ("update", "更新"),
            ("delete", "删除"),
            ("retry", "重试"),
        ],
        string="动作",
        required=True,
    )
    state = fields.Selection(
        [
            ("success", "成功"),
            ("failed", "失败"),
            ("partial", "部分成功"),
        ],
        string="结果",
        required=True,
    )
    summary = fields.Char(string="摘要", required=True)

    request_payload = fields.Text(string="请求内容")
    response_payload = fields.Text(string="响应内容")
    error_message = fields.Text(string="错误信息")

    dify_dataset_id = fields.Char(string="Dify 知识库ID")
    dify_document_id = fields.Char(string="Dify 文档ID")
    duration_ms = fields.Integer(string="耗时(ms)")
