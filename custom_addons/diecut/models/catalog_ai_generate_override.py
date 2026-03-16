# -*- coding: utf-8 -*-

from odoo import models
from odoo.exceptions import UserError


class DiecutCatalogSourceDocumentGenerateOverride(models.Model):
    _inherit = "diecut.catalog.source.document"

    def action_generate_draft(self):
        for record in self:
            if not record.raw_text:
                record.action_extract_source()
            if not record.raw_text:
                raise UserError("未提取到原文，无法生成草稿。")

            if not hasattr(record, "_queue_for_worker") or not hasattr(record, "_run_openclaw_worker_job"):
                raise UserError("Worker 未启用，无法执行 AI/TDS 生成。")

            record._queue_for_worker()
            refreshed = record._run_openclaw_worker_job()
            refreshed.write(
                {
                    "skill_profile": (refreshed.skill_profile or "generic_tds_v1+diecut_domain_v1").strip(),
                    "brand_skill_name": refreshed._resolve_brand_skill_name(),
                }
            )
        return True
