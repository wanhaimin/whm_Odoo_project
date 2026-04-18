# -*- coding: utf-8 -*-

import json
import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class DiecutCatalogParam(models.Model):
    _name = "diecut.catalog.param"
    _inherit = ["diecut.catalog.merge.mixin"]
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
    condition_schema_json = fields.Text(string="条件模板(JSON)")
    selection_role = fields.Selection(
        [
            ("filter", "主筛选"),
            ("compare", "对比参数"),
            ("detail_only", "仅技术详情"),
        ],
        string="选型角色",
        required=True,
        default="detail_only",
    )
    display_group = fields.Selection(
        [
            ("bonding", "粘接性能"),
            ("structure", "结构信息"),
            ("environment", "环境耐受"),
            ("thermal", "热性能"),
            ("electrical", "电性能"),
            ("process", "工艺与合规"),
        ],
        string="展示分组",
        required=True,
        default="bonding",
    )
    is_primary_filter = fields.Boolean(string="工作台主筛选", default=False)
    filter_widget = fields.Selection(
        [
            ("hidden", "隐藏"),
            ("checkbox", "勾选"),
            ("range", "范围"),
            ("text", "文本"),
        ],
        string="筛选控件",
        required=True,
        default="hidden",
    )
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

    @api.model
    def _name_search(self, name="", args=None, operator="ilike", limit=100, name_get_uid=None):
        args = list(args or [])
        if name:
            args += ["|", "|", "|", "|", ("name", operator, name), ("param_key", operator, name), ("aliases_text", operator, name), ("canonical_name_zh", operator, name), ("canonical_name_en", operator, name)]
        model = self.with_user(name_get_uid) if name_get_uid else self
        return model._search(args, limit=limit)

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        if not name:
            return super().name_search(name=name, domain=domain, operator=operator, limit=limit)
        records = self.search(["|", "|", "|", "|", ("name", operator, name), ("param_key", operator, name), ("aliases_text", operator, name), ("canonical_name_zh", operator, name), ("canonical_name_en", operator, name)] + list(domain or []), limit=limit)
        return [(record.id, record.display_name) for record in records]

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
                "condition_schema_json",
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
                "condition_schema_json",
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

    def _merge_extra_alias_candidates(self):
        self.ensure_one()
        values = [self.param_key, self.canonical_name_zh, self.canonical_name_en]
        return [value for value in values if value]

    @api.model
    def _merge_relation_field_blacklist(self):
        return super()._merge_relation_field_blacklist() | {("diecut.catalog.spec.def", "param_id"), ("diecut.catalog.item.spec.line", "param_id")}

    def _validate_merge_records(self, master, sources):
        super()._validate_merge_records(master, sources)
        value_types = {value for value in (sources.mapped("value_type") + [master.value_type]) if value}
        if len(value_types) > 1:
            raise ValidationError("只能合并值类型一致的参数字典。")
        main_field_flags = {bool(value) for value in (sources.mapped("is_main_field") + [master.is_main_field])}
        if len(main_field_flags) > 1:
            raise ValidationError("主字段参数与普通参数不能直接合并。")
        if master.is_main_field:
            main_field_names = {value for value in (sources.mapped("main_field_name") + [master.main_field_name]) if value}
            if len(main_field_names) > 1:
                raise ValidationError("主字段映射不一致，不能直接合并。")

    def _prepare_merge_master_vals(self, master, sources):
        vals = super()._prepare_merge_master_vals(master, sources)
        if not master.canonical_name_zh:
            fallback = next((value for value in sources.mapped("canonical_name_zh") if value), False)
            if fallback:
                vals["canonical_name_zh"] = fallback
        if not master.canonical_name_en:
            fallback = next((value for value in sources.mapped("canonical_name_en") if value), False)
            if fallback:
                vals["canonical_name_en"] = fallback
        if not master.description:
            fallback = next((value for value in sources.mapped("description") if value), False)
            if fallback:
                vals["description"] = fallback
        if not master.preferred_unit:
            fallback = next((value for value in sources.mapped("preferred_unit") if value), False)
            if fallback:
                vals["preferred_unit"] = fallback
        if not master.unit:
            fallback = next((value for value in sources.mapped("unit") if value), False)
            if fallback:
                vals["unit"] = fallback
        return vals

    def _merge_related_records(self, master, sources):
        category_param_model = self.env["diecut.catalog.spec.def"].sudo().with_context(active_test=False)
        line_model = self.env["diecut.catalog.item.spec.line"].sudo().with_context(active_test=False)
        source_ids = sources.ids
        source_keys = [key for key in sources.mapped("param_key") if key]
        merged_category_configs = 0
        moved_spec_lines = 0

        master_configs = category_param_model.search([("param_id", "=", master.id)])
        master_config_by_categ = {cfg.categ_id.id: cfg for cfg in master_configs if cfg.categ_id}
        source_configs = category_param_model.search([("param_id", "in", source_ids)], order="categ_id, sequence, id")

        for config in source_configs:
            target_config = master_config_by_categ.get(config.categ_id.id) if config.categ_id else False
            if target_config and target_config.id != config.id:
                write_vals = {}
                if not target_config.unit_override and config.unit_override:
                    write_vals["unit_override"] = config.unit_override
                if not target_config.selection_options and config.selection_options:
                    write_vals["selection_options"] = config.selection_options
                if write_vals:
                    target_config.write(write_vals)
                linked_lines = line_model.search([("category_param_id", "=", config.id)])
                if linked_lines:
                    moved_spec_lines += len(linked_lines)
                    linked_lines.write({"category_param_id": target_config.id, "param_id": master.id, "param_key": master.param_key, "param_name": master.name})
                config.unlink()
                merged_category_configs += 1
                continue

            config.write({"param_id": master.id, "param_key": master.param_key, "name": master.name, "value_type": master.value_type})
            if config.categ_id:
                master_config_by_categ[config.categ_id.id] = config
            merged_category_configs += 1

        linked_lines = line_model.search([("param_id", "in", source_ids)])
        if linked_lines:
            moved_spec_lines += len(linked_lines)
            linked_lines.write({"param_id": master.id, "param_key": master.param_key, "param_name": master.name})

        if source_keys:
            orphan_lines = line_model.search([("param_key", "in", source_keys)])
            if orphan_lines:
                moved_spec_lines += len(orphan_lines)
                orphan_lines.write({"param_id": master.id, "param_key": master.param_key, "param_name": master.name})

        category_param_model._refresh_line_count()
        master._refresh_usage_counts()
        return {"merged_category_configs": merged_category_configs, "moved_spec_lines": moved_spec_lines}

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

    def action_view_linked_items(self):
        self.ensure_one()
        if self.is_main_field:
            raise ValidationError("主字段参数请通过材料字段批量修改，不支持通过参数行入口查看或批量增删。")
        return {
            "type": "ir.actions.act_window",
            "name": f"引用型号 - {self.display_name}",
            "res_model": "diecut.catalog.item",
            "view_mode": "list,form",
            "domain": [("spec_line_ids.param_id", "=", self.id)],
            "context": {
                "split_form_view_id": self.env.ref("diecut.view_diecut_catalog_item_split_form_standalone").id,
                "split_form_view_ref": "diecut.view_diecut_catalog_item_split_form_standalone",
                "split_storage_key": f"param_{self.id}_linked_items",
                "edit": True,
                "create": True,
                "current_param_id": self.id,
                "current_param_name": self.display_name,
            },
            "views": [
                (self.env.ref("diecut.view_diecut_catalog_item_split_tree_standalone").id, "list"),
                (self.env.ref("diecut.view_diecut_catalog_item_form").id, "form"),
            ],
            "search_view_id": self.env.ref("diecut.view_diecut_catalog_item_search").id,
            "target": "current",
        }

    def action_open_param_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.display_name,
            "res_model": "diecut.catalog.param",
            "view_mode": "form",
            "view_id": self.env.ref("diecut.view_diecut_catalog_param_form").id,
            "res_id": self.id,
            "target": "current",
        }

    def unlink(self):
        line_model = self.env["diecut.catalog.item.spec.line"].sudo()
        category_def_model = self.env["diecut.catalog.spec.def"].sudo()
        for record in self:
            if record.is_main_field:
                raise UserError("主字段参数不允许直接删除，请先取消主字段映射或改为停用。")
            linked_line_count = line_model.search_count([("param_id", "=", record.id)])
            if linked_line_count:
                raise UserError(
                    f"参数“{record.display_name}”已被 {linked_line_count} 条技术参数使用，不能直接删除。请先清理引用型号，或先停用。"
                )
        linked_defs = category_def_model.search([("param_id", "in", self.ids)])
        if linked_defs:
            linked_defs.unlink()
        return super().unlink()

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
    value_raw = fields.Text(string="原始值")
    value_number = fields.Float(string="数值值")
    value_kind = fields.Selection(
        [
            ("text", "文本"),
            ("number", "数值"),
            ("boolean", "布尔"),
            ("selection", "枚举"),
        ],
        string="值形态",
        default="text",
        required=True,
    )
    value_display = fields.Char(string="显示值", compute="_compute_value_display", store=True)
    unit = fields.Char(string="单位")
    test_method = fields.Char(string="测试方法")
    test_condition = fields.Char(string="测试条件")
    remark = fields.Char(string="备注")
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
    condition_ids = fields.One2many(
        "diecut.catalog.item.spec.condition",
        "spec_line_id",
        string="条件明细",
        copy=True,
    )
    condition_summary = fields.Char(
        string="条件摘要",
        compute="_compute_condition_summary",
        store=True,
    )

    @api.model
    def _is_placeholder_text(self, value):
        if value in (False, None):
            return True
        if isinstance(value, str):
            return value.strip().lower() in {"false", "none", "null"}
        return False

    @api.model
    def _clean_placeholder_text(self, value):
        if self._is_placeholder_text(value):
            return False
        if isinstance(value, str):
            value = value.strip()
            return value or False
        return value

    @api.depends("value_raw", "value_number", "value_kind", "unit")
    def _compute_value_display(self):
        for record in self:
            if record.value_kind == "number":
                has_real_raw = not record._is_placeholder_text(record.value_raw)
                if has_real_raw and record.value_number not in (False, None):
                    value = f"{record.value_number:g}"
                else:
                    value = ""
            elif record.value_kind == "boolean":
                value = "?" if str(record.value_raw or "").strip().lower() in ("1", "true", "yes", "y", "?") else "?"
            else:
                value = record._clean_placeholder_text(record.value_raw) or ""
            unit = record._clean_placeholder_text(record.unit) or ""
            record.value_display = f"{value} {unit}".strip() if value else ""

    @api.depends("condition_ids.condition_label", "condition_ids.condition_key", "condition_ids.condition_value", "condition_ids.sequence")
    def _compute_condition_summary(self):
        for record in self:
            pieces = []
            for condition in record.condition_ids.sorted(lambda item: (item.sequence, item.id)):
                value = record._clean_placeholder_text(condition.condition_value) or ""
                if value:
                    pieces.append(value)
            record.condition_summary = " / ".join(pieces)

    @api.model
    def _guess_value_kind(self, param, raw_value):
        value_type = (param.value_type or "char").strip() if param else "char"
        if value_type == "float":
            return "number"
        if value_type == "boolean":
            return "boolean"
        if value_type == "selection":
            return "selection"
        return "text"

    @api.model
    def _normalize_value_payload(self, param, raw_value, value_kind=False, value_number=False):
        normalized_raw = self._clean_placeholder_text(raw_value)
        kind = value_kind or self._guess_value_kind(param, normalized_raw)
        if kind == "number":
            cleaned_number = False if self._is_placeholder_text(value_number) else value_number
            if cleaned_number not in (False, None, ""):
                number = float(cleaned_number)
            elif normalized_raw not in (False, None, ""):
                number = float(normalized_raw)
            else:
                number = False
            return {
                "value_kind": "number",
                "value_number": number,
                "value_raw": normalized_raw or (f"{number:g}" if number not in (False, None) else False),
            }
        if kind == "boolean":
            lowered = (normalized_raw or "").lower()
            truthy = lowered in ("1", "true", "yes", "y", "是")
            falsy = lowered in ("0", "false", "no", "n", "否", "")
            if lowered and not (truthy or falsy):
                raise ValidationError("布尔类型参数仅支持 是/否、true/false、1/0。")
            return {
                "value_kind": "boolean",
                "value_number": 1.0 if truthy else 0.0,
                "value_raw": "true" if truthy else "false",
            }
        return {
            "value_kind": kind,
            "value_number": False,
            "value_raw": normalized_raw or False,
        }

    @api.model
    def _normalize_condition_commands(self, conditions):
        commands = []
        sequence = 10
        for condition in conditions or []:
            if not isinstance(condition, dict):
                continue
            condition_key = str(condition.get("condition_key") or "").strip()
            condition_value = self._clean_placeholder_text(condition.get("condition_value"))
            if not (condition_key and condition_value):
                continue
            commands.append(
                fields.Command.create(
                    {
                        "condition_key": condition_key,
                        "condition_label": str(condition.get("condition_label") or condition_key).strip(),
                        "condition_value": str(condition_value).strip(),
                        "sequence": int(condition.get("sequence") or sequence),
                    }
                )
            )
            sequence += 10
        return commands

    @api.model
    def _condition_signature(self, conditions):
        normalized = []
        for condition in conditions or []:
            key = str(condition.get("condition_key") or "").strip().casefold()
            value = str(condition.get("condition_value") or "").strip().casefold()
            if key or value:
                normalized.append((key, value))
        return tuple(sorted(normalized))

    @api.model
    def _extract_legacy_conditions_from_param_key(self, param_key):
        key = str(param_key or "").strip().lower()
        if not key.startswith("peel_180_"):
            return []
        remainder = key[len("peel_180_") :]
        pieces = [piece for piece in remainder.split("_") if piece]
        mapping = {
            "sus": ("substrate", "被贴合物", "不锈钢"),
            "stainless": ("substrate", "被贴合物", "不锈钢"),
            "painted": ("substrate", "被贴合物", "涂装板"),
            "pp": ("substrate", "被贴合物", "PP"),
            "pe": ("substrate", "被贴合物", "PE"),
            "pvc": ("substrate", "被贴合物", "PVC"),
            "abs": ("substrate", "被贴合物", "ABS"),
            "pc": ("substrate", "被贴合物", "PC"),
            "glass": ("substrate", "被贴合物", "玻璃"),
            "immediate": ("state", "状态", "初始"),
            "normal": ("state", "状态", "常温"),
            "aged": ("state", "状态", "老化后"),
            "hot": ("state", "状态", "高温后"),
            "14": ("dwell_time", "驻留时间", "14天"),
        }
        result = []
        for piece in pieces:
            if piece in mapping:
                condition_key, condition_label, condition_value = mapping[piece]
                result.append(
                    {
                        "condition_key": condition_key,
                        "condition_label": condition_label,
                        "condition_value": str(condition_value).strip(),
                    }
                )
        return result

    @api.model
    def _ensure_condition_table(self):
        self.env.cr.execute(
            """
            CREATE TABLE IF NOT EXISTS diecut_catalog_item_spec_condition (
                id SERIAL PRIMARY KEY,
                spec_line_id INTEGER NOT NULL REFERENCES diecut_catalog_item_spec_line(id) ON DELETE CASCADE,
                sequence INTEGER DEFAULT 10,
                condition_key VARCHAR,
                condition_label VARCHAR,
                condition_value VARCHAR,
                create_uid INTEGER,
                create_date TIMESTAMP,
                write_uid INTEGER,
                write_date TIMESTAMP
            )
            """
        )
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS diecut_catalog_item_spec_condition_line_idx
                ON diecut_catalog_item_spec_condition (spec_line_id)
            """
        )

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
    def _drop_legacy_unique_constraint(self):
        self.env.cr.execute(
            """
            SELECT con.conname
              FROM pg_constraint con
              JOIN pg_class rel
                ON rel.oid = con.conrelid
             WHERE rel.relname = 'diecut_catalog_item_spec_line'
               AND con.contype = 'u'
            """
        )
        for (constraint_name,) in self.env.cr.fetchall():
            self.env.cr.execute(
                f'ALTER TABLE diecut_catalog_item_spec_line DROP CONSTRAINT IF EXISTS "{constraint_name}"'
            )

    @api.model
    def _migrate_legacy_spec_values(self):
        has_legacy_columns = any(
            self._column_exists("diecut_catalog_item_spec_line", column_name)
            for column_name in ("value_char", "value_float", "value_boolean", "value_selection", "value_text", "raw_value_text")
        )
        if not has_legacy_columns:
            return
        legacy_columns = {
            column_name: self._column_exists("diecut_catalog_item_spec_line", column_name)
            for column_name in ("value_char", "value_float", "value_boolean", "value_selection", "value_text", "raw_value_text")
        }
        select_parts = ["id", "param_id", "param_key"]
        for column_name in ("value_char", "value_float", "value_boolean", "value_selection", "value_text", "raw_value_text"):
            if legacy_columns[column_name]:
                select_parts.append(column_name)
            else:
                select_parts.append(f"NULL AS {column_name}")
        self.env.cr.execute(
            f"""
            SELECT {", ".join(select_parts)}
              FROM diecut_catalog_item_spec_line
            """
        )
        rows = self.env.cr.dictfetchall()
        param_model = self.env["diecut.catalog.param"].sudo()
        standard_peel_param = param_model.search([("param_key", "=", "peel_strength_180")], limit=1)
        for row in rows:
            param = param_model.browse(row["param_id"]) if row.get("param_id") else False
            param_key = row.get("param_key") or (param.param_key if param else False)
            if param_key and str(param_key).lower().startswith("peel_180_") and standard_peel_param:
                param = standard_peel_param
                self.env.cr.execute(
                    """
                    UPDATE diecut_catalog_item_spec_line
                       SET param_id = %s,
                           param_key = %s,
                           param_name = %s
                     WHERE id = %s
                    """,
                    (param.id, param.param_key, param.name, row["id"]),
                )
            raw_value = (
                row.get("raw_value_text")
                or row.get("value_text")
                or row.get("value_char")
                or row.get("value_selection")
            )
            raw_value = self._clean_placeholder_text(raw_value)
            value_kind = self._guess_value_kind(param, raw_value)
            value_number = row.get("value_float")
            if value_kind == "boolean" and row.get("value_boolean") in (True, False):
                raw_value = "true" if row.get("value_boolean") else "false"
            payload = self._normalize_value_payload(param, raw_value, value_kind=value_kind, value_number=value_number)
            self.env.cr.execute(
                """
                UPDATE diecut_catalog_item_spec_line
                   SET value_raw = %s,
                       value_number = %s,
                       value_kind = %s,
                       value_display = %s
                 WHERE id = %s
                """,
                (
                    payload["value_raw"],
                    None if payload["value_number"] in (False, None) else payload["value_number"],
                    payload["value_kind"],
                    False,
                    row["id"],
                ),
            )
            for index, condition in enumerate(self._extract_legacy_conditions_from_param_key(param_key), start=1):
                self.env.cr.execute(
                    """
                    INSERT INTO diecut_catalog_item_spec_condition
                        (spec_line_id, sequence, condition_key, condition_label, condition_value, create_uid, create_date, write_uid, write_date)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, NOW(), %s, NOW())
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        row["id"],
                        index * 10,
                        condition["condition_key"],
                        condition["condition_label"],
                        condition["condition_value"],
                        self.env.uid,
                        self.env.uid,
                    ),
                )

    @api.model
    def _drop_legacy_value_columns(self):
        for column_name in ("value_char", "value_float", "value_boolean", "value_selection", "value_text", "raw_value_text"):
            if self._column_exists("diecut_catalog_item_spec_line", column_name):
                self.env.cr.execute(f'ALTER TABLE diecut_catalog_item_spec_line DROP COLUMN IF EXISTS "{column_name}"')

    @api.model
    def _cleanup_placeholder_spec_values(self):
        placeholder_values = ("false", "False", "none", "None", "null", "Null")
        self.env.cr.execute(
            """
            UPDATE diecut_catalog_item_spec_condition
               SET condition_value = NULL
             WHERE lower(trim(coalesce(condition_value, ''))) IN %s
            """,
            (placeholder_values,),
        )
        self.env.cr.execute(
            """
            UPDATE diecut_catalog_item_spec_line
               SET unit = NULL
             WHERE lower(trim(coalesce(unit, ''))) IN %s
            """,
            (placeholder_values,),
        )
        self.env.cr.execute(
            """
            UPDATE diecut_catalog_item_spec_line
               SET value_raw = NULL,
                   value_number = NULL
             WHERE lower(trim(coalesce(value_raw, ''))) IN %s
               AND value_kind != 'boolean'
            """,
            (placeholder_values,),
        )
        self.env.cr.execute(
            """
            UPDATE diecut_catalog_item_spec_line
               SET value_number = NULL
             WHERE value_kind != 'number'
            """
        )
        self.env.cr.execute(
            """
            DELETE FROM diecut_catalog_item_spec_line line
             WHERE (
                    line.value_kind = 'number'
                AND (line.value_raw IS NULL OR btrim(line.value_raw) = '')
                AND line.value_number IS NULL
             ) OR (
                    line.value_kind IN ('text', 'selection')
                AND (line.value_raw IS NULL OR btrim(line.value_raw) = '')
             )
            """
        )
        self.env.cr.execute(
            """
            UPDATE diecut_catalog_item_spec_line
               SET value_display = CASE
                    WHEN value_kind = 'boolean' THEN
                        CASE WHEN lower(trim(coalesce(value_raw, ''))) IN ('1', 'true', 'yes', 'y', '?') THEN '?' ELSE '?' END
                    WHEN value_kind = 'number' THEN
                        CASE
                            WHEN value_raw IS NULL OR btrim(value_raw) = '' OR value_number IS NULL THEN ''
                            WHEN unit IS NULL OR btrim(unit) = '' THEN trim(to_char(value_number, 'FM999999999.################'))
                            ELSE trim(to_char(value_number, 'FM999999999.################') || ' ' || unit)
                        END
                    ELSE
                        CASE
                            WHEN value_raw IS NULL OR btrim(value_raw) = '' THEN ''
                            WHEN unit IS NULL OR btrim(unit) = '' THEN value_raw
                            ELSE trim(value_raw || ' ' || unit)
                        END
               END,
                   condition_summary = COALESCE(cond.summary, '')
              FROM (
                    SELECT spec_line_id, string_agg(condition_value, ' / ' ORDER BY sequence, id) AS summary
                      FROM diecut_catalog_item_spec_condition
                     WHERE condition_value IS NOT NULL
                       AND btrim(condition_value) != ''
                     GROUP BY spec_line_id
                   ) cond
             WHERE diecut_catalog_item_spec_line.id = cond.spec_line_id
                OR diecut_catalog_item_spec_line.condition_summary IS DISTINCT FROM COALESCE(cond.summary, '')
            """
        )
        self.env.cr.execute(
            """
            UPDATE diecut_catalog_item_spec_line
               SET condition_summary = ''
             WHERE id NOT IN (
                    SELECT DISTINCT spec_line_id
                      FROM diecut_catalog_item_spec_condition
                     WHERE condition_value IS NOT NULL
                       AND btrim(condition_value) != ''
             )
            """
        )

    def init(self):
        super().init()
        self._ensure_condition_table()
        self._drop_legacy_unique_constraint()
        self._migrate_legacy_spec_values()
        self._cleanup_placeholder_spec_values()
        self._drop_legacy_value_columns()

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

    @api.constrains("value_kind", "value_raw", "value_number", "param_id")
    def _check_value_payload(self):
        for record in self:
            if not record.param_id:
                continue
            expected_kind = self._guess_value_kind(record.param_id, record.value_raw)
            if record.value_kind != expected_kind:
                raise ValidationError("技术参数只能填写与参数值类型匹配的值形态。")
            if record.value_kind == "selection" and record.value_raw:
                options = record.param_id.get_selection_options_list()
                if options and record.value_raw not in options:
                    raise ValidationError("枚举参数值不在定义范围内。")

    @api.model
    def _refresh_related_item_search_text(self, items):
        if items and hasattr(items, "_compute_selection_search_text"):
            items._compute_selection_search_text()

    @api.model_create_multi
    def create(self, vals_list):
        normalized_list = []
        for vals in vals_list:
            vals = dict(vals)
            vals["unit"] = self._clean_placeholder_text(vals.get("unit"))
            vals["test_method"] = self._clean_placeholder_text(vals.get("test_method"))
            vals["test_condition"] = self._clean_placeholder_text(vals.get("test_condition"))
            vals["remark"] = self._clean_placeholder_text(vals.get("remark"))
            if "condition_ids" in vals and vals.get("condition_ids") and isinstance(vals.get("condition_ids"), list):
                normalized_list.append(vals)
                continue
            payload = self._normalize_value_payload(
                self.env["diecut.catalog.param"].browse(vals.get("param_id")) if vals.get("param_id") else False,
                vals.get("value_raw"),
                value_kind=vals.get("value_kind"),
                value_number=vals.get("value_number"),
            )
            vals.update(payload)
            normalized_list.append(vals)
        records = super().create(normalized_list)
        for record in records:
            record._sync_from_param()
        empty_records = records.filtered(lambda rec: rec.value_kind != "boolean" and rec.value_raw in (False, None, ""))
        if empty_records:
            empty_records.unlink()
        kept_records = records - empty_records
        kept_records.env["diecut.catalog.item.spec.line"]._refresh_related_item_search_text(kept_records.mapped("catalog_item_id"))
        return kept_records

    def write(self, vals):
        vals = dict(vals)
        for key in ("unit", "test_method", "test_condition", "remark"):
            if key in vals:
                vals[key] = self._clean_placeholder_text(vals.get(key))
        if any(key in vals for key in ("value_raw", "value_kind", "value_number")):
            payload = self._normalize_value_payload(
                self.env["diecut.catalog.param"].browse(vals.get("param_id")) if vals.get("param_id") else self[:1].param_id,
                vals.get("value_raw", self[:1].value_raw if self else False),
                value_kind=vals.get("value_kind", self[:1].value_kind if self else False),
                value_number=vals.get("value_number", self[:1].value_number if self else False),
            )
            vals.update(payload)
        res = super().write(vals)
        empty_records = self.filtered(lambda rec: rec.value_kind != "boolean" and rec.value_raw in (False, None, ""))
        if empty_records:
            empty_records.unlink()
        remaining_records = self - empty_records
        if "param_id" in vals:
            for record in remaining_records:
                record._sync_from_param()
        self.env["diecut.catalog.item.spec.line"]._refresh_related_item_search_text(remaining_records.mapped("catalog_item_id"))
        return res

    def unlink(self):
        items = self.mapped("catalog_item_id")
        res = super().unlink()
        self.env["diecut.catalog.item.spec.line"]._refresh_related_item_search_text(items)
        return res


class DiecutCatalogItemSpecCondition(models.Model):
    _name = "diecut.catalog.item.spec.condition"
    _description = "技术参数条件明细"
    _order = "sequence, id"

    spec_line_id = fields.Many2one(
        "diecut.catalog.item.spec.line",
        string="参数值",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="排序", default=10)
    condition_key = fields.Char(string="条件键", required=True, index=True)
    condition_label = fields.Char(string="条件名称", required=True)
    condition_value = fields.Char(string="条件值", required=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env["diecut.catalog.item.spec.line"]._refresh_related_item_search_text(records.mapped("spec_line_id.catalog_item_id"))
        return records

    def write(self, vals):
        res = super().write(vals)
        self.env["diecut.catalog.item.spec.line"]._refresh_related_item_search_text(self.mapped("spec_line_id.catalog_item_id"))
        return res

    def unlink(self):
        items = self.mapped("spec_line_id.catalog_item_id")
        res = super().unlink()
        self.env["diecut.catalog.item.spec.line"]._refresh_related_item_search_text(items)
        return res
