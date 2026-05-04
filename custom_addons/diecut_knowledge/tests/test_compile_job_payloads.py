# -*- coding: utf-8 -*-
import json
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.diecut_knowledge.services.kb_compiler import KbCompiler


class TestCompileJobPayloads(TransactionCase):
    def test_failed_job_persists_llm_payload_and_validation(self):
        source = self.env["diecut.catalog.source.document"].create(
            {
                "name": "Incremental source",
                "source_type": "manual",
                "raw_text": "source text",
            }
        )
        job = self.env["diecut.kb.compile.job"].create(
            {
                "job_type": "wiki_incremental",
                "incremental_source_document_ids": [(6, 0, source.ids)],
            }
        )

        failed_result = {
            "ok": False,
            "error": "LLM did not return patches",
            "llm_payload_json": '{"raw_answer": "plain article"}',
            "validation_message": "No patches parsed",
            "risk_level": "high",
        }
        with patch(
            "odoo.addons.diecut_knowledge.services.kb_compiler.KbCompiler.compile_incremental_wiki_job",
            return_value=failed_result,
        ), patch.object(self.env.cr, "commit", lambda: None):
            job._process_jobs()

        self.assertEqual(job.state, "failed")
        self.assertEqual(job.llm_payload_json, failed_result["llm_payload_json"])
        self.assertEqual(job.validation_message, failed_result["validation_message"])
        self.assertEqual(job.risk_level, "high")

    def test_openclaw_queued_result_waits_for_worker_run(self):
        source = self.env["diecut.catalog.source.document"].create(
            {
                "name": "OpenClaw incremental source",
                "source_type": "manual",
                "raw_text": "source text",
            }
        )
        run = self.env["chatter.ai.run"].create(
            {
                "name": "OpenClaw test run",
                "run_id": "openclaw-test-run",
                "conversation_type": "private_chat",
                "task_type": "chat",
                "model": "diecut.kb.ai.session",
                "res_id": 0,
                "trigger_message_id": self.env["mail.message"].create(
                    {
                        "model": "diecut.kb.ai.session",
                        "res_id": 0,
                        "body": "<p>trigger</p>",
                        "message_type": "comment",
                    }
                ).id,
                "requesting_partner_id": self.env.user.partner_id.id,
            }
        )
        job = self.env["diecut.kb.compile.job"].create(
            {
                "job_type": "wiki_incremental",
                "incremental_source_document_ids": [(6, 0, source.ids)],
            }
        )

        queued_result = {
            "ok": False,
            "action": "queued",
            "openclaw_run_id": run.id,
            "error": False,
            "validation_message": "OpenClaw 已提交，等待 worker 完成。",
        }
        with patch(
            "odoo.addons.diecut_knowledge.services.kb_compiler.KbCompiler.compile_incremental_wiki_job",
            return_value=queued_result,
        ), patch.object(self.env.cr, "commit", lambda: None):
            job._process_jobs()

        self.assertEqual(job.state, "waiting_llm")
        self.assertEqual(job.openclaw_run_id, run)
        self.assertFalse(job.error_message)

    def test_openclaw_completed_run_enters_patch_parser(self):
        source = self.env["diecut.catalog.source.document"].create(
            {
                "name": "OpenClaw completed source",
                "source_type": "manual",
                "raw_text": "source text",
            }
        )
        article = self.env["diecut.kb.article"].create(
            {
                "name": "Patched Wiki",
                "content_md": "patched",
                "state": "review",
            }
        )
        run = self.env["chatter.ai.run"].create(
            {
                "name": "OpenClaw completed run",
                "run_id": "openclaw-completed-run",
                "state": "succeeded",
                "conversation_type": "private_chat",
                "task_type": "chat",
                "model": "diecut.kb.ai.session",
                "res_id": 0,
                "trigger_message_id": self.env["mail.message"].create(
                    {
                        "model": "diecut.kb.ai.session",
                        "res_id": 0,
                        "body": "<p>trigger</p>",
                        "message_type": "comment",
                    }
                ).id,
                "requesting_partner_id": self.env.user.partner_id.id,
                "reply_text": "<p>{\"patches\": []}</p>",
            }
        )
        job = self.env["diecut.kb.compile.job"].create(
            {
                "job_type": "wiki_incremental",
                "state": "waiting_llm",
                "openclaw_run_id": run.id,
                "incremental_source_document_ids": [(6, 0, source.ids)],
            }
        )

        parsed_result = {
            "ok": True,
            "article_id": article.id,
            "article_ids": article.ids,
            "llm_payload_json": '{"patches": []}',
            "validation_message": "Incremental Wiki Patch Plan JSON 已归一化并应用。",
            "risk_level": "low",
        }
        with patch(
            "odoo.addons.diecut_knowledge.services.kb_compiler.KbCompiler.apply_incremental_wiki_answer",
            return_value=parsed_result,
        ) as parser, patch.object(self.env.cr, "commit", lambda: None):
            result = job._process_openclaw_results()

        self.assertEqual(result["processed"], 1)
        parser.assert_called_once()
        self.assertEqual(parser.call_args.args[0], job)
        self.assertIn('{"patches": []}', parser.call_args.args[1])
        self.assertEqual(job.state, "done")
        self.assertEqual(job.result_article_id, article)

    def test_high_risk_successful_incremental_patch_marks_source_compiled(self):
        source = self.env["diecut.catalog.source.document"].create(
            {
                "name": "High risk but applied source",
                "source_type": "manual",
                "raw_text": "source text",
            }
        )
        job = self.env["diecut.kb.compile.job"].create(
            {
                "job_type": "wiki_incremental",
                "incremental_source_document_ids": [(6, 0, source.ids)],
            }
        )
        raw_answer = json.dumps(
            {
                "risk_level": "high",
                "review_required": True,
                "patches": [
                    {
                        "operation": "create_article",
                        "title": "High Risk Applied Wiki",
                        "summary": "Applied even when high risk.",
                        "content_md": "# High Risk Applied Wiki\n\nBody.",
                        "source_document_ids": source.ids,
                        "risk_level": "high",
                        "review_required": True,
                        "risk_notes": ["Needs attention but should not block compiled state."],
                    }
                ],
            },
            ensure_ascii=False,
        )

        with patch("odoo.addons.diecut_knowledge.services.kb_enricher.KbEnricher.enrich_article"), patch(
            "odoo.addons.diecut_knowledge.services.kb_linter.KbLinter.lint_article"
        ), patch.object(KbCompiler, "_connect_article_to_wiki_graph", return_value=None), patch.object(
            KbCompiler, "_apply_wiki_patch_citations", return_value=0
        ):
            result = KbCompiler(self.env).apply_incremental_wiki_answer(job, raw_answer)

        self.assertTrue(result["ok"])
        self.assertEqual(result["risk_level"], "high")
        self.assertEqual(source.wiki_compile_state, "compiled")
        self.assertFalse(source.wiki_compile_error)
