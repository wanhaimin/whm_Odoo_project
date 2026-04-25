# -*- coding: utf-8 -*-

import base64

from markupsafe import Markup
from odoo.tests.common import TransactionCase


class TestDocumentChatRouting(TransactionCase):
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

    def _create_run_from_body(self, body):
        user = self.env.ref("base.user_admin")
        message = self.env["mail.message"].create(
            {
                "model": "diecut.catalog.source.document",
                "res_id": self.document.id,
                "message_type": "comment",
                "body": body,
                "author_id": user.partner_id.id,
            }
        )
        return self.run_model.create_run_from_message(message)

    def test_natural_language_summary_creates_document_run(self):
        run = self._create_run_from_body("<p>帮我总结这份 PDF</p>")
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
        run = self._create_run_from_body("<p>帮我把这份文档解析一下</p>")
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
        run = self._create_run_from_body("<p>解析这份文档并生成草稿</p>")
        self.assertTrue(run)
        payload = run._worker_payload()
        self.assertEqual(payload["agent_id"], "odoo-diecut-tds")

    def test_status_body_renders_safe_html_and_escapes_error_text(self):
        body = self.run_model._status_body("failed", "<b>x</b><script>alert(1)</script>")
        self.assertIsInstance(body, Markup)
        self.assertIn("<p><strong>OdooBot</strong>：失败</p>", str(body))
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", str(body))
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", str(body))
        self.assertNotIn("<script>", str(body))

    def test_format_user_error_message_normalizes_auth_failures(self):
        trigger = self.env["mail.message"].create(
            {
                "model": "diecut.catalog.source.document",
                "res_id": self.document.id,
                "message_type": "notification",
                "body": "<p>trigger</p>",
                "author_id": self.env.user.partner_id.id,
            }
        )
        run = self.run_model.create(
            {
                "run_id": "test-auth-normalization",
                "model": "diecut.catalog.source.document",
                "res_id": self.document.id,
                "trigger_message_id": trigger.id,
                "requesting_partner_id": self.env.user.partner_id.id,
                "requesting_user_id": self.env.user.id,
            }
        )
        message = run._format_user_error_message("oauth token refresh failed: please try signing in again")
        self.assertEqual(
            message,
            "OpenClaw/Codex 登录凭据或模型权限被拒绝，请在宿主机重新登录 OpenClaw/Codex，确认当前账号可使用所选模型后再试。",
        )

    def test_format_user_error_message_normalizes_forbidden(self):
        trigger = self.env["mail.message"].create(
            {
                "model": "diecut.catalog.source.document",
                "res_id": self.document.id,
                "message_type": "notification",
                "body": "<p>trigger</p>",
                "author_id": self.env.user.partner_id.id,
            }
        )
        run = self.run_model.create(
            {
                "run_id": "test-forbidden-normalization",
                "model": "diecut.catalog.source.document",
                "res_id": self.document.id,
                "trigger_message_id": trigger.id,
                "requesting_partner_id": self.env.user.partner_id.id,
                "requesting_user_id": self.env.user.id,
            }
        )
        message = run._format_user_error_message("Forbidden")
        self.assertEqual(
            message,
            "OpenClaw/Codex 登录凭据或模型权限被拒绝，请在宿主机重新登录 OpenClaw/Codex，确认当前账号可使用所选模型后再试。",
        )
