# -*- coding: utf-8 -*-

import os
import subprocess
import sys
import time

from odoo import models
from odoo.exceptions import UserError


class DiecutCatalogSourceDocumentGenerateOverride(models.Model):
    _inherit = "diecut.catalog.source.document"

    def _launch_openclaw_worker_async(self):
        self.ensure_one()
        token = (
            self.env["ir.config_parameter"].sudo().get_param("diecut.tds_copilot_api_token")
            or os.environ.get("DIECUT_TDS_WORKER_TOKEN")
            or os.environ.get("OPENCLAW_GATEWAY_TOKEN")
            or ""
        ).strip()
        if not token:
            raise UserError("未配置 TDS Copilot Worker Token，无法调用 OpenClaw worker。")

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
            "/mnt/extra-addons/diecut/scripts/openclaw_tds_worker.py",
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
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        except Exception as exc:
            raise UserError(f"OpenClaw worker 异步启动失败：{exc}") from exc

        run_id = f"manual-{self.id}-{int(time.time())}-{process.pid}"
        self.write(
            {
                "worker_run_id": run_id,
                "worker_id": "local-subprocess",
            }
        )
        return run_id

    def action_generate_draft(self):
        for record in self:
            if not record.raw_text:
                record.action_extract_source()
            if not record.raw_text:
                raise UserError("未提取到原文，无法生成草稿。")

            if not hasattr(record, "_queue_for_worker"):
                raise UserError("Worker 未启用，无法执行 AI/TDS 生成。")

            record._queue_for_worker()
            record.write(
                {
                    "skill_profile": (record.skill_profile or "generic_tds_v1+diecut_domain_v1").strip(),
                    "brand_skill_name": record._resolve_brand_skill_name(),
                }
            )
            record._launch_openclaw_worker_async()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "任务已入队",
                "message": "AI 草稿生成任务已异步启动，请稍后刷新查看状态。",
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
