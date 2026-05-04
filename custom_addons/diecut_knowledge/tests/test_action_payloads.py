# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestActionPayloads(TransactionCase):
    def test_raw_inbox_result_action_includes_client_views(self):
        action = self.env["diecut.catalog.source.document"]._raw_inbox_result_action([1])

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["view_mode"], "list,form")
        self.assertEqual(action["views"], [(False, "list"), (False, "form")])
