# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DiecutCatalogParam(models.Model):
    _name = "diecut.catalog.param"
    _description = "参数字典"
    _order = "sequence, name, id"

    name = fields.Char(string="参数名称", required=True)
    param_key = fields.Char(string="参数键", required=True, index=True)
    spec_category_id = fields.Many2one("diecut.catalog.param.category", string="参数分类", index=True)
    canonical_name_zh = fields.Char(string="标准中文名")
    canonical_name_en = fields.Char(string="标准英文名")
    aliases_text = fields.Text(string="别名")
    value_type = fields.Selection(
        [
            ("char", "文本"),
            ("float", "数值"),
            ("boolean", "布尔"),
            ("selection", "枚举"),
        ],
        string="值类型",
        required=True,
        default="char",
    )
    description = fields.Text(string="参数说明")
    method_html = fields.Html(string="标准测试方法")
    method_image = fields.Binary(string="方法示意图", attachment=True)
    method_image_filename = fields.Char(string="方法示意图文件名")
    unit = fields.Char(string="默认单位")
    preferred_unit = fields.Char(string="首选单位")
    common_units = fields.Char(string="常见单位")
    selection_options = fields.Text(
        string="枚举选项",
        help="用于 selection 类型，支持按英文逗号或换行分隔。",
    )
    sequence = fields.Integer(string="排序", default=10)
    active = fields.Boolean(string="启用", default=True)
    is_main_field = fields.Boolean(string="主字段", default=False)
    main_field_name = fields.Selection(selection="_selection_main_field_name", string="主字段映射")
    parse_hint = fields.Text(string="解析提示")
    category_config_count = fields.Integer(string="分类配置数", readonly=True, default=0)
    line_count = fields.Integer(string="已使用条数", readonly=True, default=0)

    _param_key_uniq = models.Constraint(
        "UNIQUE(param_key)",
        "参数键必须全局唯一。",
    )

    @staticmethod
    def _normalize_text(value):
        if not value:
            return False
        text = re.sub(r"\s+", " ", str(value).strip())
        return text or False

    @staticmethod
    def _normalize_optional_text(value):
        text = DiecutCatalogParam._normalize_text(value)
        if not text:
            return False
        lowered = text.lower()
        if lowered in {"false", "null", "none", "nil", "n/a", "na"}:
            return False
        return text

    @staticmethod
    def _normalize_param_key(value):
        raw = DiecutCatalogParam._normalize_text(value)
        return raw.lower() if raw else False

    @api.model
    def _selection_main_field_name(self):
        return self.env["diecut.catalog.item"]._selection_main_field_name()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "name" in vals:
                vals["name"] = self._normalize_text(vals.get("name"))
            if "param_key" in vals:
                vals["param_key"] = self._normalize_param_key(vals.get("param_key"))
            if "canonical_name_zh" in vals:
                vals["canonical_name_zh"] = self._normalize_optional_text(vals.get("canonical_name_zh"))
            if "canonical_name_en" in vals:
                vals["canonical_name_en"] = self._normalize_optional_text(vals.get("canonical_name_en"))
            for key in (
                "aliases_text",
                "description",
                "unit",
                "preferred_unit",
                "common_units",
                "selection_options",
                "parse_hint",
                "method_image_filename",
            ):
                if key in vals:
                    vals[key] = self._normalize_optional_text(vals.get(key))
            if not vals.get("preferred_unit") and vals.get("unit"):
                vals["preferred_unit"] = vals["unit"]
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if "name" in vals:
            vals["name"] = self._normalize_text(vals.get("name"))
        if "param_key" in vals:
            vals["param_key"] = self._normalize_param_key(vals.get("param_key"))
        if "canonical_name_zh" in vals:
            vals["canonical_name_zh"] = self._normalize_optional_text(vals.get("canonical_name_zh"))
        if "canonical_name_en" in vals:
            vals["canonical_name_en"] = self._normalize_optional_text(vals.get("canonical_name_en"))
        for key in (
            "aliases_text",
            "description",
            "unit",
            "preferred_unit",
            "common_units",
            "selection_options",
            "parse_hint",
            "method_image_filename",
        ):
            if key in vals:
                vals[key] = self._normalize_optional_text(vals.get(key))
        if "preferred_unit" not in vals and "unit" in vals and vals.get("unit"):
            vals["preferred_unit"] = vals["unit"]
        return super().write(vals)

    @api.constrains("param_key")
    def _check_param_key(self):
        for record in self:
            key = (record.param_key or "").strip()
            if not key:
                raise ValidationError("参数键不能为空。")
            if any(ch.isspace() for ch in key):
                raise ValidationError("参数键不能包含空白字符。")

    @api.constrains("is_main_field", "main_field_name")
    def _check_main_field_name(self):
        allowed = {key for key, _label in self._selection_main_field_name()}
        for record in self:
            if record.is_main_field and not record.main_field_name:
                raise ValidationError("主字段参数必须指定主字段映射。")
            if not record.is_main_field and record.main_field_name:
                raise ValidationError("非主字段参数不能设置主字段映射。")
            if record.main_field_name and record.main_field_name not in allowed:
                raise ValidationError("主字段映射不在允许范围内。")

    def _refresh_usage_counts(self):
        self.env.cr.execute(
            """
            UPDATE diecut_catalog_param
               SET category_config_count = 0,
                   line_count = 0
            """
        )
        self.env.cr.execute(
            """
            UPDATE diecut_catalog_param p
               SET category_config_count = cfg.cnt
              FROM (
                    SELECT param_id, COUNT(*) AS cnt
                      FROM diecut_catalog_spec_def
                     WHERE param_id IS NOT NULL
                     GROUP BY param_id
                   ) cfg
             WHERE p.id = cfg.param_id
            """
        )
        self.env.cr.execute(
            """
            UPDATE diecut_catalog_param p
               SET line_count = lines.cnt
              FROM (
                    SELECT param_id, COUNT(*) AS cnt
                      FROM diecut_catalog_item_spec_line
                     WHERE param_id IS NOT NULL
                     GROUP BY param_id
                   ) lines
             WHERE p.id = lines.param_id
            """
        )

    def get_selection_options_list(self):
        self.ensure_one()
        raw = (self.selection_options or "").replace("\r", "\n")
        values = []
        for part in raw.replace(",", "\n").split("\n"):
            item = part.strip()
            if item:
                values.append(item)
        return values


