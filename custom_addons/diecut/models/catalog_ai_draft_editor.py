# -*- coding: utf-8 -*-

import json

from odoo import api, fields, models


class DiecutCatalogSourceDocumentDraftLine(models.Model):
    _name = "diecut.catalog.source.document.draft.line"
    _description = "AI/TDS 草稿参数编辑行"
    _order = "sequence, id"

    source_document_id = fields.Many2one(
        "diecut.catalog.source.document",
        string="来源文档",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="序号", default=10)
    item_code = fields.Char(string="型号")
    param_id = fields.Many2one("diecut.catalog.param", string="参数字典")
    param_key = fields.Char(string="参数键")
    param_name = fields.Char(string="参数名称")
    spec_category_name = fields.Char(string="参数分类")
    preferred_unit = fields.Char(string="字典单位")
    dictionary_status = fields.Selection(
        [
            ("existing", "复用现有"),
            ("new", "建议新建"),
            ("pending", "待确认"),
        ],
        string="参数状态",
        default="pending",
    )
    route_label = fields.Char(string="写入位置")
    value_display = fields.Char(string="值")
    unit = fields.Char(string="单位")
    condition_summary = fields.Char(string="条件摘要")
    test_method = fields.Char(string="测试方法")
    test_condition = fields.Char(string="测试条件")
    remark = fields.Text(string="备注")
    source_key = fields.Char(string="来源键")
    source_label = fields.Char(string="来源")
    candidate_new = fields.Boolean(string="建议新建")
    is_main_field = fields.Boolean(string="主字段")
    main_field_name = fields.Char(string="主字段名")
    value_type = fields.Char(string="值类型")
    method_html = fields.Html(string="方法卡片")

    @api.onchange("param_id")
    def _onchange_param_id(self):
        for line in self:
            param = line.param_id
            if not param:
                continue
            line.param_key = param.param_key
            line.param_name = param.name
            line.spec_category_name = param.spec_category_id.name if param.spec_category_id else False
            line.preferred_unit = param.preferred_unit or param.unit or ""
            if not line.unit:
                line.unit = param.preferred_unit or param.unit or ""
            line.dictionary_status = "existing"
            line.candidate_new = False
            line.is_main_field, line.main_field_name = line._resolve_param_route(
                param.param_key,
                existing_param=param,
            )
            line.route_label = line._route_label_for_param(
                param.param_key,
                existing_param=param,
            )
            line.value_type = param.value_type or False
            line.method_html = param.method_html or False

    @api.onchange("param_key")
    def _onchange_param_key(self):
        param_model = self.env["diecut.catalog.param"].sudo()
        for line in self:
            key = (line.param_key or "").strip().lower()
            if not key:
                line.param_id = False
                continue
            param = param_model.search([("param_key", "=", key)], limit=1)
            if param:
                line.param_id = param
                line._onchange_param_id()
            elif line.dictionary_status == "existing":
                line.dictionary_status = "pending"
                line.param_id = False


