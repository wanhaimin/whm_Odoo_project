# -*- coding: utf-8 -*-

import re
from collections import Counter, defaultdict

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError


class DiecutCatalogItem(models.Model):
    _name = "diecut.catalog.item"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "材料选型目录"
    _order = "brand_id, sequence, id"

    _LEGACY_SPEC_FIELD_MAP = {
        "variant_peel_strength": ("peel_strength", "剥离力"),
        "variant_structure": ("structure", "结构描述"),
        "variant_sus_peel": ("sus_peel", "SUS剥离力"),
        "variant_pe_peel": ("pe_peel", "PE剥离力"),
        "variant_dupont": ("dupont", "DuPont冲击"),
        "variant_push_force": ("push_force", "推出力"),
        "variant_removability": ("removability", "可移除性"),
        "variant_tumbler": ("tumbler", "Tumbler滚球"),
        "variant_holding_power": ("holding_power", "保持力"),
    }

    _SERIES_TEMPLATE_FIELDS = ("product_features", "product_description", "main_applications")
    _SERIES_DEFAULT_TAG_FIELDS = (
        ("function_tag_ids", "default_function_tag_ids"),
        ("application_tag_ids", "default_application_tag_ids"),
        ("feature_tag_ids", "default_feature_tag_ids"),
    )

    name = fields.Char(string="名称", required=True)
    active = fields.Boolean(string="启用", default=True)
    sequence = fields.Integer(string="排序", default=10)

    brand_id = fields.Many2one("diecut.brand", string="品牌", required=True, index=True)
    categ_id = fields.Many2one("product.category", string="材料分类", index=True)

    code = fields.Char(string="型号编码", index=True)
    series_text = fields.Char(string="系列(兼容)", help="迁移兼容字段，仅用于旧数据与导入兼容，不再作为主入口。")
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
    product_features = fields.Text(string="系列共性特性", help="来自系列模板的共性特性，主要用于继承和导入兼容。")
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

    variant_thickness = fields.Char(string="厚度(兼容)", help="兼容旧字段，请使用 thickness。")
    variant_adhesive_thickness = fields.Char(string="胶层厚(兼容)", help="兼容旧字段，请使用 adhesive_thickness。")
    variant_color = fields.Many2one("diecut.color", string="颜色(兼容)", index=True, help="兼容旧字段，请使用 color_id。")
    variant_peel_strength = fields.Char(string="剥离力", help="遗留字段，仅用于迁移。")
    variant_structure = fields.Char(string="结构描述", help="遗留字段，仅用于迁移。")
    variant_adhesive_type = fields.Many2one("diecut.catalog.adhesive.type", string="胶系(兼容)", index=True, help="兼容旧字段，请使用 adhesive_type_id。")
    variant_base_material = fields.Many2one("diecut.catalog.base.material", string="基材(兼容)", index=True, help="兼容旧字段，请使用 base_material_id。")
    variant_sus_peel = fields.Char(string="SUS面剥离力", help="遗留字段，仅用于迁移。")
    variant_pe_peel = fields.Char(string="PE面剥离力", help="遗留字段，仅用于迁移。")
    variant_dupont = fields.Char(string="DuPont冲击", help="遗留字段，仅用于迁移。")
    variant_push_force = fields.Char(string="推出力", help="遗留字段，仅用于迁移。")
    variant_removability = fields.Char(string="可移除性", help="遗留字段，仅用于迁移。")
    variant_tumbler = fields.Char(string="Tumbler滚球", help="遗留字段，仅用于迁移。")
    variant_holding_power = fields.Char(string="保持力", help="遗留字段，仅用于迁移。")

    variant_thickness_std = fields.Char(string="厚度(标准)(兼容)", help="兼容旧字段，请使用 thickness_std。")
    variant_ref_price = fields.Float(string="参考单价(兼容)", digits=(16, 4), help="兼容旧字段，请使用 ref_price。")
    variant_is_rohs = fields.Boolean(string="ROHS(兼容)", default=False, help="兼容旧字段，请使用 is_rohs。")
    variant_is_reach = fields.Boolean(string="REACH(兼容)", default=False, help="兼容旧字段，请使用 is_reach。")
    variant_is_halogen_free = fields.Boolean(string="无卤(兼容)", default=False, help="兼容旧字段，请使用 is_halogen_free。")
    variant_catalog_structure_image = fields.Binary(string="产品结构图(兼容)", help="兼容旧字段，请使用 catalog_structure_image。")
    variant_fire_rating = fields.Selection(
        [
            ("ul94_v0", "UL94 V-0"),
            ("ul94_v1", "UL94 V-1"),
            ("ul94_v2", "UL94 V-2"),
            ("ul94_hb", "UL94 HB"),
            ("none", "无"),
        ],
        string="防火等级(兼容)",
        default="none",
        help="兼容旧字段，请使用 fire_rating。",
    )

    spec_line_ids = fields.One2many("diecut.catalog.item.spec.line", "catalog_item_id", string="技术参数", copy=True)
    spec_line_count = fields.Integer(string="参数条数", compute="_compute_spec_line_count")
    param_domain_ids = fields.Many2many(
        "diecut.catalog.param",
        compute="_compute_param_domain_ids",
        string="可选参数字典",
    )
    is_duplicate_key = fields.Boolean(string="编码重复", compute="_compute_is_duplicate_key", search="_search_is_duplicate_key")

    _FIELD_COMPATIBILITY_MAP = {
        "thickness": "variant_thickness",
        "adhesive_thickness": "variant_adhesive_thickness",
        "color_id": "variant_color",
        "adhesive_type_id": "variant_adhesive_type",
        "base_material_id": "variant_base_material",
        "thickness_std": "variant_thickness_std",
        "ref_price": "variant_ref_price",
        "is_rohs": "variant_is_rohs",
        "is_reach": "variant_is_reach",
        "is_halogen_free": "variant_is_halogen_free",
        "catalog_structure_image": "variant_catalog_structure_image",
        "fire_rating": "variant_fire_rating",
    }
    _STD_RAW_KEYS = {"thickness", "variant_thickness"}
    _STD_KEYS = {"thickness_std", "variant_thickness_std"}
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
        "function_tag_ids.name",
        "function_tag_ids.alias_text",
        "application_tag_ids.name",
        "application_tag_ids.alias_text",
        "feature_tag_ids.name",
        "feature_tag_ids.alias_text",
    )

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
        for new_name, old_name in cls._FIELD_COMPATIBILITY_MAP.items():
            if new_name in normalized and old_name not in normalized:
                normalized[old_name] = normalized[new_name]
            elif old_name in normalized and new_name not in normalized:
                normalized[new_name] = normalized[old_name]
        return normalized

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

    @api.depends("spec_line_ids")
    def _compute_spec_line_count(self):
        for record in self:
            record.spec_line_count = len(record.spec_line_ids)

    @api.depends(
        "name",
        "code",
        "series_text",
        "series_id.name",
        "product_features",
        "product_description",
        "main_applications",
        "special_applications",
        "equivalent_type",
        "function_tag_ids.name",
        "function_tag_ids.alias_text",
        "application_tag_ids.name",
        "application_tag_ids.alias_text",
        "feature_tag_ids.name",
        "feature_tag_ids.alias_text",
    )
    def _compute_selection_search_text(self):
        for record in self:
            tokens = [
                record.name,
                record.code,
                record.series_text,
                record.series_id.name,
                record.product_features,
                record.product_description,
                record.main_applications,
                record.special_applications,
                record.equivalent_type,
                " ".join(record.function_tag_ids.mapped("name")),
                " ".join(filter(None, record.function_tag_ids.mapped("alias_text"))),
                " ".join(record.application_tag_ids.mapped("name")),
                " ".join(filter(None, record.application_tag_ids.mapped("alias_text"))),
                " ".join(record.feature_tag_ids.mapped("name")),
                " ".join(filter(None, record.feature_tag_ids.mapped("alias_text"))),
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
        function_names = [self._normalize_selection_token(name) for name in self.function_tag_ids.mapped("name")]
        function_aliases = self._split_selection_aliases(self.function_tag_ids.mapped("alias_text"))
        application_names = [self._normalize_selection_token(name) for name in self.application_tag_ids.mapped("name")]
        application_aliases = self._split_selection_aliases(self.application_tag_ids.mapped("alias_text"))
        feature_names = [self._normalize_selection_token(name) for name in self.feature_tag_ids.mapped("name")]
        feature_aliases = self._split_selection_aliases(self.feature_tag_ids.mapped("alias_text"))

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
        if not value:
            return False
        normalized = re.sub(r"\s+", " ", str(value).strip())
        return normalized or False

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
    def _build_variant_std_vals_from_raw(cls, vals):
        std_vals = {}
        thickness_value = vals.get("thickness") if "thickness" in vals else vals.get("variant_thickness")
        if "thickness" in vals or "variant_thickness" in vals:
            std_vals["thickness_std"] = cls._normalize_thickness_std(thickness_value)
            std_vals["variant_thickness_std"] = std_vals["thickness_std"]
        return std_vals

    def _build_variant_std_vals(self):
        self.ensure_one()
        return self._build_variant_std_vals_from_raw(
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
        self.ensure_one()
        if not self.series_id:
            return {}
        values = {}
        for item_field, series_field in self._SERIES_DEFAULT_TAG_FIELDS:
            tag_ids = self.series_id[series_field].ids
            if tag_ids:
                values[item_field] = [Command.set(tag_ids)]
        return values

    def _apply_series_template(self, mode="overwrite"):
        for record in self:
            updates = {}
            if record.series_id:
                updates.update(record._series_template_vals())
                updates["series_text"] = record.series_id.name
            else:
                for field_name in self._SERIES_TEMPLATE_FIELDS:
                    updates[field_name] = False
                updates["series_text"] = False
            record.with_context(skip_series_sync=True).write(updates)

    def _apply_series_default_tags(self):
        for record in self:
            if not record.series_id:
                continue
            updates = {}
            for item_field, series_field in self._SERIES_DEFAULT_TAG_FIELDS:
                if record[item_field]:
                    continue
                default_tags = record.series_id[series_field]
                if default_tags:
                    updates[item_field] = [Command.set(default_tags.ids)]
            if updates:
                record.with_context(skip_series_sync=True).write(updates)

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
                record.series_text = False

    @api.onchange("series_id")
    def _onchange_series_id_sync_text_and_defaults(self):
        for record in self:
            if not record.series_id:
                record.series_text = False
                record.product_features = False
                record.product_description = False
                record.main_applications = False
                continue
            record.series_text = record.series_id.name
            template_vals = record._series_template_vals()
            for field_name in self._SERIES_TEMPLATE_FIELDS:
                record[field_name] = template_vals.get(field_name)
            for item_field, series_field in self._SERIES_DEFAULT_TAG_FIELDS:
                if not record[item_field] and record.series_id[series_field]:
                    record[item_field] = record.series_id[series_field]

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
    def _get_active_spec_defs(self, categ_id):
        return self._get_active_category_params(categ_id)

    @api.model
    def _get_effective_category_param_map(self, categ_id):
        return {record.param_id.id: record for record in self._get_active_category_params(categ_id)}

    @api.model
    def _get_active_params(self, categ_id):
        category_params = self._get_active_category_params(categ_id)
        return category_params.mapped("param_id")

    @api.model
    def _get_effective_importable_spec_def_map(self, categ_id):
        spec_defs = self._get_active_category_params(categ_id).filtered("allow_import")
        return {record.param_key: record for record in spec_defs}

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
            if (line.value_text or "").strip():
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
        if raw_value in (False, None, ""):
            return False
        if field.type == "many2one":
            if isinstance(raw_value, models.BaseModel):
                return raw_value.id
            if isinstance(raw_value, int):
                return raw_value
            model_name = getattr(field, "comodel_name", False)
            return self._resolve_or_create_taxonomy_id(model_name, raw_value) if model_name else False
        if field.type == "boolean":
            return str(raw_value).strip().lower() in ("1", "true", "yes", "y", "是")
        if field.type == "float":
            return float(raw_value)
        return str(raw_value).strip()

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
        line_vals = {
            "catalog_item_id": self.id,
            "param_id": param.id,
            "category_param_id": category_param.id if category_param else False,
            "sequence": category_param.sequence if category_param else param.sequence,
            "param_key": param.param_key,
            "param_name": param.name,
            "unit": unit or (category_param.unit_override if category_param else False) or param.unit or False,
            "normalized_unit": param.preferred_unit or unit or param.unit or False,
            "test_method": test_method or False,
            "test_condition": test_condition or False,
            "remark": remark or False,
            "raw_value_text": False if raw_value in (False, None) else str(raw_value),
            "source_document_id": source_document.id if source_document else False,
            "source_excerpt": source_excerpt or False,
            "confidence": float(confidence) if confidence not in (False, None, "") else 0.0,
            "is_ai_generated": bool(is_ai_generated),
            "review_status": review_status or "confirmed",
        }
        if param.value_type == "float":
            line_vals["value_float"] = float(raw_value) if raw_value not in (False, None, "") else 0.0
        elif param.value_type == "boolean":
            line_vals["value_boolean"] = str(raw_value).strip().lower() in ("1", "true", "yes", "y", "是")
        elif param.value_type == "selection":
            line_vals["value_selection"] = False if raw_value in (False, None, "") else str(raw_value).strip()
        else:
            line_vals["value_char"] = False if raw_value in (False, None, "") else str(raw_value).strip()

        line = self.spec_line_ids.filtered(lambda spec_line: spec_line.param_id == param)[:1]
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
        series_model = self.env["diecut.catalog.series"]
        touched_series_ids = set()
        for vals in vals_list:
            vals.update(self._normalize_compatibility_vals(vals))
            vals.update(self._prepare_taxonomy_many2one_vals(vals))
            if vals.get("code"):
                vals["code"] = vals["code"].strip()
            if vals.get("series_text"):
                vals["series_text"] = vals["series_text"].strip()
            if vals.get("series_id") and not vals.get("series_text"):
                series = series_model.browse(vals["series_id"])
                if series.exists():
                    vals["series_text"] = series.name
                    touched_series_ids.add(series.id)
            elif vals.get("series_id"):
                touched_series_ids.add(vals["series_id"])
            if vals.get("categ_id") and "spec_line_ids" not in vals and not self.env.context.get("skip_spec_autofill"):
                vals["spec_line_ids"] = self._build_default_spec_line_commands(vals["categ_id"])
        records = super().create(vals_list)
        for idx, record in enumerate(records):
            incoming = vals_list[idx] if idx < len(vals_list) else {}
            if self._STD_KEYS.intersection(incoming.keys()):
                continue
            auto_vals = self._build_variant_std_vals_from_raw(incoming)
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
        if vals.get("series_text"):
            vals["series_text"] = vals["series_text"].strip()
        if vals.get("series_id"):
            series = self.env["diecut.catalog.series"].browse(vals["series_id"])
            if series.exists():
                vals["series_text"] = series.name
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
                auto_vals = record._build_variant_std_vals()
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
            "function_tag_ids",
            "application_tag_ids",
            "feature_tag_ids",
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

    def _auto_init(self):
        table_name = self._table
        legacy_columns = {
            "variant_color": "variant_color_legacy_text",
            "variant_adhesive_type": "variant_adhesive_type_legacy_text",
            "variant_base_material": "variant_base_material_legacy_text",
        }
        for column_name, legacy_column in legacy_columns.items():
            if not self._column_exists(self.env.cr, table_name, column_name):
                continue
            if self._column_exists(self.env.cr, table_name, legacy_column):
                continue
            data_type = self._column_data_type(self.env.cr, table_name, column_name)
            if data_type not in ("character varying", "text"):
                continue
            self.env.cr.execute(f'ALTER TABLE {table_name} RENAME COLUMN "{column_name}" TO "{legacy_column}"')
        return super()._auto_init()

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
        self._migrate_variant_taxonomy_many2one()
        self._migrate_core_field_compatibility()
        self.env["diecut.color"].sudo()._refresh_all_usage_counts()
        self.env["diecut.catalog.adhesive.type"].sudo()._refresh_all_usage_counts()
        self.env["diecut.catalog.base.material"].sudo()._refresh_all_usage_counts()
        self.env["diecut.catalog.series"].sudo()._refresh_all_usage_counts()

    @api.model
    def _migrate_core_field_compatibility(self):
        for new_name, old_name in self._FIELD_COMPATIBILITY_MAP.items():
            if not self._column_exists(self.env.cr, self._table, new_name):
                continue
            if not self._column_exists(self.env.cr, self._table, old_name):
                continue
            self.env.cr.execute(
                f"""
                UPDATE {self._table}
                   SET "{new_name}" = COALESCE("{new_name}", "{old_name}"),
                       "{old_name}" = COALESCE("{old_name}", "{new_name}")
                """
            )
        return True

    @api.model
    def _migrate_legacy_spec_fields_to_lines(self):
        spec_def_model = self.env["diecut.catalog.spec.def"].sudo()
        line_model = self.env["diecut.catalog.item.spec.line"].sudo()
        legacy_field_order = list(self._LEGACY_SPEC_FIELD_MAP.keys())
        for item in self.sudo().search([]):
            if not item.categ_id:
                continue
            for field_name, (param_key, param_name) in self._LEGACY_SPEC_FIELD_MAP.items():
                legacy_value = item[field_name]
                if legacy_value in (False, None, ""):
                    continue
                spec_def = spec_def_model.search([("categ_id", "=", item.categ_id.id), ("param_key", "=", param_key)], limit=1)
                if not spec_def:
                    spec_def = spec_def_model.create(
                        {
                            "name": param_name,
                            "param_key": param_key,
                            "categ_id": item.categ_id.id,
                            "value_type": "char",
                            "sequence": 1000 + legacy_field_order.index(field_name),
                            "required": False,
                            "active": True,
                            "show_in_form": True,
                            "allow_import": True,
                        }
                    )
                line = line_model.search([("catalog_item_id", "=", item.id), ("param_id", "=", spec_def.param_id.id)], limit=1)
                if not line:
                    line_model.create(
                        {
                            "catalog_item_id": item.id,
                            "param_id": spec_def.param_id.id,
                            "category_param_id": spec_def.id,
                            "sequence": spec_def.sequence,
                            "param_key": spec_def.param_key,
                            "param_name": spec_def.name,
                            "value_char": legacy_value,
                            "unit": spec_def.unit_override or spec_def.unit,
                        }
                    )
        return True

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

    @api.model
    def _migrate_variant_taxonomy_many2one(self):
        column_map = {
            "color_id": "variant_color_legacy_text",
            "adhesive_type_id": "variant_adhesive_type_legacy_text",
            "base_material_id": "variant_base_material_legacy_text",
        }

        self.env.cr.execute(
            """
            SELECT column_name
              FROM information_schema.columns
             WHERE table_name = 'diecut_catalog_item'
            """
        )
        existing_columns = {row[0] for row in self.env.cr.fetchall()}
        legacy_columns = [column for column in column_map.values() if column in existing_columns]

        if legacy_columns:
            select_sql = ", ".join(["id"] + legacy_columns)
            self.env.cr.execute(f"SELECT {select_sql} FROM diecut_catalog_item")
            for row in self.env.cr.dictfetchall():
                record = self.sudo().browse(row["id"])
                if not record.exists():
                    continue
                vals = {}
                for field_name, legacy_column in column_map.items():
                    legacy_value = row.get(legacy_column)
                    if legacy_value in (False, None, ""):
                        continue
                    if record[field_name]:
                        continue
                    vals[field_name] = self._resolve_or_create_taxonomy_id(
                        self._TAXONOMY_MODEL_BY_FIELD[field_name], legacy_value
                    )
                if vals:
                    record.with_context(skip_series_sync=True, skip_spec_autofill=True).write(vals)

        for column_name in legacy_columns + ["variant_color_std", "variant_adhesive_std", "variant_base_material_std"]:
            if column_name in existing_columns:
                self.env.cr.execute(f'ALTER TABLE diecut_catalog_item DROP COLUMN IF EXISTS "{column_name}"')

        self.env.cr.execute(
            """
            DELETE FROM ir_model_fields
             WHERE model = 'diecut.catalog.item'
               AND name IN (
                   'variant_color_std',
                   'variant_adhesive_std',
                   'variant_base_material_std',
                   'variant_color_legacy_text',
                   'variant_adhesive_type_legacy_text',
                   'variant_base_material_legacy_text'
               )
            """
        )
        return True

    @api.model
    def _migrate_series_to_master(self):
        series_model = self.env["diecut.catalog.series"].sudo()
        items = self.sudo().search([("brand_id", "!=", False), ("series_text", "!=", False)])
        grouped = defaultdict(list)
        for item in items:
            key = (item.brand_id.id, (item.series_text or "").strip())
            if not key[1]:
                continue
            grouped[key].append(item)

        for (brand_id, series_name), records in grouped.items():
            series = series_model.search([("brand_id", "=", brand_id), ("name", "=", series_name)], limit=1)
            if not series:
                series = series_model.create({"brand_id": brand_id, "name": series_name})

            template_vals = {}
            for field_name in self._SERIES_TEMPLATE_FIELDS:
                values = [getattr(rec, field_name) for rec in records if getattr(rec, field_name)]
                if not values:
                    template_vals[field_name] = False
                    continue
                winner = Counter(values).most_common(1)[0][0]
                template_vals[field_name] = winner
            series.write(template_vals)

            for rec in records:
                write_vals = {"series_id": series.id}
                rec.with_context(skip_spec_autofill=True).write(write_vals)

        # 系列文本兜底同步
        for rec in self.sudo().search([("series_id", "!=", False)]):
            if rec.series_text != rec.series_id.name:
                rec.series_text = rec.series_id.name
        return True
