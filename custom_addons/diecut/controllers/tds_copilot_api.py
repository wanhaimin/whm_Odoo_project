# -*- coding: utf-8 -*-

import json
import os
from contextlib import contextmanager

from odoo import SUPERUSER_ID, api, http
from odoo.http import request
from odoo.modules.registry import Registry


class TdsCopilotApiController(http.Controller):
    def _json_response(self, payload, status=200):
        return request.make_response(
            json.dumps(payload, ensure_ascii=False),
            headers=[("Content-Type", "application/json; charset=utf-8")],
            status=status,
        )

    def _read_json_body(self):
        try:
            return json.loads(request.httprequest.get_data(as_text=True) or "{}")
        except Exception:
            return {}

    def _resolve_db_name(self, body=None):
        body = body or {}
        return (
            request.session.db
            or request.params.get("db")
            or body.get("db")
            or http.db_monodb()
            or ""
        ).strip()

    @contextmanager
    def _api_env(self, body=None):
        db_name = self._resolve_db_name(body=body)
        if not db_name:
            raise ValueError("missing_db")
        registry = Registry(db_name)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            yield env, db_name

    def _worker_token(self, body=None):
        try:
            with self._api_env(body=body) as (env, _db_name):
                env.cr.execute(
                    """
                    SELECT value
                    FROM ir_config_parameter
                    WHERE key = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    ["diecut.tds_copilot_api_token"],
                )
                row = env.cr.fetchone()
                token = (row[0] if row and row[0] else "") or ""
                if token.strip():
                    return token.strip()
        except Exception:
            pass
        return (
            os.environ.get("DIECUT_TDS_WORKER_TOKEN")
            or os.environ.get("OPENCLAW_GATEWAY_TOKEN")
            or ""
        ).strip()

    def _is_authorized(self, body=None):
        expected = self._worker_token(body=body)
        if not expected:
            remote_addr = (request.httprequest.remote_addr or "").strip()
            if remote_addr.startswith(("127.", "10.", "192.168.", "172.17.", "172.18.", "172.19.", "::1")):
                token = (
                    (request.httprequest.headers.get("X-Diecut-Worker-Token") or "").strip()
                    or (request.params.get("worker_token") or "").strip()
                    or ((body or {}).get("worker_token") or "").strip()
                )
                return bool(token)
            return False
        auth = request.httprequest.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
        else:
            token = (
                (request.httprequest.headers.get("X-Diecut-Worker-Token") or "").strip()
                or (request.params.get("worker_token") or "").strip()
                or ((body or {}).get("worker_token") or "").strip()
            )
        return bool(token and token == expected)

    def _require_authorized(self, body=None):
        if not self._is_authorized(body=body):
            return self._json_response({"ok": False, "error": "未授权"}, status=401)
        return None

    def _base_url(self):
        return request.httprequest.host_url.rstrip("/")

    @http.route("/api/material/extract/pending_tasks", type="http", auth="public", methods=["POST"], csrf=False)
    def tds_pending_tasks(self, **kwargs):
        body = self._read_json_body()
        unauthorized = self._require_authorized(body=body)
        if unauthorized:
            return unauthorized
        limit = int(body.get("limit") or 10)
        include_draft = bool(body.get("include_draft", True))
        with self._api_env(body=body) as (env, db_name):
            records = env["diecut.catalog.source.document"].sudo()._get_pending_worker_tasks(
                limit=limit,
                include_draft=include_draft,
                source_document_id=body.get("source_document_id"),
            )
            tasks = [record._build_worker_task_payload(base_url=self._base_url(), db_name=db_name) for record in records]
        return self._json_response({"ok": True, "tasks": tasks})

    @http.route("/api/material/extract/mark_processing", type="http", auth="public", methods=["POST"], csrf=False)
    def tds_mark_processing(self, **kwargs):
        body = self._read_json_body()
        unauthorized = self._require_authorized(body=body)
        if unauthorized:
            return unauthorized
        with self._api_env(body=body) as (env, _db_name):
            record = env["diecut.catalog.source.document"].sudo().browse(int(body.get("source_document_id") or 0))
            if not record.exists():
                return self._json_response({"ok": False, "error": "来源记录不存在"}, status=404)
            record._mark_worker_processing(worker_id=body.get("worker_id"), run_id=body.get("run_id"))
            status = record.import_status
        return self._json_response({"ok": True, "status": status})

    @http.route("/api/material/extract/attachment/<int:attachment_id>", type="http", auth="public", methods=["GET"], csrf=False)
    def tds_download_attachment(self, attachment_id, **kwargs):
        unauthorized = self._require_authorized(body=request.params)
        if unauthorized:
            return unauthorized
        with self._api_env(body=request.params) as (env, _db_name):
            attachment = env["ir.attachment"].sudo().browse(attachment_id)
            if not attachment.exists():
                return request.not_found()
            data = attachment.raw or b""
            headers = [
                ("Content-Type", attachment.mimetype or "application/octet-stream"),
                ("Content-Disposition", 'attachment; filename="%s"' % (attachment.name or "source.bin")),
            ]
        return request.make_response(data, headers=headers)

    @http.route("/api/material/extract/mark_parsed", type="http", auth="public", methods=["POST"], csrf=False)
    def tds_mark_parsed(self, **kwargs):
        body = self._read_json_body()
        unauthorized = self._require_authorized(body=body)
        if unauthorized:
            return unauthorized
        with self._api_env(body=body) as (env, _db_name):
            record = env["diecut.catalog.source.document"].sudo().browse(int(body.get("source_document_id") or 0))
            if not record.exists():
                return self._json_response({"ok": False, "error": "来源记录不存在"}, status=404)
            record._mark_worker_parsed(
                vision_payload=body.get("vision_payload"),
                draft_payload=body.get("draft_payload"),
                unmatched_payload=body.get("unmatched_payload"),
                parse_version=body.get("parse_version"),
                context_used=body.get("context_used"),
                result_message=body.get("result_message"),
                line_count=body.get("line_count"),
            )
            status = record.import_status
        return self._json_response({"ok": True, "status": status})

    @http.route("/api/material/extract/mark_failed", type="http", auth="public", methods=["POST"], csrf=False)
    def tds_mark_failed(self, **kwargs):
        body = self._read_json_body()
        unauthorized = self._require_authorized(body=body)
        if unauthorized:
            return unauthorized
        with self._api_env(body=body) as (env, _db_name):
            record = env["diecut.catalog.source.document"].sudo().browse(int(body.get("source_document_id") or 0))
            if not record.exists():
                return self._json_response({"ok": False, "error": "来源记录不存在"}, status=404)
            record._mark_worker_failed(
                error_code=body.get("error_code"),
                error_message=body.get("error_message"),
                debug_payload=body.get("debug_payload"),
            )
            status = record.import_status
        return self._json_response({"ok": True, "status": status})

    @http.route("/api/material/material/submit_review", type="http", auth="public", methods=["POST"], csrf=False)
    def tds_submit_review(self, **kwargs):
        body = self._read_json_body()
        unauthorized = self._require_authorized(body=body)
        if unauthorized:
            return unauthorized
        with self._api_env(body=body) as (env, _db_name):
            record = env["diecut.catalog.source.document"].sudo().browse(int(body.get("source_document_id") or 0))
            if not record.exists():
                return self._json_response({"ok": False, "error": "来源记录不存在"}, status=404)
            record._submit_worker_review()
            status = record.import_status
        return self._json_response({"ok": True, "status": status})
