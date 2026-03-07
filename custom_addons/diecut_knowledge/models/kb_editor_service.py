# -*- coding: utf-8 -*-

from odoo import api, models


class DiecutKbEditorService(models.AbstractModel):
    _name = "diecut.kb.editor.service"
    _description = "知识库编辑服务"

    def _empty(self):
        return self

    @api.model
    def load_tree(self):
        return self.env["diecut.kb.article"].kb_get_workspace_tree()

    @api.model
    def load_page(self, article_id):
        return self.env["diecut.kb.article"].kb_load_page_payload(article_id)

    @api.model
    def save_ops(self, article_id, ops):
        return self.env["diecut.kb.article"].kb_apply_block_ops(article_id, ops)

    @api.model
    def create_page(self, name, parent_id=False):
        return self.env["diecut.kb.article"].kb_create_page(name, parent_id)

    @api.model
    def archive_page(self, article_id):
        return self.env["diecut.kb.article"].kb_archive_page(article_id)
