# -*- coding: utf-8 -*-

import json
import re
from datetime import datetime
from pathlib import Path

from odoo import api, models


class DiecutCatalogSourceDocumentApplyFix(models.Model):
    _inherit = "diecut.catalog.source.document"

    _CANONICAL_MAIN_FIELD_ROUTE_MAP = {
        "thickness": "thickness",
        "thickness_std": "thickness_std",
        "adhesive_thickness": "adhesive_thickness",
        "color": "color_id",
        "adhesive_type": "adhesive_type_id",
        "base_material": "base_material_id",
    }

    @api.model
    def _canonical_main_field_route(self, param_key):
        key = (param_key or "").strip().lower()
        main_field_name = self._CANONICAL_MAIN_FIELD_ROUTE_MAP.get(key)
        if not main_field_name:
            return False, False
        return True, main_field_name

    @api.model
    def _merge_spec_condition_text(self, *values):
        normalize = self.env["diecut.catalog.param"]._normalize_optional_text
        parts = []
        seen = set()
        for value in values:
            text = normalize(value)
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            parts.append(text)
        return " | ".join(parts) if parts else False

    @api.model
    def _spec_line_identity_key(self, *, spec_line_model, conditions=None, test_condition=None):
        conditions = conditions or []
        if conditions and hasattr(spec_line_model, "_condition_signature"):
            return ("conditions", spec_line_model._condition_signature(conditions))
        return ("text", spec_line_model._clean_placeholder_text(test_condition) or False)

    @api.model
    def _infer_brand_from_text_candidates(self, *values):
        """Infer brand from free-text candidates like 'tesa 4980'."""
        texts = []
        for value in values:
            text = str(value or "").strip()
            if text:
                texts.append(text.lower())
        if not texts:
            return False

        brand_model = self.env["diecut.brand"].sudo()
        brands = brand_model.search([])
        for brand in brands:
            name = (brand.name or "").strip().lower()
            if not name:
                continue
            for text in texts:
                if text == name or text.startswith(name + " ") or f" {name} " in f" {text} ":
                    return brand
        return False

    @api.model
    def _is_apply_failure_unmatched_row(self, row):
        if not isinstance(row, dict):
            return False
        reason = str(row.get("reason") or "").strip()
        source_excerpt = str(row.get("source_excerpt") or "").strip()
        has_apply_shape = ("item_code" in row) and ("param_key" in row)
        if has_apply_shape and reason:
            if "参数值无法落库" in reason or "参数值跳过" in reason or "参数值入库失败" in reason:
                return True
        if has_apply_shape and not reason and source_excerpt:
            return True
        return False

    def _get_apply_report_dir(self):
        report_dir = Path(__file__).resolve().parents[1] / "scripts" / "tds_import_drafts"
        report_dir.mkdir(parents=True, exist_ok=True)
        return report_dir

    def _write_apply_failed_rows_report(self, failed_rows):
        rows = failed_rows or []
        if not rows:
            return False
        report_dir = self._get_apply_report_dir()
        safe_name = re.sub(r"[^0-9A-Za-z._-]+", "_", self.name or f"source_{self.id}")
        filename = f"{safe_name}_apply_failed_rows_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path = report_dir / filename
        report_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return filename

    def _export_catalog_csv_after_apply(self):
        """Keep scripts CSVs in sync after apply, per user expectation."""
        wizard = self.env["diecut.catalog.ops.wizard"].sudo().create(
            {
                "operation": "export_csv",
                "dry_run": False,
            }
        )
        return wizard._export_csv()

    def _resolve_spec_target_item(self, row, item_map, fallback_code_map):
        brand = (
            self._resolve_brand(row.get("brand_name"))
            or self.brand_id
            or self._infer_brand_from_text_candidates(
                row.get("name"),
                row.get("series_name"),
                row.get("source_label"),
                self.name,
            )
        )
        code = (row.get("item_code") or row.get("code") or "").strip()
        if not code:
            # In single-item docs, series_name often equals the model code.
            code = (row.get("series_name") or "").strip()
        if not code:
            # Safe fallback: only when exactly one target item exists in current payload scope.
            unique_items = list(item_map.values())
            if len(unique_items) == 1:
                return unique_items[0], True, ""
            return False, False, ""

        direct = item_map.get((brand.id if brand else 0, code))
        if direct:
            return direct, False, code

        fallback_candidates = fallback_code_map.get(code) or []
        if len(fallback_candidates) == 1:
            return fallback_candidates[0], True, code
        return False, False, code

    def action_apply_draft(self):
        for record in self:
            payload = record._load_draft_payload()
            record._run_encoding_precheck(payload)
            original_unmatched = payload.get("unmatched") if isinstance(payload.get("unmatched"), list) else []
            apply_stats = record._apply_payload(payload)
            actual_stats = record._summarize_applied_payload(payload, apply_stats)
            skipped = int((actual_stats or {}).get("spec_values_skipped") or 0)
            fallback_applied = int((actual_stats or {}).get("spec_values_applied_by_fallback") or 0)
            failed_rows = (actual_stats or {}).get("apply_failed_rows") or []
            failed_report_file = record._write_apply_failed_rows_report(failed_rows)

            semantic_unmatched = []
            for row in payload.get("unmatched") or []:
                if not record._is_apply_failure_unmatched_row(row):
                    semantic_unmatched.append(row)
            if not semantic_unmatched and original_unmatched:
                semantic_unmatched = [row for row in original_unmatched if not record._is_apply_failure_unmatched_row(row)]

            message = (
                "AI/TDS 草稿已入库。 "
                f"spec_values_total={int((actual_stats or {}).get('spec_values_total') or 0)}; "
                f"applied={int((actual_stats or {}).get('spec_values_applied') or 0)}; "
                f"applied_by_fallback={fallback_applied}; skipped={skipped}; "
                f"apply_failed={len(failed_rows)}"
            )
            if failed_report_file:
                message = f"{message}; failed_report_file={failed_report_file}"

            try:
                record._export_catalog_csv_after_apply()
                message = f"{message}; csv_export=ok"
            except Exception as exc:
                message = f"{message}; csv_export=failed({str(exc)[:120]})"

            payload["unmatched"] = semantic_unmatched
            record.write(
                {
                    "import_status": "applied",
                    "result_message": message,
                    "draft_payload": json.dumps(payload, ensure_ascii=False, indent=2),
                    "unmatched_payload": json.dumps(semantic_unmatched, ensure_ascii=False, indent=2),
                    "context_used": json.dumps(record._build_copilot_context(payload), ensure_ascii=False, indent=2),
                }
            )
        return True

    def _summarize_applied_payload(self, payload, apply_stats=None):
        self.ensure_one()
        summary = dict(apply_stats or {})
        failed_rows = list(summary.get("apply_failed_rows") or [])
        spec_rows = payload.get("spec_values") or []
        summary["spec_values_total"] = len(spec_rows)

        item_model = self.env["diecut.catalog.item"].sudo()
        param_model = self.env["diecut.catalog.param"].sudo()
        spec_line_model = self.env["diecut.catalog.item.spec.line"].sudo()

        applied = 0
        verified_failed_rows = []
        for row in spec_rows:
            code = (row.get("item_code") or row.get("code") or "").strip()
            param_key = (row.get("param_key") or "").strip().lower()
            if not (code and param_key):
                applied += 0
                continue
            brand = self._resolve_brand(row.get("brand_name")) or self.brand_id
            item_domain = [("code", "=", code)]
            if brand:
                item_domain.append(("brand_id", "=", brand.id))
            item = item_model.search(item_domain, limit=1)
            param = param_model.search([("param_key", "=", param_key)], limit=1)
            if not (item and param):
                continue
            lines = spec_line_model.search([
                ("catalog_item_id", "=", item.id),
                ("param_id", "=", param.id),
            ])
            if not lines:
                continue
            conditions = row.get("conditions") or []
            merged_test_condition = self._merge_spec_condition_text(
                row.get("test_condition"),
                row.get("condition_summary"),
            )
            if conditions and hasattr(spec_line_model, "_condition_signature"):
                target_signature = spec_line_model._condition_signature(conditions)
                lines = lines.filtered(lambda line: spec_line_model._condition_signature([
                    {
                        "condition_key": condition.condition_key,
                        "condition_value": condition.condition_value,
                    }
                    for condition in line.condition_ids
                ]) == target_signature)
            elif conditions:
                lines = lines.filtered(lambda line: line.condition_ids)
            elif merged_test_condition:
                lines = lines.filtered(
                    lambda line: spec_line_model._clean_placeholder_text(line.test_condition) == merged_test_condition
                )
            else:
                lines = lines.filtered(
                    lambda line: not spec_line_model._clean_placeholder_text(line.test_condition)
                )
            matched = bool(lines[:1])
            if matched:
                applied += 1
            else:
                verified_failed_rows.append(
                    {
                        "item_code": code or False,
                        "param_key": param_key or False,
                        "reason": "参数值未找到对应已落库记录",
                        "source_excerpt": row.get("source_excerpt") or str(row)[:200],
                        "fallback_attempted": False,
                    }
                )

        if applied:
            failed_rows = verified_failed_rows
        summary["spec_values_applied"] = applied
        summary["spec_values_skipped"] = max(summary["spec_values_total"] - applied, 0)
        summary["apply_failed_rows"] = failed_rows
        return summary

    def _apply_payload(self, payload):
        self.ensure_one()
        param_model = self.env["diecut.catalog.param"].sudo()
        category_param_model = self.env["diecut.catalog.spec.def"].sudo()
        series_model = self.env["diecut.catalog.series"].sudo()
        category_model = self.env["diecut.catalog.param.category"].sudo()
        item_model = self.env["diecut.catalog.item"].sudo().with_context(
            skip_spec_autofill=True,
            allow_spec_categ_change=True,
        )
        apply_stats = {
            "spec_values_total": 0,
            "spec_values_applied": 0,
            "spec_values_skipped": 0,
            "spec_values_applied_by_fallback": 0,
            "apply_failed_rows": [],
        }
        unmatched = payload.setdefault("unmatched", [])
        if not isinstance(unmatched, list):
            unmatched = []
            payload["unmatched"] = unmatched

        param_map = {}
        for row in payload.get("params") or []:
            param_key = (row.get("param_key") or "").strip().lower()
            if not param_key:
                continue
            normalize_optional = param_model._normalize_optional_text
            canonical_is_main, canonical_main_field_name = self._canonical_main_field_route(param_key)
            method_html = row.get("method_html") or False
            description = normalize_optional(row.get("description"))
            if not description and method_html:
                description = normalize_optional(self._strip_html_markup(method_html)[:300])
            vals = {
                "name": row.get("name") or param_key,
                "param_key": param_key,
                "value_type": row.get("value_type") or "char",
                "description": description,
                "method_html": method_html,
                "unit": normalize_optional(row.get("unit")),
                "preferred_unit": normalize_optional(row.get("preferred_unit")) or normalize_optional(row.get("unit")) or False,
                "common_units": normalize_optional(row.get("common_units")),
                "canonical_name_zh": normalize_optional(row.get("canonical_name_zh")) or normalize_optional(row.get("name")) or False,
                "canonical_name_en": normalize_optional(row.get("canonical_name_en")),
                "aliases_text": normalize_optional(row.get("aliases_text")),
                "parse_hint": normalize_optional(row.get("parse_hint")),
                "is_main_field": canonical_is_main if canonical_is_main else bool(row.get("is_main_field")),
                "main_field_name": canonical_main_field_name or row.get("main_field_name") or False,
            }
            if row.get("spec_category_name"):
                spec_category = category_model.search([("name", "=", str(row["spec_category_name"]).strip())], limit=1)
                if spec_category:
                    vals["spec_category_id"] = spec_category.id
            param = param_model.search([("param_key", "=", param_key)], limit=1)
            if param:
                param.write(vals)
            else:
                param = param_model.create(vals)
            param_map[param_key] = param

        series_map = {}
        for row in payload.get("series") or []:
            brand = (
                self._resolve_brand(row.get("brand_name"))
                or self.brand_id
                or self._infer_brand_from_text_candidates(
                    row.get("name"),
                    row.get("series_name"),
                    self.name,
                )
            )
            series_name = (row.get("name") or row.get("series_name") or "").strip()
            if not (brand and series_name):
                continue
            series = series_model.search([("brand_id", "=", brand.id), ("name", "=", series_name)], limit=1)
            vals = {
                "brand_id": brand.id,
                "name": series_name,
                "product_features": self._normalize_series_text_field(
                    self._pick_first_non_empty(row.get("product_features"), row.get("features"))
                ),
                "product_description": self._normalize_series_text_field(
                    self._pick_first_non_empty(row.get("product_description"), row.get("description"))
                ),
                "main_applications": self._normalize_series_applications_field(
                    self._pick_first_non_empty(row.get("main_applications"), row.get("applications"))
                ),
            }
            if series:
                series.write(vals)
            else:
                series = series_model.create(vals)
            series_map[(brand.id, series_name)] = series

        for row in payload.get("category_params") or []:
            categ = self._resolve_category(row.get("category_name")) or self.categ_id
            param_key = (row.get("param_key") or "").strip().lower()
            param = param_map.get(param_key) or param_model.search([("param_key", "=", param_key)], limit=1)
            if not (categ and param):
                continue
            vals = {
                "categ_id": categ.id,
                "param_id": param.id,
                "name": param.name,
                "param_key": param.param_key,
                "value_type": param.value_type,
                "unit": param.unit,
                "selection_options": param.selection_options,
                "unit_override": row.get("unit_override") or False,
                "sequence": int(row.get("sequence") or 10),
                "required": bool(row.get("required")),
                "active": row.get("active", True),
                "show_in_form": row.get("show_in_form", True),
                "allow_import": row.get("allow_import", True),
            }
            config = category_param_model.search([("categ_id", "=", categ.id), ("param_id", "=", param.id)], limit=1)
            if config:
                config.write(vals)
            else:
                category_param_model.create(vals)

        item_map = {}
        for row in payload.get("items") or []:
            brand = (
                self._resolve_brand(row.get("brand_name"))
                or self.brand_id
                or self._infer_brand_from_text_candidates(
                    row.get("brand_name"),
                    row.get("name"),
                    row.get("code"),
                    row.get("series_name"),
                    self.name,
                )
            )
            code = (row.get("code") or "").strip()
            if not (brand and code):
                continue
            series_name = (row.get("series_name") or "").strip()
            series = series_map.get((brand.id, series_name)) if series_name else False
            if not series and series_name:
                series = series_model.search([("brand_id", "=", brand.id), ("name", "=", series_name)], limit=1)
            categ = self._resolve_category(row.get("category_name")) or self.categ_id
            vals = {
                "brand_id": brand.id,
                "code": code,
                "name": row.get("name") or code,
                "categ_id": categ.id if categ else False,
                "series_id": series.id if series else False,
                "catalog_status": row.get("catalog_status") or "draft",
            }
            item = item_model.search([("brand_id", "=", brand.id), ("code", "=", code)], limit=1)
            if item:
                item.write(vals)
            else:
                item = item_model.create(vals)
            if self.extracted_image and not item.catalog_structure_image:
                item.write({"catalog_structure_image": self.extracted_image})
            item_map[(brand.id, code)] = item

        fallback_code_map = {}
        for (_brand_id, code), item in item_map.items():
            fallback_code_map.setdefault(code, []).append(item)

        expected_spec_identities = {}
        for row in payload.get("spec_values") or []:
            apply_stats["spec_values_total"] += 1
            item, fallback_used, code = self._resolve_spec_target_item(row, item_map, fallback_code_map)
            param_key = (row.get("param_key") or "").strip().lower()
            param = param_map.get(param_key) or param_model.search([("param_key", "=", param_key)], limit=1)
            if not (item and param):
                apply_stats["spec_values_skipped"] += 1
                apply_stats["apply_failed_rows"].append(
                    {
                        "item_code": code or False,
                        "param_key": param_key or False,
                        "reason": "参数值无法落库：未匹配到型号或参数字典",
                        "source_excerpt": row.get("source_excerpt") or str(row)[:200],
                        "fallback_attempted": bool(code) or len(item_map) == 1,
                    }
                )
                continue

            ok, normalized_value, reject_reason = self._coerce_spec_raw_value(param, row)
            if not ok:
                apply_stats["spec_values_skipped"] += 1
                apply_stats["apply_failed_rows"].append(
                    {
                        "item_code": code or False,
                        "param_key": param.param_key,
                        "reason": f"参数值跳过：{reject_reason}",
                        "source_excerpt": row.get("source_excerpt") or str(row)[:200],
                        "fallback_attempted": bool(fallback_used),
                    }
                )
                continue

            try:
                merged_test_condition = self._merge_spec_condition_text(
                    row.get("test_condition"),
                    row.get("condition_summary"),
                )
                identity_key = self._spec_line_identity_key(
                    spec_line_model=self.env["diecut.catalog.item.spec.line"],
                    conditions=row.get("conditions") or [],
                    test_condition=merged_test_condition,
                )
                expected_spec_identities.setdefault((item.id, param.id), set()).add(identity_key)
                item.apply_param_payload(
                    param=param,
                    raw_value=normalized_value,
                    unit=row.get("unit"),
                    test_method=row.get("test_method"),
                    test_condition=merged_test_condition,
                    remark=row.get("remark"),
                    source_document=self,
                    source_excerpt=row.get("source_excerpt"),
                    confidence=row.get("confidence"),
                    is_ai_generated=True,
                    review_status=row.get("review_status") or "pending",
                    conditions=row.get("conditions") or [],
                )
                apply_stats["spec_values_applied"] += 1
                if fallback_used:
                    apply_stats["spec_values_applied_by_fallback"] += 1
            except Exception as exc:  # 防止单条异常阻断整批入库
                apply_stats["spec_values_skipped"] += 1
                apply_stats["apply_failed_rows"].append(
                    {
                        "item_code": code or False,
                        "param_key": param.param_key,
                        "reason": f"参数值入库失败：{str(exc)[:120]}",
                        "source_excerpt": row.get("source_excerpt") or str(row)[:200],
                        "fallback_attempted": bool(fallback_used),
                    }
                )

        spec_line_model = self.env["diecut.catalog.item.spec.line"].sudo()
        for (item_id, param_id), expected_keys in expected_spec_identities.items():
            stale_lines = spec_line_model.search(
                [
                    ("catalog_item_id", "=", item_id),
                    ("param_id", "=", param_id),
                    ("source_document_id", "=", self.id),
                    ("is_ai_generated", "=", True),
                ]
            ).filtered(
                lambda line: self._spec_line_identity_key(
                    spec_line_model=spec_line_model,
                    conditions=[
                        {
                            "condition_key": condition.condition_key,
                            "condition_value": condition.condition_value,
                        }
                        for condition in line.condition_ids
                    ],
                    test_condition=line.test_condition,
                )
                not in expected_keys
            )
            if stale_lines:
                stale_lines.unlink()

        if hasattr(self, "_extract_and_apply_method_images"):
            self._extract_and_apply_method_images(param_keys=set(param_map.keys()))
        return apply_stats
