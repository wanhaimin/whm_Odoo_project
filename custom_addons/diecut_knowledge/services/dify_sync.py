# -*- coding: utf-8 -*-
"""Odoo → Dify 同步服务

负责把 `diecut.kb.article` 的内容推送到对应分类的 Dify Dataset。

调用入口：
- `DifyKnowledgeSync(env).sync_article(article)`        单篇推送/更新/删除
- `DifyKnowledgeSync(env).sync_pending(limit=20)`       批量扫 pending/failed

设计原则：
- **不抛异常**：所有失败都吞掉，写入 sync_log + 更新 sync_status='failed' 后返回
- **幂等**：同篇文章重复同步会走 update 而非 create（依赖 dify_document_id 是否已绑定）
- **轻量**：不做 chunk/embedding，全部交给 Dify 处理
"""

import json
import logging
from datetime import datetime
from typing import Optional

from .dify_client import DifyClient

_logger = logging.getLogger(__name__)


class DifyKnowledgeSync:
    """文章同步服务（每次调用都新建实例，env 来自调用方）"""

    PARAM_BASE_URL = "diecut_knowledge.dify_base_url"
    PARAM_API_KEY = "diecut_knowledge.dify_api_key"
    PARAM_TIMEOUT = "diecut_knowledge.dify_timeout"
    PARAM_RETRIES = "diecut_knowledge.dify_retries"
    PARAM_BATCH_LIMIT = "diecut_knowledge.dify_batch_limit"

    MIN_CONTENT_LENGTH = 10

    def __init__(self, env):
        self.env = env

    # --------------------------- public -------------------------------------

    def sync_article(self, article) -> dict:
        """同步单篇文章。返回 {ok, action, error}"""
        article.ensure_one()

        if article.state == "archived" and article.dify_document_id:
            return self._do_delete(article)

        if article.state != "published":
            self._mark_skipped(article, "文章状态非 published，跳过同步")
            return {"ok": True, "action": "skip", "error": None}

        if article.content_length < self.MIN_CONTENT_LENGTH:
            self._record_failure(article, "skip", f"正文过短({article.content_length} 字符)，跳过同步")
            return {"ok": False, "action": "skip", "error": "content too short"}

        client = self._build_client()
        if not client:
            self._record_failure(article, "create", "Dify 配置缺失（base_url / api_key 未设置）")
            return {"ok": False, "action": "noop", "error": "dify not configured"}

        dataset_id = article.category_id.dify_dataset_id
        if not dataset_id:
            self._record_failure(article, "create", f"分类 [{article.category_id.name}] 未绑定 Dify Dataset ID")
            return {"ok": False, "action": "noop", "error": "dataset not bound"}

        if article.dify_document_id and article.dify_dataset_id == dataset_id:
            return self._do_update(article, client, dataset_id)
        if article.dify_document_id and article.dify_dataset_id != dataset_id:
            self._do_delete(article, client=client, force_dataset_id=article.dify_dataset_id)
            return self._do_create(article, client, dataset_id)
        return self._do_create(article, client, dataset_id)

    def sync_pending(self, limit: Optional[int] = None) -> dict:
        """批量扫 pending/failed。返回 {total, ok, failed}"""
        if limit is None:
            limit = int(self._get_param(self.PARAM_BATCH_LIMIT, default="20") or 20)

        Article = self.env["diecut.kb.article"]
        published_pending = Article.search(
            [("state", "=", "published"), ("sync_status", "in", ("pending", "failed"))],
            limit=limit,
            order="last_edited_at asc, id asc",
        )
        archived_pending = Article.search(
            [("state", "=", "archived"), ("sync_status", "=", "pending"), ("dify_document_id", "!=", False)],
            limit=max(0, limit - len(published_pending)),
        )
        targets = published_pending | archived_pending

        ok_count, failed_count = 0, 0
        for article in targets:
            result = self.sync_article(article)
            if result.get("ok"):
                ok_count += 1
            else:
                failed_count += 1
        return {"total": len(targets), "ok": ok_count, "failed": failed_count}

    # --------------------------- actions ------------------------------------

    def _do_create(self, article, client: DifyClient, dataset_id: str) -> dict:
        text, metadata, doc_name = self._build_payload(article)
        ok, payload, error, duration_ms = client.create_document_by_text(
            dataset_id=dataset_id,
            name=doc_name,
            text=text,
            metadata=metadata,
        )
        if not ok:
            self._record_failure(article, "create", error, request=text[:1000], response=payload, duration_ms=duration_ms)
            return {"ok": False, "action": "create", "error": error}

        document = (payload or {}).get("document") or {}
        document_id = document.get("id") or (payload or {}).get("id")
        article.sudo().write({
            "sync_status": "synced",
            "dify_dataset_id": dataset_id,
            "dify_document_id": document_id,
            "last_sync_at": datetime.now(),
            "sync_error": False,
        })
        self._record_success(article, "create", payload, duration_ms, summary=f"已创建 Dify 文档 {document_id}")
        return {"ok": True, "action": "create", "error": None}

    def _do_update(self, article, client: DifyClient, dataset_id: str) -> dict:
        text, metadata, doc_name = self._build_payload(article)
        ok, payload, error, duration_ms = client.update_document_by_text(
            dataset_id=dataset_id,
            document_id=article.dify_document_id,
            name=doc_name,
            text=text,
        )
        if not ok:
            if "not_found" in (error or "").lower() or "404" in (error or ""):
                article.sudo().write({"dify_document_id": False, "dify_dataset_id": False})
                return self._do_create(article, client, dataset_id)
            self._record_failure(article, "update", error, request=text[:1000], response=payload, duration_ms=duration_ms)
            return {"ok": False, "action": "update", "error": error}

        article.sudo().write({
            "sync_status": "synced",
            "last_sync_at": datetime.now(),
            "sync_error": False,
        })
        self._record_success(article, "update", payload, duration_ms, summary="已更新 Dify 文档")
        return {"ok": True, "action": "update", "error": None}

    def _do_delete(self, article, client: Optional[DifyClient] = None, force_dataset_id: Optional[str] = None) -> dict:
        client = client or self._build_client()
        if not client or not article.dify_document_id:
            article.sudo().write({"sync_status": "synced"})
            return {"ok": True, "action": "noop", "error": None}

        dataset_id = force_dataset_id or article.dify_dataset_id
        if not dataset_id:
            return {"ok": False, "action": "delete", "error": "missing dataset_id"}

        ok, payload, error, duration_ms = client.delete_document(dataset_id, article.dify_document_id)
        if not ok and "not_found" not in (error or "").lower() and "404" not in (error or ""):
            self._record_failure(article, "delete", error, response=payload, duration_ms=duration_ms)
            return {"ok": False, "action": "delete", "error": error}

        article.sudo().write({
            "sync_status": "synced",
            "dify_document_id": False,
            "last_sync_at": datetime.now(),
            "sync_error": False,
        })
        self._record_success(article, "delete", payload or {}, duration_ms, summary="已从 Dify 删除")
        return {"ok": True, "action": "delete", "error": None}

    # --------------------------- payload ------------------------------------

    def _build_payload(self, article) -> tuple:
        """把 article 转成 Dify 用的 (text, metadata, doc_name)。"""
        parts = []
        if article.summary:
            parts.append(f"## 摘要\n{article.summary.strip()}\n")
        parts.append(f"## 正文\n{article.content_text.strip()}")
        if article.related_item_ids:
            codes = ", ".join((article.related_item_ids.mapped("code") or []))
            if codes:
                parts.append(f"\n## 关联型号\n{codes}")
        if article.keywords:
            parts.append(f"\n## 关键词\n{article.keywords}")

        text = "\n\n".join(parts).strip() or article.name

        metadata = {
            "odoo_id": article.id,
            "odoo_model": "diecut.kb.article",
            "category_code": article.category_code or "",
            "category_name": article.category_id.name if article.category_id else "",
            "state": article.state,
            "author": article.author_name or "",
            "publish_date": article.publish_date.isoformat() if article.publish_date else "",
            "brands": ", ".join(article.related_brand_ids.mapped("name")),
            "categories": ", ".join(article.related_categ_ids.mapped("name")),
            "items": ", ".join(article.related_item_ids.mapped("code")),
        }
        # Dify metadata 不允许 None / 复杂类型；统一转字符串
        metadata = {k: ("" if v is None else str(v)) for k, v in metadata.items()}

        doc_name = f"[{article.category_id.code}] {article.name}"[:200]
        return text, metadata, doc_name

    # --------------------------- logging ------------------------------------

    def _record_success(self, article, action: str, response: dict, duration_ms: int, summary: str):
        self.env["diecut.kb.sync.log"].sudo().create({
            "article_id": article.id,
            "direction": "push",
            "action": action,
            "state": "success",
            "summary": summary,
            "response_payload": json.dumps(response, ensure_ascii=False, indent=2)[:8000] if response else "",
            "dify_dataset_id": article.dify_dataset_id or "",
            "dify_document_id": article.dify_document_id or "",
            "duration_ms": duration_ms,
        })

    def _record_failure(
        self,
        article,
        action: str,
        error: str,
        request: str = "",
        response: Optional[dict] = None,
        duration_ms: int = 0,
    ):
        article.sudo().write({
            "sync_status": "failed",
            "sync_error": (error or "")[:2000],
        })
        self.env["diecut.kb.sync.log"].sudo().create({
            "article_id": article.id,
            "direction": "push",
            "action": action,
            "state": "failed",
            "summary": f"同步失败：{(error or '')[:120]}",
            "request_payload": request[:8000] if request else "",
            "response_payload": json.dumps(response or {}, ensure_ascii=False)[:8000],
            "error_message": error or "",
            "dify_dataset_id": article.category_id.dify_dataset_id or "",
            "dify_document_id": article.dify_document_id or "",
            "duration_ms": duration_ms,
        })

    def _mark_skipped(self, article, reason: str):
        article.sudo().write({
            "sync_status": "skipped",
            "sync_error": False,
        })
        self.env["diecut.kb.sync.log"].sudo().create({
            "article_id": article.id,
            "direction": "push",
            "action": "create",
            "state": "success",
            "summary": f"已跳过：{reason}",
        })

    # --------------------------- config -------------------------------------

    def _build_client(self) -> Optional[DifyClient]:
        base_url = self._get_param(self.PARAM_BASE_URL)
        api_key = self._get_param(self.PARAM_API_KEY)
        if not base_url or not api_key:
            return None
        try:
            timeout = int(self._get_param(self.PARAM_TIMEOUT, default="30") or 30)
        except (TypeError, ValueError):
            timeout = 30
        try:
            retries = int(self._get_param(self.PARAM_RETRIES, default="2") or 2)
        except (TypeError, ValueError):
            retries = 2
        return DifyClient(base_url=base_url, api_key=api_key, timeout=timeout, retries=retries)

    def _get_param(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.env["ir.config_parameter"].sudo().get_param(key, default=default)
