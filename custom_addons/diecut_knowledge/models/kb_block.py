# -*- coding: utf-8 -*-

import json
import html

from odoo import fields, models


class DiecutKbBlock(models.Model):
    _name = "diecut.kb.block"
    _description = "知识库内容块"
    _order = "article_id, sequence, id"

    article_id = fields.Many2one(
        "diecut.kb.article",
        string="所属页面",
        required=True,
        index=True,
        ondelete="cascade",
    )
    parent_block_id = fields.Many2one(
        "diecut.kb.block",
        string="父块",
        index=True,
        ondelete="cascade",
    )
    child_block_ids = fields.One2many("diecut.kb.block", "parent_block_id", string="子块")
    sequence = fields.Integer(string="排序", default=10, index=True)
    depth = fields.Integer(string="层级", default=0)
    block_type = fields.Selection(
        [
            ("paragraph", "正文"),
            ("heading1", "一级标题"),
            ("heading2", "二级标题"),
            ("bulleted_list", "无序列表"),
            ("numbered_list", "有序列表"),
            ("todo", "待办"),
            ("quote", "引用"),
            ("code", "代码"),
            ("divider", "分割线"),
        ],
        string="块类型",
        default="paragraph",
        required=True,
        index=True,
    )
    content_json = fields.Text(string="块内容JSON", default='{"text": ""}')
    content_html = fields.Html(string="块正文", sanitize=True)
    collapsed = fields.Boolean(string="折叠", default=False)
    is_archived = fields.Boolean(string="归档", default=False)

    def to_client_dict(self):
        self.ensure_one()
        payload = {"text": ""}
        if self.content_json:
            try:
                payload = json.loads(self.content_json)
            except Exception:
                payload = {"text": self.content_json}
        text = payload.get("text", "") if isinstance(payload, dict) else ""
        content_html = self.content_html
        if not content_html:
            content_html = (html.escape(text or "")).replace("\n", "<br>")

        return {
            "id": self.id,
            "article_id": self.article_id.id,
            "parent_block_id": self.parent_block_id.id if self.parent_block_id else False,
            "sequence": self.sequence,
            "depth": self.depth,
            "block_type": self.block_type,
            "content": payload,
            "content_html": content_html,
            "collapsed": bool(self.collapsed),
            "is_archived": bool(self.is_archived),
        }
