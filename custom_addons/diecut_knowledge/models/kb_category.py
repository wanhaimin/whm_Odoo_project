# -*- coding: utf-8 -*-

from odoo import api, fields, models


class DiecutKbCategory(models.Model):
    _name = "diecut.kb.category"
    _description = "知识库分类"
    _order = "sequence, id"

    name = fields.Char(string="分类名称", required=True, translate=True)
    code = fields.Char(string="分类编码", required=True, index=True)
    sequence = fields.Integer(string="排序", default=10)
    description = fields.Text(string="说明")
    color = fields.Integer(string="颜色")
    icon = fields.Char(string="图标")

    dify_dataset_id = fields.Char(
        string="Dify 知识库ID",
        help="对应 Dify 中该分类绑定的 Dataset ID。同步时所有该分类下的文章会推送到这个 Dataset。",
    )
    dify_dataset_name = fields.Char(string="Dify 知识库名称")

    article_count = fields.Integer(string="文章数", compute="_compute_article_count")

    _code_uniq = models.Constraint(
        "UNIQUE(code)",
        "分类编码必须唯一。",
    )

    @api.depends()
    def _compute_article_count(self):
        grouped = self.env["diecut.kb.article"].read_group(
            [("category_id", "in", self.ids), ("active", "=", True)],
            ["category_id"],
            ["category_id"],
        )
        count_map = {
            group["category_id"][0]: group["category_id_count"]
            for group in grouped
            if group.get("category_id")
        }
        for record in self:
            record.article_count = count_map.get(record.id, 0)

    def action_view_articles(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "diecut.kb.article",
            "view_mode": "list,form,kanban",
            "domain": [("category_id", "=", self.id)],
            "context": {"default_category_id": self.id},
        }
