# -*- coding: utf-8 -*-

import re

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


class DiecutCatalogItem(models.Model):
    _name = "diecut.catalog.item"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "材料选型目录"
    _order = "brand_id, sequence, id"

    _SERIES_TEMPLATE_FIELDS = ("product_features", "product_description", "main_applications")
    _PLACEHOLDER_TEXTS = {"false", "none", "null"}
    _SERIES_DEFAULT_TAG_FIELDS = (
        ("function_tag_ids", "default_function_tag_ids"),
        ("application_tag_ids", "default_application_tag_ids"),
        ("feature_tag_ids", "default_feature_tag_ids"),
    )

    name = fields.Char(string="名称", required=True)
    active = fields.Boolean(string="启用", default=True)
    sequence = fields.Integer(string="排序", default=10)

    brand_id = fields.Many2one("diecut.brand", string="品牌", required=True, index=True)
    manufacturer_id = fields.Many2one(
        "res.partner",
        string="制造商",
        domain="[('is_company', '=', True)]",
    )
    categ_id = fields.Many2one("product.category", string="材料分类", index=True)

    code = fields.Char(string="型号", index=True)
    series_id = fields.Many2one(
        "diecut.catalog.series",
        string="系列",
        domain="[('brand_id', '=', brand_id)]",
        index=True,
    )
    tds_content = fields.Html(string="TDS技术数据表")
    msds_content = fields.Html(string="MSDS安全数据表")
    datasheet_content = fields.Html(string="规格书")
    diecut_properties = fields.Properties(
        string="物理特性参数",
        definition="categ_id.diecut_properties_definition",
        copy=True,
    )
    product_features = fields.Text(string="系列特性", help="来自系列模板的共性特性，主要用于继承和导入兼容。")
    product_description = fields.Text(string="系列说明", help="来自系列模板的系列级说明，主要用于继承和导入兼容。")
    main_applications = fields.Html(string="系列主要应用", help="来自系列模板的主要应用说明。")
    special_applications = fields.Html(string="型号补充说明", help="用于记录当前型号相对系列模板的补充说明、差异点或应用备注。")
    function_tag_ids = fields.Many2many(
        "product.tag",
        "diecut_catalog_item_function_tag_rel",
        "catalog_item_id",
        "tag_id",
        string="功能标签",
    )
    application_tag_ids = fields.Many2many(
        "diecut.catalog.application.tag",
        "diecut_catalog_item_application_tag_rel",
        "catalog_item_id",
        "tag_id",
        string="应用标签",
    )
    feature_tag_ids = fields.Many2many(
        "diecut.catalog.feature.tag",
        "diecut_catalog_item_feature_tag_rel",
        "catalog_item_id",
        "tag_id",
        string="特性标签",
    )
    extra_function_tag_ids = fields.Many2many(
        "product.tag",
        string="型号追加功能标签",
        compute="_compute_item_tag_aliases",
        inverse="_inverse_item_tag_aliases",
    )
    extra_application_tag_ids = fields.Many2many(
        "diecut.catalog.application.tag",
        string="型号追加应用标签",
        compute="_compute_item_tag_aliases",
        inverse="_inverse_item_tag_aliases",
    )
    extra_feature_tag_ids = fields.Many2many(
        "diecut.catalog.feature.tag",
        string="型号追加特性标签",
        compute="_compute_item_tag_aliases",
        inverse="_inverse_item_tag_aliases",
    )
    series_function_tag_ids = fields.Many2many(
        "product.tag",
        string="系列功能标签",
        compute="_compute_series_tag_views",
    )
    series_application_tag_ids = fields.Many2many(
        "diecut.catalog.application.tag",
        string="系列应用标签",
        compute="_compute_series_tag_views",
    )
    series_feature_tag_ids = fields.Many2many(
        "diecut.catalog.feature.tag",
        string="系列特性标签",
        compute="_compute_series_tag_views",
    )
    effective_function_tag_ids = fields.Many2many(
        "product.tag",
        "diecut_catalog_item_effective_function_tag_rel",
        "catalog_item_id",
        "tag_id",
        string="有效功能标签",
        compute="_compute_effective_tag_ids",
        store=True,
    )
    effective_application_tag_ids = fields.Many2many(
        "diecut.catalog.application.tag",
        "diecut_catalog_item_effective_application_tag_rel",
        "catalog_item_id",
        "tag_id",
        string="有效应用标签",
        compute="_compute_effective_tag_ids",
        store=True,
    )
    effective_feature_tag_ids = fields.Many2many(
        "diecut.catalog.feature.tag",
        "diecut_catalog_item_effective_feature_tag_rel",
        "catalog_item_id",
        "tag_id",
        string="有效特性标签",
        compute="_compute_effective_tag_ids",
        store=True,
    )
    selection_search_text = fields.Text(
        string="选型检索文本",
        compute="_compute_selection_search_text",
        store=True,
    )
    override_product_features = fields.Boolean(string="单独维护系列共性特性", default=False)
    override_product_description = fields.Boolean(string="单独维护系列说明", default=False)
    override_main_applications = fields.Boolean(string="单独维护系列主要应用", default=False)
    equivalent_type = fields.Text(string="相当品（替代类型）")

    catalog_status = fields.Selection(
        [
            ("draft", "草稿"),
            ("review", "评审中"),
            ("published", "已发布"),
            ("deprecated", "已停用"),
        ],
        string="目录状态",
        default="draft",
        index=True,
    )

    erp_enabled = fields.Boolean(string="已启用ERP", default=False, index=True, readonly=True)
    erp_product_tmpl_id = fields.Many2one("product.template", string="ERP产品", readonly=True, copy=False)

    thickness = fields.Char(string="厚度")
    adhesive_thickness = fields.Char(string="胶层厚", help="如：13/13、15/40（双面胶层厚）")
    color_id = fields.Many2one("diecut.color", string="颜色", index=True)
    adhesive_type_id = fields.Many2one("diecut.catalog.adhesive.type", string="胶系", index=True)
    base_material_id = fields.Many2one("diecut.catalog.base.material", string="基材", index=True)
    thickness_std = fields.Char(string="厚度(标准)")
    ref_price = fields.Float(string="参考单价", digits=(16, 4))
    is_rohs = fields.Boolean(string="ROHS", default=False)
    is_reach = fields.Boolean(string="REACH", default=False)
    is_halogen_free = fields.Boolean(string="无卤", default=False)
    catalog_structure_image = fields.Binary(string="产品结构图")
    fire_rating = fields.Selection(
        [
            ("ul94_v0", "UL94 V-0"),
            ("ul94_v1", "UL94 V-1"),
            ("ul94_v2", "UL94 V-2"),
            ("ul94_hb", "UL94 HB"),
            ("none", "无"),
        ],
        string="防火等级",
        default="none",
    )

    spec_line_ids = fields.One2many("diecut.catalog.item.spec.line", "catalog_item_id", string="技术参数", copy=True)
    visible_spec_line_ids = fields.One2many(
        "diecut.catalog.item.spec.line",
        compute="_compute_visible_spec_line_ids",
        string="有效技术参数",
    )
    spec_line_count = fields.Integer(string="参数条数", compute="_compute_spec_line_count")
    param_domain_ids = fields.Many2many(
        "diecut.catalog.param",
        compute="_compute_param_domain_ids",
        string="可选参数字典",
    )
    is_duplicate_key = fields.Boolean(string="编码重复", compute="_compute_is_duplicate_key", search="_search_is_duplicate_key")

    _STD_RAW_KEYS = {"thickness"}
    _STD_KEYS = {"thickness_std"}
    _TAXONOMY_MODEL_BY_FIELD = {
        "color_id": "diecut.color",
        "adhesive_type_id": "diecut.catalog.adhesive.type",
        "base_material_id": "diecut.catalog.base.material",
    }
    _SELECTION_SEARCH_DOMAIN_FIELDS = (
        "name",
        "code",
        "series_id.name",
        "selection_search_text",
        "effective_function_tag_ids.name",
        "effective_function_tag_ids.alias_text",
        "effective_application_tag_ids.name",
        "effective_application_tag_ids.alias_text",
        "effective_feature_tag_ids.name",
        "effective_feature_tag_ids.alias_text",
    )
    _RETIRED_SELECTION_FRONT_FIELDS = {
        "brand_platform_id",
        "scene_ids",
        "substrate_tag_ids",
        "structure_tag_ids",
        "environment_tag_ids",
        "process_tag_ids",
        "function_tag_ids",
        "application_tag_ids",
        "feature_tag_ids",
    }
    _ITEM_TAG_ALIAS_MAP = {
        "extra_function_tag_ids": "function_tag_ids",
        "extra_application_tag_ids": "application_tag_ids",
        "extra_feature_tag_ids": "feature_tag_ids",
    }

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        result = super().fields_get(allfields=allfields, attributes=attributes)
        for field_name in self._RETIRED_SELECTION_FRONT_FIELDS:
            if field_name not in result:
                continue
            result[field_name]["groupable"] = False
            result[field_name]["searchable"] = False
            result[field_name]["sortable"] = False
        return result

    @api.depends("function_tag_ids", "application_tag_ids", "feature_tag_ids")
    def _compute_item_tag_aliases(self):
        for record in self:
            record.extra_function_tag_ids = record.function_tag_ids
            record.extra_application_tag_ids = record.application_tag_ids
            record.extra_feature_tag_ids = record.feature_tag_ids

    def _inverse_item_tag_aliases(self):
        for record in self:
            record.function_tag_ids = record.extra_function_tag_ids
            record.application_tag_ids = record.extra_application_tag_ids
            record.feature_tag_ids = record.extra_feature_tag_ids

    def action_open_param_mass_edit_wizard(self):
        active_ids = self.env.context.get("active_ids") or self.ids
        param_id = self.env.context.get("current_param_id")
        if not active_ids:
            raise UserError("\u8bf7\u5148\u5728\u5217\u8868\u4e2d\u52fe\u9009\u8981\u5904\u7406\u7684\u578b\u53f7\u3002")
        if not param_id:
            raise UserError(
                "\u8bf7\u5148\u4ece\u53c2\u6570\u5b57\u5178\u7684\u201c\u5f15\u7528\u578b\u53f7\u201d\u5165\u53e3\u8fdb\u5165\uff0c\u518d\u6267\u884c\u6279\u91cf\u5904\u7406\u3002"
            )
        return (
            self.env["diecut.catalog.param.mass.edit.wizard"]
            .with_context(active_ids=active_ids, current_param_id=param_id)
            .action_open_from_context()
        )

    @api.depends(
        "series_id",
        "series_id.default_function_tag_ids",
        "series_id.default_application_tag_ids",
        "series_id.default_feature_tag_ids",
    )
    def _compute_series_tag_views(self):
        for record in self:
            record.series_function_tag_ids = record.series_id.function_tag_ids
            record.series_application_tag_ids = record.series_id.application_tag_ids
            record.series_feature_tag_ids = record.series_id.feature_tag_ids

    @api.depends(
        "series_id",
        "series_id.default_function_tag_ids",
        "series_id.default_application_tag_ids",
        "series_id.default_feature_tag_ids",
        "function_tag_ids",
        "application_tag_ids",
        "feature_tag_ids",
    )
    def _compute_effective_tag_ids(self):
        for record in self:
            record.effective_function_tag_ids = record.series_id.function_tag_ids | record.function_tag_ids
            record.effective_application_tag_ids = record.series_id.application_tag_ids | record.application_tag_ids
            record.effective_feature_tag_ids = record.series_id.feature_tag_ids | record.feature_tag_ids

    @api.model
    def _selection_main_field_name(self):
        return [
            ("thickness", "厚度"),
            ("thickness_std", "厚度(标准)"),
            ("adhesive_thickness", "胶层厚"),
            ("color_id", "颜色"),
            ("adhesive_type_id", "胶系"),
            ("base_material_id", "基材"),
            ("ref_price", "参考单价"),
            ("is_rohs", "ROHS"),
            ("is_reach", "REACH"),
            ("is_halogen_free", "无卤"),
            ("fire_rating", "防火等级"),
        ]

    @classmethod
    def _normalize_compatibility_vals(cls, vals):
        normalized = dict(vals or {})
        for alias_field, storage_field in cls._ITEM_TAG_ALIAS_MAP.items():
            if alias_field in normalized and storage_field not in normalized:
                normalized[storage_field] = normalized.pop(alias_field)
        for field_name, value in list(normalized.items()):
            if cls._is_placeholder_text(value):
                field = cls._fields.get(field_name)
                if field and field.type != "boolean":
                    normalized[field_name] = False
        return normalized

    @classmethod
    def _is_placeholder_text(cls, value):
        if value in (False, None):
            return True
        if isinstance(value, str):
            return value.strip().casefold() in cls._PLACEHOLDER_TEXTS
        return False

    @classmethod
    def _clean_placeholder_text(cls, value):
        if cls._is_placeholder_text(value):
            return False
        if isinstance(value, str):
            value = value.strip()
        return value or False

    def _collect_taxonomy_usage_ids(self):
        usage_ids = {model_name: set() for model_name in self._TAXONOMY_MODEL_BY_FIELD.values()}
        for record in self.with_context(active_test=False):
            for field_name, model_name in self._TAXONOMY_MODEL_BY_FIELD.items():
                field_value = record[field_name]
                if field_value:
                    usage_ids[model_name].add(field_value.id)
        return usage_ids

    @api.model
    def _refresh_taxonomy_usage_counts_from_map(self, usage_ids):
        for model_name, ids in usage_ids.items():
            if ids:
                self.env[model_name].sudo().browse(list(ids))._refresh_usage_counts()
        return True

    @api.depends(
        "spec_line_ids",
        "spec_line_ids.value_kind",
        "spec_line_ids.value_raw",
        "spec_line_ids.value_display",
        "spec_line_ids.unit",
    )
    def _compute_spec_line_count(self):
        for record in self:
            record.spec_line_count = len(
                record.spec_line_ids.filtered(
                    lambda line: line.value_kind == "boolean"
                    or bool((line.value_display or "").strip())
                    or bool((line.value_raw or "").strip())
                )
            )

    @api.depends(
        "spec_line_ids",
        "spec_line_ids.value_kind",
        "spec_line_ids.value_raw",
        "spec_line_ids.value_display",
        "spec_line_ids.unit",
    )
    def _compute_visible_spec_line_ids(self):
        for record in self:
            record.visible_spec_line_ids = record.spec_line_ids.filtered(
                lambda line: line.value_kind == "boolean"
                or bool((line.value_display or "").strip())
                or bool((line.value_raw or "").strip())
            )

    @api.depends(
        "name",
        "code",
        "series_id.name",
        "product_features",
        "product_description",
        "main_applications",
        "special_applications",
        "equivalent_type",
        "effective_function_tag_ids.name",
        "effective_function_tag_ids.alias_text",
        "effective_application_tag_ids.name",
        "effective_application_tag_ids.alias_text",
        "effective_feature_tag_ids.name",
        "effective_feature_tag_ids.alias_text",
    )
    def _compute_selection_search_text(self):
        for record in self:
            tokens = [
                record.name,
                record.code,
                record.series_id.name,
                record.product_features,
                record.product_description,
                record.main_applications,
                record.special_applications,
                record.equivalent_type,
                " ".join(record.effective_function_tag_ids.mapped("name")),
                " ".join(filter(None, record.effective_function_tag_ids.mapped("alias_text"))),
                " ".join(record.effective_application_tag_ids.mapped("name")),
                " ".join(filter(None, record.effective_application_tag_ids.mapped("alias_text"))),
                " ".join(record.effective_feature_tag_ids.mapped("name")),
                " ".join(filter(None, record.effective_feature_tag_ids.mapped("alias_text"))),
            ]
            record.selection_search_text = "\n".join(str(token).strip() for token in tokens if token)

    @api.model
    def _extract_selection_terms_from_domain(self, domain):
        terms = []

        def visit(node):
            if isinstance(node, (list, tuple)):
                if len(node) == 3 and isinstance(node[0], str):
                    field_name, operator, value = node
                    if (
                        field_name in set(self._SELECTION_SEARCH_DOMAIN_FIELDS)
                        and operator in {"ilike", "like", "=ilike", "="}
                        and isinstance(value, str)
                        and value.strip()
                    ):
                        terms.append(value.strip())
                    return
                for item in node:
                    visit(item)

        visit(domain or [])
        deduped = []
        seen = set()
        for term in terms:
            key = term.casefold()
            if key not in seen:
                seen.add(key)
                deduped.append(term)
        return deduped

    @staticmethod
    def _normalize_selection_token(value):
        return (value or "").strip().casefold()

    @classmethod
    def _split_selection_aliases(cls, values):
        tokens = []
        seen = set()
        for value in values:
            for token in re.split(r"[\n,;，；]+", value or ""):
                normalized = cls._normalize_selection_token(token)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    tokens.append(normalized)
        return tokens

    def _selection_relevance_score(self, terms):
        self.ensure_one()
        if not terms:
            return 0

        code = self._normalize_selection_token(self.code)
        name = self._normalize_selection_token(self.name)
        series_name = self._normalize_selection_token(self.series_id.name)
        search_text = self._normalize_selection_token(self.selection_search_text)
        function_names = [self._normalize_selection_token(name) for name in self.effective_function_tag_ids.mapped("name")]
        function_aliases = self._split_selection_aliases(self.effective_function_tag_ids.mapped("alias_text"))
        application_names = [self._normalize_selection_token(name) for name in self.effective_application_tag_ids.mapped("name")]
        application_aliases = self._split_selection_aliases(self.effective_application_tag_ids.mapped("alias_text"))
        feature_names = [self._normalize_selection_token(name) for name in self.effective_feature_tag_ids.mapped("name")]
        feature_aliases = self._split_selection_aliases(self.effective_feature_tag_ids.mapped("alias_text"))

        score = 0
        for raw_term in terms:
            term = self._normalize_selection_token(raw_term)
            if not term:
                continue
            if code and code == term:
                score += 1200
            elif code and code.startswith(term):
                score += 900
            elif code and term in code:
                score += 700

            if name and name == term:
                score += 1000
            elif name and term in name:
                score += 500

            if series_name and series_name == term:
                score += 650
            elif series_name and term in series_name:
                score += 320

            if any(tag == term for tag in function_names):
                score += 600
            elif any(term in tag for tag in function_names):
                score += 300
            elif any(tag == term for tag in function_aliases):
                score += 360
            elif any(term in tag for tag in function_aliases):
                score += 180

            if any(tag == term for tag in application_names):
                score += 560
            elif any(term in tag for tag in application_names):
                score += 280
            elif any(tag == term for tag in application_aliases):
                score += 340
            elif any(term in tag for tag in application_aliases):
                score += 170

            if any(tag == term for tag in feature_names):
                score += 520
            elif any(term in tag for tag in feature_names):
                score += 260
            elif any(tag == term for tag in feature_aliases):
                score += 320
            elif any(term in tag for tag in feature_aliases):
                score += 160

            if search_text and term in search_text:
                score += 120
        return score

    @api.depends("categ_id")
    def _compute_param_domain_ids(self):
        for record in self:
            if not record.categ_id:
                record.param_domain_ids = self.env["diecut.catalog.param"]
                continue
            record.param_domain_ids = record._get_active_params(record.categ_id.id)

    @api.model
    def _get_duplicate_model_ids(self):
        self.env.cr.execute(
            """
            WITH dup AS (
                SELECT brand_id, lower(trim(code)) AS code_key
                  FROM diecut_catalog_item
                 WHERE code IS NOT NULL
                   AND trim(code) <> ''
                 GROUP BY brand_id, lower(trim(code))
                HAVING COUNT(*) > 1
            )
            SELECT i.id
              FROM diecut_catalog_item i
              JOIN dup d
                ON d.brand_id = i.brand_id
               AND d.code_key = lower(trim(i.code))
             WHERE i.code IS NOT NULL
               AND trim(i.code) <> ''
            """
        )
        return [row[0] for row in self.env.cr.fetchall()]

    def _compute_is_duplicate_key(self):
        duplicate_ids = set(self._get_duplicate_model_ids())
        for record in self:
            record.is_duplicate_key = record.id in duplicate_ids

    @api.model
    def _search_is_duplicate_key(self, operator, value):
        if operator not in ("=", "!="):
            raise ValidationError("编码重复筛选仅支持 '=' 或 '!='。")
        duplicate_ids = self._get_duplicate_model_ids()
        positive = (operator == "=" and bool(value)) or (operator == "!=" and not bool(value))
        if positive:
            return [("id", "in", duplicate_ids or [0])]
        return [("id", "not in", duplicate_ids or [0])]

    @staticmethod
    def _normalize_taxonomy_name(value):
        if value in (None, False):
            return False
        normalized = re.sub(r"\s+", " ", str(value).strip())
        if not normalized:
            return False
        if normalized.casefold() in DiecutCatalogItem._PLACEHOLDER_TAXONOMY_NAMES:
            return False
        return normalized

    @api.model
    def _resolve_or_create_taxonomy_id(self, model_name, value):
        name = self._normalize_taxonomy_name(value)
        if not name:
            return False
        taxonomy_model = self.env[model_name].sudo()
        record = taxonomy_model.search([("name", "=", name)], limit=1)
        if record:
            return record.id
        return taxonomy_model.create({"name": name}).id

    @api.model
    def _prepare_taxonomy_many2one_vals(self, vals):
        resolved = {}
        for field_name, model_name in self._TAXONOMY_MODEL_BY_FIELD.items():
            if field_name not in vals:
                continue
            value = vals.get(field_name)
            if isinstance(value, models.BaseModel):
                resolved[field_name] = value.id
                continue
            if isinstance(value, int):
                resolved[field_name] = value or False
                continue
            if value in (False, None, ""):
                resolved[field_name] = False
                continue
            resolved[field_name] = self._resolve_or_create_taxonomy_id(model_name, value)
        return resolved

    @staticmethod
    def _normalize_thickness_std(thickness_text):
        if not thickness_text:
            return False
        source = (thickness_text or "").lower().replace("渭m", "um").replace("碌m", "um").replace(" ", "")
        match = re.search(r"(\d+(?:\.\d+)?)", source)
        if not match:
            return False
        value = float(match.group(1))
        is_um = "um" in source
        is_mm = "mm" in source and not is_um
        if is_um:
            um_value = value
        elif is_mm:
            um_value = value * 1000.0
        else:
            um_value = value if value > 10 else value * 1000.0
        rounded = round(um_value, 1)
        return f"{int(rounded)}μm" if rounded.is_integer() else f"{rounded:g}μm"

    @classmethod
    def _build_thickness_std_vals_from_raw(cls, vals):
        std_vals = {}
        thickness_value = vals.get("thickness")
        if "thickness" in vals:
            std_vals["thickness_std"] = cls._normalize_thickness_std(thickness_value)
        return std_vals

    def _build_thickness_std_vals(self):
        self.ensure_one()
        return self._build_thickness_std_vals_from_raw(
            {
                "thickness": self.thickness,
            }
        )

    def _ensure_model_record(self):
        self.ensure_one()
        if not self.code:
            raise UserError("仅型号条目支持该操作。")
        return True

    def _series_template_vals(self):
        self.ensure_one()
        series = self.series_id
        if not series:
            return {}
        return {
            "product_features": series.product_features or False,
            "product_description": series.product_description or False,
            "main_applications": series.main_applications or False,
        }

    def _series_default_tag_vals(self):
        return {}

    def _apply_series_template(self, mode="overwrite"):
        for record in self:
            updates = {}
            if record.series_id:
                updates.update(record._series_template_vals())
            else:
                for field_name in self._SERIES_TEMPLATE_FIELDS:
                    updates[field_name] = False
            record.with_context(skip_series_sync=True).write(updates)

    def _apply_series_default_tags(self):
        return True

    def action_open_series_apply_wizard(self):
        self.ensure_one()
        if not self.series_id:
            raise UserError("请先选择系列。")
        return {
            "type": "ir.actions.act_window",
            "name": "应用系列模板",
            "res_model": "diecut.catalog.series.apply.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_catalog_item_id": self.id,
                "default_apply_mode": "fill_empty",
            },
        }

    def action_apply_series_template(self, mode):
        if mode not in ("fill_empty", "overwrite"):
            raise ValidationError("不支持的应用方式。")
        self._apply_series_template(mode)
        return True

    @api.onchange("brand_id")
    def _onchange_brand_id_sync_series(self):
        for record in self:
            if record.series_id and record.series_id.brand_id != record.brand_id:
                record.series_id = False

    @api.onchange("series_id")
    def _onchange_series_id_sync_text_and_defaults(self):
        for record in self:
            if not record.series_id:
                record.product_features = False
                record.product_description = False
                record.main_applications = False
                continue
            template_vals = record._series_template_vals()
            for field_name in self._SERIES_TEMPLATE_FIELDS:
                record[field_name] = template_vals.get(field_name)

    @api.model
    def _get_category_chain_ids(self, categ_id):
        if not categ_id:
            return []
        chain_ids = []
        category = self.env["product.category"].browse(categ_id)
        while category:
            chain_ids.append(category.id)
            category = category.parent_id
        chain_ids.reverse()
        return chain_ids

    @api.model
    def _get_active_category_params(self, categ_id):
        if not categ_id:
            return self.env["diecut.catalog.spec.def"]
        chain_ids = self._get_category_chain_ids(categ_id)
        if not chain_ids:
            return self.env["diecut.catalog.spec.def"]
        category_param_model = self.env["diecut.catalog.spec.def"]
        effective_by_param = {}
        for category_id in chain_ids:
            category_defs = category_param_model.search(
                [("categ_id", "=", category_id), ("active", "=", True), ("show_in_form", "=", True)],
                order="sequence, id",
            )
            for spec_def in category_defs:
                effective_by_param[spec_def.param_id.id] = spec_def
        if not effective_by_param:
            return category_param_model
        return category_param_model.browse(
            [record.id for record in sorted(effective_by_param.values(), key=lambda rec: (rec.sequence, rec.id))]
        )

    @api.model
    def _get_active_importable_category_params(self, categ_id):
        return self._get_active_category_params(categ_id)

    @api.model
    def _get_effective_category_param_map(self, categ_id):
        return {record.param_id.id: record for record in self._get_active_category_params(categ_id)}

    @api.model
    def _get_active_params(self, categ_id):
        category_params = self._get_active_category_params(categ_id)
        return category_params.mapped("param_id")

    @api.model
    def _get_effective_importable_category_param_map(self, categ_id):
        category_params = self._get_active_category_params(categ_id).filtered("allow_import")
        return {record.param_key: record for record in category_params}

    def _build_default_spec_line_commands(self, categ_id, existing_param_ids=None, existing_param_keys=None):
        existing_ids = set(existing_param_ids or [])
        existing_keys = {key for key in (existing_param_keys or []) if key}
        commands = []
        for spec_def in self._get_active_category_params(categ_id):
            if spec_def.param_id.id in existing_ids or spec_def.param_key in existing_keys:
                continue
            commands.append(
                Command.create(
                    {
                        "param_id": spec_def.param_id.id,
                        "category_param_id": spec_def.id,
                        "sequence": spec_def.sequence,
                        "param_key": spec_def.param_key,
                        "param_name": spec_def.name,
                        "unit": spec_def.unit_override or spec_def.unit,
                    }
                )
            )
        return commands

    @api.model
    def get_spec_template_commands(self, categ_id):
        categ_id = int(categ_id or 0)
        if not categ_id:
            return [list(Command.clear())]
        commands = [list(Command.clear())]
        commands.extend(list(command) for command in self._build_default_spec_line_commands(categ_id))
        return commands

    def _spec_lines_are_blank_template(self):
        self.ensure_one()
        if not self.spec_line_ids:
            return True
        for line in self.spec_line_ids:
            if (line.value_display or "").strip():
                return False
            if (line.test_method or "").strip():
                return False
            if (line.test_condition or "").strip():
                return False
            if (line.remark or "").strip():
                return False
        return True

    def _spec_lines_match_category_template(self, categ_id):
        self.ensure_one()
        if not categ_id:
            return not self.spec_line_ids
        effective_map = self._get_effective_category_param_map(categ_id)
        current_param_ids = set(self.spec_line_ids.mapped("param_id").ids)
        expected_param_ids = set(effective_map.keys())
        if current_param_ids != expected_param_ids:
            return False
        current_cfg_ids = set(self.spec_line_ids.mapped("category_param_id").ids)
        expected_cfg_ids = {cfg.id for cfg in effective_map.values()}
        return current_cfg_ids == expected_cfg_ids

    def _coerce_main_field_value(self, field_name, raw_value):
        self.ensure_one()
        field = self._fields.get(field_name)
        if not field:
            raise ValidationError(f"未知主字段：{field_name}")
        cleaned_raw = self._clean_placeholder_text(raw_value)
        if cleaned_raw in (False, None, ""):
            return False
        if field.type == "many2one":
            if isinstance(raw_value, models.BaseModel):
                return raw_value.id
            if isinstance(cleaned_raw, int):
                return cleaned_raw
            model_name = getattr(field, "comodel_name", False)
            return self._resolve_or_create_taxonomy_id(model_name, cleaned_raw) if model_name else False
        if field.type == "boolean":
            return str(raw_value).strip().lower() in ("1", "true", "yes", "y", "是")
        if field.type == "float":
            return float(cleaned_raw)
        return str(cleaned_raw).strip()

    def apply_param_payload(
        self,
        *,
        param,
        raw_value,
        unit=None,
        test_method=None,
        test_condition=None,
        remark=None,
        source_document=None,
        source_excerpt=None,
        confidence=None,
        is_ai_generated=False,
        review_status="confirmed",
        conditions=None,
    ):
        self.ensure_one()
        if not param:
            return False
        if param.is_main_field and param.main_field_name:
            main_value = self._coerce_main_field_value(param.main_field_name, raw_value)
            self.write({param.main_field_name: main_value})
            existing_line = self.spec_line_ids.filtered(lambda line: line.param_id == param)
            if existing_line:
                existing_line.unlink()
            return True

        category_param = False
        if self.categ_id:
            category_param = self._get_effective_category_param_map(self.categ_id.id).get(param.id)
        spec_line_model = self.env["diecut.catalog.item.spec.line"]
        normalized_test_condition = spec_line_model._clean_placeholder_text(test_condition)
        value_payload = spec_line_model._normalize_value_payload(param, raw_value)
        if value_payload.get("value_kind") != "boolean" and value_payload.get("value_raw") in (False, None, ""):
            return False
        line_vals = {
            "catalog_item_id": self.id,
            "param_id": param.id,
            "category_param_id": category_param.id if category_param else False,
            "sequence": category_param.sequence if category_param else param.sequence,
            "param_key": param.param_key,
            "param_name": param.name,
            "unit": spec_line_model._clean_placeholder_text(unit) or spec_line_model._clean_placeholder_text(category_param.unit_override if category_param else False) or spec_line_model._clean_placeholder_text(param.unit),
            "normalized_unit": spec_line_model._clean_placeholder_text(param.preferred_unit) or spec_line_model._clean_placeholder_text(unit) or spec_line_model._clean_placeholder_text(param.unit),
            "test_method": spec_line_model._clean_placeholder_text(test_method),
            "test_condition": normalized_test_condition,
            "remark": spec_line_model._clean_placeholder_text(remark),
            "value_raw": value_payload.get("value_raw"),
            "value_number": value_payload.get("value_number") if value_payload.get("value_number") not in (False, None, "") else False,
            "value_kind": value_payload.get("value_kind") or "text",
            "source_document_id": source_document.id if source_document else False,
            "source_excerpt": source_excerpt or False,
            "confidence": float(confidence) if confidence not in (False, None, "") else 0.0,
            "is_ai_generated": bool(is_ai_generated),
            "review_status": review_status or "confirmed",
        }

        conditions = conditions or []
        condition_commands = []
        condition_signature = ()
        if hasattr(spec_line_model, "_normalize_condition_commands"):
            condition_commands = spec_line_model._normalize_condition_commands(conditions)
        if hasattr(spec_line_model, "_condition_signature"):
            condition_signature = spec_line_model._condition_signature(conditions)
        if condition_commands:
            line_vals["condition_ids"] = [Command.clear()] + condition_commands

        line = self.spec_line_ids.filtered(lambda spec_line: spec_line.param_id == param)
        if condition_signature:
            line = line.filtered(lambda spec_line: spec_line_model._condition_signature([
                {
                    "condition_key": condition.condition_key,
                    "condition_value": condition.condition_value,
                }
                for condition in spec_line.condition_ids
            ]) == condition_signature)
        else:
            if normalized_test_condition:
                line = line.filtered(
                    lambda spec_line: (
                        not spec_line.condition_ids
                        and spec_line_model._clean_placeholder_text(spec_line.test_condition) == normalized_test_condition
                    )
                )
            else:
                line = line.filtered(
                    lambda spec_line: (
                        not spec_line.condition_ids
                        and not spec_line_model._clean_placeholder_text(spec_line.test_condition)
                    )
                )
        line = line[:1]
        if line:
            line.write(line_vals)
        else:
            self.write({"spec_line_ids": [Command.create(line_vals)]})
        return True

    @api.onchange("categ_id")
    def _onchange_categ_id_fill_spec_lines(self):
        for record in self:
            if not record.categ_id:
                continue
            previous_categ_id = record._origin.categ_id.id if record._origin and record._origin.categ_id else False
            categ_changed = bool(previous_categ_id and previous_categ_id != record.categ_id.id)
            template_mismatch = not record._spec_lines_match_category_template(record.categ_id.id)
            if categ_changed and record.spec_line_ids and not record._spec_lines_are_blank_template():
                record.categ_id = record._origin.categ_id
                return {
                    "warning": {
                        "title": "无法直接切换分类",
                        "message": "当前技术参数已填写内容，请先清空参数，或使用“重建参数模板”后再切换分类。",
                    }
                }
            if not record.spec_line_ids or (record._spec_lines_are_blank_template() and template_mismatch):
                commands = [Command.clear()] + record._build_default_spec_line_commands(record.categ_id.id)
                record.update(
                    {
                        "spec_line_ids": commands
                    }
                )
                return {"value": {"spec_line_ids": commands}}

    def action_activate_to_erp(self):
        self._ensure_model_record()
        return {
            "type": "ir.actions.act_window",
            "res_model": "diecut.catalog.activate.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_catalog_item_id": self.id,
                "from_gray_catalog_item": True,
                "is_split_view_action": self.env.context.get("is_split_view_action", False),
            },
        }

    def action_view_erp_product(self):
        self._ensure_model_record()
        if not self.erp_enabled or not self.erp_product_tmpl_id:
            raise UserError("该型号尚未关联 ERP 产品。")
        return {
            "type": "ir.actions.act_window",
            "res_model": "product.template",
            "res_id": self.erp_product_tmpl_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_full_form(self):
        self._ensure_model_record()
        return {
            "type": "ir.actions.act_window",
            "res_model": "diecut.catalog.item",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref("diecut.view_diecut_catalog_item_form").id,
            "target": "current",
            "context": {**self.env.context, "form_view_initial_mode": "edit"},
        }

    @api.model
    def action_open_selection_results(self, payload=None):
        payload = payload or {}
        action = self.env.ref("diecut.action_diecut_catalog_item_gray").read()[0]
        action["domain"] = self._build_selection_results_domain(payload)
        action["context"] = {
            **(action.get("context") or {}),
            "split_form_view_id": self.env.ref("diecut.view_diecut_catalog_item_split_form_standalone").id,
            "split_form_view_ref": "diecut.view_diecut_catalog_item_split_form_standalone",
            "edit": True,
            "create": True,
        }
        return action

    def action_open_batch_update_wizard(self):
        active_ids = self.env.context.get("active_ids") or self.ids
        if not active_ids:
            raise UserError("请先在列表中勾选要批量修改的型号。")
        return self.env["diecut.catalog.item.batch.update.wizard"].with_context(active_ids=active_ids).action_open_from_context()

    def action_fill_missing_spec_lines(self):
        for record in self:
            if not record.categ_id:
                raise UserError("请先选择材料分类。")
            existing_ids = record.spec_line_ids.mapped("param_id").ids
            existing_keys = set(record.spec_line_ids.mapped("param_key")) | set(record.spec_line_ids.mapped("param_id.param_key"))
            commands = record._build_default_spec_line_commands(record.categ_id.id, existing_ids, existing_keys)
            if commands:
                record.write({"spec_line_ids": commands})
        return True

    def action_reset_spec_lines(self):
        for record in self:
            if not record.categ_id:
                raise UserError("请先选择材料分类。")
            commands = [Command.clear()] + record._build_default_spec_line_commands(record.categ_id.id)
            record.with_context(allow_spec_categ_change=True).write({"spec_line_ids": commands})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        touched_series_ids = set()
        for vals in vals_list:
            vals.update(self._normalize_compatibility_vals(vals))
            vals.update(self._prepare_taxonomy_many2one_vals(vals))
            if vals.get("code"):
                vals["code"] = vals["code"].strip()
            if vals.get("series_id"):
                touched_series_ids.add(vals["series_id"])
            if vals.get("categ_id") and "spec_line_ids" not in vals and not self.env.context.get("skip_spec_autofill"):
                vals["spec_line_ids"] = self._build_default_spec_line_commands(vals["categ_id"])
        records = super().create(vals_list)
        for idx, record in enumerate(records):
            incoming = vals_list[idx] if idx < len(vals_list) else {}
            if self._STD_KEYS.intersection(incoming.keys()):
                continue
            auto_vals = self._build_thickness_std_vals_from_raw(incoming)
            if auto_vals:
                record.write(auto_vals)
            record._apply_series_template("overwrite")
            record._apply_series_default_tags()
            if record.series_id:
                touched_series_ids.add(record.series_id.id)
        records._refresh_taxonomy_usage_counts_from_map(records._collect_taxonomy_usage_ids())
        if touched_series_ids:
            self.env["diecut.catalog.series"].sudo().browse(list(touched_series_ids))._refresh_usage_counts()
        return records

    def write(self, vals):
        if self.env.context.get("skip_series_sync"):
            return super().write(vals)
        vals = self._normalize_compatibility_vals(vals)
        tracked_taxonomy_fields = set(self._TAXONOMY_MODEL_BY_FIELD)
        old_usage_ids = self._collect_taxonomy_usage_ids() if tracked_taxonomy_fields.intersection(vals.keys()) else None
        old_series_ids = set(self.mapped("series_id").ids) if "series_id" in vals else set()
        vals.update(self._prepare_taxonomy_many2one_vals(vals))
        if vals.get("code"):
            vals["code"] = vals["code"].strip()
        if "brand_id" in vals and "series_id" not in vals:
            brand = self.env["diecut.brand"].browse(vals["brand_id"]) if vals.get("brand_id") else False
            for record in self:
                if record.series_id and brand and record.series_id.brand_id != brand:
                    raise ValidationError("系列不属于当前品牌，请先调整系列。")
        if "categ_id" in vals and "spec_line_ids" not in vals and not self.env.context.get("allow_spec_categ_change"):
            for record in self:
                new_categ_id = vals.get("categ_id")
                if record.categ_id.id != new_categ_id and record.spec_line_ids:
                    raise ValidationError("该型号已有技术参数，不能直接切换材料分类，请先清空参数或手动重建。")
        result = super().write(vals)
        if self._STD_RAW_KEYS.intersection(vals.keys()) and not self._STD_KEYS.intersection(vals.keys()):
            for record in self:
                auto_vals = record._build_thickness_std_vals()
                if auto_vals:
                    record.write(auto_vals)
        if "series_id" in vals or set(self._SERIES_TEMPLATE_FIELDS).intersection(vals.keys()):
            for record in self:
                record._apply_series_template("overwrite")
                if "series_id" in vals:
                    record._apply_series_default_tags()
        if "categ_id" in vals and vals.get("categ_id") and "spec_line_ids" not in vals and not self.env.context.get("skip_spec_autofill"):
            for record in self.filtered(lambda item: not item.spec_line_ids):
                commands = record._build_default_spec_line_commands(record.categ_id.id)
                if commands:
                    record.write({"spec_line_ids": commands})
        if old_usage_ids is not None:
            new_usage_ids = self._collect_taxonomy_usage_ids()
            merged_usage_ids = {
                model_name: set(old_usage_ids.get(model_name, set())) | set(new_usage_ids.get(model_name, set()))
                for model_name in self._TAXONOMY_MODEL_BY_FIELD.values()
            }
            self._refresh_taxonomy_usage_counts_from_map(merged_usage_ids)
        if "series_id" in vals:
            touched_series_ids = old_series_ids | set(self.mapped("series_id").ids)
            if touched_series_ids:
                self.env["diecut.catalog.series"].sudo().browse(list(touched_series_ids))._refresh_usage_counts()
        return result

    def unlink(self):
        usage_ids = self._collect_taxonomy_usage_ids()
        series_ids = set(self.mapped("series_id").ids)
        result = super().unlink()
        self._refresh_taxonomy_usage_counts_from_map(usage_ids)
        if series_ids:
            self.env["diecut.catalog.series"].sudo().browse(list(series_ids))._refresh_usage_counts()
        return result

    @api.constrains("brand_id", "code")
    def _check_structure_rules(self):
        for record in self:
            if not record.code:
                raise ValidationError("型号编码不能为空。")
            if not record.brand_id:
                raise ValidationError("品牌不能为空。")

    @api.constrains("brand_id", "series_id")
    def _check_series_brand_match(self):
        for record in self:
            if record.series_id and record.brand_id and record.series_id.brand_id != record.brand_id:
                raise ValidationError("所选系列不属于当前品牌。")

    @api.model
    def _name_search(self, name="", args=None, operator="ilike", limit=100, name_get_uid=None):
        args = list(args or [])
        if name:
            search_parts = [(field_name, operator, name) for field_name in self._SELECTION_SEARCH_DOMAIN_FIELDS]
            search_domain = ["|"] * (len(search_parts) - 1) + search_parts
            args += search_domain
        model = self.with_user(name_get_uid) if name_get_uid else self
        return model._search(args, limit=limit)

    @api.model
    def search_fetch(self, domain, field_names=None, offset=0, limit=None, order=None):
        terms = self._extract_selection_terms_from_domain(domain)
        if not terms or order:
            return super().search_fetch(domain, field_names=field_names, offset=offset, limit=limit, order=order)

        ranking_fields = {
            "name",
            "code",
            "series_id",
            "selection_search_text",
            "effective_function_tag_ids",
            "effective_application_tag_ids",
            "effective_feature_tag_ids",
            "brand_id",
            "sequence",
        }
        fetch_fields = list(dict.fromkeys(list(field_names or []) + list(ranking_fields)))
        fetch_limit = None if limit is None else max(limit * 5, 200)
        records = super().search_fetch(domain, field_names=fetch_fields, offset=0, limit=fetch_limit, order=self._order)
        original_order = {record.id: index for index, record in enumerate(records)}
        ranked = records.sorted(
            key=lambda record: (
                -record._selection_relevance_score(terms),
                original_order.get(record.id, 0),
            )
        )
        if offset:
            ranked = ranked[offset:]
        if limit is not None:
            ranked = ranked[:limit]
        return ranked

    @api.model
    def _selection_term_split_regex(self):
        return r"[\s,;，；/]+"

    @api.model
    def _split_workbench_terms(self, values):
        terms = []
        seen = set()
        for value in values:
            for token in re.split(self._selection_term_split_regex(), value or ""):
                normalized = self._normalize_selection_token(token)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    terms.append(token.strip())
        return terms

    @api.model
    def _get_scene_keyword_terms(self, scene_ids):
        scenes = self.env["diecut.catalog.selection.scene"].browse(scene_ids or []).exists()
        if not scenes:
            return []
        return self._split_workbench_terms(
            scenes.mapped("name") + scenes.mapped("alias_text") + scenes.mapped("selection_tip")
        )

    @api.model
    def _build_keyword_domain_from_terms(self, terms):
        normalized_terms = [term for term in (terms or []) if str(term or "").strip()]
        if not normalized_terms:
            return []
        domain = []
        for term in normalized_terms:
            search_parts = [(field_name, "ilike", term) for field_name in self._SELECTION_SEARCH_DOMAIN_FIELDS]
            term_domain = expression.OR([[part] for part in search_parts])
            domain = expression.AND([domain, term_domain]) if domain else term_domain
        return domain

    @api.model
    def _build_selection_results_domain(self, payload=None):
        payload = dict(payload or {})
        domain = []
        brand_id = int(payload.get("brand_id") or 0)
        categ_id = int(payload.get("categ_id") or 0)
        platform_id = int(payload.get("brand_platform_id") or 0)
        scene_ids = [int(scene_id) for scene_id in (payload.get("scene_ids") or []) if scene_id]
        keyword = str(payload.get("keyword") or "").strip()
        if brand_id:
            domain.append(("brand_id", "=", brand_id))
        if categ_id:
            domain.append(("categ_id", "=", categ_id))
        if platform_id:
            domain.append(("series_id.brand_platform_id", "=", platform_id))
        if scene_ids:
            domain.append(("series_id.default_scene_ids", "in", scene_ids))
        terms = self._split_workbench_terms([keyword]) + self._get_scene_keyword_terms(scene_ids)
        keyword_domain = self._build_keyword_domain_from_terms(terms)
        if keyword_domain:
            domain = expression.AND([domain, keyword_domain]) if domain else keyword_domain
        return domain

    @api.model
    def _get_workbench_filter_params(self, categ_id=False):
        param_model = self.env["diecut.catalog.param"].with_context(active_test=False)
        params = param_model.search(
            [
                ("active", "=", True),
                "|",
                ("is_primary_filter", "=", True),
                ("selection_role", "in", ["filter", "compare"]),
            ],
            order="sequence, id",
        )
        if not categ_id:
            return params
        allowed_ids = set(self._get_active_params(categ_id).ids)
        return params.filtered(lambda param: param.id in allowed_ids)

    @api.model
    def _get_workbench_param_category_map(self, param_ids=None):
        config_model = self.env["diecut.catalog.spec.def"].with_context(active_test=False)
        domain = [("active", "=", True), ("show_in_form", "=", True)]
        if param_ids:
            domain.append(("param_id", "in", list(param_ids)))
        configs = config_model.search(domain, order="categ_id, sequence, id")
        mapping = {}
        for config in configs:
            mapping.setdefault(config.param_id.id, set()).add(config.categ_id.id)
        return mapping

    @api.model
    def _serialize_workbench_param(self, param, category_ids_map):
        operators_by_type = {
            "float": ["eq", "gte", "lte", "between"],
            "boolean": ["eq"],
            "selection": ["eq", "in"],
            "char": ["contains"],
        }
        return {
            "id": param.id,
            "name": param.name,
            "param_key": param.param_key,
            "value_type": param.value_type,
            "selection_role": param.selection_role,
            "display_group": param.display_group,
            "is_primary_filter": bool(param.is_primary_filter),
            "filter_widget": param.filter_widget,
            "preferred_unit": param.preferred_unit or param.unit or "",
            "selection_options": param.get_selection_options_list() if param.value_type == "selection" else [],
            "allowed_operators": operators_by_type.get(param.value_type or "char", ["contains"]),
            "allowed_category_ids": sorted(category_ids_map.get(param.id, set())),
        }

    @api.model
    def _serialize_workbench_scene(self, scene):
        return {
            "id": scene.id,
            "name": scene.name,
            "complete_name": scene.complete_name,
            "selection_tip": scene.selection_tip or "",
        }

    @api.model
    def get_selection_workbench_bootstrap(self, categ_id=False):
        categ_id = int(categ_id or 0)
        brands = self.search([("brand_id", "!=", False)]).mapped("brand_id").sorted(lambda brand: brand.name or "")
        categories = self.search([("categ_id", "!=", False)]).mapped("categ_id").sorted(
            lambda categ: (categ.complete_name or categ.name or "")
        )
        brand_count_map = {brand.id: self.search_count([("brand_id", "=", brand.id)]) for brand in brands}
        categ_count_map = {categ.id: self.search_count([("categ_id", "=", categ.id)]) for categ in categories}
        platforms = self.env["diecut.catalog.brand.platform"].search([("active", "=", True)], order="brand_id, sequence, name")
        scenes = self.env["diecut.catalog.selection.scene"].search(
            [("active", "=", True), ("is_leaf", "=", True)], order="sequence, name"
        )
        params = self._get_workbench_filter_params(categ_id)
        category_ids_map = self._get_workbench_param_category_map(params.ids)
        compare_defaults = params.filtered(lambda param: param.selection_role == "compare")[:6]
        return {
            "counts": {
                "items": self.search_count([]),
                "brands": len(brands),
                "categories": len(categories),
                "scenes": len(scenes),
                "platforms": len(platforms),
                "params": len(params),
            },
            "brands": [{"id": brand.id, "name": brand.name, "count": brand_count_map.get(brand.id, 0)} for brand in brands],
            "categories": [
                {"id": categ.id, "name": categ.complete_name or categ.name, "count": categ_count_map.get(categ.id, 0)}
                for categ in categories
            ],
            "platforms": [
                {
                    "id": platform.id,
                    "name": platform.name,
                    "brand_id": [platform.brand_id.id, platform.brand_id.name] if platform.brand_id else False,
                }
                for platform in platforms
            ],
            "scenes": [self._serialize_workbench_scene(scene) for scene in scenes],
            "featured_scenes": [self._serialize_workbench_scene(scene) for scene in scenes[:8]],
            "params": [self._serialize_workbench_param(param, category_ids_map) for param in params],
            "default_compare_param_ids": compare_defaults.ids,
        }

    @api.model
    def _normalize_workbench_condition(self, condition):
        condition = dict(condition or {})
        param_id = int(condition.get("param_id") or 0)
        if not param_id:
            return False
        param = self.env["diecut.catalog.param"].browse(param_id).exists()
        if not param or not param.active:
            return False
        operator = str(condition.get("operator") or "").strip() or {
            "float": "gte",
            "boolean": "eq",
            "selection": "eq",
            "char": "contains",
        }.get(param.value_type or "char", "contains")
        normalized = {
            "param_id": param.id,
            "param_name": param.name,
            "param_key": param.param_key,
            "value_type": param.value_type,
            "operator": operator,
            "unit": param.preferred_unit or param.unit or "",
        }
        if param.value_type == "float":
            if condition.get("value") not in (None, "", False):
                normalized["value"] = float(condition.get("value"))
            if condition.get("value_to") not in (None, "", False):
                normalized["value_to"] = float(condition.get("value_to"))
        elif param.value_type == "boolean":
            value = condition.get("value")
            normalized["value"] = str(value).strip().lower() in {"1", "true", "yes", "y", "是"}
        elif param.value_type == "selection":
            values = condition.get("values") or []
            if isinstance(values, str):
                values = [values]
            cleaned_values = [str(value).strip() for value in values if str(value or "").strip()]
            if cleaned_values:
                normalized["values"] = cleaned_values
            if condition.get("value") not in (None, "", False):
                normalized["value"] = str(condition.get("value")).strip()
        else:
            normalized["value"] = str(condition.get("value") or "").strip()
        return normalized

    @api.model
    def _get_workbench_default_compare_params(self, categ_id=False):
        params = self._get_workbench_filter_params(categ_id)
        return params.filtered(lambda param: param.selection_role == "compare")[:6]

    def _workbench_line_matches_condition(self, line, condition):
        self.ensure_one()
        operator = condition.get("operator")
        value_type = condition.get("value_type")
        if value_type == "float":
            number = line.value_number
            if number in (False, None):
                return False
            if operator == "eq":
                return number == condition.get("value")
            if operator == "gte":
                return number >= condition.get("value", 0.0)
            if operator == "lte":
                return number <= condition.get("value", 0.0)
            if operator == "between":
                lower = condition.get("value")
                upper = condition.get("value_to")
                if lower is None or upper is None:
                    return False
                return lower <= number <= upper
            return False
        if value_type == "boolean":
            lowered = str(line.value_raw or "").strip().lower()
            if lowered not in {"true", "false", "1", "0"}:
                return False
            truthy = lowered in {"true", "1"}
            return truthy is bool(condition.get("value"))
        if value_type == "selection":
            raw_value = str(line.value_raw or "").strip()
            if not raw_value:
                return False
            if operator == "in":
                return raw_value in set(condition.get("values") or [])
            return raw_value == str(condition.get("value") or "").strip()
        raw_text = self._normalize_selection_token(line.value_raw)
        expected = self._normalize_selection_token(condition.get("value"))
        if not raw_text or not expected:
            return False
        return expected in raw_text

    @api.model
    def _format_workbench_condition_label(self, condition):
        operator_labels = {
            "eq": "=",
            "gte": ">=",
            "lte": "<=",
            "between": "区间",
            "contains": "包含",
            "in": "任选",
        }
        operator = operator_labels.get(condition.get("operator"), condition.get("operator"))
        if condition.get("value_type") == "float":
            if condition.get("operator") == "between":
                value_label = f"{condition.get('value')} ~ {condition.get('value_to')}"
            else:
                value_label = f"{condition.get('value')}"
        elif condition.get("value_type") == "selection" and condition.get("operator") == "in":
            value_label = " / ".join(condition.get("values") or [])
        else:
            value_label = "是" if condition.get("value") is True else "否" if condition.get("value") is False else str(condition.get("value") or "")
        unit = condition.get("unit") or ""
        return f"{condition.get('param_name')} {operator} {value_label}{(' ' + unit) if unit and condition.get('value_type') == 'float' else ''}".strip()

    def _match_workbench_conditions(self, conditions):
        self.ensure_one()
        matched_details = []
        for condition in conditions:
            lines = self.spec_line_ids.filtered(lambda line: line.param_id.id == condition["param_id"])
            matched_line = False
            for line in lines:
                if self._workbench_line_matches_condition(line, condition):
                    matched_line = line
                    break
            if not matched_line:
                return {"matched": False, "details": []}
            matched_details.append(
                {
                    "param_id": condition["param_id"],
                    "param_name": condition["param_name"],
                    "condition_label": self._format_workbench_condition_label(condition),
                    "matched_value": matched_line.value_display or matched_line.value_raw or "",
                    "condition_summary": matched_line.condition_summary or "",
                }
            )
        return {"matched": True, "details": matched_details, "score_boost": len(matched_details) * 1000}

    def _serialize_workbench_spec_value(self, line):
        self.ensure_one()
        return {
            "display": line.value_display or line.value_raw or "",
            "raw": line.value_raw or "",
            "number": line.value_number if line.value_kind == "number" else False,
            "unit": line.unit or "",
            "condition_summary": line.condition_summary or "",
        }

    def _get_workbench_value_map(self, param_ids):
        self.ensure_one()
        param_id_set = set(param_ids or [])
        value_map = {}
        relevant_lines = self.spec_line_ids.filtered(lambda line: line.param_id.id in param_id_set)
        for line in relevant_lines.sorted(lambda record: (record.sequence, record.id)):
            key = str(line.param_id.id)
            if key not in value_map:
                value_map[key] = self._serialize_workbench_spec_value(line)
        return value_map

    @api.model
    def _sort_workbench_results(self, results, sort):
        if sort == "brand":
            return sorted(results, key=lambda item: ((item.get("brand_name") or ""), -(item.get("score") or 0), item.get("code") or ""))
        if sort == "series":
            return sorted(results, key=lambda item: ((item.get("series_name") or ""), -(item.get("score") or 0), item.get("code") or ""))
        if sort == "thickness":
            return sorted(results, key=lambda item: (item.get("thickness_sort") is None, item.get("thickness_sort") or 0.0, item.get("code") or ""))
        return sorted(results, key=lambda item: (-(item.get("score") or 0), item.get("code") or ""))

    @api.model
    def get_selection_workbench_results(self, payload=None):
        payload = dict(payload or {})
        limit = max(1, min(int(payload.get("limit") or 24), 80))
        sort = str(payload.get("sort") or "relevance")
        domain = self._build_selection_results_domain(payload)
        terms = self._split_workbench_terms([str(payload.get("keyword") or "").strip()]) + self._get_scene_keyword_terms(
            payload.get("scene_ids") or []
        )
        conditions = [
            normalized
            for normalized in (self._normalize_workbench_condition(condition) for condition in (payload.get("conditions") or []))
            if normalized
        ]
        compare_param_ids = [int(param_id) for param_id in (payload.get("compare_param_ids") or []) if param_id]
        categ_id = int(payload.get("categ_id") or 0)
        if not compare_param_ids:
            compare_param_ids = self._get_workbench_default_compare_params(categ_id).ids
        relevant_param_ids = list(dict.fromkeys([condition["param_id"] for condition in conditions] + compare_param_ids))
        search_fields = [
            "name",
            "code",
            "brand_id",
            "series_id",
            "categ_id",
            "thickness_std",
            "thickness",
            "color_id",
            "adhesive_type_id",
            "base_material_id",
            "selection_search_text",
        ]
        fetch_limit = max(limit * 6, 120)
        records = self.search_fetch(domain, field_names=search_fields, limit=fetch_limit)
        results = []
        for record in records:
            matched = record._match_workbench_conditions(conditions)
            if not matched["matched"]:
                continue
            score = matched.get("score_boost", 0)
            if terms:
                score += record._selection_relevance_score(terms)
            compare_values = record._get_workbench_value_map(relevant_param_ids)
            keyword_reasons = []
            if terms:
                keyword_reasons.append(f"命中关键词：{' / '.join(terms[:4])}")
            if payload.get("scene_ids"):
                scene_names = self.env["diecut.catalog.selection.scene"].browse(payload.get("scene_ids") or []).mapped("name")
                if scene_names:
                    keyword_reasons.append(f"贴合场景：{' / '.join(scene_names[:3])}")
            thickness_match = re.search(r"(\d+(?:\.\d+)?)", record.thickness_std or "")
            results.append(
                {
                    "id": record.id,
                    "name": record.name,
                    "code": record.code,
                    "brand_name": record.brand_id.name if record.brand_id else "",
                    "series_name": record.series_id.name if record.series_id else "",
                    "category_name": record.categ_id.complete_name if record.categ_id else "",
                    "thickness": record.thickness or "",
                    "thickness_std": record.thickness_std or "",
                    "thickness_sort": float(thickness_match.group(1)) if thickness_match else None,
                    "color_name": record.color_id.name if record.color_id else "",
                    "adhesive_type_name": record.adhesive_type_id.name if record.adhesive_type_id else "",
                    "base_material_name": record.base_material_id.name if record.base_material_id else "",
                    "matched_reasons": [detail["condition_label"] for detail in matched["details"]] + keyword_reasons,
                    "matched_specs": matched["details"],
                    "compare_values": compare_values,
                    "score": score,
                }
            )
        results = self._sort_workbench_results(results, sort)[:limit]
        compare_params = self.env["diecut.catalog.param"].browse(relevant_param_ids).exists()
        category_ids_map = self._get_workbench_param_category_map(compare_params.ids)
        return {
            "results": results,
            "compare_params": [self._serialize_workbench_param(param, category_ids_map) for param in compare_params],
            "total": len(results),
            "sort": sort,
        }

    @staticmethod
    def _column_exists(cr, table_name, column_name):
        cr.execute(
            """
            SELECT 1
              FROM information_schema.columns
             WHERE table_name = %s
               AND column_name = %s
            """,
            (table_name, column_name),
        )
        return bool(cr.fetchone())

    @staticmethod
    def _column_data_type(cr, table_name, column_name):
        cr.execute(
            """
            SELECT data_type
              FROM information_schema.columns
             WHERE table_name = %s
               AND column_name = %s
            """,
            (table_name, column_name),
        )
        row = cr.fetchone()
        return row[0] if row else None

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            ALTER TABLE diecut_catalog_item
                DROP COLUMN IF EXISTS selection_reason_summary
            """
        )
        self.env.cr.execute(
            """
            DELETE FROM ir_model_fields
             WHERE model = 'diecut.catalog.item'
               AND name = 'selection_reason_summary'
            """
        )
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS diecut_catalog_item_model_brand_code_uidx
            ON diecut_catalog_item (brand_id, lower(trim(code)))
            WHERE code IS NOT NULL AND trim(code) <> ''
            """
        )

    @api.model
    def _migrate_product_info_fields(self):
        self.env.cr.execute(
            """
            SELECT column_name
              FROM information_schema.columns
             WHERE table_name = 'diecut_catalog_item'
               AND column_name IN ('feature_desc', 'typical_applications')
            """
        )
        existing = {row[0] for row in self.env.cr.fetchall()}
        if not existing:
            return True

        select_parts = ["id"]
        for column in ("feature_desc", "typical_applications"):
            if column in existing:
                select_parts.append(column)
            else:
                select_parts.append(f"NULL AS {column}")
        self.env.cr.execute(f"SELECT {', '.join(select_parts)} FROM diecut_catalog_item")

        for row in self.env.cr.dictfetchall():
            values = {}
            feature_desc = row.get("feature_desc")
            typical_applications = row.get("typical_applications")
            record = self.sudo().browse(row["id"])
            if not record.exists():
                continue
            if not record.product_features and feature_desc:
                values["product_features"] = feature_desc
            if not record.main_applications:
                blocks = []
                if typical_applications:
                    blocks.append(typical_applications)
                if blocks:
                    values["main_applications"] = "<hr/>".join(blocks)
            if values:
                record.write(values)

        self.env.cr.execute(
            """
            ALTER TABLE diecut_catalog_item
                DROP COLUMN IF EXISTS feature_desc,
                DROP COLUMN IF EXISTS typical_applications
            """
        )
        self.env.cr.execute(
            """
            DELETE FROM ir_model_fields
             WHERE model = 'diecut.catalog.item'
               AND name IN ('feature_desc', 'typical_applications')
            """
        )
        return True
    _PLACEHOLDER_TAXONOMY_NAMES = {"false", "none", "null", "nil", "n/a", "na"}
