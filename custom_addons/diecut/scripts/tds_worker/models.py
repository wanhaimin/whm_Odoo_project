# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskContext:
    raw: dict[str, Any]
    normalized: dict[str, Any]


@dataclass
class ExtractedDocument:
    raw_text: str = ""
    attachments: list[dict[str, Any]] = field(default_factory=list)
    page_count: int = 0
    source_filename: str = ""
    mime_type: str = ""
    file_hash: str = ""
    used_cache: bool = False


@dataclass
class PipelineResult:
    source_document_id: int
    mode: str
    raw_len: int
    image_pages: int
    vision_payload: dict[str, Any]
    draft_payload: dict[str, Any]
    context_used: dict[str, Any]
    metrics: dict[str, Any] = field(default_factory=dict)
