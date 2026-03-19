# -*- coding: utf-8 -*-
import base64
import json
import mimetypes
from pathlib import Path

SOURCE_NAME = "tesa 6928 TDS"
PDF_PATH = Path("/mnt/extra-addons/diecut/scripts/tesa_tds_pdfs/tesa_6928_tds.pdf")
DRAFT_PATH = Path("/mnt/extra-addons/diecut/scripts/tds_import_drafts/tesa_6928_tds_draft.json")
BRAND_NAME = "Tesa"
CATEGORY_NAME = "PET双面胶带"
ITEM_CODE = "6928"
SERIES_NAME = "tesa 6928"


def _get_or_create(model_name, name):
    if not name:
        return False
    record = env[model_name].sudo().search([("name", "=", name)], limit=1)
    if record:
        return record
    return env[model_name].sudo().create({"name": name})


def load_payload():
    return json.loads(DRAFT_PATH.read_text(encoding="utf-8"))


def upsert_source_document(payload):
    brand = env["diecut.brand"].sudo().search([("name", "=", BRAND_NAME)], limit=1)
    source = env["diecut.catalog.source.document"].sudo().search([("name", "=", SOURCE_NAME)], limit=1)
    vals = {
        "name": SOURCE_NAME,
        "source_type": "pdf",
        "source_filename": PDF_PATH.name,
        "brand_id": brand.id or False,
        "import_status": "generated",
        "parse_version": "manual-tds-v1",
        "draft_payload": json.dumps(payload, ensure_ascii=False, indent=2),
        "unmatched_payload": "[]",
        "result_message": "基于 tesa 6928 标准 TDS 人工校核生成的五表导入草稿。",
    }
    if source:
        source.write(vals)
    else:
        source = env["diecut.catalog.source.document"].sudo().create(vals)

    if PDF_PATH.exists():
        attachment_model = env["ir.attachment"].sudo()
        datas = base64.b64encode(PDF_PATH.read_bytes()).decode()
        mimetype = mimetypes.guess_type(str(PDF_PATH))[0] or "application/pdf"
        attachment = attachment_model.search(
            [
                ("res_model", "=", "diecut.catalog.source.document"),
                ("res_id", "=", source.id),
                ("res_field", "=", False),
                ("name", "=", PDF_PATH.name),
            ],
            limit=1,
        )
        if attachment:
            attachment.write({"datas": datas, "mimetype": mimetype, "type": "binary"})
        else:
            attachment = attachment_model.create(
                {
                    "name": PDF_PATH.name,
                    "type": "binary",
                    "datas": datas,
                    "mimetype": mimetype,
                    "res_model": "diecut.catalog.source.document",
                    "res_id": source.id,
                }
            )
        source.write(
            {
                "primary_attachment_id": attachment.id,
                "source_file": datas,
                "source_filename": PDF_PATH.name,
            }
        )
    return source


def sync_main_fields():
    item = env["diecut.catalog.item"].sudo().search([("brand_id.name", "=", BRAND_NAME), ("code", "=", ITEM_CODE)], limit=1)
    if not item:
        return False
    color = _get_or_create("diecut.color", "透明")
    adhesive = _get_or_create("diecut.catalog.adhesive.type", "改性丙烯酸")
    base_material = _get_or_create("diecut.catalog.base.material", "PET（聚酯）薄膜")
    vals = {
        "thickness": 125.0,
        "product_features": "优异的静态剪切力和剥离力性能平衡\n轻型包装的安全封闭性能\n高温下对不同泡棉及橡胶等严苛表面具有强大粘接性能\n高初粘力，立即固定于被粘表面",
        "product_description": "tesa® 6928 是透明的双面自粘胶带，由 PET 基材和改性丙烯酸胶粘剂组成，采用便于移除的助剥设计离型纸。",
        "main_applications": "轻型信封和纸箱的封闭\n汽车行业中 ABS 塑料部件的固定\n家具行业中装饰型材和装饰线条的固定",
        "special_applications": "纸离型纸；离型纸厚度 69 µm；离型纸重量 80 g/m²；离型纸颜色 棕色。",
    }
    if color:
        vals["color_id"] = color.id
    if adhesive:
        vals["adhesive_type_id"] = adhesive.id
    if base_material:
        vals["base_material_id"] = base_material.id
    item.write(vals)
    return item


def main():
    if not DRAFT_PATH.exists():
        raise FileNotFoundError("draft not found: %s" % DRAFT_PATH)
    payload = load_payload()
    source = upsert_source_document(payload)
    source._run_encoding_precheck(payload)
    source.action_validate_draft()
    source.action_apply_draft()
    item = sync_main_fields()
    env.cr.commit()
    print("source_id=%s" % source.id)
    print("item=%s" % (item.display_name if item else "NOT_FOUND"))
    print("draft_path=%s" % DRAFT_PATH)
    print("series_count=%s" % len(payload.get("series") or []))
    print("item_count=%s" % len(payload.get("items") or []))
    print("param_count=%s" % len(payload.get("params") or []))
    print("spec_count=%s" % len(payload.get("spec_values") or []))


main()
