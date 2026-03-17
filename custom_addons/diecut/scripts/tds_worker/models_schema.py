# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConditionPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    state: str | None = None
    substrate: str | None = None
    temperature: str | None = None
    humidity: str | None = None
    duration: str | None = None
    block: str | None = None


class SeriesDraft(BaseModel):
    model_config = ConfigDict(extra="allow")

    series_name: str | None = None
    brand_name: str | None = None
    category_name: str | None = None

    product_description: str | None = None
    product_features: str | None = None
    main_applications: str | None = None
    special_applications: str | None = None

    source_page: int | None = None
    source_text: str | None = None
    source_label: str | None = None

    confidence: float | None = None
    review_note: str | None = None


class ItemDraft(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str | None = None
    name: str | None = None
    series_name: str | None = None
    brand_name: str | None = None
    category_name: str | None = None

    thickness: str | None = None
    thickness_std: str | None = None
    adhesive_thickness: str | None = None

    color_name: str | None = None
    adhesive_type_name: str | None = None
    base_material_name: str | None = None
    liner_material_name: str | None = None

    density: str | None = None
    hardness: str | None = None
    temperature_resistance: str | None = None
    item_features: str | None = None
    equivalent_notes: str | None = None

    source_page: int | None = None
    source_text: str | None = None
    source_label: str | None = None

    confidence: float | None = None
    review_note: str | None = None


class ParamDraft(BaseModel):
    model_config = ConfigDict(extra="allow")

    param_key: str | None = None
    name: str | None = None
    canonical_name_zh: str | None = None
    canonical_name_en: str | None = None

    value_type: str | None = None
    preferred_unit: str | None = None
    spec_category_name: str | None = None

    is_main_field: bool | None = None
    main_field_name: str | None = None

    method_html: str | None = None
    parse_hint: str | None = None

    source_page: int | None = None
    source_text: str | None = None
    source_label: str | None = None

    confidence: float | None = None
    review_note: str | None = None


class CategoryParamDraft(BaseModel):
    model_config = ConfigDict(extra="allow")

    category_name: str | None = None
    categ_name: str | None = None

    param_key: str | None = None
    param_name: str | None = None

    required: bool | None = None
    show_in_form: bool | None = None
    allow_import: bool | None = None
    unit_override: str | None = None

    source: str | None = None
    confidence: float | None = None
    review_note: str | None = None


class SpecValueDraft(BaseModel):
    model_config = ConfigDict(extra="allow")

    item_code: str | None = None
    series_name: str | None = None
    scope: Literal["item", "series"] | None = None

    param_key: str | None = None
    param_name: str | None = None

    value: str | float | int | None = None
    raw_value: str | None = None
    unit: str | None = None

    condition: ConditionPayload | dict[str, Any] | None = None

    test_method: str | None = None
    test_condition: str | None = None

    source_label: str | None = None
    source_page: int | None = None
    source_text: str | None = None

    confidence: float | None = None
    review_note: str | None = None


class UnmatchedDraft(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str | None = None
    source_label: str | None = None

    content: str | None = None
    source_page: int | None = None
    source_text: str | None = None

    reason: str | None = None
    candidate_param_key: str | None = None
    candidate_name: str | None = None

    confidence: float | None = None
    review_note: str | None = None


class TdsDraftPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series: list[SeriesDraft] = Field(default_factory=list)
    items: list[ItemDraft] = Field(default_factory=list)
    params: list[ParamDraft] = Field(default_factory=list)
    category_params: list[CategoryParamDraft] = Field(default_factory=list)
    spec_values: list[SpecValueDraft] = Field(default_factory=list)
    unmatched: list[UnmatchedDraft] = Field(default_factory=list)
