# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys

from odoo import api, fields, models
from odoo.exceptions import UserError


class DiecutCatalogSourceDocumentWorkerRuntime(models.Model):
    _inherit = "diecut.catalog.source.document"

    import_status = fields.Selection(
        selection_add=[
            ("queued", "已排队"),
            ("processing", "处理中"),
            ("parsed", "已解析"),
            ("failed", "解析失败"),
        ],
        ondelete={
            "queued": "set default",
            "processing": "set default",
            "parsed": "set default",
            "failed": "set default",
        },
    )

    worker_run_id = fields.Char(string="执行批次")
    worker_id = fields.Char(string="执行器")
    queued_at = fields.Datetime(string="排队时间")
    processing_started_at = fields.Datetime(string="开始处理时间")
    parsed_at = fields.Datetime(string="解析完成时间")
    failed_at = fields.Datetime(string="失败时间")
    worker_attempt_count = fields.Integer(string="处理次数", default=0)
    worker_last_error_code = fields.Char(string="最近错误码")
    worker_last_error_message = fields.Text(string="最近错误信息")
    worker_debug_payload = fields.Text(string="调试载荷")

    def _has_worker_source(self):
        self.ensure_one()
        return bool(self.primary_attachment_id or self.source_file or self.source_url or self.raw_text)

    @api.model
    def _get_pending_worker_tasks(self, limit=10, include_draft=True, source_document_id=False):
        statuses = ["queued", "failed"]
        if include_draft:
            statuses.insert(0, "draft")
        domain = [("active", "=", True), ("import_status", "in", statuses)]
        if source_document_id:
            domain.append(("id", "=", int(source_document_id)))
        records = self.search(domain, order="write_date asc, id asc", limit=max(limit * 3, limit))
        return records.filtered(lambda rec: rec._has_worker_source())[:limit]

    def _has_openclaw_provider(self):
        self.ensure_one()
        vision_provider = (self.env["ir.config_parameter"].sudo().get_param("diecut.ai_tds_vision_provider") or "").strip()
        struct_provider = (self.env["ir.config_parameter"].sudo().get_param("diecut.ai_tds_struct_provider") or "").strip()
        return vision_provider == "openclaw" or struct_provider == "openclaw"

    def _queue_for_worker(self):
        self.ensure_one()
        self.write(
            {
                "import_status": "queued",
                "queued_at": fields.Datetime.now(),
                "worker_last_error_code": False,
                "worker_last_error_message": False,
                "worker_debug_payload": False,
            }
        )
        return True

    def _run_openclaw_worker_job(self, timeout=1200):
        self.ensure_one()
        token = (
            self.env["ir.config_parameter"].sudo().get_param("diecut.tds_copilot_api_token")
            or os.environ.get("DIECUT_TDS_WORKER_TOKEN")
            or os.environ.get("OPENCLAW_GATEWAY_TOKEN")
            or ""
        ).strip()
        if not token:
            raise UserError("未配置 TDS Copilot Worker Token，无法调用 OpenClaw worker。")

        script_path = "/mnt/extra-addons/diecut/scripts/openclaw_tds_worker.py"
        env = os.environ.copy()
        env["DIECUT_TDS_WORKER_TOKEN"] = token
        env["ODOO_DB"] = self.env.cr.dbname
        env["ODOO_BASE_URL"] = "http://127.0.0.1:8069"
        for role in ("vision", "struct"):
            provider = (self.env["ir.config_parameter"].sudo().get_param(f"diecut.ai_tds_{role}_provider") or "").strip()
            if provider != "openclaw":
                continue
            gateway_url = (self.env["ir.config_parameter"].sudo().get_param(f"diecut.ai_tds_{role}_gateway_url") or "").strip()
            gateway_token = (self.env["ir.config_parameter"].sudo().get_param(f"diecut.ai_tds_{role}_gateway_token") or "").strip()
            agent_id = (self.env["ir.config_parameter"].sudo().get_param(f"diecut.ai_tds_{role}_agent_id") or "").strip()
            model = (self.env["ir.config_parameter"].sudo().get_param(f"diecut.ai_tds_{role}_model") or "").strip()
            if gateway_url:
                env["OPENCLAW_GATEWAY_URL"] = gateway_url
            if gateway_token:
                env["OPENCLAW_GATEWAY_TOKEN"] = gateway_token
            if agent_id:
                env["OPENCLAW_AGENT_ID"] = agent_id
            if model:
                env["OPENCLAW_MODEL"] = model

        cmd = [
            sys.executable,
            script_path,
            "--base-url",
            env["ODOO_BASE_URL"],
            "--db",
            self.env.cr.dbname,
            "--limit",
            "1",
            "--source-id",
            str(self.id),
        ]
        try:
            self.env.cr.commit()
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise UserError("OpenClaw worker 执行超时，请稍后重试。") from exc

        self.invalidate_recordset()
        refreshed = self.browse(self.id)
        if result.returncode != 0:
            details = (result.stderr or result.stdout or "").strip()
            raise UserError(f"OpenClaw worker 执行失败：{details or '未知错误'}")
        if refreshed.import_status not in ("parsed", "review", "validated", "applied"):
            details = (refreshed.worker_last_error_message or refreshed.result_message or result.stdout or "").strip()
            raise UserError(f"OpenClaw worker 未生成草稿：{details or '状态未进入待确认'}")
        return refreshed

    def _build_worker_task_payload(self, base_url=False, db_name=False):
        self.ensure_one()
        attachment = self.primary_attachment_id or self._get_effective_primary_attachment()
        fresh_context = self._build_copilot_context()
        try:
            stored_context = json.loads(self.context_used or "{}")
        except Exception:
            stored_context = {}
        context_used = dict(stored_context or {})
        context_used.update(fresh_context or {})
        database_name = db_name or self.env.cr.dbname
        return {
            "source_document_id": self.id,
            "db_name": database_name,
            "name": self.name,
            "status": self.import_status,
            "brand": self.brand_id.name if self.brand_id else False,
            "category": self.categ_id.name if self.categ_id else False,
            "primary_attachment_id": attachment.id if attachment else False,
            "primary_attachment_name": attachment.name if attachment else False,
            "primary_attachment_mimetype": attachment.mimetype if attachment else False,
            "attachment_count": self.attachment_count,
            "source_url": self.source_url or False,
            "skill_profile": self.skill_profile or False,
            "brand_skill_name": self.brand_skill_name or self._resolve_brand_skill_name() or False,
            "parse_version": self.parse_version or False,
            "queued_at": fields.Datetime.to_string(self.queued_at) if self.queued_at else False,
            "processing_started_at": fields.Datetime.to_string(self.processing_started_at) if self.processing_started_at else False,
            "worker_attempt_count": self.worker_attempt_count,
            "last_error_code": self.worker_last_error_code or False,
            "last_error_message": self.worker_last_error_message or False,
            "raw_text": self.raw_text or False,
            "existing_vision_payload": self.vision_payload or False,
            "context_used": context_used,
            "attachment_download_url": (
                f"{base_url}/api/material/extract/attachment/{attachment.id}?db={database_name}"
                if base_url and attachment
                else False
            ),
        }

    def _mark_worker_processing(self, worker_id=False, run_id=False):
        self.ensure_one()
        now = fields.Datetime.now()
        values = {
            "import_status": "processing",
            "worker_id": (worker_id or "").strip() or self.worker_id,
            "worker_run_id": (run_id or "").strip() or self.worker_run_id,
            "processing_started_at": now,
            "worker_attempt_count": (self.worker_attempt_count or 0) + 1,
            "worker_last_error_code": False,
            "worker_last_error_message": False,
            "worker_debug_payload": False,
        }
        if self.import_status == "draft" and not self.queued_at:
            values["queued_at"] = now
        self.write(values)
        return True

    def _mark_worker_parsed(
        self,
        *,
        vision_payload=False,
        draft_payload=False,
        unmatched_payload=False,
        parse_version=False,
        context_used=False,
        result_message=False,
        line_count=False,
    ):
        self.ensure_one()
        values = {
            "import_status": "parsed",
            "parsed_at": fields.Datetime.now(),
            "worker_last_error_code": False,
            "worker_last_error_message": False,
        }
        if vision_payload not in (False, None):
            values["vision_payload"] = vision_payload
        if draft_payload not in (False, None):
            values["draft_payload"] = draft_payload
        if unmatched_payload not in (False, None):
            values["unmatched_payload"] = unmatched_payload
        if parse_version not in (False, None):
            values["parse_version"] = parse_version
        if context_used not in (False, None):
            values["context_used"] = context_used
        if result_message not in (False, None):
            values["result_message"] = result_message
        self.write(values)
        if line_count not in (False, None):
            self.write({"result_message": "%s\nworker_line_count=%s" % ((self.result_message or "").rstrip(), line_count)})
        return True

    def _mark_worker_failed(self, error_code=False, error_message=False, debug_payload=False):
        self.ensure_one()
        self.write(
            {
                "import_status": "failed",
                "failed_at": fields.Datetime.now(),
                "worker_last_error_code": (error_code or "").strip() or False,
                "worker_last_error_message": error_message or False,
                "worker_debug_payload": debug_payload or False,
                "result_message": "解析失败：%s" % (error_message or error_code or "未知错误"),
            }
        )
        return True

    def _submit_worker_review(self):
        self.ensure_one()
        if self.import_status not in ("parsed", "generated", "validated"):
            raise UserError("当前状态不允许提交待确认。")
        self.write({"import_status": "review"})
        return True
