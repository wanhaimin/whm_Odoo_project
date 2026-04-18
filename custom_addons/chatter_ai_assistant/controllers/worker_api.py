# -*- coding: utf-8 -*-

import json

from odoo import http
from odoo.http import request


class ChatterAiWorkerApi(http.Controller):
    def _json_response(self, payload, status=200):
        return request.make_response(
            json.dumps(payload, ensure_ascii=False),
            headers=[("Content-Type", "application/json; charset=utf-8")],
            status=status,
        )

    def _payload(self):
        raw = request.httprequest.get_data(cache=False, as_text=True) or ""
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    @http.route("/chatter_ai_assistant/worker/claim", type="http", auth="public", methods=["POST"], csrf=False)
    def claim(self, **kwargs):
        payload = self._payload()
        run = request.env["chatter.ai.run"].sudo()
        try:
            result = run.claim_next_run_for_worker(payload.get("token"))
        except Exception as exc:  # pylint: disable=broad-except
            return self._json_response({"ok": False, "error": str(exc)}, status=403)
        return self._json_response({"ok": True, "run": result or False})

    @http.route("/chatter_ai_assistant/worker/complete", type="http", auth="public", methods=["POST"], csrf=False)
    def complete(self, **kwargs):
        payload = self._payload()
        run = request.env["chatter.ai.run"].sudo()
        try:
            result = run.complete_run_from_worker(payload.get("token"), payload.get("run_id"), payload.get("payload") or {})
        except Exception as exc:  # pylint: disable=broad-except
            return self._json_response({"ok": False, "error": str(exc)}, status=403)
        return self._json_response({"ok": True, "result": result})

    @http.route("/chatter_ai_assistant/worker/fail", type="http", auth="public", methods=["POST"], csrf=False)
    def fail(self, **kwargs):
        payload = self._payload()
        run = request.env["chatter.ai.run"].sudo()
        try:
            error_message = payload.get("error_message") or payload.get("error") or payload.get("message")
            result = run.fail_run_from_worker(payload.get("token"), payload.get("run_id"), error_message)
        except Exception as exc:  # pylint: disable=broad-except
            return self._json_response({"ok": False, "error": str(exc)}, status=403)
        return self._json_response({"ok": True, "result": result})

    @http.route("/chatter_ai_assistant/frontend/status", type="http", auth="user", methods=["GET"], csrf=False)
    def frontend_status(self, **kwargs):
        snapshot = request.env["chatter.ai.run"].frontend_status_snapshot()
        return self._json_response({"ok": True, "status": snapshot})

    @http.route(
        [
            "/chatter_ai_assistant/worker/material_update",
            "/chatter_ai_assistant/import/material_update",
        ],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def material_update(self, **kwargs):
        payload = self._payload()
        source_model = request.env["diecut.catalog.source.document"].sudo()
        token = payload.get("token")
        if not source_model._openclaw_import_secret_is_valid(token):
            return self._json_response({"ok": False, "error": "Invalid import token."}, status=403)
        try:
            result = source_model.import_openclaw_material_update(payload)
        except Exception as exc:  # pylint: disable=broad-except
            return self._json_response({"ok": False, "error": str(exc)}, status=400)
        return self._json_response({"ok": True, "result": result})
