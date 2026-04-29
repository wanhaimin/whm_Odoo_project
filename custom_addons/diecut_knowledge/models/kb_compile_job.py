# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DiecutKbCompileJob(models.Model):
    _name = "diecut.kb.compile.job"
    _description = "知识编译队列"
    _order = "priority desc, create_date asc, id asc"
    _rec_name = "display_name"

    display_name = fields.Char(string="描述", compute="_compute_display_name", store=False)

    item_id = fields.Many2one("diecut.catalog.item", string="产品", index=True)
    source_document_id = fields.Many2one(
        "diecut.catalog.source.document", string="源资料", index=True
    )

    job_type = fields.Selection(
        [
            ("catalog_item", "产品编译"),
            ("source_document", "资料编译"),
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
            ("done", "已完成"),
            ("failed", "编译失败"),
        ],
        string="状态",
        default="pending",
        index=True,
        tracking=True,
    )
    priority = fields.Integer(string="优先级", default=0, help="数值越高越优先处理")

    result_article_id = fields.Many2one(
        "diecut.kb.article", string="生成文章", readonly=True
    )
    error_message = fields.Text(string="错误信息", readonly=True)

    create_uid = fields.Many2one(
        "res.users", string="创建人", default=lambda self: self.env.user
    )

    @api.depends("item_id", "source_document_id", "job_type", "create_date")
    def _compute_display_name(self):
        for record in self:
            parts = []
            if record.item_id:
                parts.append("[%s] %s" % (record.item_id.code or "", record.item_id.name or ""))
            elif record.source_document_id:
                parts.append(record.source_document_id.name or "")
            elif record.job_type == "comparison":
                parts.append("对比分析(%d个)" % len(record.comparison_item_ids))
            parts.append(dict(record._fields["job_type"].selection).get(record.job_type, ""))
            record.display_name = " / ".join(filter(None, parts)) or ("Job #%d" % record.id)

    def action_run_now(self):
        """手动立即执行选中的 job"""
        self._process_jobs()
        return True

    def action_cancel(self):
        """取消排队中的 job"""
        self.filtered(lambda j: j.state == "pending").write({"state": "done", "error_message": "已取消"})
        return True

    def action_retry(self):
        """重试失败的 job"""
        self.filtered(lambda j: j.state == "failed").write({"state": "pending", "error_message": False})
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
        jobs = self.search(
            [("state", "=", "pending")],
            limit=limit,
            order=self._order,
        )
        if not jobs:
            return {"processed": 0}
        jobs._process_jobs()
        return {"processed": len(jobs)}

    def _process_jobs(self):
        from ..services.kb_compiler import KbCompiler

        compiler = KbCompiler(self.env)
        for job in self:
            if job.state != "pending":
                continue
            job.state = "processing"
            self.env.cr.commit()

            try:
                if job.job_type == "catalog_item" and job.item_id:
                    result = compiler.compile_from_item(job.item_id, force=True)
                elif job.job_type == "source_document" and job.source_document_id:
                    result = compiler.compile_from_source_document(
                        job.source_document_id, force=True
                    )
                elif job.job_type == "comparison" and len(job.comparison_item_ids) >= 2:
                    result = compiler.compile_comparison(job.comparison_item_ids)
                else:
                    job.write({"state": "failed", "error_message": "编译参数不完整"})
                    self.env.cr.commit()
                    continue

                if result.get("ok"):
                    article_id = result.get("article_id")
                    job.write({
                        "state": "done",
                        "result_article_id": article_id or False,
                        "error_message": False,
                    })
                else:
                    job.write({
                        "state": "failed",
                        "error_message": (result.get("error") or "编译失败")[:2000],
                    })
            except Exception as exc:
                _logger.exception("Compile job %s failed", job.id)
                job.write({
                    "state": "failed",
                    "error_message": str(exc)[:2000],
                })
            self.env.cr.commit()
