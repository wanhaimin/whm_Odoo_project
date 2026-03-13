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

    name = fields.Char(string="名称", required=True)
    active = fields.Boolean(string="启用", default=True)
    sequence = fields.Integer(string="排序", default=10)

    brand_id = fields.Many2one("diecut.brand", string="品牌", required=True, index=True)
    categ_id = fields.Many2one("product.category", string="材料分类", index=True)

    code = fields.Char(string="型号编码", index=True)
    series_text = fields.Char(string="系列", help="迁移兼容字段，不再作为主入口。")
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
    product_features = fields.Text(string="产品特点")
    product_description = fields.Text(string="产品描述")
    main_applications = fields.Html(string="主要应用")
    special_applications = fields.Html(string="型号特性")
    override_product_features = fields.Boolean(string="覆盖产品特点", default=False)
    override_product_description = fields.Boolean(string="覆盖产品描述", default=False)
    override_main_applications = fields.Boolean(string="覆盖主要应用", default=False)
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

    variant_thickness = fields.Char(string="厚度")
    variant_adhesive_thickness = fields.Char(string="胶层厚", help="如：13/13、15/40（双面胶层厚）")
    variant_color = fields.Char(string="颜色")
    variant_peel_strength = fields.Char(string="剥离力", help="遗留字段，仅用于迁移。")
    variant_structure = fields.Char(string="结构描述", help="遗留字段，仅用于迁移。")
    variant_adhesive_type = fields.Char(string="胶系")
    variant_base_material = fields.Char(string="基材")
    variant_sus_peel = fields.Char(string="SUS面剥离力", help="遗留字段，仅用于迁移。")
    variant_pe_peel = fields.Char(string="PE面剥离力", help="遗留字段，仅用于迁移。")
    variant_dupont = fields.Char(string="DuPont冲击", help="遗留字段，仅用于迁移。")
    variant_push_force = fields.Char(string="推出力", help="遗留字段，仅用于迁移。")
    variant_removability = fields.Char(string="可移除性", help="遗留字段，仅用于迁移。")
    variant_tumbler = fields.Char(string="Tumbler滚球", help="遗留字段，仅用于迁移。")
    variant_holding_power = fields.Char(string="保持力", help="遗留字段，仅用于迁移。")

    variant_thickness_std = fields.Char(string="厚度(标准)")
    variant_color_std = fields.Char(string="颜色(标准)")
    variant_adhesive_std = fields.Char(string="胶系(标准)")
    variant_base_material_std = fields.Char(string="基材(标准)")
    variant_ref_price = fields.Float(string="参考单价", digits=(16, 4))
    variant_is_rohs = fields.Boolean(string="ROHS", default=False)
    variant_is_reach = fields.Boolean(string="REACH", default=False)
    variant_is_halogen_free = fields.Boolean(string="无卤", default=False)
    variant_catalog_structure_image = fields.Binary(string="产品结构图")
    variant_fire_rating = fields.Selection(
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
    spec_line_count = fields.Integer(string="参数条数", compute="_compute_spec_line_count")
    spec_def_domain_ids = fields.Many2many(
        "diecut.catalog.spec.def",
        compute="_compute_spec_def_domain_ids",
        string="可选参数定义",
    )
    is_duplicate_key = fields.Boolean(string="编码重复", compute="_compute_is_duplicate_key", search="_search_is_duplicate_key")

    _STD_RAW_KEYS = {"variant_thickness", "variant_color", "variant_adhesive_type", "variant_base_material"}
    _STD_KEYS = {"variant_thickness_std", "variant_color_std", "variant_adhesive_std", "variant_base_material_std"}

    @api.depends("spec_line_ids")
    def _compute_spec_line_count(self):
        for record in self:
            record.spec_line_count = len(record.spec_line_ids)

    @api.depends("categ_id")
    def _compute_spec_def_domain_ids(self):
        for record in self:
            if not record.categ_id:
                record.spec_def_domain_ids = self.env["diecut.catalog.spec.def"]
                continue
            record.spec_def_domain_ids = record._get_active_spec_defs(record.categ_id.id)

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
    def _normalize_text_std(value):
        if not value:
            return False
        normalized = re.sub(r"\s+", " ", (value or "").strip())
        return normalized or False

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
        if "variant_thickness" in vals:
            std_vals["variant_thickness_std"] = cls._normalize_thickness_std(vals.get("variant_thickness"))
        if "variant_color" in vals:
            std_vals["variant_color_std"] = cls._normalize_text_std(vals.get("variant_color"))
        if "variant_adhesive_type" in vals:
            std_vals["variant_adhesive_std"] = cls._normalize_text_std(vals.get("variant_adhesive_type"))
        if "variant_base_material" in vals:
            std_vals["variant_base_material_std"] = cls._normalize_text_std(vals.get("variant_base_material"))
        return std_vals

    def _build_variant_std_vals(self):
        self.ensure_one()
        return self._build_variant_std_vals_from_raw(
            {
                "variant_thickness": self.variant_thickness,
                "variant_color": self.variant_color,
                "variant_adhesive_type": self.variant_adhesive_type,
                "variant_base_material": self.variant_base_material,
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
    def _get_active_spec_defs(self, categ_id):
        if not categ_id:
            return self.env["diecut.catalog.spec.def"]
        chain_ids = self._get_category_chain_ids(categ_id)
        if not chain_ids:
            return self.env["diecut.catalog.spec.def"]
        spec_def_model = self.env["diecut.catalog.spec.def"]
        effective_by_key = {}
        for category_id in chain_ids:
            category_defs = spec_def_model.search(
                [("categ_id", "=", category_id), ("active", "=", True), ("show_in_form", "=", True)],
                order="sequence, id",
            )
            for spec_def in category_defs:
                effective_by_key[spec_def.param_key] = spec_def
        if not effective_by_key:
            return spec_def_model
        return spec_def_model.browse([record.id for record in sorted(effective_by_key.values(), key=lambda rec: (rec.sequence, rec.id))])

    @api.model
    def _get_effective_importable_spec_def_map(self, categ_id):
        spec_defs = self._get_active_spec_defs(categ_id).filtered("allow_import")
        return {record.param_key: record for record in spec_defs}

    def _build_default_spec_line_commands(self, categ_id, existing_spec_def_ids=None, existing_param_keys=None):
        existing_ids = set(existing_spec_def_ids or [])
        existing_keys = {key for key in (existing_param_keys or []) if key}
        commands = []
        for spec_def in self._get_active_spec_defs(categ_id):
            if spec_def.id in existing_ids or spec_def.param_key in existing_keys:
                continue
            commands.append(
                Command.create(
                    {
                        "spec_def_id": spec_def.id,
                        "sequence": spec_def.sequence,
                        "param_key": spec_def.param_key,
                        "param_name": spec_def.name,
                        "unit": spec_def.unit,
                    }
                )
            )
        return commands

    @api.onchange("categ_id")
    def _onchange_categ_id_fill_spec_lines(self):
        for record in self:
            if not record.categ_id:
                continue
            if record._origin and record._origin.id and record._origin.categ_id != record.categ_id and record._origin.spec_line_ids:
                record.categ_id = record._origin.categ_id
                return {
                    "warning": {
                        "title": "无法直接切换分类",
                        "message": "该型号已经存在技术参数，请先清空参数，或使用“按分类模板补齐参数”处理。",
                    }
                }
            if not record.spec_line_ids:
                record.spec_line_ids = record._build_default_spec_line_commands(record.categ_id.id)

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
            existing_ids = record.spec_line_ids.mapped("spec_def_id").ids
            existing_keys = set(record.spec_line_ids.mapped("param_key")) | set(record.spec_line_ids.mapped("spec_def_id.param_key"))
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
        for vals in vals_list:
            if vals.get("code"):
                vals["code"] = vals["code"].strip()
            if vals.get("series_text"):
                vals["series_text"] = vals["series_text"].strip()
            if vals.get("series_id") and not vals.get("series_text"):
                series = series_model.browse(vals["series_id"])
                if series.exists():
                    vals["series_text"] = series.name
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
        return records

    def write(self, vals):
        if self.env.context.get("skip_series_sync"):
            return super().write(vals)
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
        if "categ_id" in vals and not self.env.context.get("allow_spec_categ_change"):
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
        if "categ_id" in vals and vals.get("categ_id") and "spec_line_ids" not in vals and not self.env.context.get("skip_spec_autofill"):
            for record in self.filtered(lambda item: not item.spec_line_ids):
                commands = record._build_default_spec_line_commands(record.categ_id.id)
                if commands:
                    record.write({"spec_line_ids": commands})
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

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS diecut_catalog_item_model_brand_code_uidx
            ON diecut_catalog_item (brand_id, lower(trim(code)))
            WHERE code IS NOT NULL AND trim(code) <> ''
            """
        )

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
                line = line_model.search([("catalog_item_id", "=", item.id), ("spec_def_id", "=", spec_def.id)], limit=1)
                if not line:
                    line_model.create(
                        {
                            "catalog_item_id": item.id,
                            "spec_def_id": spec_def.id,
                            "sequence": spec_def.sequence,
                            "param_key": spec_def.param_key,
                            "param_name": spec_def.name,
                            "value_char": legacy_value,
                            "unit": spec_def.unit,
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
