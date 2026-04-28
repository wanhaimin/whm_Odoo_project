# -*- coding: utf-8 -*-
"""客户问答工单 → Dify 同步服务

每个 diecut.kb.qa_ticket 同步为 Dify 中一份 Q&A 格式文档：
  - name = "[客户问答] {问题摘要}"
  - text = "## 问题\n{question}\n\n## 答复\n{answer}" 格式
  - metadata = 分类/来源/客户/关联型号

设计要点：
- 复用 DifyClient + sync_log 模型
- 写入时标 sync_status=pending，真正同步走 cron / 手动按钮
- 幂等：依赖 dify_document_id 区分创建/更新
"""

import json
import logging
from datetime import datetime
from typing import Optional

from .dify_client import DifyClient

_logger = logging.getLogger(__name__)


class QaTicketSync:
    PARAM_BASE_URL = "diecut_knowledge.dify_base_url"
    PARAM_API_KEY = "diecut_knowledge.dify_api_key"
    PARAM_TIMEOUT = "diecut_knowledge.dify_timeout"
    PARAM_RETRIES = "diecut_knowledge.dify_retries"
    PARAM_BATCH_LIMIT = "diecut_knowledge.dify_batch_limit"

    def __init__(self, env):
        self.env = env

    # --------------------------- public -------------------------------------

    def sync_ticket(self, ticket) -> dict:
        ticket.ensure_one()

        if ticket.state == "archived" and ticket.dify_document_id:
            return self._do_delete(ticket)

        if ticket.state != "published":
            self._mark(ticket, "skipped", "状态非 published")
            return {"ok": True, "action": "skip", "error": None}

        if not ticket.question or not ticket.answer:
            self._mark(ticket, "skipped", "问题或答复为空")
            return {"ok": True, "action": "skip", "error": None}

        client, dataset_id = self._build_client_and_dataset(ticket)
        if not client:
            self._mark(ticket, "failed", "Dify 未配置（base_url / api_key）")
            return {"ok": False, "action": "noop", "error": "dify not configured"}
        if not dataset_id:
            self._mark(ticket, "failed", "未绑定 Dify Dataset ID")
            return {"ok": False, "action": "noop", "error": "dataset not bound"}

        if ticket.dify_document_id and ticket.dify_dataset_id == dataset_id:
            return self._do_update(ticket, client, dataset_id)
        if ticket.dify_document_id and ticket.dify_dataset_id != dataset_id:
            self._do_delete(ticket, client, ticket.dify_dataset_id)
            return self._do_create(ticket, client, dataset_id)
        return self._do_create(ticket, client, dataset_id)

    def sync_pending(self, limit: Optional[int] = None) -> dict:
        if limit is None:
            limit = int(self._get_param(self.PARAM_BATCH_LIMIT, default="20") or 20)

        Ticket = self.env["diecut.kb.qa_ticket"]
        published = Ticket.search(
            [("state", "=", "published"), ("sync_status", "in", ("pending", "failed"))],
            limit=limit,
            order="write_date asc, id asc",
        )
        archived = Ticket.search(
            [("state", "=", "archived"), ("sync_status", "=", "pending"),
             ("dify_document_id", "!=", False)],
            limit=max(0, limit - len(published)),
        )
        targets = published | archived

        ok_count, fail_count = 0, 0
        for ticket in targets:
            result = self.sync_ticket(ticket)
            if result.get("ok"):
                ok_count += 1
            else:
                fail_count += 1
        return {"total": len(targets), "ok": ok_count, "failed": fail_count}

    # --------------------------- actions ------------------------------------

    def _do_create(self, ticket, client: DifyClient, dataset_id: str) -> dict:
        text, metadata, doc_name = self._build_payload(ticket)
        ok, payload, error, duration = client.create_document_by_text(
            dataset_id=dataset_id,
            name=doc_name,
            text=text,
            metadata=metadata,
        )
        if not ok:
            self._record_failure(ticket, "create", error, text[:1000], payload, duration)
            return {"ok": False, "action": "create", "error": error}

        document = (payload or {}).get("document") or {}
        document_id = document.get("id") or (payload or {}).get("id")
        ticket.sudo().write({
            "sync_status": "synced",
            "dify_dataset_id": dataset_id,
            "dify_document_id": document_id,
            "last_sync_at": datetime.now(),
            "sync_error": False,
        })
        return {"ok": True, "action": "create", "error": None}

    def _do_update(self, ticket, client: DifyClient, dataset_id: str) -> dict:
        text, _meta, doc_name = self._build_payload(ticket)
        ok, payload, error, duration = client.update_document_by_text(
            dataset_id=dataset_id,
            document_id=ticket.dify_document_id,
            name=doc_name,
            text=text,
        )
        if not ok:
            if "not_found" in (error or "").lower() or "404" in (error or ""):
                ticket.sudo().write({"dify_document_id": False, "dify_dataset_id": False})
                return self._do_create(ticket, client, dataset_id)
            self._record_failure(ticket, "update", error, text[:1000], payload, duration)
            return {"ok": False, "action": "update", "error": error}

        ticket.sudo().write({
            "sync_status": "synced",
            "last_sync_at": datetime.now(),
            "sync_error": False,
        })
        return {"ok": True, "action": "update", "error": None}

    def _do_delete(self, ticket, client=None, force_dataset_id=None) -> dict:
        client = client or self._build_client()
        if not client or not ticket.dify_document_id:
            ticket.sudo().write({"sync_status": "synced"})
            return {"ok": True, "action": "noop", "error": None}

        dataset_id = force_dataset_id or ticket.dify_dataset_id
        if not dataset_id:
            return {"ok": False, "action": "delete", "error": "missing dataset_id"}

        ok, payload, error, duration = client.delete_document(dataset_id, ticket.dify_document_id)
        if not ok and "not_found" not in (error or "").lower() and "404" not in (error or ""):
            self._record_failure(ticket, "delete", error, "", payload, duration)
            return {"ok": False, "action": "delete", "error": error}

        ticket.sudo().write({
            "sync_status": "synced",
            "dify_document_id": False,
            "last_sync_at": datetime.now(),
            "sync_error": False,
        })
        return {"ok": True, "action": "delete", "error": None}

    # --------------------------- payload ------------------------------------

    def _build_payload(self, ticket) -> tuple:
        parts = [
            f"## 问题\n\n{ticket.question.strip()}",
            f"## 答复\n\n{ticket.answer.strip()}",
        ]
        if ticket.keywords:
            parts.append(f"\n## 关键词\n\n{ticket.keywords.strip()}")
        if ticket.related_item_ids:
            codes = ", ".join(ticket.related_item_ids.mapped("code") or [])
            if codes:
                parts.append(f"\n## 关联型号\n\n{codes}")

        text = "\n\n".join(parts).strip()
        doc_name = f"[客户问答] {ticket.name}"[:200]

        metadata = {
            "odoo_id": ticket.id,
            "odoo_model": "diecut.kb.qa_ticket",
            "category": ticket.category_id.name or "",
            "customer": ticket.customer_name or "",
            "source": ticket.source or "",
            "source_ref": ticket.source_ref or "",
            "resolved_date": ticket.resolved_date.isoformat() if ticket.resolved_date else "",
        }
        metadata = {k: ("" if v is None else str(v)) for k, v in metadata.items()}
        return text, metadata, doc_name

    # --------------------------- helpers ------------------------------------

    def _mark(self, ticket, status: str, reason: str):
        error_val = reason if status == "failed" else (False if status == "skipped" else False)
        ticket.sudo().write({
            "sync_status": status,
            "sync_error": (reason or "")[:2000] if status == "failed" else error_val,
        })

    def _record_failure(self, ticket, action: str, error: str,
                        request: str = "", response: dict = None, duration: int = 0):
        ticket.sudo().write({
            "sync_status": "failed",
            "sync_error": (error or "")[:2000],
        })
        self.env["diecut.kb.sync.log"].sudo().create({
            "article_id": False,
            "direction": "push",
            "action": action,
            "state": "failed",
            "summary": f"QA 工单 [{ticket.name}] 同步失败：{(error or '')[:120]}",
            "request_payload": request[:8000] if request else "",
            "response_payload": json.dumps(response or {}, ensure_ascii=False)[:8000],
            "error_message": error or "",
            "dify_dataset_id": ticket.category_id.dify_dataset_id or "",
            "dify_document_id": ticket.dify_document_id or "",
            "duration_ms": duration,
        })

    def _build_client_and_dataset(self, ticket) -> tuple:
        base_url = self._get_param(self.PARAM_BASE_URL)
        api_key = self._get_param(self.PARAM_API_KEY)
        dataset_id = ticket.category_id.dify_dataset_id
        if not base_url or not api_key:
            return None, dataset_id
        try:
            timeout = int(self._get_param(self.PARAM_TIMEOUT, default="30") or 30)
        except (TypeError, ValueError):
            timeout = 30
        try:
            retries = int(self._get_param(self.PARAM_RETRIES, default="2") or 2)
        except (TypeError, ValueError):
            retries = 2
        return DifyClient(base_url=base_url, api_key=api_key, timeout=timeout, retries=retries), dataset_id

    def _build_client(self):
        base_url = self._get_param(self.PARAM_BASE_URL)
        api_key = self._get_param(self.PARAM_API_KEY)
        if not base_url or not api_key:
            return None
        return DifyClient(base_url=base_url, api_key=api_key)

    def _get_param(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.env["ir.config_parameter"].sudo().get_param(key, default=default)
