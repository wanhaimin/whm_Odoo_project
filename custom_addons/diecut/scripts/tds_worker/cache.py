# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CACHE_DIR = Path(__file__).resolve().parents[1] / ".tds_worker_cache"

EXTRACT_VERSION = "extract-v1"
VISION_PROMPT_VERSION = "vision-prompt-v1"
STRUCT_PROMPT_VERSION = "struct-prompt-v1"
SINGLE_PROMPT_VERSION = "single-prompt-v2-slim"
UNDERSTANDING_PROMPT_VERSION = "understanding-prompt-v1"


def ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def stable_json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(payload: Any) -> str:
    return sha256_text(stable_json_dumps(payload))


def _cache_path(namespace: str, cache_key: str) -> Path:
    ensure_cache_dir()
    return CACHE_DIR / namespace / f"{cache_key}.json"


def load_json_cache(namespace: str, cache_key: str) -> dict[str, Any] | None:
    path = _cache_path(namespace, cache_key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_json_cache(namespace: str, cache_key: str, payload: dict[str, Any]):
    path = _cache_path(namespace, cache_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_extract_cache_key(source_document_id: int, file_hash: str, fast_mode: bool) -> str:
    mode = "fast" if fast_mode else "full"
    return f"{source_document_id}__{file_hash}__{EXTRACT_VERSION}__{mode}"


def build_vision_cache_key(source_document_id: int, file_hash: str, model: str, context_signature: str) -> str:
    model_slug = model.replace("/", "_")
    return f"{source_document_id}__{file_hash}__{model_slug}__{VISION_PROMPT_VERSION}__{context_signature}"


def build_struct_cache_key(
    source_document_id: int,
    file_hash: str,
    model: str,
    context_signature: str,
    vision_signature: str,
) -> str:
    model_slug = model.replace("/", "_")
    return (
        f"{source_document_id}__{file_hash}__{model_slug}__{STRUCT_PROMPT_VERSION}"
        f"__{context_signature}__{vision_signature}"
    )


def build_single_cache_key(
    source_document_id: int,
    file_hash: str,
    model: str,
    context_signature: str,
    fast_mode: bool,
) -> str:
    model_slug = model.replace("/", "_")
    mode = "fast" if fast_mode else "full"
    return (
        f"{source_document_id}__{file_hash}__{model_slug}__{SINGLE_PROMPT_VERSION}"
        f"__{context_signature}__{mode}"
    )


def build_understanding_cache_key(source_document_id: int, file_hash: str, model: str, context_signature: str) -> str:
    model_slug = model.replace("/", "_")
    return (
        f"{source_document_id}__{file_hash}__{model_slug}__{UNDERSTANDING_PROMPT_VERSION}"
        f"__{context_signature}"
    )
