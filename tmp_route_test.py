import base64
import json
from pathlib import Path
import requests
pdf = Path(r"E:\workspace\my_odoo_project\custom_addons\diecut\scripts\tesa_tds_pdfs\tesa_4963_tds.pdf")
payload = {
    "token": "chatter-ai-local-dev",
    "brand": "Tesa",
    "material_code": "4963",
    "document_type": "tds",
    "source_platform": "odoo",
    "source_filename": pdf.name,
    "source_file_base64": base64.b64encode(pdf.read_bytes()).decode("ascii"),
    "raw_text": "External route pilot raw text for tesa 4963.",
    "content_html": "<div><h1>Tesa 4963 External Route Pilot</h1><p>Marker: 2026-03-26 17:08 CST</p></div>",
    "draft_payload": {"items": [{"code": "4963", "name": "tesa 4963"}], "series": [], "params": [], "category_params": [], "spec_values": [], "unmatched": []},
    "unmatched_payload": [],
    "trace_id": "pilot-4963-route-20260326-1708"
}
r = requests.post("http://localhost:8070/chatter_ai_assistant/worker/material_update", json=payload, timeout=120)
print(r.status_code)
print(r.text)
