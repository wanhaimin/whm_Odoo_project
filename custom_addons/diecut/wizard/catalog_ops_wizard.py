# -*- coding: utf-8 -*-

import base64
import csv
import io
import logging
import os
from pathlib import Path
from urllib.parse import quote

_logger = logging.getLogger(__name__)

from odoo import Command, fields, models
from odoo.exceptions import UserError
from odoo.modules.module import get_module_path

from ..tools import find_suspicious_text_entries, format_suspicious_entries, repair_mojibake_text, deep_repair_mojibake


class CatalogFieldInfo(models.TransientModel):
    _name = "diecut.catalog.field.info"
    _description = "目录字段元数据"

    wizard_id = fields.Many2one("diecut.catalog.ops.wizard", required=True, ondelete="cascade")
    model_name = fields.Selection(
        [
            ("diecut.catalog.item", "材料型号主表"),
            ("diecut.catalog.item.spec.line", "参数值表"),
            ("diecut.catalog.param", "参数字典"),
            ("diecut.catalog.param.category", "参数分类"),
            ("diecut.catalog.spec.def", "分类参数配置"),
            ("diecut.catalog.series", "系列字典"),
            ("diecut.catalog.source.document", "AI/TDS 草稿"),
        ],
        string="所属模型",
    )
    field_name = fields.Char(string="字段技术名")
    field_string = fields.Char(string="中文标签")
    field_type = fields.Char(string="字段类型")
    field_help = fields.Text(string="用途说明")


