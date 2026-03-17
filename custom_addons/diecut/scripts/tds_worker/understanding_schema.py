# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DocumentMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    doc_type: Literal["tds", "brochure", "msds", "webpage", "unknown"] | str | None = None
    source_type: Literal["pdf", "image", "ocr", "web"] | str | None = None
    brand_name: str | None = None
    series_name: str | None = None
    title: str | None = None
    language: str | None = None
    page_count: int | None = None
    material_family: str | None = None
    is_series_document: bool | None = None
    is_multi_item_document: bool | None = None
    confidence: float | None = None


class SectionBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    section_id: str | None = None
    page: int | None = None
    section_type: str | None = None
    section_title: str | None = None
    text: str | None = None
    source_text: str | None = None
    scope: Literal["series", "item", "mixed", "unknown"] | None = None
    confidence: float | None = None


class TableBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    table_id: str | None = None
    page: int | None = None
    table_type: str | None = None
    title: str | None = None
    headers: list[str] = Field(default_factory=list)
    row_labels: list[str] = Field(default_factory=list)
    units: dict[str, str] = Field(default_factory=dict)
    raw_cells: list[list[str]] = Field(default_factory=list)
    source_text: str | None = None
    confidence: float | None = None


class CandidateItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    item_code: str | None = None
    item_name: str | None = None
    series_name: str | None = None
    page: int | None = None
    source: str | None = None
    source_text: str | None = None
    confidence: float | None = None


class CandidateFact(BaseModel):
    model_config = ConfigDict(extra="allow")

    fact_id: str | None = None
    page: int | None = None
    section_id: str | None = None
    table_id: str | None = None
    scope: Literal["series", "item", "mixed", "unknown"] | None = None
    item_code: str | None = None
    series_name: str | None = None
    label: str | None = None
    normalized_concept: str | None = None
    value: str | float | int | None = None
    raw_value: str | None = None
    unit: str | None = None
    source_text: str | None = None
    mapping_reason: str | None = None
    confidence: float | None = None


class CandidateContent(BaseModel):
    model_config = ConfigDict(extra="allow")

    content_id: str | None = None
    page: int | None = None
    section_id: str | None = None
    content_type: str | None = None
    scope: Literal["series", "item", "mixed", "unknown"] | None = None
    item_code: str | None = None
    text: str | None = None
    source_text: str | None = None
    mapping_reason: str | None = None
    confidence: float | None = None


class MethodBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    method_id: str | None = None
    page: int | None = None
    method_name: str | None = None
    related_concept: str | None = None
    text: str | None = None
    source_text: str | None = None
    confidence: float | None = None


class UnresolvedBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    page: int | None = None
    section_id: str | None = None
    problem_type: str | None = None
    content: str | None = None
    reason: str | None = None
    candidate_concept: str | None = None
    source_text: str | None = None
    confidence: float | None = None


class DocumentUnderstandingPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    document_meta: DocumentMeta = Field(default_factory=DocumentMeta)
    sections: list[SectionBlock] = Field(default_factory=list)
    tables: list[TableBlock] = Field(default_factory=list)
    candidate_items: list[CandidateItem] = Field(default_factory=list)
    candidate_facts: list[CandidateFact] = Field(default_factory=list)
    candidate_content: list[CandidateContent] = Field(default_factory=list)
    methods: list[MethodBlock] = Field(default_factory=list)
    unresolved: list[UnresolvedBlock] = Field(default_factory=list)


def normalize_understanding_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    value = payload if isinstance(payload, dict) else {}
    try:
        return DocumentUnderstandingPayload.model_validate(value).model_dump(mode="python")
    except Exception:
        # lenient fallback
        return {
            "document_meta": value.get("document_meta") if isinstance(value.get("document_meta"), dict) else {},
            "sections": value.get("sections") if isinstance(value.get("sections"), list) else [],
            "tables": value.get("tables") if isinstance(value.get("tables"), list) else [],
            "candidate_items": value.get("candidate_items") if isinstance(value.get("candidate_items"), list) else [],
            "candidate_facts": value.get("candidate_facts") if isinstance(value.get("candidate_facts"), list) else [],
            "candidate_content": value.get("candidate_content") if isinstance(value.get("candidate_content"), list) else [],
            "methods": value.get("methods") if isinstance(value.get("methods"), list) else [],
            "unresolved": value.get("unresolved") if isinstance(value.get("unresolved"), list) else [],
        }
