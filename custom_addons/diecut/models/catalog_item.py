# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class DiecutCatalogItem(models.Model):
    _name = "diecut.catalog.item"
    _description = "材料选型条目"
    _parent_name = "parent_id"
    _parent_store = True
    _order = "brand_id, is_system_default_series, sequence, id"

    name = fields.Char(string="名称", required=True)
    active = fields.Boolean(string="启用", default=True)
    sequence = fields.Integer(string="排序", default=10)

    item_level = fields.Selection(
        [("series", "系列"), ("model", "型号")],
        string="层级",
        required=True,
        default="model",
    )
    parent_id = fields.Many2one(
        "diecut.catalog.item",
        string="所属系列",
        index=True,
        ondelete="restrict",
        domain="[('item_level', '=', 'series')]",
    )
    child_ids = fields.One2many("diecut.catalog.item", "parent_id", string="型号列表")
    parent_path = fields.Char(index=True)

    brand_id = fields.Many2one("diecut.brand", string="品牌", required=True, index=True)
    categ_id = fields.Many2one("product.category", string="材料分类", index=True)

    code = fields.Char(string="型号编码", index=True)
    series_code = fields.Char(string="系列编码", index=True)
    is_system_default_series = fields.Boolean(string="系统默认系列", default=False, index=True)

    catalog_status = fields.Selection(
        [
            ("draft", "草稿"),
            ("review", "评审中"),
            ("published", "已发布"),
            ("deprecated", "已停产"),
        ],
        string="目录状态",
        default="draft",
        index=True,
    )

    legacy_tmpl_id = fields.Many2one("product.template", string="旧系列", readonly=True, copy=False, index=True)
    legacy_variant_id = fields.Many2one("product.product", string="旧型号", readonly=True, copy=False, index=True)

    erp_enabled = fields.Boolean(string="已启用ERP", default=False, index=True)
    erp_product_tmpl_id = fields.Many2one("product.template", string="ERP产品", readonly=True, copy=False)
    variant_thickness = fields.Char(string="厚度")
    variant_color = fields.Char(string="颜色")
    variant_adhesive_type = fields.Char(string="胶系(变体)")
    variant_base_material = fields.Char(string="基材(变体)")
    variant_thickness_std = fields.Char(string="厚度(标准)")
    variant_color_std = fields.Char(string="颜色(标准)")
    variant_adhesive_std = fields.Char(string="胶系(标准)")
    variant_base_material_std = fields.Char(string="基材(标准)")
    variant_ref_price = fields.Float(string="参考单价", digits=(16, 4))
    variant_note = fields.Text(string="型号备注")
    variant_is_rohs = fields.Boolean(string="ROHS", default=False)
    variant_is_reach = fields.Boolean(string="REACH", default=False)
    variant_is_halogen_free = fields.Boolean(string="无卤", default=False)
    variant_tds_file = fields.Binary(string="TDS技术数据表")
    variant_tds_filename = fields.Char(string="TDS文件名")
    variant_msds_file = fields.Binary(string="MSDS安全数据表")
    variant_msds_filename = fields.Char(string="MSDS文件名")
    variant_datasheet = fields.Binary(string="规格书")
    variant_datasheet_filename = fields.Char(string="规格书文件名")
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
    is_orphan = fields.Boolean(
        string="孤儿型号",
        compute="_compute_is_orphan",
        store=True,
        index=True,
    )
    is_duplicate_key = fields.Boolean(
        string="编码重复",
        compute="_compute_is_duplicate_key",
        search="_search_is_duplicate_key",
    )

    @api.depends("item_level", "parent_id")
    def _compute_is_orphan(self):
        for record in self:
            record.is_orphan = bool(record.item_level == "model" and not record.parent_id)

    @api.model
    def _get_duplicate_model_ids(self):
        return self.env["diecut.catalog.shadow.service"].get_duplicate_model_ids()

    def _compute_is_duplicate_key(self):
        duplicate_ids = set(self._get_duplicate_model_ids())
        for record in self:
            record.is_duplicate_key = bool(record.item_level == "model" and record.id in duplicate_ids)

    @api.model
    def _search_is_duplicate_key(self, operator, value):
        if operator not in ("=", "!="):
            raise ValidationError("编码重复筛选仅支持 '=' 或 '!='。")
        duplicate_ids = self._get_duplicate_model_ids()
        positive = (operator == "=" and bool(value)) or (operator == "!=" and not bool(value))
        if positive:
            return [("id", "in", duplicate_ids or [0])]
        return [("id", "not in", duplicate_ids or [0])]

    @api.model
    def shadow_backfill_from_legacy(self, dry_run=False, limit=None):
        return self.env["diecut.catalog.shadow.service"].shadow_backfill_from_legacy(
            dry_run=dry_run,
            limit=limit,
        )

    @api.model
    def shadow_reconcile_report(self):
        return self.env["diecut.catalog.shadow.service"].shadow_reconcile_report()

    def _ensure_model_record(self):
        self.ensure_one()
        if self.item_level != "model":
            raise UserError("仅型号条目支持该操作。")
        if not self.legacy_variant_id:
            raise UserError("当前新模型条目未绑定旧型号，无法执行ERP操作。")
        return self.legacy_variant_id

    def _sync_erp_status_from_legacy(self):
        self.ensure_one()
        legacy = self.legacy_variant_id
        self.with_context(skip_shadow_sync=True).write(
            {
                "erp_enabled": bool(legacy.is_activated),
                "erp_product_tmpl_id": legacy.activated_product_tmpl_id.id,
            }
        )

    def action_activate_to_erp(self):
        legacy = self._ensure_model_record()
        action = legacy.action_activate_to_erp()
        self._sync_erp_status_from_legacy()
        return action

    def action_view_erp_product(self):
        legacy = self._ensure_model_record()
        action = legacy.action_view_erp_product()
        self._sync_erp_status_from_legacy()
        return action

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code"):
                vals["code"] = vals["code"].strip()
            if vals.get("series_code"):
                vals["series_code"] = vals["series_code"].strip()
            level = vals.get("item_level")
            if level == "series" and vals.get("is_system_default_series") and not vals.get("series_code"):
                vals["series_code"] = "DEFAULT"
        records = super().create(vals_list)
        if not self.env.context.get("skip_shadow_sync"):
            self.env["diecut.catalog.sync.service"].sync_items_to_legacy(records)
        return records

    def write(self, vals):
        if vals.get("code"):
            vals["code"] = vals["code"].strip()
        if vals.get("series_code"):
            vals["series_code"] = vals["series_code"].strip()
        res = super().write(vals)
        if not self.env.context.get("skip_shadow_sync"):
            self.env["diecut.catalog.sync.service"].sync_items_to_legacy(self, changed_fields=set(vals.keys()))
        return res

    @api.constrains("item_level", "parent_id", "brand_id", "code", "series_code", "is_system_default_series")
    def _check_structure_rules(self):
        for record in self:
            if record.item_level == "model":
                if not record.parent_id:
                    raise ValidationError("型号必须挂在某个系列下。")
                if not record.code:
                    raise ValidationError("型号编码不能为空。")
                if record.parent_id.item_level != "series":
                    raise ValidationError("型号的父级必须是系列。")
                if record.parent_id.brand_id != record.brand_id:
                    raise ValidationError("型号品牌必须与所属系列品牌一致。")
            elif record.parent_id:
                raise ValidationError("系列不能设置父级。")

            if record.item_level == "series" and not record.series_code and not record.is_system_default_series:
                raise ValidationError("系列编码不能为空。")

            if record.is_system_default_series:
                if record.item_level != "series":
                    raise ValidationError("仅系列可以标记为系统默认系列。")
                if not record.brand_id:
                    raise ValidationError("系统默认系列必须绑定品牌。")

        if self._has_cycle():
            raise ValidationError("系列层级存在循环引用，请检查所属系列设置。")

    def init(self):
        super().init()
        cr = self.env.cr
        cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS diecut_catalog_item_model_brand_code_uidx
            ON diecut_catalog_item (brand_id, lower(trim(code)))
            WHERE item_level = 'model' AND code IS NOT NULL AND trim(code) <> ''
            """
        )
        cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS diecut_catalog_item_series_brand_code_uidx
            ON diecut_catalog_item (brand_id, lower(trim(series_code)))
            WHERE item_level = 'series' AND series_code IS NOT NULL AND trim(series_code) <> ''
            """
        )
        cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS diecut_catalog_item_brand_default_series_uidx
            ON diecut_catalog_item (brand_id)
            WHERE item_level = 'series' AND is_system_default_series = TRUE
            """
        )
        cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS diecut_catalog_item_legacy_variant_uidx
            ON diecut_catalog_item (legacy_variant_id)
            WHERE legacy_variant_id IS NOT NULL
            """
        )
        cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS diecut_catalog_item_legacy_series_uidx
            ON diecut_catalog_item (legacy_tmpl_id)
            WHERE item_level = 'series' AND legacy_tmpl_id IS NOT NULL
            """
        )
