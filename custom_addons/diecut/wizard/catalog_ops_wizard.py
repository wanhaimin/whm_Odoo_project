# -*- coding: utf-8 -*-

import base64
import csv
import io
import os
from urllib.parse import quote

from odoo import Command, fields, models
from odoo.exceptions import UserError
from odoo.modules.module import get_module_path


class CatalogFieldInfo(models.TransientModel):
    _name = "diecut.catalog.field.info"
    _description = "选型目录字段元数据"

    wizard_id = fields.Many2one("diecut.catalog.ops.wizard", required=True, ondelete="cascade")
    model_name = fields.Selection([("diecut.catalog.item", "目录条目")], string="所属模型")
    field_name = fields.Char(string="字段技术名")
    field_string = fields.Char(string="中文标签")
    field_type = fields.Char(string="字段类型")
    field_help = fields.Text(string="用途说明")


class CatalogOpsWizard(models.TransientModel):
    _name = "diecut.catalog.ops.wizard"
    _description = "数据运维向导"

    _MAIN_CSV_FILENAME = "catalog_items.csv"
    _SPEC_CSV_FILENAME = "catalog_item_specs.csv"
    _SPEC_DEF_CSV_FILENAME = "catalog_spec_defs.csv"
    _SERIES_CSV_FILENAME = "catalog_series.csv"

    operation = fields.Selection(
        [
            ("export_csv", "导出四CSV（DB -> scripts）"),
            ("validate_csv", "校验四CSV（不入库）"),
            ("sync_csv_to_db", "四CSV同步入库（严格对齐）"),
            ("cutover_baseline_snapshot", "生成切换基线记录"),
            ("edit_csv", "CSV轻量编辑"),
            ("view_fields_manual", "字段维护清单（catalog_item.py）"),
        ],
        string="操作",
        required=True,
        default="export_csv",
    )
    csv_target = fields.Selection(
        [("main", "主表 CSV"), ("spec", "技术参数 CSV"), ("spec_def", "参数定义 CSV"), ("series", "系列模板 CSV")],
        string="编辑文件",
        default="main",
    )
    dry_run = fields.Boolean(string="预演", default=True)
    sync_scope = fields.Selection([("all", "全量同步"), ("codes", "按型号同步"), ("category", "按分类同步")], string="同步范围", default="all")
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
            "spec_def": self._SPEC_DEF_CSV_FILENAME,
            "series": self._SERIES_CSV_FILENAME,
        }
        selected = target or self.csv_target
        if selected not in mapping:
            raise UserError(f"不支持的 CSV 类型: {selected}")
        return os.path.join(self._scripts_dir(), mapping[selected])

    @staticmethod
    def _read_csv_rows(path):
        with open(path, "r", encoding="utf-8-sig", newline="") as fp:
            return list(csv.DictReader(fp))

    @staticmethod
    def _norm(v):
        return "" if v is None else str(v).replace("\r", "").strip()

    def _resolve_brand_from_row(self, row):
        xmlid = self._norm(row.get("brand_id_xml"))
        if xmlid:
            full = xmlid if "." in xmlid else f"diecut.{xmlid}"
            try:
                rec = self.env.ref(full)
                if rec and rec._name == "diecut.brand":
                    return rec
            except Exception:
                pass
        name = self._norm(row.get("brand_name"))
        if name:
            rec = self.env["diecut.brand"].search([("name", "ilike", name)], limit=1)
            if rec:
                return rec
            if not self.dry_run:
                return self.env["diecut.brand"].create({"name": name})
        return False

    def _resolve_categ(self, xmlid):
        value = self._norm(xmlid)
        if not value:
            return False
        full = value if "." in value else f"diecut.{value}"
        try:
            rec = self.env.ref(full)
            return rec if rec and rec._name == "product.category" else False
        except Exception:
            return False

    def _resolve_or_create_series(self, brand, row):
        name = self._norm(row.get("series_name")) or self._norm(row.get("series_text"))
        if not brand or not name:
            return False
        series = self.env["diecut.catalog.series"].search([("brand_id", "=", brand.id), ("name", "=", name)], limit=1)
        if series:
            return series
        if not self.dry_run:
            return self.env["diecut.catalog.series"].create({"brand_id": brand.id, "name": name})
        return False

    def _export_csv(self):
        os.makedirs(self._scripts_dir(), exist_ok=True)
        items = self.env["diecut.catalog.item"].search([], order="brand_id, sequence, id")
        defs = self.env["diecut.catalog.spec.def"].search([], order="categ_id, sequence, id")
        series_list = self.env["diecut.catalog.series"].search([], order="brand_id, sequence, id")

        main_headers = ["brand_id_xml", "brand_name", "categ_id_xml", "series_name", "name", "code", "catalog_status", "product_features", "product_description", "main_applications", "special_applications"]
        spec_headers = ["brand_id_xml", "brand_name", "categ_id_xml", "item_code", "param_key", "value", "unit", "test_method", "test_condition", "remark", "sequence"]
        def_headers = ["categ_id_xml", "param_key", "name", "value_type", "unit", "selection_options", "sequence", "required", "active", "show_in_form", "allow_import"]
        series_headers = ["brand_id_xml", "brand_name", "series_name", "product_features", "product_description", "main_applications", "active", "sequence"]

        main_rows, spec_rows, def_rows, series_rows = [], [], [], []
        for rec in items:
            bx = rec.brand_id.get_external_id().get(rec.brand_id.id, "") if rec.brand_id else ""
            cx = rec.categ_id.get_external_id().get(rec.categ_id.id, "") if rec.categ_id else ""
            bx = bx.split(".", 1)[1] if "." in bx else bx
            cx = cx.split(".", 1)[1] if "." in cx else cx
            main_rows.append({"brand_id_xml": bx, "brand_name": rec.brand_id.name if rec.brand_id else "", "categ_id_xml": cx, "series_name": rec.series_id.name if rec.series_id else "", "name": rec.name or "", "code": rec.code or "", "catalog_status": rec.catalog_status or "", "product_features": rec.product_features or "", "product_description": rec.product_description or "", "main_applications": rec.main_applications or "", "special_applications": rec.special_applications or ""})
            for line in rec.spec_line_ids.sorted(lambda x: (x.sequence, x.id)):
                spec_rows.append({"brand_id_xml": bx, "brand_name": rec.brand_id.name if rec.brand_id else "", "categ_id_xml": cx, "item_code": rec.code or "", "param_key": line.param_key or "", "value": line.value_text or "", "unit": line.unit or "", "test_method": line.test_method or "", "test_condition": line.test_condition or "", "remark": line.remark or "", "sequence": str(line.sequence or 10)})
        for d in defs:
            cx = d.categ_id.get_external_id().get(d.categ_id.id, "") if d.categ_id else ""
            cx = cx.split(".", 1)[1] if "." in cx else cx
            def_rows.append({"categ_id_xml": cx, "param_key": d.param_key or "", "name": d.name or "", "value_type": d.value_type or "", "unit": d.unit or "", "selection_options": d.selection_options or "", "sequence": str(d.sequence or 10), "required": "1" if d.required else "0", "active": "1" if d.active else "0", "show_in_form": "1" if d.show_in_form else "0", "allow_import": "1" if d.allow_import else "0"})
        for s in series_list:
            bx = s.brand_id.get_external_id().get(s.brand_id.id, "") if s.brand_id else ""
            bx = bx.split(".", 1)[1] if "." in bx else bx
            series_rows.append({"brand_id_xml": bx, "brand_name": s.brand_id.name if s.brand_id else "", "series_name": s.name or "", "product_features": s.product_features or "", "product_description": s.product_description or "", "main_applications": s.main_applications or "", "active": "1" if s.active else "0", "sequence": str(s.sequence or 10)})

        if not self.dry_run:
            for target, headers, rows in (("main", main_headers, main_rows), ("spec", spec_headers, spec_rows), ("spec_def", def_headers, def_rows), ("series", series_headers, series_rows)):
                with open(self._csv_path(target), "w", encoding="utf-8-sig", newline="") as fp:
                    writer = csv.DictWriter(fp, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(rows)
        return f"导出完成（{'预演' if self.dry_run else '已落地'}）\n主表:{len(main_rows)} 参数值:{len(spec_rows)} 参数定义:{len(def_rows)} 系列模板:{len(series_rows)}"

    def _validate_csv_only(self):
        errors = []
        for target in ("main", "spec", "spec_def", "series"):
            if not os.path.exists(self._csv_path(target)):
                errors.append(f"{target} CSV 文件不存在")
        main_rows = self._read_csv_rows(self._csv_path("main")) if not errors else []
        for i, row in enumerate(main_rows, start=2):
            brand = self._resolve_brand_from_row(row)
            if not brand:
                errors.append(f"[{self._MAIN_CSV_FILENAME} 行{i}] 品牌不存在（brand_id_xml/brand_name）")
            if not (self._norm(row.get("series_name")) or self._norm(row.get("series_text"))):
                errors.append(f"[{self._MAIN_CSV_FILENAME} 行{i}] series_name/series_text 不能为空")
            if not self._norm(row.get("code")):
                errors.append(f"[{self._MAIN_CSV_FILENAME} 行{i}] code 不能为空")
        if errors:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["message"])
            for e in errors:
                writer.writerow([e])
            self.validation_report_file = base64.b64encode(output.getvalue().encode("utf-8-sig"))
            self.validation_report_filename = "catalog_validation_report.csv"
            return "CSV 校验失败（未入库）\n" + "\n".join(errors[:30])
        self.validation_report_file = False
        self.validation_report_filename = False
        return "CSV 校验通过（未入库）"

    def _sync_csv_to_db(self):
        msg = self._validate_csv_only()
        if "失败" in msg:
            return msg
        main_rows = self._read_csv_rows(self._csv_path("main"))
        spec_rows = self._read_csv_rows(self._csv_path("spec"))
        spec_def_rows = self._read_csv_rows(self._csv_path("spec_def"))
        series_rows = self._read_csv_rows(self._csv_path("series"))

        spec_def_model = self.env["diecut.catalog.spec.def"]
        for row in spec_def_rows:
            cx = self._resolve_categ(row.get("categ_id_xml"))
            if not cx:
                continue
            key = self._norm(row.get("param_key"))
            if not key:
                continue
            vals = {"categ_id": cx.id, "param_key": key, "name": self._norm(row.get("name")) or key, "value_type": self._norm(row.get("value_type")) or "char", "unit": self._norm(row.get("unit")) or False, "selection_options": self._norm(row.get("selection_options")) or False, "sequence": int(float(self._norm(row.get("sequence")) or 10)), "required": self._norm(row.get("required")) in ("1", "true", "True"), "active": self._norm(row.get("active")) not in ("0", "false", "False"), "show_in_form": self._norm(row.get("show_in_form")) not in ("0", "false", "False"), "allow_import": self._norm(row.get("allow_import")) not in ("0", "false", "False")}
            rec = spec_def_model.search([("categ_id", "=", cx.id), ("param_key", "=", key)], limit=1)
            if rec:
                if not self.dry_run:
                    rec.write(vals)
            elif not self.dry_run:
                spec_def_model.create(vals)

        series_model = self.env["diecut.catalog.series"]
        for row in series_rows:
            brand = self._resolve_brand_from_row(row)
            if not brand:
                continue
            name = self._norm(row.get("series_name"))
            if not name:
                continue
            vals = {"brand_id": brand.id, "name": name, "product_features": self._norm(row.get("product_features")) or False, "product_description": self._norm(row.get("product_description")) or False, "main_applications": self._norm(row.get("main_applications")) or False, "active": self._norm(row.get("active")) not in ("0", "false", "False"), "sequence": int(float(self._norm(row.get("sequence")) or 10))}
            rec = series_model.search([("brand_id", "=", brand.id), ("name", "=", name)], limit=1)
            if rec:
                if not self.dry_run:
                    rec.write(vals)
            elif not self.dry_run:
                series_model.create(vals)

        item_model = self.env["diecut.catalog.item"].with_context(skip_spec_autofill=True)
        db_map = {}
        for rec in item_model.search(self._record_domain_for_scope()):
            key = self._db_key(rec.brand_id.id if rec.brand_id else 0, rec.code)
            if key:
                db_map[key] = rec
        resolved = {}
        for row in main_rows:
            brand = self._resolve_brand_from_row(row)
            if not brand:
                continue
            code = self._norm(row.get("code"))
            if not code:
                continue
            series = self._resolve_or_create_series(brand, row)
            categ = self._resolve_categ(row.get("categ_id_xml"))
            vals = {"brand_id": brand.id, "code": code, "name": self._norm(row.get("name")) or code, "categ_id": categ.id if categ else False, "series_id": series.id if series else False, "series_text": series.name if series else (self._norm(row.get("series_name")) or False), "catalog_status": self._norm(row.get("catalog_status")) or "draft", "product_features": self._norm(row.get("product_features")) or False, "product_description": self._norm(row.get("product_description")) or False, "main_applications": self._norm(row.get("main_applications")) or False, "special_applications": self._norm(row.get("special_applications")) or False}
            resolved[self._db_key(brand.id, code)] = vals

        if self.dry_run:
            return f"四CSV 同步入库完成（预演）\n主表有效记录: {len(resolved)} 参数行数: {len(spec_rows)}"

        for key, vals in resolved.items():
            rec = db_map.get(key)
            if rec:
                rec.write(vals)
            else:
                item_model.create(vals)
        for key, rec in db_map.items():
            if key not in resolved:
                rec.unlink()

        item_map = {}
        for rec in item_model.search(self._record_domain_for_scope()):
            k = self._db_key(rec.brand_id.id if rec.brand_id else 0, rec.code)
            if k:
                item_map[k] = rec
        grouped_specs = {}
        for row in spec_rows:
            brand = self._resolve_brand_from_row(row)
            k = self._db_key(brand.id if brand else 0, self._norm(row.get("item_code")))
            if k:
                grouped_specs.setdefault(k, []).append(row)
        for key, item in item_map.items():
            commands = [Command.clear()]
            effective = item._get_effective_importable_spec_def_map(item.categ_id.id) if item.categ_id else {}
            for row in grouped_specs.get(key, []):
                pkey = self._norm(row.get("param_key"))
                spec_def = effective.get(pkey)
                if not spec_def:
                    continue
                commands.append(
                    Command.create(
                        {
                            "spec_def_id": spec_def.id,
                            "sequence": int(float(self._norm(row.get("sequence")) or (spec_def.sequence or 10))),
                            "param_key": spec_def.param_key,
                            "param_name": spec_def.name,
                            "value_char": self._norm(row.get("value")) if spec_def.value_type == "char" else False,
                            "value_float": float(self._norm(row.get("value"))) if spec_def.value_type == "float" and self._norm(row.get("value")) else False,
                            "value_boolean": self._norm(row.get("value")).lower() in ("1", "true", "yes", "y", "是") if spec_def.value_type == "boolean" and self._norm(row.get("value")) else False,
                            "value_selection": self._norm(row.get("value")) if spec_def.value_type == "selection" else False,
                            "unit": self._norm(row.get("unit")) or spec_def.unit,
                            "test_method": self._norm(row.get("test_method")) or False,
                            "test_condition": self._norm(row.get("test_condition")) or False,
                            "remark": self._norm(row.get("remark")) or False,
                        }
                    )
                )
            item.write({"spec_line_ids": commands})
        return "四CSV 同步入库完成（已执行）"

    def _write_log(self, success, detail, extra_vals=None):
        vals = {"operation": self.operation, "success": success, "detail": detail}
        if extra_vals:
            vals.update(extra_vals)
        self.env["diecut.catalog.ops.log"].create(vals)

    def _build_cutover_baseline(self, limit=None):
        catalog = self.env["diecut.catalog.item"]
        model_domain = [("code", "!=", False)]
        total_models = catalog.search_count(model_domain)
        duplicate_ids = catalog._get_duplicate_model_ids()
        missing_series_text = catalog.search_count([("code", "!=", False), ("series_text", "=", False)])
        sampled_models = catalog.search_count([("id", "in", catalog.search(model_domain, limit=limit).ids)]) if limit and limit > 0 else total_models
        return {"read_mode": "new_gray", "catalog_models": {"total": total_models, "sampled": sampled_models, "duplicate_code_count": len(duplicate_ids), "series_text_missing_count": missing_series_text}}

    def action_show_guide(self):
        self.ensure_one()
        self.guide_message = (
            "【数据运维操作指南】\n"
            f"1) 导出四CSV：scripts/{self._MAIN_CSV_FILENAME}、scripts/{self._SPEC_CSV_FILENAME}、scripts/{self._SPEC_DEF_CSV_FILENAME}、scripts/{self._SERIES_CSV_FILENAME}\n"
            "2) 四CSV 同步入库：先参数定义/系列模板，再主表与参数值。"
        )
        return {"type": "ir.actions.act_window", "name": "数据运维", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}

    def action_load_csv_editor(self):
        self.ensure_one()
        path = self._csv_path()
        if not os.path.exists(path):
            raise UserError(f"未找到文件: {path}")
        with open(path, "r", encoding="utf-8-sig") as fp:
            self.csv_content = fp.read()
        self.result_message = f"已加载 {os.path.basename(path)}。"
        return {"type": "ir.actions.act_window", "name": "数据运维", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}

    def action_save_csv_editor(self):
        self.ensure_one()
        path = self._csv_path()
        if self.csv_content is None:
            raise UserError("没有可保存内容。")
        os.makedirs(self._scripts_dir(), exist_ok=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as fp:
            fp.write(self.csv_content.replace("\r\n", "\n"))
        self.result_message = f"已保存 {os.path.basename(path)}。"
        return {"type": "ir.actions.act_window", "name": "数据运维", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}

    def action_open_aggrid_editor(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": f"/diecut/catalog/csv-grid?file={quote(os.path.basename(self._csv_path()))}", "target": "new"}

    def _collect_field_entries(self):
        entries = []
        model = self.env["diecut.catalog.item"]
        native = {"id", "display_name", "create_uid", "create_date", "write_uid", "write_date", "__last_update"}
        for field_name, field in model._fields.items():
            if field_name in native or field_name in self._legacy_spec_field_names():
                continue
            entries.append({"model_name": "diecut.catalog.item", "field_name": field_name, "field_string": field.string or field_name, "field_type": field.type, "field_help": field.help or ""})
        entries.sort(key=lambda x: x["field_name"])
        return entries

    def _reload_field_info_lines(self):
        self.ensure_one()
        commands = [fields.Command.clear()]
        commands.extend(fields.Command.create(v) for v in self._collect_field_entries())
        self.field_info_ids = commands

    def action_load_fields_manual(self):
        self.ensure_one()
        self._reload_field_info_lines()
        return {"type": "ir.actions.act_window", "name": "数据运维", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}

    def action_execute(self):
        self.ensure_one()
        self.validation_report_file = False
        self.validation_report_filename = False
        log_extra = {}
        try:
            if self.operation == "export_csv":
                message = self._export_csv()
            elif self.operation == "validate_csv":
                message = self._validate_csv_only()
            elif self.operation == "sync_csv_to_db":
                message = self._sync_csv_to_db()
            elif self.operation == "cutover_baseline_snapshot":
                limit = self.backfill_limit if (self.backfill_limit or 0) > 0 else None
                payload = self._build_cutover_baseline(limit=limit)
                c = payload["catalog_models"]
                message = f"切换基线记录已生成\n入口模式: {payload['read_mode']}\n型号总数: {c['total']}\n抽样条数: {c['sampled']}\n重复编码数: {c['duplicate_code_count']}\nseries_text 缺失数: {c['series_text_missing_count']}"
                log_extra = {"read_mode": payload["read_mode"], "shadow_model_count": c["total"], "duplicate_brand_code_count": c["duplicate_code_count"], "orphan_model_count": c["series_text_missing_count"], "baseline_payload": str(payload)}
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
        return {"type": "ir.actions.act_window", "name": "数据运维", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}
