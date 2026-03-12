# -*- coding: utf-8 -*-
import csv
import json
import os
from urllib.parse import quote

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.modules.module import get_module_path


class CatalogFieldInfo(models.TransientModel):
    _name = "diecut.catalog.field.info"
    _description = "选型目录字段元数据"

    wizard_id = fields.Many2one("diecut.catalog.ops.wizard", required=True, ondelete="cascade")
    model_name = fields.Selection([
        ("diecut.catalog.item", "目录条目"),
    ], string="所属模型")
    field_name = fields.Char(string="字段技术名")
    field_string = fields.Char(string="中文标签")
    field_type = fields.Char(string="字段类型")
    field_help = fields.Text(string="用途说明")


class CatalogOpsWizard(models.TransientModel):
    _name = "diecut.catalog.ops.wizard"
    _description = "数据运维向导"

    _CSV_FILENAME = "catalog_items.csv"
    _JSON_FILENAME = "catalog_materials.json"

    operation = fields.Selection(
        [
            ("export_csv", "导出CSV（DB -> scripts）"),
            ("generate_assets", "从CSV严格同步JSON"),
            ("sync_csv_to_db", "CSV同步入库（严格对齐）"),
            ("cutover_baseline_snapshot", "生成切换基线记录"),
            ("edit_csv", "CSV轻量编辑"),
            ("view_fields_manual", "字段维护清单（catalog_item.py）"),
        ],
        string="操作",
        required=True,
        default="export_csv",
    )

    dry_run = fields.Boolean(string="预演", default=True)
    backfill_limit = fields.Integer(string="统计上限", default=0, help="0表示不限制")
    result_message = fields.Text(string="执行结果", readonly=True)
    guide_message = fields.Text(string="操作指南", readonly=True)
    csv_content = fields.Text(string="CSV内容")

    field_info_ids = fields.One2many("diecut.catalog.field.info", "wizard_id", string="字段清单")

    @api.onchange("operation")
    def _onchange_operation_populate_fields(self):
        if self.operation == "view_fields_manual":
            self._reload_field_info_lines()

    def _module_dir(self):
        module_dir = get_module_path("diecut")
        if not module_dir:
            raise UserError("未找到diecut模块目录。")
        return module_dir

    def _scripts_dir(self):
        return os.path.join(self._module_dir(), "scripts")

    def _data_dir(self):
        return os.path.join(self._module_dir(), "data")

    def _csv_path(self):
        return os.path.join(self._scripts_dir(), self._CSV_FILENAME)

    def _json_path(self):
        return os.path.join(self._data_dir(), self._JSON_FILENAME)

    @staticmethod
    def _read_csv_rows(path):
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as fp:
                return list(csv.DictReader(fp))
        except UnicodeDecodeError:
            with open(path, "r", encoding="gbk", newline="") as fp:
                return list(csv.DictReader(fp))

    @staticmethod
    def _to_bool(value, default=False):
        if value is None:
            return default
        s = str(value).strip().lower()
        if not s:
            return default
        if s in ("1", "true", "t", "yes", "y", "是"):
            return True
        if s in ("0", "false", "f", "no", "n", "否"):
            return False
        return default

    @staticmethod
    def _to_int(value, default=0):
        if value is None:
            return default
        s = str(value).strip()
        if not s:
            return default
        try:
            return int(float(s))
        except Exception:
            return default

    @staticmethod
    def _to_float(value, default=0.0):
        if value is None:
            return default
        s = str(value).strip()
        if not s:
            return default
        try:
            return float(s)
        except Exception:
            return default

    @staticmethod
    def _normalize_text(value):
        if value is None:
            return ""
        return str(value).replace("\r", "").strip()

    @staticmethod
    def _key_from_parts(brand_xml, code):
        b = (brand_xml or "").strip().lower()
        c = (code or "").strip().lower()
        if not b or not c:
            return None
        return f"{b}::{c}"

    @staticmethod
    def _db_key(brand_id, code):
        try:
            b = int(brand_id or 0)
        except Exception:
            b = 0
        c = (code or "").strip().lower()
        if not b or not c:
            return None
        return f"{b}::{c}"

    def _ref_xmlid(self, xmlid):
        xmlid = (xmlid or "").strip()
        if not xmlid:
            return False
        full = xmlid if "." in xmlid else f"diecut.{xmlid}"
        try:
            return self.env.ref(full)
        except Exception:
            return False

    @staticmethod
    def _xml_stub(xmlid, prefix):
        value = (xmlid or "").strip()
        if value.startswith(prefix):
            return value[len(prefix):].strip()
        return value

    def _resolve_brand(self, brand_xml):
        rec = self._ref_xmlid(brand_xml)
        if rec and rec._name == "diecut.brand":
            return rec

        stub = self._xml_stub(brand_xml, "brand_").lower()
        aliases = {
            "huangguan": "皇冠",
            "tesa": "Tesa",
        }
        candidates = []
        if stub:
            candidates.append(stub)
        if stub in aliases:
            candidates.insert(0, aliases[stub])

        brand_model = self.env["diecut.brand"]
        for name in candidates:
            hit = brand_model.search([("name", "ilike", name)], limit=1)
            if hit:
                return hit
        if not self.dry_run:
            create_name = aliases.get(stub) or stub or (brand_xml or "").strip() or "Unknown"
            return brand_model.create({"name": create_name})
        return False

    def _resolve_category(self, categ_xml):
        rec = self._ref_xmlid(categ_xml)
        if rec and rec._name == "product.category":
            return rec
        return False

    def _managed_field_names(self):
        model = self.env["diecut.catalog.item"]
        fields_map = model._fields
        blocked = {"id", "display_name", "create_uid", "create_date", "write_uid", "write_date", "__last_update", "is_duplicate_key"}
        names = []
        for name, field in fields_map.items():
            if name in blocked:
                continue
            if field.compute and not field.store:
                continue
            if field.type in ("one2many", "many2many"):
                continue
            names.append(name)
        return set(names)

    def _catalog_csv_headers(self):
        preferred = [
            "brand_id_xml", "categ_id_xml", "name", "code", "series_text", "catalog_status", "active", "sequence",
            "equivalent_type", "feature_desc", "special_applications", "typical_applications", "tds_content", "msds_content", "datasheet_content",
            "variant_thickness", "variant_adhesive_thickness", "variant_color", "variant_peel_strength", "variant_structure",
            "variant_adhesive_type", "variant_base_material", "variant_sus_peel", "variant_pe_peel", "variant_dupont",
            "variant_push_force", "variant_removability", "variant_tumbler", "variant_holding_power",
            "variant_thickness_std", "variant_color_std", "variant_adhesive_std", "variant_base_material_std",
            "variant_ref_price", "variant_is_rohs", "variant_is_reach", "variant_is_halogen_free", "variant_fire_rating",
        ]
        managed = self._managed_field_names()
        extras = sorted([n for n in managed if n not in preferred and n not in ("brand_id", "categ_id", "erp_product_tmpl_id", "diecut_properties")])
        return preferred + extras

    def _snapshot_csv_records(self):
        csv_path = self._csv_path()
        if not os.path.exists(csv_path):
            raise UserError(f"未找到CSV文件: {csv_path}")

        raw_rows = self._read_csv_rows(csv_path)
        snapshots = {}
        order = []

        for row in raw_rows:
            row = {k: self._normalize_text(v) for k, v in (row or {}).items()}
            key = self._key_from_parts(row.get("brand_id_xml"), row.get("code"))
            if not key:
                continue
            if key not in snapshots:
                order.append(key)
            snapshots[key] = row
        return [snapshots[k] for k in order]

    def _write_json_snapshot(self, rows):
        json_path = self._json_path()
        os.makedirs(self._data_dir(), exist_ok=True)
        payload = [dict(r) for r in rows]
        if not self.dry_run:
            with open(json_path, "w", encoding="utf-8") as fp:
                json.dump(payload, fp, ensure_ascii=False, indent=4)
        return json_path, len(payload)

    def _coerce_field_value(self, field, raw):
        if field.type == "boolean":
            return self._to_bool(raw, default=False)
        if field.type == "integer":
            return self._to_int(raw, default=0)
        if field.type in ("float", "monetary"):
            return self._to_float(raw, default=0.0)
        if field.type == "selection":
            value = self._normalize_text(raw)
            return value or False
        if field.type in ("char", "text", "html"):
            value = self._normalize_text(raw)
            return value or False
        if field.type == "many2one":
            return False
        value = self._normalize_text(raw)
        return value or False

    def _build_vals_from_csv_row(self, row):
        model = self.env["diecut.catalog.item"]
        vals = {}

        brand = self._resolve_brand(row.get("brand_id_xml"))
        if not brand:
            raise UserError(f"品牌外部ID不存在: {row.get('brand_id_xml')}")
        vals["brand_id"] = brand.id

        categ_xml = row.get("categ_id_xml")
        if categ_xml:
            categ = self._resolve_category(categ_xml)
            if categ:
                vals["categ_id"] = categ.id

        csv_keys = set(row.keys())
        managed = self._managed_field_names()
        ignored = {"brand_id_xml", "categ_id_xml", "brand_id", "categ_id", "erp_product_tmpl_id", "diecut_properties"}

        for field_name in (managed & csv_keys) - ignored:
            field = model._fields[field_name]
            vals[field_name] = self._coerce_field_value(field, row.get(field_name))

        if not vals.get("name"):
            vals["name"] = row.get("code") or "未命名型号"
        if "active" not in vals:
            vals["active"] = True
        if "sequence" not in vals:
            vals["sequence"] = 10

        return vals

    def _export_csv(self):
        headers = self._catalog_csv_headers()
        csv_path = self._csv_path()
        os.makedirs(self._scripts_dir(), exist_ok=True)

        records = self.env["diecut.catalog.item"].search([], order="brand_id, sequence, id")
        rows = []
        for rec in records:
            brand_xml = rec.brand_id.get_external_id().get(rec.brand_id.id, "") if rec.brand_id else ""
            categ_xml = rec.categ_id.get_external_id().get(rec.categ_id.id, "") if rec.categ_id else ""
            if brand_xml and "." in brand_xml:
                brand_xml = brand_xml.split(".", 1)[1]
            if categ_xml and "." in categ_xml:
                categ_xml = categ_xml.split(".", 1)[1]

            line = {"brand_id_xml": brand_xml, "categ_id_xml": categ_xml}
            for h in headers:
                if h in ("brand_id_xml", "categ_id_xml"):
                    continue
                if h not in rec._fields:
                    line[h] = ""
                    continue
                value = rec[h]
                if rec._fields[h].type == "boolean":
                    line[h] = "1" if value else "0"
                else:
                    line[h] = "" if value in (False, None) else str(value)
            rows.append(line)

        if not self.dry_run:
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as fp:
                writer = csv.DictWriter(fp, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)

        return f"导出完成（{'预演' if self.dry_run else '已落盘'}）\\n记录数: {len(rows)}\\nCSV: {csv_path}"

    def _generate_assets(self):
        rows = self._snapshot_csv_records()
        json_path, count = self._write_json_snapshot(rows)
        return f"JSON同步完成（{'预演' if self.dry_run else '已落盘'}）\\n记录数: {count}\\nJSON: {json_path}"

    def _sync_csv_to_db(self):
        rows = self._snapshot_csv_records()
        self._write_json_snapshot(rows)

        model = self.env["diecut.catalog.item"]
        all_db = model.search([("code", "!=", False)])
        db_map = {}
        for rec in all_db:
            key = self._db_key(rec.brand_id.id if rec.brand_id else 0, rec.code)
            if key:
                db_map[key] = rec

        resolved_rows = []
        for row in rows:
            vals = self._build_vals_from_csv_row(row)
            key = self._db_key(vals.get("brand_id"), vals.get("code"))
            if not key:
                continue
            resolved_rows.append((key, row, vals))

        resolved_map = {}
        for key, row, vals in resolved_rows:
            resolved_map[key] = (row, vals)
        csv_keys = set(resolved_map.keys())

        if self.dry_run:
            to_create_count = len([k for k in csv_keys if k not in db_map])
            to_update_count = len([k for k in csv_keys if k in db_map])
            to_delete_count = len([k for k in db_map.keys() if k not in csv_keys])
            return (
                "CSV同步入库完成（预演）\\n"
                f"CSV有效记录: {len(csv_keys)}\\n"
                f"新增: {to_create_count}\\n"
                f"更新: {to_update_count}\\n"
                f"删除: {to_delete_count}"
            )

        to_create = []
        to_update = []
        for key, (_row, vals) in resolved_map.items():
            rec = db_map.get(key)
            if rec:
                to_update.append((rec, vals))
            else:
                to_create.append(vals)

        to_delete = [rec for key, rec in db_map.items() if key not in csv_keys]

        for rec, vals in to_update:
            rec.write(vals)
        if to_create:
            model.create(to_create)
        if to_delete:
            model.browse([r.id for r in to_delete]).unlink()

        return (
            "CSV同步入库完成（已执行）\\n"
            f"CSV有效记录: {len(csv_keys)}\\n"
            f"新增: {len(to_create)}\\n"
            f"更新: {len(to_update)}\\n"
            f"删除: {len(to_delete)}"
        )

    def _write_log(self, success, detail, extra_vals=None):
        vals = {
            "operation": self.operation,
            "success": success,
            "detail": detail,
        }
        if extra_vals:
            vals.update(extra_vals)
        self.env["diecut.catalog.ops.log"].create(vals)

    def _build_cutover_baseline(self, limit=None):
        catalog = self.env["diecut.catalog.item"]
        model_domain = [("code", "!=", False)]
        total_models = catalog.search_count(model_domain)
        duplicate_ids = catalog._get_duplicate_model_ids()
        missing_series_text = catalog.search_count([("code", "!=", False), ("series_text", "=", False)])
        sample_domain = model_domain
        if limit and limit > 0:
            sample_domain = [("id", "in", catalog.search(model_domain, limit=limit).ids)]
        sampled_models = catalog.search_count(sample_domain)
        payload = {
            "read_mode": "new_gray",
            "catalog_models": {
                "total": total_models,
                "sampled": sampled_models,
                "duplicate_code_count": len(duplicate_ids),
                "series_text_missing_count": missing_series_text,
            },
        }
        return payload

    def action_show_guide(self):
        self.ensure_one()
        self.guide_message = (
            "【数据运维操作指南】\\n"
            "1) 导出CSV（DB -> scripts）：生成 scripts/catalog_items.csv\\n"
            "2) 从CSV严格同步JSON：覆盖 data/catalog_materials.json\\n"
            "3) CSV同步入库（严格对齐）：以CSV为基准执行新增/更新/删除\\n"
            "4) CSV轻量编辑：编辑并保存 catalog_items.csv\\n"
            "5) 字段维护清单：查看 diecut.catalog.item 字段"
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
            raise UserError(f"未找到文件: {path}")
        try:
            with open(path, "r", encoding="utf-8-sig") as fp:
                content = fp.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="gbk") as fp:
                content = fp.read()
        self.csv_content = content
        self.result_message = f"已加载 {self._CSV_FILENAME}，行数: {len(content.splitlines())}。"
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
            raise UserError("没有可保存内容，请先加载CSV。")
        os.makedirs(self._scripts_dir(), exist_ok=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as fp:
            fp.write(self.csv_content.replace("\r\n", "\n"))
        self.result_message = f"已保存 {self._CSV_FILENAME}，行数: {len(self.csv_content.splitlines())}。"
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
            "url": f"/diecut/catalog/csv-grid?file={quote(self._CSV_FILENAME)}",
            "target": "new",
        }

    def _collect_field_entries(self):
        field_entries = []
        model = self.env["diecut.catalog.item"]
        system_native_fields = {"id", "display_name", "create_uid", "create_date", "write_uid", "write_date", "__last_update"}

        for fname, field in model._fields.items():
            if fname in system_native_fields:
                continue
            field_entries.append({
                "model_name": "diecut.catalog.item",
                "field_name": fname,
                "field_string": field.string or fname,
                "field_type": field.type,
                "field_help": field.help or "",
            })

        field_entries.sort(key=lambda x: x["field_name"])
        return field_entries

    def _reload_field_info_lines(self):
        self.ensure_one()
        entries = self._collect_field_entries()
        commands = [fields.Command.clear()]
        commands.extend(fields.Command.create(vals) for vals in entries)
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
        log_extra = {}
        try:
            if self.operation == "export_csv":
                msg = self._export_csv()
            elif self.operation == "generate_assets":
                msg = self._generate_assets()
            elif self.operation == "sync_csv_to_db":
                msg = self._sync_csv_to_db()
            elif self.operation == "cutover_baseline_snapshot":
                limit = self.backfill_limit if (self.backfill_limit or 0) > 0 else None
                payload = self._build_cutover_baseline(limit=limit)
                catalog_models = payload["catalog_models"]
                msg = (
                    "切换基线记录已生成\\n"
                    f"入口模式: {payload['read_mode']}\\n"
                    f"型号总数: {catalog_models['total']}\\n"
                    f"抽样条数: {catalog_models['sampled']}\\n"
                    f"重复编码数: {catalog_models['duplicate_code_count']}\\n"
                    f"series_text缺失数: {catalog_models['series_text_missing_count']}"
                )
                log_extra = {
                    "read_mode": payload["read_mode"],
                    "shadow_model_count": catalog_models["total"],
                    "duplicate_brand_code_count": catalog_models["duplicate_code_count"],
                    "orphan_model_count": catalog_models["series_text_missing_count"],
                    "baseline_payload": json.dumps(payload, ensure_ascii=False, indent=2),
                }
            elif self.operation == "view_fields_manual":
                self.action_load_fields_manual()
                msg = "字段清单已刷新。"
            elif self.operation == "edit_csv":
                self.action_save_csv_editor()
                msg = self.result_message or "CSV已保存。"
            else:
                raise UserError("不支持的操作。")

            self.result_message = msg
            self._write_log(True, msg, log_extra)
        except Exception as exc:
            err = f"执行失败: {exc}"
            self.result_message = err
            self.env.cr.rollback()
            try:
                self._write_log(False, err, log_extra)
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