class DiecutCatalogSpecDef(models.Model):
    _name = "diecut.catalog.spec.def"
    _description = "分类参数配置"
    _order = "categ_id, sequence, id"

    param_id = fields.Many2one("diecut.catalog.param", string="参数字典", required=True, index=True, ondelete="restrict")
    name = fields.Char(string="参数名称", required=True)
    param_key = fields.Char(string="参数键", required=True, index=True)
    description = fields.Text(string="参数说明", related="param_id.description", readonly=True)
    method_html = fields.Html(string="标准测试方法", related="param_id.method_html", readonly=True)
    method_image = fields.Binary(string="方法示意图", related="param_id.method_image", readonly=True)
    method_image_filename = fields.Char(string="方法示意图文件名", related="param_id.method_image_filename", readonly=True)
    categ_id = fields.Many2one("product.category", string="适用分类", required=True, index=True)
    value_type = fields.Selection(
        [
            ("char", "文本"),
            ("float", "数值"),
            ("boolean", "布尔"),
            ("selection", "枚举"),
        ],
        string="值类型",
        required=True,
        default="char",
    )
    unit = fields.Char(string="默认单位")
    selection_options = fields.Text(
        string="枚举选项",
        help="用于 selection 类型，支持按英文逗号或换行分隔。",
    )
    sequence = fields.Integer(string="排序", default=10)
    required = fields.Boolean(string="必填", default=False)
    active = fields.Boolean(string="启用", default=True)
    show_in_form = fields.Boolean(string="表单显示", default=True)
    allow_import = fields.Boolean(string="允许导入", default=True)
    unit_override = fields.Char(string="分类单位覆盖")
    line_count = fields.Integer(string="已使用条数", readonly=True, default=0)

    _categ_param_uniq = models.Constraint(
        "UNIQUE(categ_id, param_id)",
        "同一分类下同一参数不能重复配置。",
    )

    @api.model
    def _prepare_param_vals(self, vals):
        name = DiecutCatalogParam._normalize_text(vals.get("name"))
        param_key = DiecutCatalogParam._normalize_param_key(vals.get("param_key"))
        if not param_key:
            raise ValidationError("参数键不能为空。")
        return {
            "name": name or param_key,
            "param_key": param_key,
            "value_type": vals.get("value_type") or "char",
            "description": DiecutCatalogParam._normalize_optional_text(vals.get("description")),
            "unit": DiecutCatalogParam._normalize_optional_text(vals.get("unit")),
            "selection_options": DiecutCatalogParam._normalize_optional_text(vals.get("selection_options")),
            "sequence": vals.get("sequence") or 10,
            "active": vals.get("active", True),
        }

    @api.model
    def _resolve_param_id(self, vals):
        if vals.get("param_id"):
            return vals["param_id"]
        param_vals = self._prepare_param_vals(vals)
        param_model = self.env["diecut.catalog.param"].sudo()
        param = param_model.search([("param_key", "=", param_vals["param_key"])], limit=1)
        if param:
            update_vals = {
                "name": param_vals["name"],
                "value_type": param_vals["value_type"],
                "description": param_vals["description"],
                "unit": param_vals["unit"],
                "selection_options": param_vals["selection_options"],
                "sequence": param_vals["sequence"],
                "active": param_vals["active"],
            }
            param.write(update_vals)
            return param.id
        return param_model.create(param_vals).id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["name"] = DiecutCatalogParam._normalize_text(vals.get("name")) or vals.get("name")
            vals["param_key"] = DiecutCatalogParam._normalize_param_key(vals.get("param_key")) or vals.get("param_key")
            vals["param_id"] = self._resolve_param_id(vals)
            if "unit_override" not in vals:
                vals["unit_override"] = vals.get("unit") or False
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if any(
            key in vals
            for key in ("name", "param_key", "value_type", "description", "unit", "selection_options", "sequence", "active", "param_id")
        ):
            if "name" in vals:
                vals["name"] = DiecutCatalogParam._normalize_text(vals.get("name"))
            if "param_key" in vals:
                vals["param_key"] = DiecutCatalogParam._normalize_param_key(vals.get("param_key"))
            if not vals.get("param_id"):
                merged = {
                    "name": vals.get("name") or self[:1].name,
                    "param_key": vals.get("param_key") or self[:1].param_key,
                    "value_type": vals.get("value_type") or self[:1].value_type,
                    "description": vals.get("description") if "description" in vals else self[:1].param_id.description,
                    "unit": vals.get("unit") if "unit" in vals else self[:1].unit,
                    "selection_options": vals.get("selection_options") if "selection_options" in vals else self[:1].selection_options,
                    "sequence": vals.get("sequence") if "sequence" in vals else self[:1].sequence,
                    "active": vals.get("active") if "active" in vals else self[:1].active,
                }
                vals["param_id"] = self._resolve_param_id(merged)
            if "unit_override" not in vals and "unit" in vals:
                vals["unit_override"] = vals.get("unit") or False
        return super().write(vals)

    def _refresh_line_count(self):
        self.env.cr.execute(
            """
            UPDATE diecut_catalog_spec_def
               SET line_count = 0
            """
        )
        self.env.cr.execute(
            """
            UPDATE diecut_catalog_spec_def cfg
               SET line_count = lines.cnt
              FROM (
                    SELECT category_param_id, COUNT(*) AS cnt
                      FROM diecut_catalog_item_spec_line
                     WHERE category_param_id IS NOT NULL
                     GROUP BY category_param_id
                   ) lines
             WHERE cfg.id = lines.category_param_id
            """
        )

    @api.constrains("param_key")
    def _check_param_key(self):
        for record in self:
            key = (record.param_key or "").strip()
            if not key:
                raise ValidationError("参数键不能为空。")
            if any(ch.isspace() for ch in key):
                raise ValidationError("参数键不能包含空白字符。")

    def get_selection_options_list(self):
        self.ensure_one()
        if self.param_id:
            return self.param_id.get_selection_options_list()
        raw = (self.selection_options or "").replace("\r", "\n")
        values = []
        for part in raw.replace(",", "\n").split("\n"):
            item = part.strip()
            if item:
                values.append(item)
        return values

    @api.model
    def _migrate_global_params_and_configs(self):
        param_model = self.env["diecut.catalog.param"].sudo()
        category_configs = self.sudo().with_context(active_test=False).search([], order="sequence, id")
        for config in category_configs:
            param_vals = {
                "name": config.name,
                "param_key": config.param_key,
                "value_type": config.value_type,
                "description": False,
                "unit": config.unit,
                "selection_options": config.selection_options,
                "sequence": config.sequence,
                "active": config.active,
            }
            param_id = self._resolve_param_id_sql(param_vals)
            self.env.cr.execute(
                """
                UPDATE diecut_catalog_spec_def cfg
                   SET param_id = %s,
                       name = param.name,
                       param_key = param.param_key,
                       value_type = param.value_type,
                       selection_options = param.selection_options,
                       unit_override = COALESCE(NULLIF(cfg.unit_override, ''), cfg.unit)
                  FROM diecut_catalog_param param
                 WHERE cfg.id = %s
                   AND param.id = %s
                """,
                (param_id, config.id, param_id),
            )

        if not self._column_exists("diecut_catalog_item_spec_line", "param_id"):
            self.env.cr.execute("ALTER TABLE diecut_catalog_item_spec_line ADD COLUMN param_id integer")
        if not self._column_exists("diecut_catalog_item_spec_line", "category_param_id"):
            self.env.cr.execute("ALTER TABLE diecut_catalog_item_spec_line ADD COLUMN category_param_id integer")

        if self._column_exists("diecut_catalog_item_spec_line", "spec_def_id"):
            self.env.cr.execute(
                """
                SELECT line.id,
                       line.spec_def_id,
                       line.param_id,
                       cfg.param_id,
                       cfg.param_key,
                       cfg.name,
                       COALESCE(NULLIF(line.unit, ''), cfg.unit_override, cfg.unit, '')
                  FROM diecut_catalog_item_spec_line line
                  JOIN diecut_catalog_spec_def cfg
                    ON cfg.id = line.spec_def_id
                """
            )
            for (
                line_id,
                legacy_spec_def_id,
                current_param_id,
                config_param_id,
                param_key,
                param_name,
                unit_value,
            ) in self.env.cr.fetchall():
                if current_param_id:
                    continue
                self.env.cr.execute(
                    """
                    UPDATE diecut_catalog_item_spec_line
                       SET category_param_id = %s,
                           param_id = %s,
                           param_key = COALESCE(NULLIF(param_key, ''), %s),
                           param_name = COALESCE(NULLIF(param_name, ''), %s),
                           unit = COALESCE(NULLIF(unit, ''), %s)
                     WHERE id = %s
                    """,
                    (
                        legacy_spec_def_id,
                        config_param_id,
                        param_key,
                        param_name,
                        unit_value or "",
                        line_id,
                    ),
                )
        self._refresh_line_count()
        param_model._refresh_usage_counts()
        return True

    def init(self):
        super().init()
        self._migrate_global_params_and_configs()

    @api.model
    def _column_exists(self, table_name, column_name):
        self.env.cr.execute(
            """
            SELECT 1
              FROM information_schema.columns
             WHERE table_name = %s
               AND column_name = %s
            """,
            (table_name, column_name),
        )
        return bool(self.env.cr.fetchone())

    @api.model
    def _resolve_param_id_sql(self, vals):
        param_key = DiecutCatalogParam._normalize_param_key(vals.get("param_key"))
        name = DiecutCatalogParam._normalize_text(vals.get("name")) or param_key
        value_type = vals.get("value_type") or "char"
        unit = vals.get("unit") or False
        description = DiecutCatalogParam._normalize_optional_text(vals.get("description"))
        selection_options = DiecutCatalogParam._normalize_optional_text(vals.get("selection_options"))
        unit = DiecutCatalogParam._normalize_optional_text(unit)
        sequence = vals.get("sequence") or 10
        active = vals.get("active", True)
        self.env.cr.execute(
            """
            SELECT id
              FROM diecut_catalog_param
             WHERE param_key = %s
             LIMIT 1
            """,
            (param_key,),
        )
        row = self.env.cr.fetchone()
        if row:
            self.env.cr.execute(
                """
                UPDATE diecut_catalog_param
                   SET name = %s,
                       value_type = %s,
                       description = %s,
                       unit = %s,
                       selection_options = %s,
                       sequence = %s,
                       active = %s
                 WHERE id = %s
                """,
                (name, value_type, description, unit, selection_options, sequence, active, row[0]),
            )
            return row[0]
        self.env.cr.execute(
            """
            INSERT INTO diecut_catalog_param
                (name, param_key, value_type, description, unit, selection_options, sequence, active, category_config_count, line_count, create_uid, create_date, write_uid, write_date)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, 0, 0, %s, NOW(), %s, NOW())
            RETURNING id
            """,
            (name, param_key, value_type, description, unit, selection_options, sequence, active, self.env.uid, self.env.uid),
        )
        return self.env.cr.fetchone()[0]


