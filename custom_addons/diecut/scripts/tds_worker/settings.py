# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WorkerSettings:
    gateway_url: str
    gateway_token: str
    agent_id: str
    model: str
    odoo_base_url: str
    odoo_db: str
    odoo_transport: str
    worker_token: str
    prefer_single_pass: bool = True
    fast_mode: bool = True
    pdf_max_text_pages_fast: int = 3
    pdf_max_text_pages_full: int = 8
    pdf_max_image_pages_fast: int = 0
    pdf_max_image_pages_full: int = 3
    single_pass_timeout_fast: int = 120
    single_pass_timeout_full: int = 480
    vision_timeout: int = 720
    struct_timeout: int = 900


def _truthy(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in ("0", "false", "no")


def load_openclaw_config() -> dict:
    cfg_path = Path.home() / ".openclaw" / "openclaw.json"
    if not cfg_path.exists():
        return {}
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_settings(
    odoo_base_url: str | None = None,
    worker_token: str | None = None,
    db_name: str | None = None,
) -> WorkerSettings:
    config = load_openclaw_config()
    gateway_port = (((config.get("gateway") or {}).get("port")) or 18789)
    gateway_url = os.environ.get("OPENCLAW_GATEWAY_URL") or f"ws://127.0.0.1:{gateway_port}"
    gateway_token = (
        os.environ.get("OPENCLAW_GATEWAY_TOKEN")
        or (((config.get("gateway") or {}).get("auth") or {}).get("token"))
        or config.get("gatewayToken")
        or ""
    )
    odoo_transport = (
        os.environ.get("ODOO_CLIENT_TRANSPORT")
        or os.environ.get("OPENCLAW_ODOO_TRANSPORT")
        or "http"
    ).strip().lower()
    if odoo_transport not in ("http", "xmlrpc", "jsonrpc"):
        odoo_transport = "http"

    return WorkerSettings(
        gateway_url=gateway_url,
        gateway_token=gateway_token,
        agent_id=os.environ.get("OPENCLAW_AGENT_ID") or "odoo-diecut-dev",
        model=os.environ.get("OPENCLAW_MODEL") or "openai-codex/gpt-5.4",
        odoo_base_url=odoo_base_url or os.environ.get("ODOO_BASE_URL", "http://localhost:8070"),
        odoo_db=db_name or os.environ.get("ODOO_DB", "odoo"),
        odoo_transport=odoo_transport,
        worker_token=worker_token or os.environ.get("DIECUT_TDS_WORKER_TOKEN") or os.environ.get("OPENCLAW_GATEWAY_TOKEN", ""),
        prefer_single_pass=_truthy(os.environ.get("OPENCLAW_SINGLE_PASS"), True),
        fast_mode=_truthy(os.environ.get("OPENCLAW_FAST_MODE"), True),
    )
