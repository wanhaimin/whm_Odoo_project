# -*- coding: utf-8 -*-

import base64

from odoo.tests.common import SavepointCase


class TestDocumentChatRouting(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.run_model = cls.env["chatter.ai.run"]
        cls.document = cls.env["diecut.catalog.source.document"].create(
            {
                "name": "Test Source",
                "source_type": "pdf",
                "raw_text": "sample source text",
            }
        )

    def test_natural_language_summary_creates_document_run(self):
        self.env["mail.message"].create(
            {
                "model": "diecut.catalog.source.document",
                "res_id": self.document.id,
                "message_type": "comment",
                "body": "<p>帮我总结这份 PDF</p>",
                "author_id": self.env.user.partner_id.id,
            }
        )
        run = self.run_model.search(
            [("model", "=", "diecut.catalog.source.document"), ("res_id", "=", self.document.id)],
            order="id desc",
            limit=1,
        )
        self.assertTrue(run)
        self.assertEqual(run.task_type, "document")
        self.assertEqual(run.document_action, "summarize")

    def test_document_run_uses_record_attachment_when_message_has_none(self):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "spec.pdf",
                "datas": base64.b64encode(b"%PDF-1.4 test"),
                "mimetype": "application/pdf",
                "res_model": "diecut.catalog.source.document",
                "res_id": self.document.id,
                "type": "binary",
            }
        )
        self.document.primary_attachment_id = attachment
        self.env["mail.message"].create(
            {
                "model": "diecut.catalog.source.document",
                "res_id": self.document.id,
                "message_type": "comment",
                "body": "<p>帮我把这份文档解析一下</p>",
                "author_id": self.env.user.partner_id.id,
            }
        )
        run = self.run_model.search(
            [
                ("model", "=", "diecut.catalog.source.document"),
                ("res_id", "=", self.document.id),
                ("document_action", "=", "parse"),
            ],
            order="id desc",
            limit=1,
        )
        self.assertTrue(run)
        self.assertIn(attachment, run.source_attachment_ids)
        self.assertEqual(run.source_kind, "pdf")

    def test_document_worker_payload_prefers_tds_agent(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "chatter_ai_assistant.openclaw_general_agent_id",
            "odoo-diecut-dev",
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "chatter_ai_assistant.openclaw_tds_agent_id",
            "odoo-diecut-tds",
        )
        self.env["mail.message"].create(
            {
                "model": "diecut.catalog.source.document",
                "res_id": self.document.id,
                "message_type": "comment",
                "body": "<p>甯垜鎶婅繖浠芥枃妗ｈВ鏋愪竴涓?/p>",
                "author_id": self.env.user.partner_id.id,
            }
        )
        run = self.run_model.search(
            [
                ("model", "=", "diecut.catalog.source.document"),
                ("res_id", "=", self.document.id),
                ("document_action", "=", "parse"),
            ],
            order="id desc",
            limit=1,
        )
        self.assertTrue(run)
        payload = run._worker_payload()
        self.assertEqual(payload["agent_id"], "odoo-diecut-tds")