class DiecutCatalogItemSpecLine(models.Model):
    _name = "diecut.catalog.item.spec.line"
    _description = "材料技术参数值"
    _order = "sequence, id"

    catalog_item_id = fields.Many2one(
        "diecut.catalog.item",
        string="目录型号",
        required=True,
        ondelete="cascade",
        index=True,
    )
    param_id = fields.Many2one(
        "diecut.catalog.param",
        string="参数字典",
        required=True,
        index=True,
        domain="[('id', 'in', catalog_item_id.param_domain_ids)]",
    )
    category_param_id = fields.Many2one(
        "diecut.catalog.spec.def",
        string="分类参数配置",
        index=True,
        readonly=True,
    )
    spec_def_id = fields.Many2one(
        "diecut.catalog.spec.def",
        string="分类参数配置(兼容)",
        related="category_param_id",
        readonly=True,
    )
    categ_id = fields.Many2one(
        "product.category",
        string="材料分类",
        related="catalog_item_id.categ_id",
        store=True,
        readonly=True,
        index=True,
    )
    sequence = fields.Integer(string="排序", default=10)
    param_key = fields.Char(string="参数键", index=True)
    param_name = fields.Char(string="参数名称")
    method_html = fields.Html(string="标准测试方法", related="param_id.method_html", readonly=True)
    value_type = fields.Selection(
        related="param_id.value_type",
        string="值类型",
        store=True,
        readonly=True,
    )
    value_char = fields.Char(string="文本值")
    value_float = fields.Float(string="数值")
    value_boolean = fields.Boolean(string="布尔值")
    value_selection = fields.Char(string="枚举值")
    value_text = fields.Char(
        string="参数值",
        compute="_compute_value_text",
        inverse="_inverse_value_text",
        help="统一显示和编辑参数值。",
    )
    display_value = fields.Char(string="显示值", compute="_compute_display_value")
    unit = fields.Char(string="单位")
    test_method = fields.Char(string="测试方法")
    test_condition = fields.Char(string="测试条件")
    remark = fields.Char(string="备注")
    raw_value_text = fields.Text(string="原始值文本")
    normalized_unit = fields.Char(string="标准单位")
    source_document_id = fields.Many2one("diecut.catalog.source.document", string="来源文档", index=True)
    source_excerpt = fields.Text(string="来源片段")
    confidence = fields.Float(string="置信度", digits=(16, 4))
    is_ai_generated = fields.Boolean(string="AI生成", default=False)
    review_status = fields.Selection(
        [
            ("pending", "待确认"),
            ("confirmed", "已确认"),
            ("rejected", "已驳回"),
        ],
        string="审核状态",
        default="confirmed",
    )

    _item_param_uniq = models.Constraint(
        "UNIQUE(catalog_item_id, param_id)",
        "同一型号下同一参数不能重复。",
    )

    @api.depends("value_type", "value_char", "value_float", "value_boolean", "value_selection")
    def _compute_value_text(self):
        for record in self:
            if record.value_type == "float":
                record.value_text = "" if record.value_float in (False, None) else f"{record.value_float:g}"
            elif record.value_type == "boolean":
                record.value_text = "是" if record.value_boolean else ""
            elif record.value_type == "selection":
                record.value_text = record.value_selection or ""
            else:
                record.value_text = record.value_char or ""

    def _inverse_value_text(self):
        for record in self:
            raw = (record.value_text or "").strip()
            if record.value_type == "float":
                record.value_char = False
                record.value_boolean = False
                record.value_selection = False
                record.value_float = float(raw) if raw else 0.0
            elif record.value_type == "boolean":
                normalized = raw.lower()
                if not raw:
                    record.value_boolean = False
                elif normalized in ("1", "true", "yes", "y", "是"):
                    record.value_boolean = True
                elif normalized in ("0", "false", "no", "n", "否"):
                    record.value_boolean = False
                else:
                    raise ValidationError("布尔类型参数仅支持 是/否、true/false、1/0。")
                record.value_char = False
                record.value_float = 0.0
                record.value_selection = False
            elif record.value_type == "selection":
                record.value_char = False
                record.value_float = 0.0
                record.value_boolean = False
                record.value_selection = raw or False
            else:
                record.value_float = 0.0
                record.value_boolean = False
                record.value_selection = False
                record.value_char = raw or False

    @api.depends("value_text", "unit")
    def _compute_display_value(self):
        for record in self:
            value = (record.value_text or "").strip()
            unit = (record.unit or "").strip()
            record.display_value = f"{value} {unit}".strip() if value else ""

    @api.onchange("param_id")
    def _onchange_param_id(self):
        for record in self:
            record._sync_from_param()

    def _sync_from_param(self):
        self.ensure_one()
        if not self.param_id:
            return
        category_param = False
        if self.catalog_item_id and self.catalog_item_id.categ_id:
            category_param = self.catalog_item_id._get_effective_category_param_map(self.catalog_item_id.categ_id.id).get(
                self.param_id.id
            )
        self.category_param_id = category_param.id if category_param else False
        self.sequence = category_param.sequence if category_param else self.param_id.sequence
        self.param_key = self.param_id.param_key
        self.param_name = self.param_id.name
        if not self.unit:
            self.unit = (category_param.unit_override if category_param else False) or self.param_id.unit or False
        if not self.normalized_unit:
            self.normalized_unit = self.param_id.preferred_unit or self.param_id.unit or False

    @api.constrains("catalog_item_id", "param_id")
    def _check_category_match(self):
        for record in self:
            if not record.param_id or not record.catalog_item_id or not record.catalog_item_id.categ_id:
                continue
            allowed = record.catalog_item_id._get_effective_category_param_map(record.catalog_item_id.categ_id.id)
            if record.param_id.id not in allowed and not record.param_id.is_main_field:
                raise ValidationError("参数字典不属于当前型号分类继承链。")

    @api.constrains("value_type", "value_char", "value_float", "value_boolean", "value_selection", "param_id")
    def _check_value_payload(self):
        for record in self:
            if not record.param_id:
                continue
            payload = {
                "char": bool((record.value_char or "").strip()),
                "float": record.value_float not in (False, None, 0.0),
                "boolean": bool(record.value_boolean),
                "selection": bool((record.value_selection or "").strip()),
            }
            for key, has_value in payload.items():
                if key != record.value_type and has_value:
                    raise ValidationError("技术参数只能填写与值类型匹配的字段。")
            if record.value_type == "selection" and record.value_selection:
                options = record.param_id.get_selection_options_list()
                if options and record.value_selection not in options:
                    raise ValidationError("枚举参数值不在定义范围内。")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._sync_from_param()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "param_id" in vals:
            for record in self:
                record._sync_from_param()
        return res
