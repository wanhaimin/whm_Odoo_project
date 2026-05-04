# -*- coding: utf-8 -*-

import html
import logging
import re

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DiecutKbCompileJob(models.Model):
    _name = "diecut.kb.compile.job"
    _description = "知识编译队列"
    _order = "priority desc, create_date asc, id asc"
    _rec_name = "display_name"

    display_name = fields.Char(string="描述", compute="_compute_display_name", store=False)

    item_id = fields.Many2one("diecut.catalog.item", string="产品", index=True)
    source_document_id = fields.Many2one("diecut.catalog.source.document", string="源资料", index=True)
    incremental_source_document_ids = fields.Many2many(
        "diecut.catalog.source.document",
        "diecut_kb_compile_job_source_rel",
        "job_id",
        "source_document_id",
        string="增量资料",
    )

    job_type = fields.Selection(
        [
            ("catalog_item", "产品编译"),
            ("source_document", "资料编译"),
            ("wiki_incremental", "Wiki 增量编译"),
            ("comparison", "对比分析"),
        ],
        string="编译类型",
        required=True,
    )
    comparison_item_ids = fields.Many2many(
        "diecut.catalog.item",
        "diecut_kb_compile_job_comparison_rel",
        "job_id",
        "item_id",
        string="对比产品",
    )

    state = fields.Selection(
        [
            ("pending", "排队中"),
            ("processing", "编译中"),
            ("waiting_llm", "等待 OpenClaw"),
            ("done", "已应用 patch"),
            ("failed", "输出解析失败"),
        ],
        string="状态",
        default="pending",
        index=True,
    )
    status_label = fields.Char(string="编译状态", compute="_compute_status_label")
    priority = fields.Integer(string="优先级", default=0, help="数值越高越优先处理")
    trigger_question = fields.Text(string="触发问题", readonly=True)
    source_layer = fields.Selection(
        [
            ("wiki", "已编译 Wiki"),
            ("raw_source", "原始资料"),
            ("catalog", "材料目录"),
            ("mixed", "混合来源"),
        ],
        string="来源层级",
        readonly=True,
    )
    source_reason = fields.Text(string="命中说明", readonly=True)
    input_summary = fields.Text(string="输入摘要", readonly=True)
    llm_payload_json = fields.Text(string="LLM 输出 JSON", readonly=True)
    validation_message = fields.Text(string="Schema 校验结果", readonly=True)
    risk_level = fields.Selection(
        [
            ("low", "低风险"),
            ("medium", "中风险"),
            ("high", "高风险"),
        ],
        string="风险等级",
        readonly=True,
    )

    result_article_id = fields.Many2one("diecut.kb.article", string="生成文章", readonly=True)
    result_article_ids = fields.Many2many(
        "diecut.kb.article",
        "diecut_kb_compile_job_result_article_rel",
        "job_id",
        "article_id",
        string="生成文章列表",
        readonly=True,
    )
    target_article_ids = fields.Many2many(
        "diecut.kb.article",
        "diecut_kb_compile_job_target_article_rel",
        "job_id",
        "article_id",
        string="候选 Wiki 目标",
        readonly=True,
    )
    compile_group_key = fields.Char(string="增量分组键", size=240, index=True, readonly=True)
    source_hash_snapshot = fields.Text(string="资料 Hash 快照", readonly=True)
    model_profile_id = fields.Many2one("diecut.llm.model.profile", string="使用模型", ondelete="set null")
    openclaw_run_id = fields.Many2one("chatter.ai.run", string="OpenClaw 任务", readonly=True, ondelete="set null", index=True)
    error_message = fields.Text(string="错误信息", readonly=True)

    create_uid = fields.Many2one("res.users", string="创建人", default=lambda self: self.env.user)

    @api.depends("item_id", "source_document_id", "incremental_source_document_ids", "job_type", "create_date")
    def _compute_display_name(self):
        for record in self:
            parts = []
            if record.item_id:
                parts.append("[%s] %s" % (record.item_id.code or "", record.item_id.name or ""))
            elif record.source_document_id:
                parts.append(record.source_document_id.name or "")
            elif record.job_type == "wiki_incremental":
                parts.append(record.compile_group_key or ("%s sources" % len(record.incremental_source_document_ids)))
            elif record.job_type == "comparison":
                parts.append("对比分析(%d个)" % len(record.comparison_item_ids))
            parts.append(dict(record._fields["job_type"].selection).get(record.job_type, ""))
            record.display_name = " / ".join(filter(None, parts)) or ("Job #%d" % record.id)

    @api.depends("state", "openclaw_run_id.state")
    def _compute_status_label(self):
        labels = dict(self._fields["state"].selection)
        for record in self:
            if record.state == "waiting_llm":
                if record.openclaw_run_id.state == "running":
                    record.status_label = "OpenClaw 运行中"
                elif record.openclaw_run_id.state in ("failed", "cancelled"):
                    record.status_label = "输出解析失败"
                else:
                    record.status_label = "等待 OpenClaw"
            else:
                record.status_label = labels.get(record.state, record.state or "")

    def action_run_now(self):
        """Run selected jobs immediately."""
        self._process_jobs()
        return True

    def action_cancel(self):
        """Cancel pending jobs."""
        self.filtered(lambda job: job.state in ("pending", "waiting_llm")).write({"state": "done", "error_message": "已取消"})
        return True

    def action_retry(self):
        """Retry failed jobs."""
        self.filtered(lambda job: job.state == "failed").write(
            {"state": "pending", "error_message": False, "openclaw_run_id": False}
        )
        return True

    @api.model
    def cron_process_compile_queue(self, limit=None):
        if limit is None:
            limit = int(
                self.env["ir.config_parameter"].sudo().get_param(
                    "diecut_knowledge.compile_batch_limit", default="5"
                )
                or 5
            )
        jobs = self.search([("state", "=", "pending")], limit=limit, order=self._order)
        if not jobs:
            return {"processed": 0}
        jobs._process_jobs()
        return {"processed": len(jobs)}

    @api.model
    def cron_process_openclaw_results(self, limit=None):
        if limit is None:
            limit = int(
                self.env["ir.config_parameter"].sudo().get_param(
                    "diecut_knowledge.openclaw_result_batch_limit", default="10"
                )
                or 10
            )
        jobs = self.search([("state", "=", "waiting_llm")], limit=limit, order=self._order)
        if not jobs:
            return {"processed": 0}
        return jobs._process_openclaw_results()

    def _process_jobs(self):
        from ..services.kb_compiler import KbCompiler

        for job in self:
            if job.state != "pending":
                continue
            if not job.model_profile_id:
                job.model_profile_id = self.env["diecut.llm.model.profile"].sudo().get_default_profile("wiki_compile")
            compiler = KbCompiler(self.env(context=dict(self.env.context, llm_model_profile_id=job.model_profile_id.id)))
            job.state = "processing"
            self.env.cr.commit()

            try:
                if job.job_type == "catalog_item" and job.item_id:
                    result = compiler.compile_from_item(job.item_id, force=True)
                elif job.job_type == "source_document" and job.source_document_id:
                    result = compiler.compile_from_source_document(job.source_document_id, force=True)
                elif job.job_type == "wiki_incremental" and job.incremental_source_document_ids:
                    result = compiler.compile_incremental_wiki_job(job)
                elif job.job_type == "comparison" and len(job.comparison_item_ids) >= 2:
                    result = compiler.compile_comparison(job.comparison_item_ids)
                else:
                    job.write({"state": "failed", "error_message": "编译参数不完整"})
                    self.env.cr.commit()
                    continue

                if result.get("ok"):
                    job._write_compile_success(result)
                elif result.get("action") == "queued":
                    job.write(
                        {
                            "state": "waiting_llm",
                            "openclaw_run_id": result.get("openclaw_run_id") or False,
                            "error_message": False,
                            "risk_level": result.get("risk_level") or job.risk_level,
                            "llm_payload_json": result.get("llm_payload_json") or job.llm_payload_json,
                            "validation_message": result.get("validation_message") or "OpenClaw 已提交，等待 worker 完成。",
                        }
                    )
                else:
                    job._write_compile_failure(result)
            except Exception as exc:
                _logger.exception("Compile job %s failed", job.id)
                job.write(
                    {
                        "state": "failed",
                        "error_message": str(exc)[:2000],
                    }
                )
            self.env.cr.commit()

    def _process_openclaw_results(self):
        from ..services.kb_compiler import KbCompiler

        processed = 0
        for job in self:
            if job.state != "waiting_llm":
                continue
            run = job.openclaw_run_id.sudo().exists()
            if not run:
                job._write_compile_failure(
                    {
                        "error": "OpenClaw 任务不存在，无法读取编译结果",
                        "validation_message": "OpenClaw run missing before result parsing.",
                        "risk_level": "high",
                    }
                )
                processed += 1
                self.env.cr.commit()
                continue
            if run.state in ("queued", "running"):
                job.write(
                    {
                        "validation_message": "OpenClaw 仍在处理：%s" % dict(run._fields["state"].selection).get(run.state, run.state),
                    }
                )
                self.env.cr.commit()
                continue
            if run.state in ("failed", "cancelled"):
                job._write_compile_failure(
                    {
                        "error": run.error_message or "OpenClaw 执行失败",
                        "validation_message": "OpenClaw worker finished with state: %s" % run.state,
                        "risk_level": "high",
                    }
                )
                processed += 1
                self.env.cr.commit()
                continue

            raw_answer = self._openclaw_run_answer_text(run)
            compiler = KbCompiler(self.env(context=dict(self.env.context, llm_model_profile_id=job.model_profile_id.id)))
            try:
                result = compiler.apply_incremental_wiki_answer(job, raw_answer)
                if result.get("ok"):
                    job._write_compile_success(result)
                else:
                    job._write_compile_failure(result)
            except Exception as exc:
                _logger.exception("Compile job %s failed while parsing OpenClaw result", job.id)
                job._write_compile_failure(
                    {
                        "error": str(exc)[:2000],
                        "validation_message": "OpenClaw output parsing raised an exception.",
                        "risk_level": "high",
                    }
                )
            processed += 1
            self.env.cr.commit()
        return {"processed": processed}

    def _write_compile_success(self, result):
        for job in self:
            article_ids = result.get("article_ids") or []
            article_id = result.get("article_id") or (article_ids[0] if article_ids else False)
            job.write(
                {
                    "state": "done",
                    "result_article_id": article_id or False,
                    "result_article_ids": [(6, 0, article_ids or ([article_id] if article_id else []))],
                    "error_message": False,
                    "risk_level": result.get("risk_level") or job.risk_level,
                    "llm_payload_json": result.get("llm_payload_json") or job.llm_payload_json,
                    "validation_message": result.get("validation_message") or job.validation_message,
                }
            )

    def _write_compile_failure(self, result):
        for job in self:
            job.write(
                {
                    "state": "failed",
                    "error_message": (result.get("error") or "编译失败")[:2000],
                    "risk_level": result.get("risk_level") or job.risk_level,
                    "llm_payload_json": result.get("llm_payload_json") or job.llm_payload_json,
                    "validation_message": result.get("validation_message") or job.validation_message,
                }
            )

    @staticmethod
    def _openclaw_run_answer_text(run):
        answer = run.reply_text or run.result_summary or ""
        return html.unescape(re.sub(r"<[^>]+>", "\n", answer)).strip()
