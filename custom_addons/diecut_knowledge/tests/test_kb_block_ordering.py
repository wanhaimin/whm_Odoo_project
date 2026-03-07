# -*- coding: utf-8 -*-

import json

from odoo.tests.common import TransactionCase


class TestKbBlockOrdering(TransactionCase):
    def test_save_ops_updates_sequence(self):
        article = self.env["diecut.kb.article"].create({"name": "排序测试"})
        blocks = article.block_ids
        first = blocks[0]
        second = self.env["diecut.kb.block"].create(
            {
                "article_id": article.id,
                "sequence": 20,
                "block_type": "paragraph",
                "content_json": json.dumps({"text": "B"}, ensure_ascii=False),
            }
        )

        result = self.env["diecut.kb.editor.service"].save_ops(
            article.id,
            [
                {"type": "update", "id": first.id, "sequence": 30},
                {"type": "update", "id": second.id, "sequence": 10},
            ],
        )
        self.assertTrue(result["ok"])
        ordered = self.env["diecut.kb.block"].search([("article_id", "=", article.id)], order="sequence, id")
        self.assertEqual(ordered[0].id, second.id)
