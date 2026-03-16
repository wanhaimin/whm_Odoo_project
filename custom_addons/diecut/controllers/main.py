# -*- coding: utf-8 -*-

import csv
import io
import json
import os

from odoo import http
from odoo.http import request
from odoo.modules.module import get_module_path


class CatalogCsvGridController(http.Controller):
    _ALLOWED = {
        "catalog_items.csv",
        "catalog_item_specs.csv",
        "catalog_params.csv",
        "catalog_category_params.csv",
        "catalog_series.csv",
    }
    _READ_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")

    def _scripts_dir(self):
        module_dir = get_module_path("diecut")
        if not module_dir:
            return None
        return os.path.join(module_dir, "scripts")

    def _resolve_csv(self, filename):
        name = (filename or "").strip()
        if name not in self._ALLOWED:
            return None, None
        scripts_dir = self._scripts_dir()
        if not scripts_dir:
            return None, None
        return os.path.join(scripts_dir, name), name

    def _read_csv_text(self, full_path):
        raw = open(full_path, "rb").read()
        last_error = None
        for encoding in self._READ_ENCODINGS:
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError as exc:
                last_error = exc
        raise UnicodeDecodeError(
            last_error.encoding if last_error else "utf-8",
            last_error.object if last_error else b"",
            last_error.start if last_error else 0,
            last_error.end if last_error else 1,
            last_error.reason if last_error else "无法识别 CSV 编码",
        )

    @http.route("/diecut/catalog/csv-grid", type="http", auth="user")
    def csv_grid_page(self, file="catalog_items.csv", **kwargs):
        _full_path, safe_name = self._resolve_csv(file)
        if not safe_name:
            return request.not_found()
        html = f"""<!doctype html>
<html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>AG Grid CSV 编辑器 - {safe_name}</title>
<link rel="stylesheet" href="https://unpkg.com/ag-grid-community/styles/ag-grid.css">
<link rel="stylesheet" href="https://unpkg.com/ag-grid-community/styles/ag-theme-alpine.css">
<style>body{{margin:0;font-family:Arial,sans-serif}}.toolbar{{padding:10px;display:flex;gap:8px;align-items:center;border-bottom:1px solid #ddd}}.toolbar .status{{margin-left:auto;color:#444}}#grid{{height:calc(100vh - 54px);width:100%}}button{{padding:6px 12px;border:1px solid #999;background:#f7f7f7;cursor:pointer}}button.primary{{background:#6f42c1;color:#fff;border-color:#6f42c1}}.ag-cell-error{{background-color:#f8d7da!important}}#errorList{{max-height:120px;overflow:auto;font-size:12px;color:#721c24;margin-top:4px}}</style>
</head><body>
<div class="toolbar"><strong>AG Grid CSV 编辑器</strong><span>文件: {safe_name}</span><button id="reloadBtn">刷新</button><button id="addRowBtn">新增行</button><button id="saveBtn" class="primary">保存</button><span id="status" class="status">加载中...</span></div>
<div id="errorList" style="display:none;"></div><div id="grid" class="ag-theme-alpine"></div>
<script src="https://unpkg.com/ag-grid-community/dist/ag-grid-community.min.js"></script>
<script>
const fileName={json.dumps(safe_name)};const statusEl=document.getElementById('status');const gridDiv=document.getElementById('grid');const errorListEl=document.getElementById('errorList');let gridApi=null,headers=[],validationErrors=new Set();
async function loadData(){{validationErrors=new Set();errorListEl.style.display='none';statusEl.textContent='加载中...';const resp=await fetch(`/diecut/catalog/csv-grid/data?file=${{encodeURIComponent(fileName)}}`);const payload=await resp.json();if(!payload.ok){{statusEl.textContent='加载失败: '+(payload.error||'未知错误');return;}}headers=payload.headers||[];const columnDefs=headers.map(h=>({{field:h,editable:true,resizable:true,sortable:true,filter:true,getCellClass:(p)=>validationErrors.has(p.rowIndex+':'+p.colDef.field)?'ag-cell-error':''}}));const rowData=payload.rows||[];gridDiv.innerHTML='';gridApi=agGrid.createGrid(gridDiv,{{columnDefs,rowData,defaultColDef:{{flex:1,minWidth:140}},enableCellTextSelection:true,suppressRowClickSelection:true,rowSelection:'multiple'}});statusEl.textContent=`已加载 ${{rowData.length}} 行`;}}
function collectRows(){{const rows=[];if(!gridApi)return rows;gridApi.forEachNode(n=>rows.push(n.data||{{}}));return rows;}}
async function saveData(){{validationErrors=new Set();errorListEl.style.display='none';if(gridApi)gridApi.refreshCells({{force:true}});statusEl.textContent='保存中...';const rows=collectRows();const resp=await fetch('/diecut/catalog/csv-grid/save',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{file:fileName,headers,rows}})}});const payload=await resp.json();if(!payload.ok){{statusEl.textContent=(payload.error||'保存失败')+(payload.errors&&payload.errors.length?`（${{payload.errors.length}}处）`:'');if(payload.errors&&payload.errors.length){{payload.errors.forEach(e=>validationErrors.add(e.rowIndex+':'+e.field));errorListEl.innerHTML='<strong>校验错误：</strong><br>'+payload.errors.map(e=>'第'+(e.rowIndex+1)+'行 · '+e.field+': '+e.message).join('<br>');errorListEl.style.display='block';if(gridApi)gridApi.refreshCells({{force:true}});}}return;}}statusEl.textContent=`已保存，${{payload.row_count}} 行`;}}
document.getElementById('reloadBtn').addEventListener('click',()=>window.location.reload());
document.getElementById('addRowBtn').addEventListener('click',()=>{{if(!gridApi)return;const obj=Object.fromEntries((headers||[]).map(h=>[h,'']));gridApi.applyTransaction({{add:[obj]}});}});
document.getElementById('saveBtn').addEventListener('click',saveData);loadData();
</script></body></html>"""
        return request.make_response(html, headers=[("Content-Type", "text/html; charset=utf-8")])

    @http.route("/diecut/catalog/csv-grid/data", type="http", auth="user")
    def csv_grid_data(self, file="catalog_items.csv", **kwargs):
        full_path, safe_name = self._resolve_csv(file)
        if not safe_name:
            return request.make_response(
                json.dumps({"ok": False, "error": "非法文件名"}),
                headers=[("Content-Type", "application/json")],
            )
        if not os.path.exists(full_path):
            return request.make_response(
                json.dumps({"ok": False, "error": f"文件不存在: {safe_name}"}),
                headers=[("Content-Type", "application/json")],
            )
        try:
            reader = list(csv.reader(io.StringIO(self._read_csv_text(full_path))))
        except UnicodeDecodeError:
            return request.make_response(
                json.dumps({"ok": False, "error": "CSV 编码无法识别，请保存为 UTF-8 或 GB18030"}),
                headers=[("Content-Type", "application/json; charset=utf-8")],
            )
        headers = reader[0] if reader else []
        rows = []
        for row in reader[1:]:
            values = list(row) + [""] * max(0, len(headers) - len(row))
            rows.append({headers[i]: values[i] for i in range(len(headers))})
        return request.make_response(
            json.dumps({"ok": True, "headers": headers, "rows": rows}, ensure_ascii=False),
            headers=[("Content-Type", "application/json; charset=utf-8")],
        )

    def _validate_csv_primary_keys(self, safe_name, headers, rows):
        errors = []
        if safe_name == "catalog_items.csv":
            key_fields = ("code",)
            needs_brand = True
        elif safe_name == "catalog_item_specs.csv":
            key_fields = ("item_code", "param_key")
            needs_brand = True
        elif safe_name == "catalog_params.csv":
            key_fields = ("param_key",)
            needs_brand = False
        elif safe_name == "catalog_category_params.csv":
            key_fields = ("categ_id_xml", "param_key")
            needs_brand = False
        elif safe_name == "catalog_series.csv":
            key_fields = ("series_name",)
            needs_brand = True
        else:
            return errors
        for field_name in key_fields:
            if field_name not in headers:
                errors.append({"rowIndex": -1, "field": field_name, "message": f"缺少列 {field_name}"})
        if needs_brand and "brand_id_xml" not in headers and "brand_name" not in headers:
            errors.append({"rowIndex": -1, "field": "brand_id_xml/brand_name", "message": "缺少列 brand_id_xml 或 brand_name"})
        if any(error["rowIndex"] == -1 for error in errors):
            return errors
        seen = {}
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            parts = []
            if needs_brand:
                bx = (row.get("brand_id_xml") or "").strip().lower()
                bn = (row.get("brand_name") or "").strip().lower()
                brand_key = bx or (f"name:{bn}" if bn else "")
                if not brand_key:
                    errors.append({"rowIndex": idx, "field": "brand_id_xml/brand_name", "message": "不能为空"})
                parts.append(brand_key)
            for field_name in key_fields:
                value = (row.get(field_name) or "").strip().lower()
                if not value:
                    errors.append({"rowIndex": idx, "field": field_name, "message": "不能为空"})
                parts.append(value)
            if all(parts):
                key = tuple(parts)
                if key in seen:
                    errors.append({"rowIndex": idx, "field": key_fields[-1], "message": f"与第 {seen[key] + 1} 行重复"})
                else:
                    seen[key] = idx
        return errors

    @http.route("/diecut/catalog/csv-grid/save", type="http", auth="user", methods=["POST"], csrf=False)
    def csv_grid_save(self, **kwargs):
        try:
            payload = json.loads(request.httprequest.get_data(as_text=True) or "{}")
        except Exception:
            payload = {}
        full_path, safe_name = self._resolve_csv(payload.get("file"))
        if not safe_name:
            return request.make_response(
                json.dumps({"ok": False, "error": "非法文件名"}),
                headers=[("Content-Type", "application/json")],
            )
        headers = payload.get("headers") or []
        rows = payload.get("rows") or []
        if not isinstance(headers, list) or not all(isinstance(header, str) and header for header in headers):
            return request.make_response(
                json.dumps({"ok": False, "error": "表头不合法"}),
                headers=[("Content-Type", "application/json")],
            )
        validation_errors = self._validate_csv_primary_keys(safe_name, headers, rows)
        if validation_errors:
            return request.make_response(
                json.dumps({"ok": False, "error": "主键校验未通过", "errors": validation_errors}, ensure_ascii=False),
                headers=[("Content-Type", "application/json; charset=utf-8")],
            )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        for row in rows:
            if isinstance(row, dict):
                writer.writerow([row.get(header, "") for header in headers])
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8-sig", newline="") as fp:
            fp.write(output.getvalue())
        return request.make_response(
            json.dumps({"ok": True, "row_count": len(rows)}, ensure_ascii=False),
            headers=[("Content-Type", "application/json; charset=utf-8")],
        )
