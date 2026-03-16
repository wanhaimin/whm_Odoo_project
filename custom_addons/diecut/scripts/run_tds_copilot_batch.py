# -*- coding: utf-8 -*-
import base64
import json
import mimetypes
import os
import re
import traceback
from datetime import datetime
from pathlib import Path


PDF_DIR = Path("/mnt/extra-addons/diecut/scripts/tesa_tds_pdfs")
REPORT_DIR = Path("/mnt/extra-addons/diecut/scripts/tds_batch_reports")
NAME_PREFIX = "Batch TDS :: "


def _slug_to_title(stem):
    stem = stem.replace("_tds", "").replace("_technical_data_sheet", "")
    stem = stem.replace("-", " ").replace("_", " ")
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem or "TDS"


def _guess_brand_id(stem):
    low = stem.lower()
    if low.startswith("3m"):
        return env["diecut.brand"].sudo().search([("name", "ilike", "3M")], limit=1).id or False
    if low.startswith("tesa") or "德莎" in stem:
        return env["diecut.brand"].sudo().search([("name", "ilike", "tesa")], limit=1).id or False
    return False


def _upsert_source_doc(pdf_path):
    title = _slug_to_title(pdf_path.stem)
    name = f"{NAME_PREFIX}{title}"
    source = env["diecut.catalog.source.document"].sudo().search([("name", "=", name)], limit=1)
    vals = {
        "name": name,
        "source_type": "pdf",
        "source_filename": pdf_path.name,
    }
    brand_id = _guess_brand_id(pdf_path.stem)
    if brand_id:
        vals["brand_id"] = brand_id
    if source:
        source.write(vals)
    else:
        source = env["diecut.catalog.source.document"].sudo().create(vals)

    attachment_model = env["ir.attachment"].sudo()
    existing = attachment_model.search(
        [
            ("res_model", "=", "diecut.catalog.source.document"),
            ("res_id", "=", source.id),
            ("res_field", "=", False),
            ("name", "=", pdf_path.name),
        ],
        limit=1,
    )
    datas = base64.b64encode(pdf_path.read_bytes()).decode()
    mimetype = mimetypes.guess_type(str(pdf_path))[0] or "application/pdf"
    if existing:
        existing.write({"datas": datas, "mimetype": mimetype, "type": "binary"})
        attachment = existing
    else:
        attachment = attachment_model.create(
            {
                "name": pdf_path.name,
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
            "source_filename": pdf_path.name,
            "result_message": False,
            "unmatched_payload": False,
        }
    )
    return source


def _payload_counts(source):
    try:
        payload = json.loads(source.draft_payload or "{}")
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return {bucket: len(payload.get(bucket) or []) for bucket in ("series", "items", "params", "category_params", "spec_values", "unmatched")}


def _run_one(pdf_path):
    source = _upsert_source_doc(pdf_path)
    source.action_extract_source()
    source.action_generate_draft()
    source.action_validate_draft()
    env.cr.commit()
    source.invalidate_recordset()
    counts = _payload_counts(source)
    return {
        "file": pdf_path.name,
        "source_id": source.id,
        "status": source.import_status,
        "parse_version": source.parse_version,
        "counts": counts,
        "message": source.result_message or "",
    }


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(
        [
            path
            for path in PDF_DIR.glob("*.pdf")
            if path.is_file()
        ]
    )
    results = {
        "ran_at": datetime.utcnow().isoformat() + "Z",
        "total": len(files),
        "success": [],
        "failed": [],
    }
    for pdf_path in files:
        try:
            result = _run_one(pdf_path)
            results["success"].append(result)
            print(f"OK | {pdf_path.name} | {result['status']} | {result['parse_version']} | {result['counts']}")
        except Exception as exc:
            env.cr.rollback()
            failure = {
                "file": pdf_path.name,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
            results["failed"].append(failure)
            print(f"FAIL | {pdf_path.name} | {exc}")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"tds_batch_report_{stamp}.json"
    report_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"REPORT | {report_path}")


main()