class DiecutCatalogSourceDocumentDraftEditor(models.Model):
    _inherit = "diecut.catalog.source.document"

    _CANONICAL_MAIN_FIELD_ROUTE_MAP = {
        "thickness": "thickness",
        "thickness_std": "thickness_std",
        "adhesive_thickness": "adhesive_thickness",
        "color": "color_id",
        "adhesive_type": "adhesive_type_id",
        "base_material": "base_material_id",
    }

    def _selection_catalog_status(self):
        return [
            ("draft", "草稿"),
            ("review", "评审中"),
            ("published", "已发布"),
            ("deprecated", "已停用"),
        ]

    def _selection_fire_rating(self):
        return [
            ("ul94_v0", "UL94 V-0"),
            ("ul94_v1", "UL94 V-1"),
            ("ul94_v2", "UL94 V-2"),
            ("ul94_hb", "UL94 HB"),
            ("none", "无"),
        ]

    @api.model
    def _canonical_main_field_route(self, param_key):
        key = (param_key or "").strip().lower()
        main_field_name = self._CANONICAL_MAIN_FIELD_ROUTE_MAP.get(key)
        if not main_field_name:
            return False, False
        return True, main_field_name

    @api.model
    def _resolve_param_route(self, param_key, meta_row=None, existing_param=None, *, is_main_field=None, main_field_name=None):
        canonical_is_main, canonical_field_name = self._canonical_main_field_route(param_key)
        if canonical_is_main:
            return canonical_is_main, canonical_field_name
        meta_row = meta_row if isinstance(meta_row, dict) else {}
        resolved_is_main = bool(
            is_main_field
            if is_main_field is not None
            else existing_param.is_main_field
            if existing_param
            else meta_row.get("is_main_field")
        )
        resolved_main_field = (
            main_field_name
            or (existing_param.main_field_name if existing_param else False)
            or meta_row.get("main_field_name")
            or False
        )
        return resolved_is_main, resolved_main_field

    @api.model
    def _route_label_for_param(self, param_key, meta_row=None, existing_param=None, *, is_main_field=None, main_field_name=None):
        resolved_is_main, resolved_main_field = self._resolve_param_route(
            param_key,
            meta_row=meta_row,
            existing_param=existing_param,
            is_main_field=is_main_field,
            main_field_name=main_field_name,
        )
        if resolved_is_main:
            return f"主表字段 / {resolved_main_field}" if resolved_main_field else "主表字段"
        return "参数值表"

    draft_item_name = fields.Char(string="名称")
    draft_item_code = fields.Char(string="型号")
    draft_series_name = fields.Char(string="系列")
    draft_catalog_status = fields.Selection(selection="_selection_catalog_status", string="目录状态")
    draft_manufacturer_id = fields.Many2one("res.partner", string="制造商", domain="[('is_company', '=', True)]")
    draft_manufacturer_name = fields.Char(string="制造商备用")
    draft_thickness = fields.Float(string="厚度")
    draft_thickness_std = fields.Char(string="厚度(标准)")
    draft_adhesive_thickness = fields.Float(string="胶层厚")
    draft_color_id = fields.Many2one("diecut.color", string="颜色")
    draft_color_name = fields.Char(string="颜色备用")
    draft_adhesive_type_id = fields.Many2one("diecut.catalog.adhesive.type", string="胶系")
    draft_adhesive_type_name = fields.Char(string="胶系备用")
    draft_base_material_id = fields.Many2one("diecut.catalog.base.material", string="基材")
    draft_base_material_name = fields.Char(string="基材备用")
    draft_ref_price = fields.Float(string="参考单价")
    draft_is_rohs = fields.Boolean(string="ROHS")
    draft_is_reach = fields.Boolean(string="REACH")
    draft_is_halogen_free = fields.Boolean(string="无卤")
    draft_fire_rating = fields.Selection(selection="_selection_fire_rating", string="防火等级")
    draft_equivalent_type = fields.Text(string="相当品(替代类型)")
    draft_special_applications = fields.Html(string="型号补充说明")
    draft_series_function_tags = fields.Char(string="系列功能标签", readonly=True)
    draft_series_application_tags = fields.Char(string="系列应用标签", readonly=True)
    draft_series_feature_tags = fields.Char(string="系列特性标签", readonly=True)
    draft_product_features = fields.Text(string="系列特性")
    draft_product_description = fields.Text(string="系列描述")
    draft_main_applications = fields.Html(string="系列主要应用")
    draft_line_ids = fields.One2many(
        "diecut.catalog.source.document.draft.line",
        "source_document_id",
        string="草稿参数",
        copy=False,
    )
    draft_editor_note = fields.Text(string="草稿编辑说明", compute="_compute_draft_editor_note")

    @api.depends("draft_payload", "draft_line_ids")
    def _compute_draft_editor_note(self):
        for record in self:
            try:
                payload = json.loads(record.draft_payload or "{}")
            except Exception:
                payload = {}
            item_count = len((payload or {}).get("items") or [])
            if item_count > 1:
                record.draft_editor_note = (
                    f"当前草稿包含 {item_count} 个型号。编辑器优先展示主型号，同时保留技术参数表里的型号列，"
                    "可以逐行人工修改参数、条件、测试方法和字典归属。"
                )
            else:
                record.draft_editor_note = (
                    "当前草稿可以按正式物料表单方式直接编辑。保存后会同步回结构化草稿 JSON，"
                    "再执行入库时会按最新编辑内容写入系统。"
                )

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("skip_draft_editor_sync"):
            return res
        if "draft_payload" in vals:
            self._sync_draft_editor_from_payload()
        return res

    def action_save_draft_editor(self):
        for record in self:
            payload = record._build_payload_from_draft_editor()
            record.with_context(skip_draft_editor_sync=True).write(
                {
                    "draft_payload": json.dumps(payload, ensure_ascii=False, indent=2),
                    "unmatched_payload": json.dumps(payload.get("unmatched") or [], ensure_ascii=False, indent=2),
                    "context_used": json.dumps(record._build_copilot_context(payload), ensure_ascii=False, indent=2),
                }
            )
            record._sync_draft_editor_from_payload()
            if hasattr(record, "_refresh_handbook_review_from_current_draft") and record.handbook_review_id:
                record._refresh_handbook_review_from_current_draft(
                    summary=record.result_message or False,
                    confidence=record.handbook_review_id.confidence or False,
                )
        return True

    def action_refresh_draft_editor(self):
        self._sync_draft_editor_from_payload()
        return True

    def action_apply_draft(self):
        self.action_save_draft_editor()
        return super().action_apply_draft()

    def _sync_draft_editor_from_payload(self):
        for record in self:
            try:
                payload = json.loads(record.draft_payload or "{}")
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}

            series_row = ((payload.get("series") or [{}])[:1] or [{}])[0] or {}
            item_row = ((payload.get("items") or [{}])[:1] or [{}])[0] or {}
            spec_rows = payload.get("spec_values") or []
            param_rows = payload.get("params") or []
            series_ref = record._find_editor_series(item_row, series_row)
            primary_code = (
                record._pick_first_non_empty(
                    item_row.get("code"),
                    item_row.get("item_code"),
                    next(
                        (
                            row.get("item_code")
                            for row in spec_rows
                            if isinstance(row, dict) and row.get("item_code")
                        ),
                        False,
                    ),
                )
                or False
            )

            line_commands = [(5, 0, 0)]
            param_map = {}
            for row in param_rows:
                if not isinstance(row, dict):
                    continue
                param_key = (row.get("param_key") or "").strip().lower()
                if param_key:
                    param_map[param_key] = row

            used_param_keys = set()
            sequence = 10
            for spec_row in spec_rows:
                if not isinstance(spec_row, dict):
                    continue
                param_key = (spec_row.get("param_key") or "").strip().lower()
                meta_row = param_map.get(param_key, {})
                line_commands.append(
                    (
                        0,
                        0,
                        record._draft_line_vals_from_payload_row(
                            meta_row=meta_row,
                            spec_row=spec_row,
                            fallback_item_code=primary_code,
                            sequence=sequence,
                        ),
                    )
                )
                if param_key:
                    used_param_keys.add(param_key)
                sequence += 10

            for param_key, meta_row in param_map.items():
                if param_key in used_param_keys:
                    continue
                line_commands.append(
                    (
                        0,
                        0,
                        record._draft_line_vals_from_payload_row(
                            meta_row=meta_row,
                            spec_row={},
                            fallback_item_code=primary_code,
                            sequence=sequence,
                        ),
                    )
                )
                sequence += 10

            manufacturer_name = record._pick_first_non_empty(
                item_row.get("manufacturer_name"),
                item_row.get("manufacturer"),
                item_row.get("maker_name"),
            )
            color_name = record._pick_first_non_empty(item_row.get("color_name"), item_row.get("color"))
            adhesive_type_name = record._pick_first_non_empty(
                item_row.get("adhesive_type_name"), item_row.get("adhesive_type")
            )
            base_material_name = record._pick_first_non_empty(
                item_row.get("base_material_name"), item_row.get("base_material")
            )
            header_vals = {
                "draft_item_name": record._pick_first_non_empty(item_row.get("name"), item_row.get("code")) or False,
                "draft_item_code": record._pick_first_non_empty(item_row.get("code"), primary_code) or False,
                "draft_series_name": record._pick_first_non_empty(
                    item_row.get("series_name"),
                    series_row.get("name"),
                    series_row.get("series_name"),
                )
                or False,
                "draft_catalog_status": item_row.get("catalog_status") or "draft",
                "draft_manufacturer_id": record._find_editor_company(manufacturer_name).id or False,
                "draft_manufacturer_name": manufacturer_name or False,
                "draft_thickness": record._safe_float_or_false(item_row.get("thickness")) or False,
                "draft_thickness_std": record._pick_first_non_empty(item_row.get("thickness_std")) or False,
                "draft_adhesive_thickness": record._safe_float_or_false(item_row.get("adhesive_thickness")) or False,
                "draft_color_id": record._find_editor_taxonomy("diecut.color", color_name).id or False,
                "draft_color_name": color_name or False,
                "draft_adhesive_type_id": record._find_editor_taxonomy(
                    "diecut.catalog.adhesive.type", adhesive_type_name
                ).id
                or False,
                "draft_adhesive_type_name": adhesive_type_name or False,
                "draft_base_material_id": record._find_editor_taxonomy(
                    "diecut.catalog.base.material", base_material_name
                ).id
                or False,
                "draft_base_material_name": base_material_name or False,
                "draft_ref_price": record._safe_float_or_false(item_row.get("ref_price")) or False,
                "draft_is_rohs": bool(item_row.get("is_rohs")),
                "draft_is_reach": bool(item_row.get("is_reach")),
                "draft_is_halogen_free": bool(item_row.get("is_halogen_free")),
                "draft_fire_rating": item_row.get("fire_rating") or "none",
                "draft_equivalent_type": item_row.get("equivalent_type") or False,
                "draft_special_applications": item_row.get("special_applications") or False,
                "draft_series_function_tags": ", ".join(series_ref.function_tag_ids.mapped("name")) if series_ref else False,
                "draft_series_application_tags": ", ".join(series_ref.application_tag_ids.mapped("name")) if series_ref else False,
                "draft_series_feature_tags": ", ".join(series_ref.feature_tag_ids.mapped("name")) if series_ref else False,
                "draft_product_features": record._series_features_text(series_row) or False,
                "draft_product_description": record._series_description_text(series_row) or False,
                "draft_main_applications": record._normalize_series_applications_field(
                    record._pick_first_non_empty(series_row.get("main_applications"), series_row.get("applications"))
                )
                or False,
                "draft_line_ids": line_commands,
            }
            record.with_context(skip_draft_editor_sync=True).write(header_vals)

    def _draft_line_vals_from_payload_row(self, meta_row, spec_row, fallback_item_code=False, sequence=10):
        meta_row = meta_row if isinstance(meta_row, dict) else {}
        spec_row = spec_row if isinstance(spec_row, dict) else {}
        param_key = (spec_row.get("param_key") or meta_row.get("param_key") or "").strip().lower()
        source_key = spec_row.get("source") or meta_row.get("source") or False
        existing_param = (
            self.env["diecut.catalog.param"].sudo().search([("param_key", "=", param_key)], limit=1)
            if param_key
            else False
        )
        existing_param = existing_param if existing_param and existing_param.exists() else self.env["diecut.catalog.param"]
        if source_key and hasattr(self, "_render_source_mark"):
            source_label = self._render_source_mark(source_key)
        else:
            source_label = source_key or ""
        dictionary_status = "new" if meta_row.get("candidate_new") else ("existing" if existing_param else "pending")
        merged_test_condition = self._merge_draft_condition_texts(
            spec_row.get("test_condition"),
            spec_row.get("condition_summary"),
        )
        resolved_is_main, resolved_main_field = self._resolve_param_route(
            param_key,
            meta_row=meta_row,
            existing_param=existing_param,
        )
        return {
            "sequence": sequence,
            "item_code": spec_row.get("item_code") or spec_row.get("code") or fallback_item_code or False,
            "param_id": existing_param.id or False,
            "param_key": param_key or False,
            "param_name": self._preview_value("spec_values", spec_row, "param_name")
            or meta_row.get("name")
            or (existing_param.name if existing_param else False)
            or param_key
            or "",
            "spec_category_name": meta_row.get("spec_category_name") or meta_row.get("spec_category") or "",
            "preferred_unit": meta_row.get("preferred_unit") or meta_row.get("unit") or (existing_param.preferred_unit if existing_param else False) or "",
            "dictionary_status": dictionary_status,
            "route_label": self._route_label_for_param(
                param_key,
                meta_row=meta_row,
                existing_param=existing_param,
            ),
            "value_display": self._preview_value("spec_values", spec_row, "display_value") if spec_row else "",
            "unit": self._normalize_optional_payload_text(
                spec_row.get("unit") or meta_row.get("preferred_unit") or meta_row.get("unit") or (existing_param.unit if existing_param else False)
            )
            or "",
            "condition_summary": "",
            "test_method": self._normalize_optional_payload_text(spec_row.get("test_method")) or "",
            "test_condition": merged_test_condition or "",
            "remark": self._normalize_optional_payload_text(spec_row.get("remark")) or "",
            "source_key": source_key or False,
            "source_label": source_label or "",
            "candidate_new": bool(meta_row.get("candidate_new")),
            "is_main_field": resolved_is_main,
            "main_field_name": resolved_main_field,
            "value_type": (existing_param.value_type if existing_param else False) or meta_row.get("value_type") or False,
            "method_html": (existing_param.method_html if existing_param else False) or meta_row.get("method_html") or False,
        }

    def _build_payload_from_draft_editor(self):
        self.ensure_one()
        base_payload = self._load_draft_payload()
        if not isinstance(base_payload, dict):
            base_payload = {}
        payload = {bucket: list(base_payload.get(bucket) or []) for bucket in self._DRAFT_BUCKETS}
        original_series = ((payload.get("series") or [{}])[:1] or [{}])[0] or {}
        original_item = ((payload.get("items") or [{}])[:1] or [{}])[0] or {}

        payload["series"] = [
            {
                **original_series,
                "brand_name": self.brand_id.name if self.brand_id else original_series.get("brand_name") or False,
                "series_name": self.draft_series_name or original_series.get("series_name") or False,
                "name": self.draft_series_name or original_series.get("name") or False,
                "product_description": self.draft_product_description or False,
                "description": self.draft_product_description or False,
                "product_features": self.draft_product_features or False,
                "features": [line.strip() for line in (self.draft_product_features or "").splitlines() if line.strip()],
                "main_applications": self.draft_main_applications or False,
                "applications": self._html_list_to_items(self.draft_main_applications),
            }
        ]

        payload["items"] = [
            {
                **original_item,
                "brand_name": self.brand_id.name if self.brand_id else original_item.get("brand_name") or False,
                "category_name": self.categ_id.name if self.categ_id else original_item.get("category_name") or False,
                "code": self.draft_item_code or False,
                "name": self.draft_item_name or self.draft_item_code or False,
                "series_name": self.draft_series_name or False,
                "catalog_status": self.draft_catalog_status or "draft",
                "manufacturer_name": self.draft_manufacturer_id.name or self.draft_manufacturer_name or False,
                "thickness": self.draft_thickness or False,
                "thickness_std": self.draft_thickness_std or False,
                "adhesive_thickness": self.draft_adhesive_thickness or False,
                "color_name": self.draft_color_id.name or self.draft_color_name or False,
                "adhesive_type_name": self.draft_adhesive_type_id.name or self.draft_adhesive_type_name or False,
                "base_material_name": self.draft_base_material_id.name or self.draft_base_material_name or False,
                "ref_price": self.draft_ref_price or False,
                "is_rohs": bool(self.draft_is_rohs),
                "is_reach": bool(self.draft_is_reach),
                "is_halogen_free": bool(self.draft_is_halogen_free),
                "fire_rating": self.draft_fire_rating or False,
                "equivalent_type": self.draft_equivalent_type or False,
                "special_applications": self.draft_special_applications or False,
            }
        ]

        params_by_key = {}
        spec_values = []
        existing_param_map = {
            (row.get("param_key") or "").strip().lower(): row
            for row in (base_payload.get("params") or [])
            if isinstance(row, dict) and row.get("param_key")
        }
        for line in self.draft_line_ids.sorted(key=lambda rec: (rec.sequence, rec.id)):
            selected_param = line.param_id
            param_key = (selected_param.param_key or line.param_key or "").strip().lower()
            if not param_key:
                continue
            meta = dict(existing_param_map.get(param_key) or {})
            resolved_is_main, resolved_main_field = self._resolve_param_route(
                param_key,
                meta_row=meta,
                existing_param=selected_param,
                is_main_field=line.is_main_field,
                main_field_name=line.main_field_name,
            )
            meta.update(
                {
                    "param_key": param_key,
                    "name": line.param_name or selected_param.name or meta.get("name") or param_key,
                    "spec_category_name": line.spec_category_name
                    or (selected_param.spec_category_id.name if selected_param.spec_category_id else False)
                    or meta.get("spec_category_name")
                    or meta.get("spec_category")
                    or False,
                    "preferred_unit": line.preferred_unit
                    or selected_param.preferred_unit
                    or selected_param.unit
                    or meta.get("preferred_unit")
                    or meta.get("unit")
                    or False,
                    "unit": line.preferred_unit or selected_param.unit or meta.get("unit") or False,
                    "is_main_field": resolved_is_main,
                    "main_field_name": resolved_main_field,
                    "value_type": line.value_type or selected_param.value_type or meta.get("value_type") or "char",
                    "method_html": line.method_html or selected_param.method_html or meta.get("method_html") or False,
                    "candidate_new": False if selected_param else (line.dictionary_status == "new" or bool(line.candidate_new)),
                }
            )
            params_by_key[param_key] = meta
            merged_test_condition = self._merge_draft_condition_texts(
                line.test_condition,
                line.condition_summary,
            )
            if any(
                value not in (False, None, "")
                for value in (
                    line.value_display,
                    line.unit,
                    line.test_method,
                    merged_test_condition,
                    line.remark,
                )
            ):
                spec_values.append(
                    {
                        "item_code": line.item_code or self.draft_item_code or False,
                        "param_key": param_key,
                        "param_name": line.param_name or selected_param.name or param_key,
                        "value": line.value_display or False,
                        "display_value": line.value_display or False,
                        "unit": line.unit or False,
                        "condition_summary": False,
                        "test_method": line.test_method or False,
                        "test_condition": merged_test_condition or False,
                        "remark": line.remark or False,
                        "source": line.source_key or False,
                    }
                )

        payload["params"] = list(params_by_key.values())
        payload["spec_values"] = spec_values
        return payload

    @api.model
    def _html_list_to_items(self, value):
        text = self._preview_text_from_rich_value(value)
        if not text:
            return []
        return [line.strip("-• ").strip() for line in text.splitlines() if line.strip()]

    @api.model
    def _normalize_text_value(self, value):
        if value in (False, None):
            return False
        text = str(value).strip()
        return text or False

    @api.model
    def _normalize_optional_payload_text(self, value):
        text = self._normalize_text_value(value)
        if not text:
            return False
        if text.lower() in {"false", "none", "null", "n/a"}:
            return False
        return text

    @api.model
    def _merge_draft_condition_texts(self, *values):
        parts = []
        seen = set()
        for value in values:
            text = self._normalize_optional_payload_text(value)
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            parts.append(text)
        return " | ".join(parts) if parts else False

    @api.model
    def _find_editor_taxonomy(self, model_name, name):
        text = self._normalize_text_value(name)
        if not text:
            return self.env[model_name]
        return self.env[model_name].sudo().search([("name", "=", text)], limit=1)

    @api.model
    def _find_editor_company(self, name):
        text = self._normalize_text_value(name)
        if not text:
            return self.env["res.partner"]
        return self.env["res.partner"].sudo().search(
            [("is_company", "=", True), ("name", "=", text)],
            limit=1,
        )

    def _find_editor_series(self, item_row, series_row):
        self.ensure_one()
        series_name = self._pick_first_non_empty(
            item_row.get("series_name") if isinstance(item_row, dict) else False,
            series_row.get("name") if isinstance(series_row, dict) else False,
            series_row.get("series_name") if isinstance(series_row, dict) else False,
            self.draft_series_name,
        )
        if not series_name:
            return self.env["diecut.catalog.series"]
        domain = [("name", "=", series_name)]
        if self.brand_id:
            domain.append(("brand_id", "=", self.brand_id.id))
        return self.env["diecut.catalog.series"].sudo().search(domain, limit=1)
