# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase


class TestKbEditorService(TransactionCase):
    def test_load_tree_and_page_payload(self):
        article = self.env["diecut.kb.article"].create({"name": "测试页面"})

        tree = self.env["diecut.kb.editor.service"].load_tree()
        self.assertTrue(any(item["id"] == article.id for item in tree))

        payload = self.env["diecut.kb.editor.service"].load_page(article.id)
        self.assertEqual(payload["article"]["id"], article.id)
        self.assertTrue(payload["blocks"])
