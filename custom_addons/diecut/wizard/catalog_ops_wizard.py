# -*- coding: utf-8 -*-
import csv
import json
import os
import re
from urllib.parse import quote
from html import unescape
from xml.sax.saxutils import escape

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.modules.module import get_module_path

try:
    from odoo.tools.convert import convert_file
except Exception:  # pragma: no cover
    from odoo.tools import convert_file


class CatalogFieldInfo(models.TransientModel):
    _name = "diecut.catalog.field.info"
    _description = "选型目录字段元数据"

    wizard_id = fields.Many2one("diecut.catalog.ops.wizard")
    model_name = fields.Selection([
        ('product.template', '系列 (Template)'),
        ('product.product', '型号 (Product)')
    ], string="所属层级")
    field_name = fields.Char(string="字段技术名称")
    field_string = fields.Char(string="中文标签")
    field_type = fields.Char(string="字段类型")
    field_help = fields.Text(string="用途说明 / Help")


class CatalogOpsWizard(models.TransientModel):
    _name = "diecut.catalog.ops.wizard"
    _description = "数据运维向导"

    operation = fields.Selection(
        [
            ("export_csv", "导出CSV（DB -> scripts）"),
            ("generate_assets", "从CSV生成JSON/XML"),
            ("sync_csv_to_db", "CSV同步入库"),
            ("shadow_backfill", "新架构影子回填（旧模型 -> catalog.item）"),
            ("shadow_reconcile", "新架构影子对账报告"),
            ("shadow_refresh_fields", "新架构字段刷新（旧模型 -> 新模型）"),
            ("shadow_compare_fields", "新旧字段一致性检查"),
            ("shadow_compare_attachments", "新旧附件一致性检查"),
            ("cutover_baseline_snapshot", "生成切换基线记录"),
            ("import_xml", "导入指定XML"),
            ("cleanup_xml", "清理未匹配品牌XML"),
            ("edit_csv", "CSV轻量编辑"),
            ("view_fields_manual", "字段维护清单"),
        ],
        string="操作",
        required=True,
        default="export_csv",
    )
    field_info_ids = fields.One2many(
        "diecut.catalog.field.info", "wizard_id", string="字段清单"
    )

    @api.onchange('operation')
    def _onchange_operation_populate_fields(self):
        if self.operation == 'view_fields_manual':
            self._reload_field_info_lines()
    xml_file = fields.Selection(selection="_selection_xml_files", string="XML文件")
    auto_create_external_ids = fields.Boolean(string="自动补齐外部ID", default=True)
    prune_unmatched_xml = fields.Boolean(string="删除未匹配品牌XML", default=False)
    dry_run = fields.Boolean(string="预演（不落盘/不删除）", default=True)
    backfill_limit = fields.Integer(string="回填上限", default=0, help="仅用于影子回填；0 表示不限制。")
    confirm_delete_token = fields.Char(
        string="删除确认词",
        help="执行真实删除前，请输入：DELETE",
    )
    delete_preview = fields.Text(string="待删除项目", readonly=True)
    result_message = fields.Text(string="执行结果", readonly=True)
    guide_message = fields.Text(string="操作指南", readonly=True)
    csv_target_file = fields.Selection(
        [
            ("series.csv", "series.csv（系列）"),
            ("variants.csv", "variants.csv（型号）"),
        ],
        string="CSV文件",
        default="series.csv",
    )
    csv_content = fields.Text(string="CSV内容")

    def _module_dir(self):
        module_dir = get_module_path("diecut")
        if not module_dir:
            raise UserError("未找到 diecut 模块目录。")
        return module_dir

    def _data_dir(self):
        return os.path.join(self._module_dir(), "data")

    def _scripts_dir(self):
        return os.path.join(self._module_dir(), "scripts")

    def _csv_file_path(self):
        self.ensure_one()
        filename = self.csv_target_file or "series.csv"
        if filename not in ("series.csv", "variants.csv"):
            raise UserError("仅允许编辑 series.csv 或 variants.csv。")
        return os.path.join(self._scripts_dir(), filename), filename

    @api.model
    def _selection_xml_files(self):
        data_dir = self._data_dir()
        if not os.path.isdir(data_dir):
            return []
        return [(f, f) for f in sorted(os.listdir(data_dir)) if f.lower().endswith(".xml")]

    @staticmethod
    def _strip_html(html_str):
        if not html_str:
            return ""
        text = re.sub(r"<br\s*/?>", "\n", html_str, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = unescape(text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _slug(text):
        value = (text or "").strip().lower()
        value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", value)
        return value.strip("_") or "x"

    def _local_xmlid(self, record, fallback_prefix):
        if not record:
            return ""
        xml_map = record.get_external_id()
        full = xml_map.get(record.id)
        if full and "." in full:
            return full.split(".", 1)[1]
        if full:
            return full
        if not self.auto_create_external_ids or self.dry_run:
            return f"{fallback_prefix}_{record.id}"

        model_name = record._name
        base = f"{fallback_prefix}_{self._slug(getattr(record, 'name', '') or record.display_name)}_{record.id}"
        name = base
        seq = 1
        imd = self.env["ir.model.data"]
        while imd.search_count([("module", "=", "diecut"), ("name", "=", name)]):
            seq += 1
            name = f"{base}_{seq}"
        imd.create(
            {
                "module": "diecut",
                "name": name,
                "model": model_name,
                "res_id": record.id,
                "noupdate": True,
            }
        )
        return name

    def _export_csv(self):
        scripts_dir = self._scripts_dir()
        data_dir = self._data_dir()
        os.makedirs(scripts_dir, exist_ok=True)

        tmpl_recs = self.env["product.template"].search([("is_catalog", "=", True)])
        series_rows = []
        tmpl_xml_map = {}
        for tmpl in tmpl_recs:
            series_xml = self._local_xmlid(tmpl, "catalog_ui")
            tmpl_xml_map[tmpl.id] = series_xml
            brand_xml = self._local_xmlid(tmpl.brand_id, "brand_ui") if tmpl.brand_id else ""
            categ_xml = self._local_xmlid(tmpl.categ_id, "categ_ui") if tmpl.categ_id else ""
            series_rows.append(
                [
                    brand_xml,
                    categ_xml,
                    series_xml,
                    tmpl.name or "",
                    tmpl.series_name or "",
                    tmpl.catalog_base_material or "",
                    tmpl.catalog_adhesive_type or "",
                    tmpl.catalog_characteristics or "",
                    self._strip_html(tmpl.catalog_features or ""),
                    self._strip_html(tmpl.catalog_applications or ""),
                ]
            )

        series_csv = os.path.join(scripts_dir, "series.csv")
        if not self.dry_run:
            with open(series_csv, "w", encoding="utf-8-sig", newline="") as fp:
                writer = csv.writer(fp)
                writer.writerow(
                    [
                        "brand_id_xml",
                        "categ_id_xml",
                        "series_xml_id",
                        "name",
                        "series_name",
                        "catalog_base_material",
                        "catalog_adhesive_type",
                        "catalog_characteristics",
                        "catalog_features",
                        "catalog_applications",
                    ]
                )
                writer.writerows(series_rows)

        variant_recs = self.env["product.product"].search([("product_tmpl_id.is_catalog", "=", True)])
        base_headers = [
            "series_xml_id",
            "default_code",
            "variant_thickness",
            "variant_color",
            "variant_adhesive_type",
            "variant_base_material",
            "variant_peel_strength",
        ]
        extra_headers = set()
        variant_fields = []
        for fname, field in self.env["product.product"]._fields.items():
            if not fname.startswith("variant_"):
                continue
            if fname in (
                "variant_seller_ids",
                "variant_tds_file",
                "variant_msds_file",
                "variant_datasheet",
                "variant_catalog_structure_image",
                "variant_tds_filename",
                "variant_msds_filename",
                "variant_datasheet_filename",
                "variant_replacement_catalog_ids",
            ):
                continue
            if not field.store:
                continue
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", fname):
                continue
            variant_fields.append(fname)

        for rec in variant_recs:
            for fname in variant_fields:
                value = rec[fname]
                if value and fname not in base_headers:
                    extra_headers.add(fname)
        headers_list = base_headers + sorted(extra_headers)

        variants_rows = []
        json_data = {}
        for rec in variant_recs:
            series_xml = tmpl_xml_map.get(rec.product_tmpl_id.id) or self._local_xmlid(rec.product_tmpl_id, "catalog_ui")
            code = rec.default_code or ""
            row = []
            v_dict = {"default_code": code}
            for header in headers_list:
                if header == "series_xml_id":
                    row.append(series_xml)
                elif header == "default_code":
                    row.append(code)
                else:
                    val = rec[header]
                    val_str = str(val) if val else ""
                    row.append(val_str)
                    if val:
                        v_dict[header] = val_str
            variants_rows.append(row)
            json_data.setdefault(series_xml, []).append(v_dict)

        variants_csv = os.path.join(scripts_dir, "variants.csv")
        json_out = [{"series_xml_id": f"diecut.{sid}", "variants": rows} for sid, rows in json_data.items()]
        json_path = os.path.join(data_dir, "catalog_materials.json")
        if not self.dry_run:
            with open(variants_csv, "w", encoding="utf-8-sig", newline="") as fp:
                writer = csv.writer(fp)
                writer.writerow(headers_list)
                writer.writerows(variants_rows)
            with open(json_path, "w", encoding="utf-8") as fp:
                json.dump(json_out, fp, ensure_ascii=False, indent=4)

        return (
            f"导出完成（{'预演' if self.dry_run else '已落盘'}）\n"
            f"系列: {len(series_rows)}\n型号: {len(variants_rows)}\n"
            f"series.csv: {series_csv}\nvariants.csv: {variants_csv}\njson: {json_path}"
        )

    def _read_csv_safe(self, path):
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as fp:
                rows = list(csv.reader(fp))
        except UnicodeDecodeError:
            with open(path, "r", encoding="gbk", newline="") as fp:
                rows = list(csv.reader(fp))
        return [[col.replace("\r", "") for col in row] for row in rows]

    @staticmethod
    def _brand_to_xml_filename(brand_xml_id):
        if brand_xml_id.startswith("brand_ui_"):
            parts = brand_xml_id.split("_")
            brand_str = "_".join(parts[2:-1]) if len(parts) >= 4 else parts[-1]
        elif brand_xml_id.startswith("brand_"):
            brand_str = brand_xml_id.replace("brand_", "")
        else:
            brand_str = brand_xml_id
        return f"catalog_{brand_str}_data.xml"

    @staticmethod
    def _text_to_html(text):
        if not text or not text.strip():
            return ""
        if re.search(r"<[a-z][a-z0-9]*[\s>]", text, re.IGNORECASE):
            return text
        paragraphs = [line.strip() for line in text.strip().split("\n") if line.strip()]
        return "".join(f"<p>{p}</p>" for p in paragraphs)

    def _generate_assets(self, prune_xml=False):
        scripts_dir = self._scripts_dir()
        data_dir = self._data_dir()
        series_csv = os.path.join(scripts_dir, "series.csv")
        variants_csv = os.path.join(scripts_dir, "variants.csv")
        if not os.path.exists(series_csv):
            raise UserError(f"未找到文件: {series_csv}")
        if not os.path.exists(variants_csv):
            raise UserError(f"未找到文件: {variants_csv}")

        variants_by_series = {}
        variants_data = self._read_csv_safe(variants_csv)
        if variants_data:
            headers = variants_data[0]
            for row in variants_data[1:]:
                if not row or not row[0].strip():
                    continue
                row_dict = dict(zip(headers, row))
                series_id = row_dict.pop("series_xml_id", "")
                if not series_id:
                    continue
                clean = {k: v.strip() for k, v in row_dict.items() if v and v.strip()}
                if clean:
                    variants_by_series.setdefault(series_id, []).append(clean)

        series_by_brand = {}
        series_data = self._read_csv_safe(series_csv)
        if series_data:
            headers = series_data[0]
            for row in series_data[1:]:
                if not row:
                    continue
                row_dict = dict(zip(headers, row))
                if not row_dict.get("series_xml_id", "").strip():
                    continue
                brand_xml_id = row_dict.get("brand_id_xml", "").strip()
                series_by_brand.setdefault(brand_xml_id, []).append(row_dict)

        json_output = []
        for series_id, variants in variants_by_series.items():
            full_xml_id = series_id if series_id.startswith("diecut.") else f"diecut.{series_id}"
            json_output.append({"series_xml_id": full_xml_id, "variants": variants})

        json_path = os.path.join(data_dir, "catalog_materials.json")
        if not self.dry_run:
            with open(json_path, "w", encoding="utf-8") as fp:
                json.dump(json_output, fp, ensure_ascii=False, indent=4)

        target_files = {self._brand_to_xml_filename(k) for k in series_by_brand.keys()}
        deleted = self._list_unmatched_brand_xml(target_files)
        if prune_xml and not self.dry_run:
            for filename in deleted:
                os.remove(os.path.join(data_dir, filename))

        generated = []
        for brand_xml_id, series_list in series_by_brand.items():
            xml_filename = self._brand_to_xml_filename(brand_xml_id)
            brand_str = xml_filename[len("catalog_") : -len("_data.xml")]
            xml_path = os.path.join(data_dir, xml_filename)
            generated.append(xml_filename)

            lines = []
            lines.append('<?xml version="1.0" encoding="utf-8"?>')
            lines.append("<odoo>")
            lines.append('    <data noupdate="1">')
            if brand_xml_id and not brand_xml_id.startswith("brand_ui_exported"):
                lines.append(f'        <record id="{brand_xml_id}" model="diecut.brand">')
                lines.append(f"            <field name=\"name\">{escape(brand_str.title() or 'Unknown Brand')}</field>")
                lines.append("        </record>")
                lines.append("")
            for series in series_list:
                lines.append(f'        <record id="{series["series_xml_id"]}" model="product.template">')
                lines.append(f'            <field name="name"><![CDATA[{series.get("name", "")}]]></field>')
                lines.append("            <field name=\"is_catalog\">True</field>")
                lines.append("            <field name=\"catalog_status\">published</field>")
                categ_xml = series.get("categ_id_xml") or "category_tape_foam"
                lines.append(f'            <field name="categ_id" ref="{categ_xml}" />')
                if brand_xml_id:
                    lines.append(f'            <field name="brand_id" ref="{brand_xml_id}" />')
                lines.append(
                    f'            <field name="catalog_base_material"><![CDATA[{series.get("catalog_base_material", "")}]]></field>'
                )
                lines.append(
                    f'            <field name="catalog_adhesive_type"><![CDATA[{series.get("catalog_adhesive_type", "")}]]></field>'
                )
                lines.append(
                    f'            <field name="catalog_characteristics"><![CDATA[{series.get("catalog_characteristics", "")}]]></field>'
                )
                lines.append(f'            <field name="catalog_features"><![CDATA[{series.get("catalog_features", "")}]]></field>')
                lines.append(
                    f'            <field name="catalog_applications"><![CDATA[{self._text_to_html(series.get("catalog_applications", ""))}]]></field>'
                )
                lines.append(f'            <field name="series_name"><![CDATA[{series.get("series_name", "")}]]></field>')
                lines.append("            <field name=\"purchase_ok\">False</field>")
                lines.append("            <field name=\"sale_ok\">False</field>")
                lines.append("            <field name=\"type\">consu</field>")
                lines.append("        </record>")
            lines.append("    </data>")
            lines.append("</odoo>")
            if not self.dry_run:
                with open(xml_path, "w", encoding="utf-8") as fp:
                    fp.write("\n".join(lines))

        load_json_xml = os.path.join(data_dir, "load_json_data.xml")
        load_xml_content = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<odoo>\n"
            "    <data noupdate=\"0\">\n"
            "        <function model=\"product.template\" name=\"_load_catalog_base_data_from_json\" />\n"
            "    </data>\n"
            "</odoo>\n"
        )
        if not self.dry_run:
            with open(load_json_xml, "w", encoding="utf-8") as fp:
                fp.write(load_xml_content)

        return generated, deleted, json_path

    def _target_xml_filenames_from_series(self):
        scripts_dir = self._scripts_dir()
        series_csv = os.path.join(scripts_dir, "series.csv")
        if not os.path.exists(series_csv):
            raise UserError(f"未找到文件: {series_csv}")
        series_data = self._read_csv_safe(series_csv)
        series_by_brand = {}
        if series_data:
            headers = series_data[0]
            for row in series_data[1:]:
                if not row:
                    continue
                row_dict = dict(zip(headers, row))
                if not row_dict.get("series_xml_id", "").strip():
                    continue
                brand_xml_id = row_dict.get("brand_id_xml", "").strip()
                series_by_brand.setdefault(brand_xml_id, []).append(row_dict)
        return {self._brand_to_xml_filename(k) for k in series_by_brand.keys()}

    def _list_unmatched_brand_xml(self, target_files=None):
        data_dir = self._data_dir()
        if target_files is None:
            target_files = self._target_xml_filenames_from_series()
        candidates = []
        for existing in os.listdir(data_dir):
            if not (existing.startswith("catalog_") and existing.endswith("_data.xml")):
                continue
            if existing not in target_files:
                candidates.append(existing)
        return sorted(candidates)

    def action_preview_delete_list(self):
        self.ensure_one()
        files = self._list_unmatched_brand_xml()
        msg = "将删除以下XML文件（CSV未匹配）:\n" + ("\n".join(files) if files else "(无)")
        self.delete_preview = msg
        self.result_message = f"待删除数量: {len(files)}"
        return {
            "type": "ir.actions.act_window",
            "name": "数据运维",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_show_guide(self):
        self.ensure_one()
        self.guide_message = (
            "【数据运维操作指南】\n"
            "1) 导出CSV（DB -> scripts）\n"
            "   - 用途：把当前系统中的选型数据导出到 scripts/series.csv 与 scripts/variants.csv。\n"
            "   - 建议：先勾选“预演”，确认数量无误后再取消预演落盘。\n\n"
            "2) 从CSV生成JSON/XML\n"
            "   - 用途：根据 CSV 生成 data/catalog_materials.json 与 catalog_*_data.xml。\n"
            "   - 不会写数据库，仅生成文件。\n"
            "   - 勾选“删除未匹配品牌XML”时，可先点“预览删除项目”。\n\n"
            "3) CSV同步入库\n"
            "   - 用途：先生成文件，再自动导入 XML 并触发 JSON 同步到数据库。\n"
            "   - 这是会写数据库的操作。\n\n"
            "4) 导入指定XML\n"
            "   - 用途：导入 data 目录下选定的单个 XML 文件。\n"
            "   - 预演模式下仅提示，不实际导入。\n\n"
            "5) 清理未匹配品牌XML\n"
            "   - 用途：删除 data 目录中不在当前 CSV 品牌集合内的 catalog_*_data.xml。\n"
            "   - 真删前请先“预览删除项目”，并在非预演模式输入确认词 DELETE。\n\n"
            "6) CSV轻量编辑\n"
            "   - 用途：在界面直接编辑 scripts 下 CSV（series/variants）。\n"
            "   - 先点“加载CSV”，编辑后点“保存CSV”。\n"
            "   - 建议保存后先执行“从CSV生成JSON/XML（预演）”检查结果。\n\n"
            "7) 新架构影子回填（旧模型 -> catalog.item）\n"
            "   - 用途：把旧选型型号按品牌/系列规则回填到 diecut.catalog.item。\n"
            "   - 可设置“回填上限”做小批量灰度验证。\n"
            "   - 建议先预演，确认跳过与错误数量后再执行。\n\n"
            "8) 新架构影子对账报告\n"
            "   - 用途：检查旧型号总量与新影子模型一致性（缺失、重复、孤儿）。\n"
            "   - 建议在影子回填后立即执行。\n\n"
            "9) 新旧字段一致性检查\n"
            "   - 用途：对比新模型与旧型号关键字段是否一致（技术参数/状态/映射等）。\n"
            "   - 建议在影子回填后和每次部署后执行。\n\n"
            "10) 新架构字段刷新（旧模型 -> 新模型）\n"
            "   - 用途：按 legacy_variant_id 将旧型号关键字段批量刷新到新模型。\n"
            "   - 适用于模型字段新增后的历史数据补齐。\n\n"
            "11) 新旧附件一致性检查\n"
            "   - 用途：对比新旧模型附件字段（文件名/是否有附件）的一致性。\n"
            "   - 建议在字段刷新后执行。\n\n"
            "12) 生成切换基线记录\n"
            "   - 用途：将入口模式、影子对账、字段一致性、附件一致性打包记录到运维日志。\n"
            "   - 建议每次部署后执行一次，用于审计与回归对比。\n\n"
            "【推荐流程】\n"
            "导出CSV -> 编辑CSV -> 从CSV生成JSON/XML（预演） -> CSV同步入库（先预演，再执行）\n"
            "新架构迁移：影子回填（先预演） -> 影子回填（执行） -> 影子对账报告 -> 字段刷新 -> 字段一致性检查 -> 附件一致性检查 -> 生成切换基线记录"
        )
        return {
            "type": "ir.actions.act_window",
            "name": "数据运维",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _ensure_delete_confirmation(self, files):
        if self.dry_run or not files:
            return
        if (self.confirm_delete_token or "").strip().upper() != "DELETE":
            raise UserError(
                "检测到将执行真实删除，请先输入删除确认词 DELETE。\n"
                f"待删除数量: {len(files)}\n"
                + "\n".join(files[:50])
            )

    def action_load_csv_editor(self):
        self.ensure_one()
        path, filename = self._csv_file_path()
        if not os.path.exists(path):
            raise UserError(f"未找到文件: {path}")
        try:
            with open(path, "r", encoding="utf-8-sig") as fp:
                content = fp.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="gbk") as fp:
                content = fp.read()
        self.csv_content = content
        self.result_message = f"已加载 {filename}，共 {len(content.splitlines())} 行。"
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
        path, filename = self._csv_file_path()
        if self.csv_content is None:
            raise UserError("没有可保存内容，请先加载CSV。")
        os.makedirs(self._scripts_dir(), exist_ok=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as fp:
            fp.write(self.csv_content.replace("\r\n", "\n"))
        self.result_message = f"已保存 {filename}，共 {len(self.csv_content.splitlines())} 行。"
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
        _path, filename = self._csv_file_path()
        return {
            "type": "ir.actions.act_url",
            "url": f"/diecut/catalog/csv-grid?file={quote(filename)}",
            "target": "new",
        }

    def _import_xml(self, xml_file):
        if not xml_file:
            raise UserError("请先选择 XML 文件。")
        module_dir = self._module_dir()
        full_path = os.path.join(self._data_dir(), os.path.basename(xml_file))
        if not os.path.isfile(full_path):
            raise UserError(f"文件不存在: {full_path}")
        relative = os.path.relpath(full_path, module_dir).replace("\\", "/")
        convert_file(self.env, "diecut", relative, {}, mode="init", noupdate=False, kind="data")
        return relative

    def _cleanup_unmatched_xml(self):
        _generated, deleted, _json_path = self._generate_assets(prune_xml=True)
        return deleted

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
        runtime = self.env["diecut.catalog.runtime.service"]
        shadow = self.env["diecut.catalog.shadow.service"]
        reconcile = shadow.shadow_reconcile_report()
        mapped = shadow.compare_mapped_fields(limit=limit, sample_size=20)
        attachments = shadow.compare_attachment_fields(limit=limit, sample_size=20)
        payload = {
            "read_mode": runtime.get_read_mode(),
            "reconcile": reconcile,
            "mapped_fields": {
                "all_match": mapped["all_match"],
                "mismatch_field_count": mapped["mismatch_field_count"],
                "sample_rows": mapped["sample_rows"],
                "top_mismatch": mapped["mismatch_counts"],
            },
            "attachments": {
                "all_match": attachments["all_match"],
                "mismatch_field_count": attachments["mismatch_field_count"],
                "sample_rows": attachments["sample_rows"],
                "top_mismatch": attachments["mismatch_counts"],
            },
        }
        return payload

    def action_execute(self):
        self.ensure_one()
        log_extra = {}
        try:
            if self.operation == "export_csv":
                msg = self._export_csv()
            elif self.operation == "generate_assets":
                if self.prune_unmatched_xml:
                    planned = self._list_unmatched_brand_xml()
                    self._ensure_delete_confirmation(planned)
                generated, deleted, json_path = self._generate_assets(prune_xml=self.prune_unmatched_xml)
                msg = (
                    f"生成完成（{'预演' if self.dry_run else '已落盘'}）\n"
                    f"JSON: {json_path}\n生成XML: {len(generated)}\n删除XML: {len(deleted)}\n"
                    + ("\n".join(deleted[:200]) if deleted else "(无删除项)")
                )
            elif self.operation == "sync_csv_to_db":
                if self.prune_unmatched_xml:
                    planned = self._list_unmatched_brand_xml()
                    self._ensure_delete_confirmation(planned)
                generated, deleted, _json_path = self._generate_assets(prune_xml=self.prune_unmatched_xml)
                if not self.dry_run:
                    module_dir = self._module_dir()
                    for filename in generated:
                        rel = os.path.relpath(os.path.join(self._data_dir(), filename), module_dir).replace("\\", "/")
                        convert_file(self.env, "diecut", rel, {}, mode="init", noupdate=False, kind="data")
                    convert_file(self.env, "diecut", "data/load_json_data.xml", {}, mode="init", noupdate=False, kind="data")
                msg = (
                    f"CSV同步入库完成（{'预演' if self.dry_run else '已执行'}）\n"
                    f"生成XML: {len(generated)}\n删除XML: {len(deleted)}\n"
                    + ("\n".join(deleted[:200]) if deleted else "(无删除项)")
                )
            elif self.operation == "import_xml":
                if self.dry_run:
                    msg = f"预演：将导入文件 {self.xml_file or '(未选择)'}"
                else:
                    rel = self._import_xml(self.xml_file)
                    msg = f"导入成功: {rel}"
            elif self.operation == "shadow_backfill":
                limit = self.backfill_limit if (self.backfill_limit or 0) > 0 else None
                stats = self.env["diecut.catalog.shadow.service"].shadow_backfill_from_legacy(
                    dry_run=self.dry_run,
                    limit=limit,
                )
                msg = (
                    f"影子回填完成（{'预演' if self.dry_run else '已执行'}）\n"
                    f"回填上限: {limit or '不限'}\n"
                    f"旧型号总数: {stats['total_variants']}\n"
                    f"系列写入: {stats['series_upserted']}\n"
                    f"型号写入: {stats['models_upserted']}\n"
                    f"跳过(无编码): {stats['models_skipped_no_code']}\n"
                    f"跳过(无品牌): {stats['models_skipped_no_brand']}\n"
                    f"错误数: {stats['errors']}"
                )
            elif self.operation == "shadow_reconcile":
                report = self.env["diecut.catalog.shadow.service"].shadow_reconcile_report()
                msg = (
                    "影子对账报告\n"
                    f"旧模型型号数: {report['legacy_model_count']}\n"
                    f"新模型型号数: {report['shadow_model_count']}\n"
                    f"缺失影子记录: {report['missing_shadow_count']}\n"
                    f"品牌+编码重复组: {report['duplicate_brand_code_count']}\n"
                    f"孤儿型号(无父系列): {report['orphan_model_count']}"
                )
            elif self.operation == "shadow_compare_fields":
                limit = self.backfill_limit if (self.backfill_limit or 0) > 0 else None
                report = self.env["diecut.catalog.shadow.service"].compare_mapped_fields(limit=limit, sample_size=20)
                mismatch_lines = []
                for field_name, count in sorted(report["mismatch_counts"].items(), key=lambda x: (-x[1], x[0]))[:10]:
                    mismatch_lines.append(f"- {field_name}: {count}")
                msg = (
                    "新旧字段一致性检查\n"
                    f"检查条数: {report['total_checked']}\n"
                    f"异常记录数: {report['mismatch_rows']}\n"
                    f"异常字段数: {report['mismatch_field_count']}\n"
                    f"结论: {'全部一致' if report['all_match'] else '存在不一致'}\n"
                    + ("字段异常TOP:\n" + "\n".join(mismatch_lines) if mismatch_lines else "字段异常TOP:\n(无)")
                )
            elif self.operation == "shadow_refresh_fields":
                limit = self.backfill_limit if (self.backfill_limit or 0) > 0 else None
                stats = self.env["diecut.catalog.shadow.service"].refresh_model_fields_from_legacy(limit=limit)
                msg = (
                    "新架构字段刷新完成\n"
                    f"处理条数: {stats['total']}\n"
                    f"刷新条数: {stats['updated']}"
                )
            elif self.operation == "shadow_compare_attachments":
                limit = self.backfill_limit if (self.backfill_limit or 0) > 0 else None
                report = self.env["diecut.catalog.shadow.service"].compare_attachment_fields(limit=limit, sample_size=20)
                mismatch_lines = []
                for field_name, count in sorted(report["mismatch_counts"].items(), key=lambda x: (-x[1], x[0]))[:10]:
                    mismatch_lines.append(f"- {field_name}: {count}")
                msg = (
                    "新旧附件一致性检查\n"
                    f"检查条数: {report['total_checked']}\n"
                    f"异常记录数: {report['sample_rows']}\n"
                    f"异常字段数: {report['mismatch_field_count']}\n"
                    f"结论: {'全部一致' if report['all_match'] else '存在不一致'}\n"
                    + ("附件异常TOP:\n" + "\n".join(mismatch_lines) if mismatch_lines else "附件异常TOP:\n(无)")
                )
            elif self.operation == "cutover_baseline_snapshot":
                limit = self.backfill_limit if (self.backfill_limit or 0) > 0 else None
                payload = self._build_cutover_baseline(limit=limit)
                reconcile = payload["reconcile"]
                mapped = payload["mapped_fields"]
                attachments = payload["attachments"]
                msg = (
                    "切换基线记录已生成\n"
                    f"入口模式: {payload['read_mode']}\n"
                    f"对账(旧/新/缺失/重复/孤儿): "
                    f"{reconcile['legacy_model_count']}/{reconcile['shadow_model_count']}/"
                    f"{reconcile['missing_shadow_count']}/{reconcile['duplicate_brand_code_count']}/"
                    f"{reconcile['orphan_model_count']}\n"
                    f"字段一致: {'是' if mapped['all_match'] else '否'}，异常字段: {mapped['mismatch_field_count']}，异常记录: {mapped['sample_rows']}\n"
                    f"附件一致: {'是' if attachments['all_match'] else '否'}，异常字段: {attachments['mismatch_field_count']}，异常记录: {attachments['sample_rows']}"
                )
                log_extra = {
                    "read_mode": payload["read_mode"],
                    "legacy_model_count": reconcile["legacy_model_count"],
                    "shadow_model_count": reconcile["shadow_model_count"],
                    "missing_shadow_count": reconcile["missing_shadow_count"],
                    "duplicate_brand_code_count": reconcile["duplicate_brand_code_count"],
                    "orphan_model_count": reconcile["orphan_model_count"],
                    "mapped_all_match": mapped["all_match"],
                    "mapped_mismatch_field_count": mapped["mismatch_field_count"],
                    "mapped_sample_rows": mapped["sample_rows"],
                    "attachment_all_match": attachments["all_match"],
                    "attachment_mismatch_field_count": attachments["mismatch_field_count"],
                    "attachment_sample_rows": attachments["sample_rows"],
                    "baseline_payload": json.dumps(payload, ensure_ascii=False, indent=2),
                }
            elif self.operation == "cleanup_xml":
                planned = self._list_unmatched_brand_xml()
                self._ensure_delete_confirmation(planned)
                deleted = self._cleanup_unmatched_xml()
                msg = (
                    f"清理完成（{'预演' if self.dry_run else '已删除'}），数量: {len(deleted)}\n"
                    + ("\n".join(deleted[:200]) if deleted else "(无删除项)")
                )
            elif self.operation == "view_fields_manual":
                self.action_load_fields_manual()
                msg = "字段清单已刷新。"
            elif self.operation == "edit_csv":
                # 轻量编辑模式下，执行按钮默认做保存动作
                self.action_save_csv_editor()
                msg = self.result_message or "已保存CSV。"
            else:
                raise UserError("不支持的操作。")
            self.result_message = msg
            self._write_log(True, msg, log_extra)
        except Exception as exc:
            err = f"执行失败: {exc}"
            self.result_message = err
            self._write_log(False, err, log_extra)
            raise
        return {
            "type": "ir.actions.act_window",
            "name": "数据运维",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _collect_field_entries(self):
        field_entries = []

        tmpl_core_fnames = {'brand_id', 'series_name', 'manufacturer_id', 'is_catalog', 'categ_id', 'color_id', 'variant_color_std_index'}
        tmpl_model = self.env['product.template']
        for fname, field in tmpl_model._fields.items():
            if fname.startswith('catalog_') or fname in tmpl_core_fnames:
                field_entries.append({
                    'model_name': 'product.template',
                    'field_name': fname,
                    'field_string': field.string or fname,
                    'field_type': field.type,
                    'field_help': field.help or ''
                })

        prod_core_fnames = {'default_code', 'active', 'barcode'}
        prod_model = self.env['product.product']
        for fname, field in prod_model._fields.items():
            if fname.startswith('variant_') or fname in prod_core_fnames:
                if fname.endswith('_std_index') and not field.string:
                    continue
                field_entries.append({
                    'model_name': 'product.product',
                    'field_name': fname,
                    'field_string': field.string or fname,
                    'field_type': field.type,
                    'field_help': field.help or ''
                })

        field_entries.sort(key=lambda x: (x['model_name'], x['field_name']))
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
            "name": "????",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