class CatalogOpsWizard(models.TransientModel):
    _name = "diecut.catalog.ops.wizard"
    _description = "数据运维向导"

    _CSV_READ_ENCODINGS = ("utf-8-sig", "utf-8")
    _PLACEHOLDER_TEXTS = {"false", "none", "null", "nil", "n/a", "na"}

    _MAIN_CSV_FILENAME = "catalog_items.csv"
    _SPEC_CSV_FILENAME = "catalog_item_specs.csv"
    _PARAM_CSV_FILENAME = "catalog_params.csv"
    _CATEGORY_PARAM_CSV_FILENAME = "catalog_category_params.csv"
    _SERIES_CSV_FILENAME = "catalog_series.csv"
    _MAIN_FIELD_PARAM_KEYS = {
        "thickness",
        "thickness_std",
        "adhesive_thickness",
        "color",
        "adhesive_type",
        "base_material",
        "ref_price",
        "is_rohs",
        "is_reach",
        "is_halogen_free",
        "fire_rating",
    }
    _SPEC_ONLY_PARAM_KEYS = {
        "density",
        "hardness",
        "compression_set",
        "rebound_rate",
        "peel_strength_180",
        "peel_strength",
        "foil_peel_strength",
        "initial_tack",
        "holding_power",
        "static_shear_70c",
        "thermal_conductivity_xy",
        "thermal_conductivity_z",
        "surface_resistance",
        "shielding_effectiveness",
        "breakdown_voltage",
        "dielectric_strength",
    }

    _FIELD_MANUAL_MODEL_FIELDS = {
        "diecut.catalog.item": (
            "active", "sequence", "brand_id", "categ_id", "code", "name", "series_id",
            "catalog_status", "extra_function_tag_ids", "extra_application_tag_ids", "extra_feature_tag_ids",
            "effective_function_tag_ids", "effective_application_tag_ids", "effective_feature_tag_ids",
            "selection_search_text", "special_applications",
            "tds_content", "msds_content", "datasheet_content",
            "diecut_properties", "equivalent_type", "erp_enabled", "erp_product_tmpl_id",
            "thickness", "adhesive_thickness", "color_id",
            "adhesive_type_id", "base_material_id", "thickness_std",
            "ref_price", "is_rohs", "is_reach", "is_halogen_free",
            "catalog_structure_image", "fire_rating",
        ),
        "diecut.catalog.item.spec.line": (
            "catalog_item_id", "param_id", "category_param_id", "categ_id", "sequence", "param_key",
            "param_name", "value_type", "value_kind", "value_raw", "value_number", "value_display",
            "condition_summary", "unit", "normalized_unit", "test_method", "test_condition", "remark",
            "source_document_id", "source_excerpt", "confidence", "is_ai_generated", "review_status",
        ),
        "diecut.catalog.param": (
            "name", "param_key", "spec_category_id", "canonical_name_zh", "canonical_name_en", "aliases_text",
            "value_type", "description", "unit", "preferred_unit", "common_units", "selection_options",
            "is_main_field", "main_field_name", "parse_hint",
            "target_bucket", "target_field", "scope_hint", "section_hints",
            "extraction_priority", "llm_enabled", "is_note_field", "is_method_field",
            "is_numeric_preferred", "allow_series_fallback", "confidence_rule",
            "sequence", "active",
            "category_config_count", "line_count",
        ),
        "diecut.catalog.param.category": (
            "name", "code", "parent_id", "description", "sequence", "active", "param_count",
        ),
        "diecut.catalog.series": (
            "name", "brand_id", "active", "sequence", "function_tag_ids", "application_tag_ids", "feature_tag_ids",
            "product_features", "product_description", "main_applications",
            "item_count",
        ),
        "diecut.catalog.source.document": (
            "name", "source_type", "source_url", "source_file", "source_filename", "brand_id", "categ_id",
            "parse_version", "import_status", "raw_text", "draft_payload", "result_message",
            "unmatched_payload", "line_count",
        ),
    }

    operation = fields.Selection(
        [
            ("export_csv", "导出 CSV（DB -> scripts）"),
            ("validate_csv", "校验 CSV（不入库）"),
            ("sync_csv_to_db", "CSV 同步入库（严格对齐）"),
            ("cutover_baseline_snapshot", "生成切换基线记录"),
            ("edit_csv", "CSV 轻量编辑"),
            ("view_fields_manual", "字段维护清单"),
        ],
        string="操作",
        required=True,
        default="export_csv",
    )
    csv_target = fields.Selection(
        [
            ("main", "主表 CSV"),
            ("spec", "参数值 CSV"),
            ("param", "参数字典 CSV"),
            ("category_param", "分类参数配置 CSV"),
            ("series", "系列字典 CSV"),
        ],
        string="编辑文件",
        default="main",
    )
    dry_run = fields.Boolean(string="预演", default=True)
    sync_scope = fields.Selection(
        [("all", "全量同步"), ("codes", "按型号同步"), ("category", "按分类同步")],
        string="同步范围",
        default="all",
    )
    sync_item_codes = fields.Text(string="限定型号")
    sync_categ_id = fields.Many2one("product.category", string="限定分类")
    backfill_limit = fields.Integer(string="统计上限", default=0)
    result_message = fields.Text(string="执行结果", readonly=True)
    guide_message = fields.Text(string="操作指南", readonly=True)
    csv_content = fields.Text(string="CSV 内容")
    validation_report_file = fields.Binary(string="校验报告", readonly=True, attachment=False)
    validation_report_filename = fields.Char(string="校验报告文件名", readonly=True)
    field_info_ids = fields.One2many("diecut.catalog.field.info", "wizard_id", string="字段清单")

    def _scripts_dir(self):
        module_dir = get_module_path("diecut")
        if not module_dir:
            raise UserError("未找到 diecut 模块目录。")
        return os.path.join(module_dir, "scripts")

    def _csv_path(self, target=None):
        mapping = {
            "main": self._MAIN_CSV_FILENAME,
            "spec": self._SPEC_CSV_FILENAME,
            "param": self._PARAM_CSV_FILENAME,
            "category_param": self._CATEGORY_PARAM_CSV_FILENAME,
            "series": self._SERIES_CSV_FILENAME,
        }
        selected = target or self.csv_target
        if selected not in mapping:
            raise UserError(f"不支持的 CSV 类型：{selected}")
        return os.path.join(self._scripts_dir(), mapping[selected])

    @classmethod
    def _read_csv_text(cls, path):
        csv_path = Path(path)
        raw = csv_path.read_bytes()
        last_error = None
        for encoding in cls._CSV_READ_ENCODINGS:
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError as exc:
                last_error = exc
        raise UserError("CSV 文件编码无法识别，请保存为 UTF-8 或 GB18030：%s" % csv_path.name) from last_error

    @classmethod
    def _read_csv_rows(cls, path):
        rows = list(csv.DictReader(io.StringIO(cls._read_csv_text(path))))
        return deep_repair_mojibake(rows)

    def _load_all_csv_rows(self):
        return {
            "main": self._read_csv_rows(self._csv_path("main")),
            "spec": self._read_csv_rows(self._csv_path("spec")),
            "param": self._read_csv_rows(self._csv_path("param")),
            "category_param": self._read_csv_rows(self._csv_path("category_param")),
            "series": self._read_csv_rows(self._csv_path("series")),
        }

    def _run_csv_encoding_precheck(self, rows_by_target):
        findings = []
        for target, rows in rows_by_target.items():
            for index, row in enumerate(rows, start=2):
                findings.extend(find_suspicious_text_entries(row, prefix=f"{target}[{index}]"))
        if findings:
            detail = format_suspicious_entries(findings)
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["message"])
            writer.writerow(["检测到疑似乱码或编码异常内容，已阻止导入。"])
            for line in detail.splitlines():
                writer.writerow([line])
            self.validation_report_file = base64.b64encode(output.getvalue().encode("utf-8-sig"))
            self.validation_report_filename = "catalog_encoding_precheck.csv"
            raise UserError("检测到疑似乱码或编码异常内容，请先修正后再继续。\n" + detail)

    def _run_csv_encoding_precheck_for_operation(self):
        rows_by_target = {
            "main": self._read_csv_rows(self._csv_path("main")),
            "spec": self._read_csv_rows(self._csv_path("spec")),
            "param": self._read_csv_rows(self._csv_path("param")),
            "category_param": self._read_csv_rows(self._csv_path("category_param")),
            "series": self._read_csv_rows(self._csv_path("series")),
        }
        self._run_csv_encoding_precheck(rows_by_target)

    @staticmethod
    def _norm(value):
        if value in (None, False):
            return ""
        text = repair_mojibake_text(str(value))
        normalized = text.replace("\r", "").strip()
        if normalized.casefold() in CatalogOpsWizard._PLACEHOLDER_TEXTS:
            return ""
        return normalized

    def _row_get(self, row, *keys):
        for key in keys:
            value = row.get(key)
            if self._norm(value):
                return value
        return False

    @staticmethod
    def _to_bool(value, default=False):
        raw = "" if value is None else str(value).strip().lower()
        if not raw:
            return default
        return raw in ("1", "true", "yes", "y", "是")

    @staticmethod
    def _to_float(value, default=0.0):
        raw = "" if value is None else str(value).strip()
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    @staticmethod
    def _db_key(brand_id, code):
        code_value = (code or "").strip()
        return f"{brand_id or 0}::{code_value.lower()}" if code_value else False

    def _record_domain_for_scope(self):
        if self.sync_scope == "codes":
            codes = [line.strip() for line in (self.sync_item_codes or "").splitlines() if line.strip()]
            return [("code", "in", codes or ["__empty__"])]
        if self.sync_scope == "category" and self.sync_categ_id:
            return [("categ_id", "child_of", self.sync_categ_id.id)]
        return []

    def _resolve_brand_from_row(self, row):
        xmlid = self._norm(row.get("brand_id_xml"))
        if xmlid:
            full = xmlid if "." in xmlid else f"diecut.{xmlid}"
            try:
                record = self.env.ref(full)
                if record and record._name == "diecut.brand":
                    return record
            except Exception:
                pass
        name = self._norm(row.get("brand_name"))
        if name:
            record = self.env["diecut.brand"].search([("name", "=", name)], limit=1)
            if record:
                return record
            if not self.dry_run:
                return self.env["diecut.brand"].create({"name": name})
        return False

    def _resolve_categ(self, xmlid):
        value = self._norm(xmlid)
        if not value:
            return False
        full = value if "." in value else f"diecut.{value}"
        try:
            record = self.env.ref(full)
            return record if record and record._name == "product.category" else False
        except Exception:
            _logger.debug("_resolve_categ: xmlid %r not found", full)
            return False

    def _resolve_or_create_series(self, brand, row):
        name = self._norm(row.get("series_name"))
        if not brand or not name:
            return False
        series = self.env["diecut.catalog.series"].search([("brand_id", "=", brand.id), ("name", "=", name)], limit=1)
        if series:
            return series
        if not self.dry_run:
            return self.env["diecut.catalog.series"].create({"brand_id": brand.id, "name": name})
        return False

    def _resolve_or_create_named_record(self, model_name, raw_name):
        name = self._norm(raw_name)
        if not name:
            return False
        model = self.env[model_name]
        record = model.search([("name", "=", name)], limit=1)
        if record:
            return record
        if not self.dry_run:
            return model.create({"name": name})
        return False

    def _resolve_or_create_param(self, row):
        param_model = self.env["diecut.catalog.param"]
        param_key = self._norm(row.get("param_key"))
        name = self._norm(row.get("name")) or self._norm(row.get("param_name")) or param_key
        if not (param_key or name):
            return False
        domain = [("param_key", "=", param_key)] if param_key else [("name", "=", name)]
        record = param_model.search(domain, limit=1)
        if record:
            return record
        if self.dry_run:
            return False
        spec_category_name = self._norm(row.get("spec_category"))
        spec_category = False
        if spec_category_name:
            spec_category = self.env["diecut.catalog.param.category"].search([("name", "=", spec_category_name)], limit=1)
            if not spec_category:
                spec_category = self.env["diecut.catalog.param.category"].create({"name": spec_category_name})
        return param_model.create(
            {
                "name": name,
                "param_key": param_key or name,
                "spec_category_id": spec_category.id if spec_category else False,
                "canonical_name_zh": self._norm(row.get("canonical_name_zh")) or name,
                "canonical_name_en": self._norm(row.get("canonical_name_en")) or False,
                "aliases_text": self._norm(row.get("aliases_text")) or False,
                "value_type": self._norm(row.get("value_type")) or "char",
                "description": self._norm(row.get("description")) or False,
                "unit": self._norm(row.get("unit")) or False,
                "preferred_unit": self._norm(row.get("preferred_unit")) or self._norm(row.get("unit")) or False,
                "common_units": self._norm(row.get("common_units")) or False,
                "selection_options": self._norm(row.get("selection_options")) or False,
                "is_main_field": self._to_bool(row.get("is_main_field")),
                "main_field_name": self._norm(row.get("main_field_name")) or False,
                "parse_hint": self._norm(row.get("parse_hint")) or False,
                "target_bucket": self._norm(row.get("target_bucket")) or "spec_values",
                "target_field": self._norm(row.get("target_field")) or False,
                "scope_hint": self._norm(row.get("scope_hint")) or "item",
                "section_hints": self._norm(row.get("section_hints")) or False,
                "extraction_priority": int(self._to_float(row.get("extraction_priority"), default=50)),
                "llm_enabled": self._to_bool(row.get("llm_enabled"), default=True),
                "is_note_field": self._to_bool(row.get("is_note_field")),
                "is_method_field": self._to_bool(row.get("is_method_field")),
                "is_numeric_preferred": self._to_bool(row.get("is_numeric_preferred")),
                "allow_series_fallback": self._to_bool(row.get("allow_series_fallback")),
                "confidence_rule": self._norm(row.get("confidence_rule")) or False,
                "sequence": int(self._to_float(row.get("sequence"), default=10)),
                "active": self._to_bool(row.get("active"), default=True),
            }
        )

    def _export_csv(self):
        os.makedirs(self._scripts_dir(), exist_ok=True)
        item_model = self.env["diecut.catalog.item"]
        items = item_model.search(self._record_domain_for_scope(), order="brand_id, sequence, id")
        params = self.env["diecut.catalog.param"].search([], order="sequence, id")
        category_params = self.env["diecut.catalog.spec.def"].search([], order="categ_id, sequence, id")
        series_list = self.env["diecut.catalog.series"].search([], order="brand_id, sequence, id")

        main_headers = [
            "brand_id_xml", "brand_name", "categ_id_xml", "series_name", "name", "code", "catalog_status",
            "active", "sequence", "equivalent_type", "product_features", "product_description",
            "main_applications", "special_applications", "thickness", "adhesive_thickness",
            "color_id", "adhesive_type_id", "base_material_id", "ref_price",
            "is_rohs", "is_reach", "is_halogen_free", "fire_rating",
        ]
        spec_headers = [
            "brand_id_xml", "brand_name", "categ_id_xml", "item_code", "param_key", "param_name", "value",
            "unit", "condition_summary", "test_method", "test_condition", "remark", "sequence",
        ]
        param_headers = [
            "param_key", "name", "spec_category", "canonical_name_zh", "canonical_name_en", "aliases_text",
            "value_type", "description", "unit", "preferred_unit", "common_units",
            "selection_options", "is_main_field", "main_field_name", "parse_hint",
            "target_bucket", "target_field", "scope_hint", "section_hints",
            "extraction_priority", "llm_enabled", "is_note_field", "is_method_field",
            "is_numeric_preferred", "allow_series_fallback", "confidence_rule",
            "sequence", "active"
        ]
        category_param_headers = [
            "categ_id_xml", "param_key", "param_name", "unit_override", "sequence", "required",
            "active", "show_in_form", "allow_import",
        ]
        series_headers = [
            "brand_id_xml", "brand_name", "series_name", "product_features",
            "product_description", "main_applications", "active", "sequence",
        ]

        main_rows, spec_rows, param_rows, category_param_rows, series_rows = [], [], [], [], []

        for item in items:
            brand_xml = item.brand_id.get_external_id().get(item.brand_id.id, "") if item.brand_id else ""
            categ_xml = item.categ_id.get_external_id().get(item.categ_id.id, "") if item.categ_id else ""
            brand_xml = brand_xml.split(".", 1)[1] if "." in brand_xml else brand_xml
            categ_xml = categ_xml.split(".", 1)[1] if "." in categ_xml else categ_xml
            main_rows.append(
                {
                    "brand_id_xml": brand_xml,
                    "brand_name": item.brand_id.name if item.brand_id else "",
                    "categ_id_xml": categ_xml,
                    "series_name": item.series_id.name if item.series_id else "",
                    "name": item.name or "",
                    "code": item.code or "",
                    "catalog_status": item.catalog_status or "",
                    "active": "1" if item.active else "0",
                    "sequence": str(item.sequence or 10),
                    "equivalent_type": item.equivalent_type or "",
                    "product_features": item.product_features or "",
                    "product_description": item.product_description or "",
                    "main_applications": item.main_applications or "",
                    "special_applications": item.special_applications or "",
                    "thickness": item.thickness or "",
                    "adhesive_thickness": item.adhesive_thickness or "",
                    "color_id": item.color_id.name if item.color_id else "",
                    "adhesive_type_id": item.adhesive_type_id.name if item.adhesive_type_id else "",
                    "base_material_id": item.base_material_id.name if item.base_material_id else "",
                    "ref_price": str(item.ref_price or 0.0),
                    "is_rohs": "1" if item.is_rohs else "0",
                    "is_reach": "1" if item.is_reach else "0",
                    "is_halogen_free": "1" if item.is_halogen_free else "0",
                    "fire_rating": item.fire_rating or "none",
                }
            )
            for line in item.spec_line_ids.sorted(lambda rec: (rec.sequence, rec.id)):
                spec_rows.append(
                    {
                        "brand_id_xml": brand_xml,
                        "brand_name": item.brand_id.name if item.brand_id else "",
                        "categ_id_xml": categ_xml,
                        "item_code": item.code or "",
                        "param_key": line.param_key or "",
                        "param_name": line.param_name or "",
                        "value": line.value_display or line.value_raw or "",
                        "unit": line.unit or "",
                        "condition_summary": line.condition_summary or "",
                        "test_method": line.test_method or "",
                        "test_condition": line.test_condition or "",
                        "remark": line.remark or "",
                        "sequence": str(line.sequence or 10),
                    }
                )

        for param in params:
            param_rows.append(
                {
                    "param_key": param.param_key or "",
                    "name": param.name or "",
                    "spec_category": param.spec_category_id.name if param.spec_category_id else "",
                    "canonical_name_zh": param.canonical_name_zh or "",
                    "canonical_name_en": param.canonical_name_en or "",
                    "aliases_text": param.aliases_text or "",
                    "value_type": param.value_type or "",
                    "description": param.description or "",
                    "unit": param.unit or "",
                    "preferred_unit": param.preferred_unit or "",
                    "common_units": param.common_units or "",
                    "selection_options": param.selection_options or "",
                    "is_main_field": "1" if param.is_main_field else "0",
                    "main_field_name": param.main_field_name or "",
                    "parse_hint": param.parse_hint or "",
                    "target_bucket": param.target_bucket or "",
                    "target_field": param.target_field or "",
                    "scope_hint": param.scope_hint or "",
                    "section_hints": param.section_hints or "",
                    "extraction_priority": str(param.extraction_priority or 0),
                    "llm_enabled": "1" if param.llm_enabled else "0",
                    "is_note_field": "1" if param.is_note_field else "0",
                    "is_method_field": "1" if param.is_method_field else "0",
                    "is_numeric_preferred": "1" if param.is_numeric_preferred else "0",
                    "allow_series_fallback": "1" if param.allow_series_fallback else "0",
                    "confidence_rule": param.confidence_rule or "",
                    "sequence": str(param.sequence or 10),
                    "active": "1" if param.active else "0",
                }
            )

        for category_param in category_params:
            categ_xml = category_param.categ_id.get_external_id().get(category_param.categ_id.id, "") if category_param.categ_id else ""
            categ_xml = categ_xml.split(".", 1)[1] if "." in categ_xml else categ_xml
            category_param_rows.append(
                {
                    "categ_id_xml": categ_xml,
                    "param_key": category_param.param_key or "",
                    "param_name": category_param.name or "",
                    "unit_override": category_param.unit_override or "",
                    "sequence": str(category_param.sequence or 10),
                    "required": "1" if category_param.required else "0",
                    "active": "1" if category_param.active else "0",
                    "show_in_form": "1" if category_param.show_in_form else "0",
                    "allow_import": "1" if category_param.allow_import else "0",
                }
            )

        for series in series_list:
            brand_xml = series.brand_id.get_external_id().get(series.brand_id.id, "") if series.brand_id else ""
            brand_xml = brand_xml.split(".", 1)[1] if "." in brand_xml else brand_xml
            series_rows.append(
                {
                    "brand_id_xml": brand_xml,
                    "brand_name": series.brand_id.name if series.brand_id else "",
                    "series_name": series.name or "",
                    "product_features": series.product_features or "",
                    "product_description": series.product_description or "",
                    "main_applications": series.main_applications or "",
                    "active": "1" if series.active else "0",
                    "sequence": str(series.sequence or 10),
                }
            )

        if not self.dry_run:
            for target, headers, rows in (
                ("main", main_headers, main_rows),
                ("spec", spec_headers, spec_rows),
                ("param", param_headers, param_rows),
                ("category_param", category_param_headers, category_param_rows),
                ("series", series_headers, series_rows),
            ):
                with open(self._csv_path(target), "w", encoding="utf-8-sig", newline="") as fp:
                    writer = csv.DictWriter(fp, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(rows)

        return (
            f"导出完成（{'预演' if self.dry_run else '已落地'}）\n"
            f"主表:{len(main_rows)} 参数值:{len(spec_rows)} 参数字典:{len(param_rows)} "
            f"分类参数配置:{len(category_param_rows)} 系列模板:{len(series_rows)}"
        )

    def _validate_csv_only(self, preloaded_rows=None):
        errors = []
        for target in ("main", "spec", "param", "category_param", "series"):
            if not os.path.exists(self._csv_path(target)):
                errors.append(f"{target} CSV 文件不存在。")

        if errors:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["message"])
            for error in errors:
                writer.writerow([error])
            self.validation_report_file = base64.b64encode(output.getvalue().encode("utf-8-sig"))
            self.validation_report_filename = "catalog_validation_report.csv"
            return "CSV 校验失败（未入库）\n" + "\n".join(errors[:30])

        rows = preloaded_rows or self._load_all_csv_rows()
        main_rows = rows["main"]
        param_rows = rows["param"]
        category_param_rows = rows["category_param"]

        self._run_csv_encoding_precheck(rows)
        for line_no, row in enumerate(main_rows, start=2):
            brand = self._resolve_brand_from_row(row)
            if not brand:
                errors.append(f"[{self._MAIN_CSV_FILENAME} 行{line_no}] 品牌不存在（brand_id_xml/brand_name）。")
            if not self._norm(row.get("series_name")):
                errors.append(f"[{self._MAIN_CSV_FILENAME} 行{line_no}] series_name 不能为空。")
            if not self._norm(row.get("code")):
                errors.append(f"[{self._MAIN_CSV_FILENAME} 行{line_no}] code 不能为空。")

        for line_no, row in enumerate(param_rows, start=2):
            if not (self._norm(row.get("param_key")) or self._norm(row.get("name"))):
                errors.append(f"[{self._PARAM_CSV_FILENAME} 行{line_no}] param_key 与 name 不能同时为空。")

        for line_no, row in enumerate(category_param_rows, start=2):
            categ_xml = self._norm(row.get("categ_id_xml"))
            # 允许空分类行存在（兼容历史/遗留数据），同步阶段将自动跳过。
            # 仅在“填写了分类但无法解析”时才报错阻断。
            if categ_xml and not self._resolve_categ(categ_xml):
                errors.append(f"[{self._CATEGORY_PARAM_CSV_FILENAME} 行{line_no}] 分类不存在。")
            if not self._norm(row.get("param_key")):
                errors.append(f"[{self._CATEGORY_PARAM_CSV_FILENAME} 行{line_no}] param_key 不能为空。")

        if errors:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["message"])
            for error in errors:
                writer.writerow([error])
            self.validation_report_file = base64.b64encode(output.getvalue().encode("utf-8-sig"))
            self.validation_report_filename = "catalog_validation_report.csv"
            return "CSV 校验失败（未入库）\n" + "\n".join(errors[:30])

        self.validation_report_file = False
        self.validation_report_filename = False
        return "CSV 校验通过（未入库）"

    def _sync_csv_to_db(self):
        rows = self._load_all_csv_rows()
        message = self._validate_csv_only(preloaded_rows=rows)
        if "失败" in message:
            return message

        main_rows = rows["main"]
        spec_rows = rows["spec"]
        param_rows = rows["param"]
        category_param_rows = rows["category_param"]
        series_rows = rows["series"]

        param_model = self.env["diecut.catalog.param"]
        for row in param_rows:
            param = self._resolve_or_create_param(row)
            if not param:
                continue
            spec_category_name = self._norm(row.get("spec_category"))
            spec_category = False
            if spec_category_name:
                spec_category = self.env["diecut.catalog.param.category"].search([("name", "=", spec_category_name)], limit=1)
                if not spec_category and not self.dry_run:
                    spec_category = self.env["diecut.catalog.param.category"].create({"name": spec_category_name})
            vals = {
                "name": self._norm(row.get("name")) or self._norm(row.get("param_key")),
                "param_key": self._norm(row.get("param_key")) or self._norm(row.get("name")),
                "spec_category_id": spec_category.id if spec_category else False,
                "canonical_name_zh": self._norm(row.get("canonical_name_zh")) or self._norm(row.get("name")) or self._norm(row.get("param_key")),
                "canonical_name_en": self._norm(row.get("canonical_name_en")) or False,
                "aliases_text": self._norm(row.get("aliases_text")) or False,
                "value_type": self._norm(row.get("value_type")) or "char",
                "description": self._norm(row.get("description")) or False,
                "unit": self._norm(row.get("unit")) or False,
                "preferred_unit": self._norm(row.get("preferred_unit")) or self._norm(row.get("unit")) or False,
                "common_units": self._norm(row.get("common_units")) or False,
                "selection_options": self._norm(row.get("selection_options")) or False,
                "is_main_field": self._to_bool(row.get("is_main_field")),
                "main_field_name": self._norm(row.get("main_field_name")) or False,
                "parse_hint": self._norm(row.get("parse_hint")) or False,
                "target_bucket": self._norm(row.get("target_bucket")) or "spec_values",
                "target_field": self._norm(row.get("target_field")) or False,
                "scope_hint": self._norm(row.get("scope_hint")) or "item",
                "section_hints": self._norm(row.get("section_hints")) or False,
                "extraction_priority": int(self._to_float(row.get("extraction_priority"), default=50)),
                "llm_enabled": self._to_bool(row.get("llm_enabled"), default=True),
                "is_note_field": self._to_bool(row.get("is_note_field")),
                "is_method_field": self._to_bool(row.get("is_method_field")),
                "is_numeric_preferred": self._to_bool(row.get("is_numeric_preferred")),
                "allow_series_fallback": self._to_bool(row.get("allow_series_fallback")),
                "confidence_rule": self._norm(row.get("confidence_rule")) or False,
                "sequence": int(self._to_float(row.get("sequence"), default=10)),
                "active": self._to_bool(row.get("active"), default=True),
            }
            record = param_model.search([("param_key", "=", vals["param_key"])], limit=1)
            if record and not self.dry_run:
                record.write(vals)

        category_param_model = self.env["diecut.catalog.spec.def"]
        for row in category_param_rows:
            categ = self._resolve_categ(row.get("categ_id_xml"))
            if not categ:
                continue
            param = self._resolve_or_create_param(row)
            if not param:
                continue
            vals = {
                "categ_id": categ.id,
                "param_id": param.id,
                "name": param.name,
                "param_key": param.param_key,
                "value_type": param.value_type,
                "unit": param.unit or False,
                "selection_options": param.selection_options or False,
                "unit_override": self._norm(row.get("unit_override")) or False,
                "sequence": int(self._to_float(row.get("sequence"), default=10)),
                "required": self._to_bool(row.get("required")),
                "active": self._to_bool(row.get("active"), default=True),
                "show_in_form": self._to_bool(row.get("show_in_form"), default=True),
                "allow_import": self._to_bool(row.get("allow_import"), default=True),
            }
            record = category_param_model.search([("categ_id", "=", categ.id), ("param_id", "=", param.id)], limit=1)
            if record:
                if not self.dry_run:
                    record.write(vals)
            elif not self.dry_run:
                category_param_model.create(vals)

        series_model = self.env["diecut.catalog.series"]
        for row in series_rows:
            brand = self._resolve_brand_from_row(row)
            if not brand:
                continue
            name = self._norm(row.get("series_name"))
            if not name:
                continue
            vals = {
                "brand_id": brand.id,
                "name": name,
                "product_features": self._norm(row.get("product_features")) or False,
                "product_description": self._norm(row.get("product_description")) or False,
                "main_applications": self._norm(row.get("main_applications")) or False,
                "active": self._to_bool(row.get("active"), default=True),
                "sequence": int(self._to_float(row.get("sequence"), default=10)),
            }
            record = series_model.search([("brand_id", "=", brand.id), ("name", "=", name)], limit=1)
            if record:
                if not self.dry_run:
                    record.write(vals)
            elif not self.dry_run:
                series_model.create(vals)

        item_model = self.env["diecut.catalog.item"].with_context(
            skip_spec_autofill=True,
            allow_spec_categ_change=True,
        )
        db_map = {}
        for item in item_model.search(self._record_domain_for_scope()):
            key = self._db_key(item.brand_id.id if item.brand_id else 0, item.code)
            if key:
                db_map[key] = item

        resolved_items = {}
        for row in main_rows:
            brand = self._resolve_brand_from_row(row)
            if not brand:
                continue
            code = self._norm(row.get("code"))
            if not code:
                continue
            series = self._resolve_or_create_series(brand, row)
            categ = self._resolve_categ(row.get("categ_id_xml"))
            color = self._resolve_or_create_named_record("diecut.color", self._row_get(row, "color_id"))
            adhesive = self._resolve_or_create_named_record("diecut.catalog.adhesive.type", self._row_get(row, "adhesive_type_id"))
            base_material = self._resolve_or_create_named_record("diecut.catalog.base.material", self._row_get(row, "base_material_id"))
            resolved_items[self._db_key(brand.id, code)] = {
                "brand_id": brand.id,
                "code": code,
                "name": self._norm(row.get("name")) or code,
                "categ_id": categ.id if categ else False,
                "series_id": series.id if series else False,
                "catalog_status": self._norm(row.get("catalog_status")) or "draft",
                "active": self._to_bool(row.get("active"), default=True),
                "sequence": int(self._to_float(row.get("sequence"), default=10)),
                "equivalent_type": self._norm(row.get("equivalent_type")) or False,
                "product_features": self._norm(row.get("product_features")) or False,
                "product_description": self._norm(row.get("product_description")) or False,
                "main_applications": self._norm(row.get("main_applications")) or False,
                "special_applications": self._norm(row.get("special_applications")) or False,
                "thickness": self._norm(self._row_get(row, "thickness")) or False,
                "adhesive_thickness": self._norm(self._row_get(row, "adhesive_thickness")) or False,
                "color_id": color.id if color else False,
                "adhesive_type_id": adhesive.id if adhesive else False,
                "base_material_id": base_material.id if base_material else False,
                "ref_price": self._to_float(self._row_get(row, "ref_price"), default=0.0),
                "is_rohs": self._to_bool(self._row_get(row, "is_rohs")),
                "is_reach": self._to_bool(self._row_get(row, "is_reach")),
                "is_halogen_free": self._to_bool(self._row_get(row, "is_halogen_free")),
                "fire_rating": self._norm(self._row_get(row, "fire_rating")) or "none",
            }

        if self.dry_run:
            return f"CSV 同步入库完成（预演）\n主表有效记录: {len(resolved_items)} 参数行数: {len(spec_rows)}"

        for key, vals in resolved_items.items():
            record = db_map.get(key)
            if record:
                record.write(vals)
            else:
                item_model.create(vals)
        deleted_keys = [k for k in db_map if k not in resolved_items]
        if deleted_keys:
            deleted_codes = ", ".join(k.split("::", 1)[-1] for k in deleted_keys[:20])
            _logger.info("sync_csv_to_db: deleting %d item(s) not in CSV: %s", len(deleted_keys), deleted_codes)
        for key in deleted_keys:
            db_map[key].unlink()

        item_map = {}
        for item in item_model.search(self._record_domain_for_scope()):
            key = self._db_key(item.brand_id.id if item.brand_id else 0, item.code)
            if key:
                item_map[key] = item

        grouped_specs = {}
        for row in spec_rows:
            brand = self._resolve_brand_from_row(row)
            key = self._db_key(brand.id if brand else 0, self._norm(row.get("item_code")))
            if key:
                grouped_specs.setdefault(key, []).append(row)

        for key, item in item_map.items():
            commands = [Command.clear()]
            effective_map = item._get_effective_importable_category_param_map(item.categ_id.id) if item.categ_id else {}
            for row in grouped_specs.get(key, []):
                param_key = self._norm(row.get("param_key"))
                param = self.env["diecut.catalog.param"].search([("param_key", "=", param_key)], limit=1)
                category_param = effective_map.get(param_key)
                if param and param.is_main_field:
                    item.apply_param_payload(
                        param=param,
                        raw_value=self._norm(row.get("value")),
                        unit=self._norm(row.get("unit")) or False,
                        test_method=self._norm(row.get("test_method")) or False,
                        test_condition=self._norm(row.get("test_condition")) or False,
                        remark=self._norm(row.get("remark")) or False,
                        review_status="confirmed",
                    )
                    continue
                if not category_param:
                    continue
                raw_value = self._norm(row.get("value"))
                commands.append(
                    Command.create(
                        {
                            "param_id": category_param.param_id.id,
                            "category_param_id": category_param.id,
                            "sequence": int(self._to_float(row.get("sequence"), default=category_param.sequence or 10)),
                            "param_key": category_param.param_key,
                            "param_name": category_param.name,
                            "value_kind": (
                                "number" if category_param.value_type == "float"
                                else "boolean" if category_param.value_type == "boolean"
                                else "selection" if category_param.value_type == "selection"
                                else "text"
                            ),
                            "value_raw": raw_value or False,
                            "value_number": self._to_float(raw_value) if category_param.value_type == "float" and raw_value else False,
                            "unit": self._norm(row.get("unit")) or category_param.unit_override or category_param.unit,
                            "test_method": self._norm(row.get("test_method")) or False,
                            "test_condition": self._norm(row.get("test_condition")) or False,
                            "remark": self._norm(row.get("remark")) or False,
                        }
                    )
                )
            item.write({"spec_line_ids": commands})

        return "CSV 同步入库完成（已执行）"

    def _write_log(self, success, detail, extra_vals=None):
        vals = {"operation": self.operation, "success": success, "detail": detail}
        if extra_vals:
            vals.update(extra_vals)
        self.env["diecut.catalog.ops.log"].create(vals)

    def _build_cutover_baseline(self, limit=None):
        catalog_model = self.env["diecut.catalog.item"]
        model_domain = [("code", "!=", False)]
        total_models = catalog_model.search_count(model_domain)
        duplicate_ids = catalog_model._get_duplicate_model_ids()
        missing_series_id = catalog_model.search_count([("code", "!=", False), ("series_id", "=", False)])
        sampled_models = catalog_model.search_count([("id", "in", catalog_model.search(model_domain, limit=limit).ids)]) if limit and limit > 0 else total_models
        return {
            "read_mode": "new_gray",
            "catalog_models": {
                "total": total_models,
                "sampled": sampled_models,
                "duplicate_code_count": len(duplicate_ids),
                "series_id_missing_count": missing_series_id,
            },
        }

    def action_show_guide(self):
        self.ensure_one()
        self.guide_message = (
            "【数据运维操作指南】\n"
            f"1) 导出五张 CSV：scripts/{self._MAIN_CSV_FILENAME}、scripts/{self._SPEC_CSV_FILENAME}、"
            f"scripts/{self._PARAM_CSV_FILENAME}、scripts/{self._CATEGORY_PARAM_CSV_FILENAME}、scripts/{self._SERIES_CSV_FILENAME}\n"
            "2) CSV 同步入库顺序：先参数字典 / 分类参数配置 / 系列字典，再主表与参数值。\n"
            "3) 主字段型参数会按参数字典路由写入主表；其余参数写入参数值表。\n"
            "4) AI/TDS 草稿请从“打开AI/TDS草稿”进入，先校验，再人工确认入库。"
        )
        return {
            "type": "ir.actions.act_window",
            "name": "数据运维",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_load_csv_editor(self):
        self.ensure_one()
        path = self._csv_path()
        if not os.path.exists(path):
            raise UserError(f"未找到文件：{path}")
        self.csv_content = self._read_csv_text(path)
        self.result_message = f"已加载 {os.path.basename(path)}。"
        return {
            "type": "ir.actions.act_window",
            "name": "数据运维",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_save_csv_editor(self):
        self.ensure_one()
        path = self._csv_path()
        if self.csv_content is None:
            raise UserError("没有可保存内容。")
        os.makedirs(self._scripts_dir(), exist_ok=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as fp:
            fp.write(self.csv_content.replace("\r\n", "\n"))
        self.result_message = f"已保存 {os.path.basename(path)}。"
        return {
            "type": "ir.actions.act_window",
            "name": "数据运维",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_open_aggrid_editor(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/diecut/catalog/csv-grid?file={quote(os.path.basename(self._csv_path()))}",
            "target": "new",
        }

    def action_open_source_documents(self):
        self.ensure_one()
        return self.env.ref("diecut.action_diecut_catalog_source_document").read()[0]

    def _collect_field_entries(self):
        entries = []
        for model_name, field_names in self._FIELD_MANUAL_MODEL_FIELDS.items():
            model = self.env[model_name]
            for field_name in field_names:
                field = model._fields.get(field_name)
                if not field:
                    continue
                entries.append(
                    {
                        "model_name": model_name,
                        "field_name": field_name,
                        "field_string": field.string or field_name,
                        "field_type": field.type,
                        "field_help": field.help or "",
                    }
                )
        entries.sort(key=lambda item: (item["model_name"], item["field_name"]))
        return entries

    def _reload_field_info_lines(self):
        self.ensure_one()
        commands = [fields.Command.clear()]
        commands.extend(fields.Command.create(vals) for vals in self._collect_field_entries())
        self.field_info_ids = commands

    def action_load_fields_manual(self):
        self.ensure_one()
        self._reload_field_info_lines()
        return {
            "type": "ir.actions.act_window",
            "name": "数据运维",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_execute(self):
        self.ensure_one()
        self.validation_report_file = False
        self.validation_report_filename = False
        log_extra = {}
        try:
            if self.operation in ("validate_csv", "sync_csv_to_db"):
                self._run_csv_encoding_precheck_for_operation()
            if self.operation == "export_csv":
                message = self._export_csv()
            elif self.operation == "validate_csv":
                message = self._validate_csv_only()
            elif self.operation == "sync_csv_to_db":
                message = self._sync_csv_to_db()
            elif self.operation == "cutover_baseline_snapshot":
                limit = self.backfill_limit if (self.backfill_limit or 0) > 0 else None
                payload = self._build_cutover_baseline(limit=limit)
                catalog_info = payload["catalog_models"]
                message = (
                    "切换基线记录已生成\n"
                    f"入口模式: {payload['read_mode']}\n"
                    f"型号总数: {catalog_info['total']}\n"
                    f"抽样条数: {catalog_info['sampled']}\n"
                    f"重复编码数: {catalog_info['duplicate_code_count']}\n"
                    f"series_id 缺失数: {catalog_info['series_id_missing_count']}"
                )
                log_extra = {
                    "read_mode": payload["read_mode"],
                    "shadow_model_count": catalog_info["total"],
                    "duplicate_brand_code_count": catalog_info["duplicate_code_count"],
                    "orphan_model_count": catalog_info["series_id_missing_count"],
                    "baseline_payload": str(payload),
                }
            elif self.operation == "view_fields_manual":
                self.action_load_fields_manual()
                message = "字段清单已刷新。"
            elif self.operation == "edit_csv":
                self.action_save_csv_editor()
                message = self.result_message or "CSV 已保存。"
            else:
                raise UserError("不支持的操作。")
            self.result_message = message
            self._write_log(True, message, log_extra)
        except Exception as exc:
            self.result_message = f"执行失败: {exc}"
            self.env.cr.rollback()
            try:
                self._write_log(False, self.result_message, log_extra)
            except Exception:
                pass
            raise
        return {
            "type": "ir.actions.act_window",
            "name": "数据运维",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
