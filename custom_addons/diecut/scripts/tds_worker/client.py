# -*- coding: utf-8 -*-
from __future__ import annotations

from abc import ABC, abstractmethod
import json
from typing import Any

import requests


class OdooClientError(RuntimeError):
    pass


class BaseOdooClient(ABC):
    @abstractmethod
    def pending_tasks(self, *, limit: int, include_draft: bool = True, source_document_id: int | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def mark_processing(self, *, source_document_id: int, worker_id: str, run_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def mark_parsed(self, *, source_document_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def mark_failed(self, *, source_document_id: int, error_code: str, error_message: str, debug_payload: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def submit_review(self, *, source_document_id: int) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def download_attachment(self, url: str) -> bytes:
        raise NotImplementedError


class HttpWorkerClient(BaseOdooClient):
    def __init__(self, base_url: str, token: str, db_name: str = "odoo"):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.db_name = db_name
        self.session = requests.Session()

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _request_json(self, path: str, payload: dict, timeout: int = 120):
        full_payload = {"db": self.db_name, "worker_token": self.token}
        full_payload.update(payload or {})
        try:
            response = self.session.post(
                self.base_url + path,
                headers=self.headers,
                data=json.dumps(full_payload, ensure_ascii=False).encode("utf-8"),
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            raise OdooClientError(f"HTTP API request failed: path={path}, err={exc}") from exc

    def _request_binary(self, url: str, timeout: int = 240) -> bytes:
        separator = "&" if "?" in url else "?"
        try:
            response = self.session.get(
                f"{url}{separator}worker_token={self.token}",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=timeout,
            )
            response.raise_for_status()
            return response.content
        except Exception as exc:
            raise OdooClientError(f"Attachment download failed: url={url}, err={exc}") from exc

    # Legacy compatibility methods.
    def post_json(self, path: str, payload: dict):
        return self._request_json(path, payload)

    def get_binary(self, url: str) -> bytes:
        return self._request_binary(url)

    def pending_tasks(self, *, limit: int, include_draft: bool = True, source_document_id: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"limit": int(limit), "include_draft": bool(include_draft)}
        if source_document_id:
            payload["source_document_id"] = int(source_document_id)
        return self._request_json("/api/material/extract/pending_tasks", payload)

    def mark_processing(self, *, source_document_id: int, worker_id: str, run_id: str) -> dict[str, Any]:
        return self._request_json(
            "/api/material/extract/mark_processing",
            {
                "source_document_id": int(source_document_id),
                "worker_id": worker_id,
                "run_id": run_id,
            },
        )

    def mark_parsed(self, *, source_document_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        request_payload = {"source_document_id": int(source_document_id)}
        request_payload.update(payload or {})
        return self._request_json("/api/material/extract/mark_parsed", request_payload)

    def mark_failed(self, *, source_document_id: int, error_code: str, error_message: str, debug_payload: str) -> dict[str, Any]:
        return self._request_json(
            "/api/material/extract/mark_failed",
            {
                "source_document_id": int(source_document_id),
                "error_code": error_code,
                "error_message": error_message,
                "debug_payload": debug_payload,
            },
        )

    def submit_review(self, *, source_document_id: int) -> dict[str, Any]:
        return self._request_json("/api/material/material/submit_review", {"source_document_id": int(source_document_id)})

    def download_attachment(self, url: str) -> bytes:
        return self._request_binary(url)


class XmlRpcOdooClient(BaseOdooClient):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def pending_tasks(self, *, limit: int, include_draft: bool = True, source_document_id: int | None = None) -> dict[str, Any]:
        raise NotImplementedError("XmlRpcOdooClient is a placeholder; use transport='http' for now.")

    def mark_processing(self, *, source_document_id: int, worker_id: str, run_id: str) -> dict[str, Any]:
        raise NotImplementedError("XmlRpcOdooClient is a placeholder; use transport='http' for now.")

    def mark_parsed(self, *, source_document_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("XmlRpcOdooClient is a placeholder; use transport='http' for now.")

    def mark_failed(self, *, source_document_id: int, error_code: str, error_message: str, debug_payload: str) -> dict[str, Any]:
        raise NotImplementedError("XmlRpcOdooClient is a placeholder; use transport='http' for now.")

    def submit_review(self, *, source_document_id: int) -> dict[str, Any]:
        raise NotImplementedError("XmlRpcOdooClient is a placeholder; use transport='http' for now.")

    def download_attachment(self, url: str) -> bytes:
        raise NotImplementedError("XmlRpcOdooClient is a placeholder; use transport='http' for now.")


def create_odoo_client(base_url: str, token: str, db_name: str = "odoo", transport: str = "http") -> BaseOdooClient:
    mode = (transport or "http").strip().lower()
    if mode == "http":
        return HttpWorkerClient(base_url=base_url, token=token, db_name=db_name)
    if mode == "xmlrpc":
        return XmlRpcOdooClient(base_url=base_url, token=token, db_name=db_name)
    raise ValueError(f"Unsupported Odoo client transport: {transport}")


# Backward-compatible alias used by existing imports.
OdooWorkerClient = HttpWorkerClient
