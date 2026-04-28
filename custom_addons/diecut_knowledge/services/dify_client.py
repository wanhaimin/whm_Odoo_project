# -*- coding: utf-8 -*-
"""Dify HTTP 客户端

文档参考：
- Dataset API：https://docs.dify.ai/api-reference/knowledge-base
- Chat API   ：https://docs.dify.ai/api-reference/chat-messages

本客户端只做 *薄封装*：
- 不抛 Odoo 自身的异常（让上层 sync 服务统一处理）
- 所有方法返回 (ok: bool, payload: dict, error: str|None) 三元组
- 超时和重试由调用方控制
"""

import json
import logging
import time
from typing import Optional

import requests

_logger = logging.getLogger(__name__)


class DifyApiError(Exception):
    """Dify API 调用失败"""

    def __init__(self, status_code: int, message: str, payload: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.payload = payload or {}


class DifyClient:
    """Dify API 客户端。

    用法：
        client = DifyClient(base_url="http://dify:5001", api_key="dataset-xxx")
        ok, doc, err = client.create_document_by_text(
            dataset_id="...", name="VHB 选型指南", text="...", metadata={"odoo_id": 7}
        )
    """

    DEFAULT_TIMEOUT = 30
    DEFAULT_RETRIES = 2
    DEFAULT_RETRY_BACKOFF = 0.6

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
    ):
        if not base_url:
            raise ValueError("Dify base_url is required")
        if not api_key:
            raise ValueError("Dify api_key is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries
        self.retry_backoff = retry_backoff

    # --------------------------- internal -----------------------------------

    def _headers(self, json_body: bool = True) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        files: Optional[dict] = None,
        data: Optional[dict] = None,
    ) -> tuple:
        url = f"{self.base_url}/v1{path}"
        last_error = None
        for attempt in range(self.retries + 1):
            t0 = time.monotonic()
            try:
                response = requests.request(
                    method,
                    url,
                    headers=self._headers(json_body=files is None),
                    params=params,
                    json=json_body if files is None and json_body is not None else None,
                    data=data if files is not None else None,
                    files=files,
                    timeout=self.timeout,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                _logger.warning("Dify %s %s attempt %s failed: %s", method, path, attempt + 1, last_error)
                if attempt < self.retries:
                    time.sleep(self.retry_backoff * (attempt + 1))
                    continue
                return False, {}, last_error, int((time.monotonic() - t0) * 1000)

            duration_ms = int((time.monotonic() - t0) * 1000)
            try:
                payload = response.json() if response.content else {}
            except ValueError:
                payload = {"_raw": response.text[:500]}

            if 200 <= response.status_code < 300:
                return True, payload, None, duration_ms

            error_msg = payload.get("message") or payload.get("error") or response.text[:300]
            _logger.warning(
                "Dify %s %s failed [%s]: %s", method, path, response.status_code, error_msg
            )
            if response.status_code in (429, 502, 503, 504) and attempt < self.retries:
                time.sleep(self.retry_backoff * (attempt + 1))
                last_error = f"HTTP {response.status_code}: {error_msg}"
                continue
            return False, payload, f"HTTP {response.status_code}: {error_msg}", duration_ms

        return False, {}, last_error or "unknown error", 0

    # --------------------------- datasets -----------------------------------

    def list_datasets(self, page: int = 1, limit: int = 20):
        return self._request("GET", "/datasets", params={"page": page, "limit": limit})

    def create_dataset(self, name: str, description: str = "", indexing_technique: str = "high_quality"):
        return self._request(
            "POST",
            "/datasets",
            json_body={
                "name": name,
                "description": description,
                "indexing_technique": indexing_technique,
                "permission": "only_me",
            },
        )

    # --------------------------- documents (text) ---------------------------

    def create_document_by_text(
        self,
        dataset_id: str,
        name: str,
        text: str,
        *,
        indexing_technique: str = "high_quality",
        process_rule: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ):
        body = {
            "name": name,
            "text": text,
            "indexing_technique": indexing_technique,
            "process_rule": process_rule or self._default_process_rule(),
        }
        if metadata:
            body["doc_metadata"] = metadata
            body["doc_form"] = "text_model"
        return self._request(
            "POST",
            f"/datasets/{dataset_id}/document/create-by-text",
            json_body=body,
        )

    def update_document_by_text(
        self,
        dataset_id: str,
        document_id: str,
        name: str,
        text: str,
        *,
        process_rule: Optional[dict] = None,
    ):
        body = {
            "name": name,
            "text": text,
            "process_rule": process_rule or self._default_process_rule(),
        }
        return self._request(
            "POST",
            f"/datasets/{dataset_id}/documents/{document_id}/update-by-text",
            json_body=body,
        )

    def delete_document(self, dataset_id: str, document_id: str):
        return self._request("DELETE", f"/datasets/{dataset_id}/documents/{document_id}")

    def get_document_indexing_status(self, dataset_id: str, batch: str):
        return self._request(
            "GET",
            f"/datasets/{dataset_id}/documents/{batch}/indexing-status",
        )

    # --------------------------- documents (file) ---------------------------

    def create_document_by_file(
        self,
        dataset_id: str,
        file_name: str,
        file_bytes: bytes,
        mimetype: str,
        *,
        indexing_technique: str = "high_quality",
        process_rule: Optional[dict] = None,
    ):
        url = f"{self.base_url}/v1/datasets/{dataset_id}/document/create-by-file"
        process_payload = {
            "indexing_technique": indexing_technique,
            "process_rule": process_rule or self._default_process_rule(),
        }
        files = {
            "file": (file_name, file_bytes, mimetype),
            "data": (None, json.dumps(process_payload), "application/json"),
        }
        t0 = time.monotonic()
        try:
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files=files,
                timeout=self.timeout * 2,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            return False, {}, f"{type(exc).__name__}: {exc}", int((time.monotonic() - t0) * 1000)

        duration_ms = int((time.monotonic() - t0) * 1000)
        try:
            payload = response.json() if response.content else {}
        except ValueError:
            payload = {"_raw": response.text[:500]}

        if 200 <= response.status_code < 300:
            return True, payload, None, duration_ms
        error_msg = payload.get("message") or payload.get("error") or response.text[:300]
        return False, payload, f"HTTP {response.status_code}: {error_msg}", duration_ms

    # --------------------------- chat ---------------------------------------

    def chat_messages(
        self,
        query: str,
        *,
        user: str,
        conversation_id: str = "",
        inputs: Optional[dict] = None,
        response_mode: str = "blocking",
        files: Optional[list] = None,
    ):
        return self._request(
            "POST",
            "/chat-messages",
            json_body={
                "query": query,
                "user": user,
                "conversation_id": conversation_id,
                "inputs": inputs or {},
                "response_mode": response_mode,
                "files": files or [],
            },
        )

    # --------------------------- helpers ------------------------------------

    @staticmethod
    def _default_process_rule() -> dict:
        return {
            "mode": "custom",
            "rules": {
                "pre_processing_rules": [
                    {"id": "remove_extra_spaces", "enabled": True},
                    {"id": "remove_urls_emails", "enabled": False},
                ],
                "segmentation": {
                    "separator": "\n\n",
                    "max_tokens": 500,
                    "chunk_overlap": 50,
                },
            },
        }
