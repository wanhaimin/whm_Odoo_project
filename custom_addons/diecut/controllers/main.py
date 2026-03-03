# -*- coding: utf-8 -*-
import csv
import io
import json
import os

from odoo import http
from odoo.http import request
from odoo.modules.module import get_module_path


class MaterialWebsite(http.Controller):
    
    @http.route(['/materials', '/materials/page/<int:page>'], type='http', auth='public', website=True)
    def materials_list(self, page=1, category=None, search=None, **kwargs):
        """材料列表页面"""
        # 使用 Odoo 原生的 website_published 机制
        # 对于 Product, 可以在 is_published 上过滤，且只看 raw material
        domain = [('is_published', '=', True), ('is_raw_material', '=', True)]
        
        # 分类筛选
        if category:
            category_obj = request.env['product.category'].sudo().browse(int(category or 0))
            domain.append(('categ_id', '=', category_obj.id))
        
        # 搜索
        if search:
            domain += ['|', ('name', 'ilike', search), ('default_code', 'ilike', search)]
        
        # 分页
        materials_per_page = 12
        total_materials = request.env['product.template'].sudo().search_count(domain)
        pager = request.website.pager(
            url='/materials',
            total=total_materials,
            page=page,
            step=materials_per_page,
            url_args={'category': category, 'search': search}
        )
        
        materials = request.env['product.template'].sudo().search(
            domain,
            limit=materials_per_page,
            offset=pager['offset'],
            order='create_date desc'
        )
        
        # 获取所有分类 (只获取原材料分类)
        # 假设原材料分类是 'category_type'='raw' 或者您有特定的根分类
        categories = request.env['product.category'].sudo().search([('category_type', '=', 'raw')]) 
        if not categories:
             categories = request.env['product.category'].sudo().search([])

        return request.render('diecut.materials_list', {
            'materials': materials,
            'categories': categories,
            'pager': pager,
            'search': search,
            'current_category': int(category or 0) if category else None,
            'total_count': total_materials,
        })
    
    @http.route(['/material/<int:material_id>'], type='http', auth='public', website=True)
    def material_detail(self, material_id, **kwargs):
        """材料详情页面"""
        # Browse product.template
        material = request.env['product.template'].sudo().browse(material_id)
        
        if not material.exists() or not material.is_published: # or not material.is_raw_material:
            return request.redirect('/materials')
        
        # 增加浏览次数
        # 注意：product.template 原生没有 view_count, 使用我们自定义加的
        if hasattr(material, 'view_count'):
             material.sudo().write({'view_count': material.view_count + 1})

        # 推荐材料(同分类)
        recommended_materials = request.env['product.template'].sudo().search([
            ('categ_id', '=', material.categ_id.id),
            ('id', '!=', material.id),
            ('is_published', '=', True),
            ('is_raw_material', '=', True)
        ], limit=4)
        
        return request.render('diecut.material_detail', {
            'material': material,
            'recommended_materials': recommended_materials,
        })
    
    @http.route(['/sample/order'], type='http', auth='user', website=True)
    def sample_order_form(self, **kwargs):
        """打样订单表单"""
        materials = request.env['product.template'].sudo().search([
            ('is_published', '=', True),
            ('is_raw_material', '=', True)
        ])
        
        return request.render('diecut.sample_order_form', {
            'materials': materials,
        })
    
    @http.route(['/sample/order/submit'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def sample_order_submit(self, **post):
        """提交打样订单"""
        # 创建打样订单
        order_vals = {
            'partner_id': request.env.user.partner_id.id,
            'product_name': post.get('product_name'),
            'product_model': post.get('product_model'),
            'application': post.get('application'),
            'quantity': int(post.get('quantity') or 10),
            'urgency': post.get('urgency', 'normal'),
            'note': post.get('note'),
        }
        
        order = request.env['sample.order'].sudo().create(order_vals)
        
        # 创建订单明细
        # material_id 此处来自前端选择，实际上是 product.template ID
        # 如果 sample.order.line 需要 product.product, 我们需要转换
        template_id = int(post.get('material_id') or 0)
        product_id = False
        if template_id:
             tmpl = request.env['product.template'].sudo().browse(template_id)
             # 获取第一个变体
             if tmpl.product_variant_ids:
                 product_id = tmpl.product_variant_ids[0].id
        
        line_vals = {
            'order_id': order.id,
            'material_id': product_id, # 注意 sample.order.line 现在应该链接 product.product
            'length': float(post.get('length') or 0.0),
            'width': float(post.get('width') or 0.0),
            'thickness': float(post.get('thickness') or 0.0),
            'quantity': int(post.get('quantity') or 10),
            'process_type': post.get('process_type', 'die_cut'),
            'special_requirements': post.get('special_requirements'),
        }
        # 如果没选材料（product_id is False），可能要在 sample.order.line 允许为空或者抛错
        # 假设允许为空
        
        request.env['sample.order.line'].sudo().create(line_vals)
        
        # 提交订单
        order.action_submit()
        
        return request.redirect('/sample/order/success/%s' % order.id)
    
    @http.route(['/sample/order/success/<int:order_id>'], type='http', auth='user', website=True)
    def sample_order_success(self, order_id, **kwargs):
        """订单提交成功页面"""
        order = request.env['sample.order'].sudo().browse(order_id)
        
        if not order.exists():
            return request.redirect('/materials')
        
        return request.render('diecut.sample_order_success', {
            'order': order,
        })
    
    @http.route(['/my/sample/orders'], type='http', auth='user', website=True)
    def my_sample_orders(self, **kwargs):
        """我的打样订单"""
        orders = request.env['sample.order'].sudo().search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], order='create_date desc')
        
        return request.render('diecut.my_sample_orders', {
            'orders': orders,
        })


class CatalogCsvGridController(http.Controller):
    _ALLOWED = {"series.csv", "variants.csv"}

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

    @http.route("/diecut/catalog/csv-grid", type="http", auth="user")
    def csv_grid_page(self, file="series.csv", **kwargs):
        _full_path, safe_name = self._resolve_csv(file)
        if not safe_name:
            return request.not_found()

        html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CSV编辑器 - {safe_name}</title>
  <link rel="stylesheet" href="https://unpkg.com/ag-grid-community/styles/ag-grid.css">
  <link rel="stylesheet" href="https://unpkg.com/ag-grid-community/styles/ag-theme-alpine.css">
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; }}
    .toolbar {{ padding: 10px; display: flex; gap: 8px; align-items: center; border-bottom: 1px solid #ddd; }}
    .toolbar .status {{ margin-left: auto; color: #444; }}
    #grid {{ height: calc(100vh - 54px); width: 100%; }}
    button {{ padding: 6px 12px; border: 1px solid #999; background: #f7f7f7; cursor: pointer; }}
    button.primary {{ background: #6f42c1; color: #fff; border-color: #6f42c1; }}
    .ag-cell-error {{ background-color: #f8d7da !important; }}
    #errorList {{ max-height: 120px; overflow: auto; font-size: 12px; color: #721c24; margin-top: 4px; }}
  </style>
</head>
<body>
  <div class="toolbar">
    <strong>AG Grid CSV编辑器</strong>
    <span>文件: {safe_name}</span>
    <button id="reloadBtn">刷新</button>
    <button id="addRowBtn">新增行</button>
    <button id="saveBtn" class="primary">保存</button>
    <span id="status" class="status">加载中...</span>
  </div>
  <div id="errorList" style="display:none;"></div>
  <div id="grid" class="ag-theme-alpine"></div>
  <script src="https://unpkg.com/ag-grid-community/dist/ag-grid-community.min.js"></script>
  <script>
    const fileName = {json.dumps(safe_name)};
    const statusEl = document.getElementById('status');
    const gridDiv = document.getElementById('grid');
    const errorListEl = document.getElementById('errorList');
    let gridApi = null;
    let headers = [];
    let validationErrors = new Set();

    async function loadData() {{
      validationErrors = new Set();
      errorListEl.style.display = 'none';
      statusEl.textContent = '加载中...';
      const resp = await fetch(`/diecut/catalog/csv-grid/data?file=${{encodeURIComponent(fileName)}}`);
      const payload = await resp.json();
      if (!payload.ok) {{
        statusEl.textContent = '加载失败: ' + (payload.error || '未知错误');
        return;
      }}
      headers = payload.headers || [];
      const columnDefs = headers.map(h => ({{
        field: h,
        editable: true,
        resizable: true,
        sortable: true,
        filter: true,
        getCellClass: (params) => validationErrors.has(params.rowIndex + ':' + params.colDef.field) ? 'ag-cell-error' : ''
      }}));
      const rowData = payload.rows || [];
      const options = {{
        columnDefs,
        rowData,
        defaultColDef: {{ flex: 1, minWidth: 140 }},
        enableCellTextSelection: true,
        suppressRowClickSelection: true,
        rowSelection: 'multiple',
      }};
      gridDiv.innerHTML = '';
      gridApi = agGrid.createGrid(gridDiv, options);
      statusEl.textContent = `已加载 ${{rowData.length}} 行`;
    }}

    function collectRows() {{
      const rows = [];
      if (!gridApi) return rows;
      gridApi.forEachNode(node => rows.push(node.data || {{}}));
      return rows;
    }}

    async function saveData() {{
      validationErrors = new Set();
      errorListEl.style.display = 'none';
      if (gridApi) gridApi.refreshCells({{ force: true }});
      statusEl.textContent = '保存中...';
      const rows = collectRows();
      const resp = await fetch('/diecut/catalog/csv-grid/save', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ file: fileName, headers, rows }})
      }});
      const payload = await resp.json();
      if (!payload.ok) {{
        statusEl.textContent = (payload.error || '保存失败') + (payload.errors && payload.errors.length ? '（' + payload.errors.length + ' 处）' : '');
        if (payload.errors && payload.errors.length) {{
          payload.errors.forEach(e => validationErrors.add(e.rowIndex + ':' + e.field));
          errorListEl.innerHTML = '<strong>校验错误：</strong><br>' + payload.errors.map(e => '第' + (e.rowIndex + 1) + '行 · ' + e.field + ': ' + e.message).join('<br>');
          errorListEl.style.display = 'block';
          if (gridApi) gridApi.refreshCells({{ force: true }});
        }}
        return;
      }}
      statusEl.textContent = `已保存，${{payload.row_count}} 行`;
    }}

    document.getElementById('reloadBtn').addEventListener('click', () => window.location.reload());
    document.getElementById('addRowBtn').addEventListener('click', () => {{
      if (!gridApi) return;
      const obj = Object.fromEntries((headers || []).map(h => [h, '']));
      gridApi.applyTransaction({{ add: [obj] }});
    }});
    document.getElementById('saveBtn').addEventListener('click', saveData);

    loadData();
  </script>
</body>
</html>"""
        return request.make_response(html, headers=[("Content-Type", "text/html; charset=utf-8")])

    @http.route("/diecut/catalog/csv-grid/data", type="http", auth="user")
    def csv_grid_data(self, file="series.csv", **kwargs):
        full_path, safe_name = self._resolve_csv(file)
        if not safe_name:
            return request.make_response(json.dumps({"ok": False, "error": "非法文件名"}), headers=[("Content-Type", "application/json")])

        if not os.path.exists(full_path):
            return request.make_response(json.dumps({"ok": False, "error": f"文件不存在: {safe_name}"}), headers=[("Content-Type", "application/json")])

        try:
            with open(full_path, "r", encoding="utf-8-sig", newline="") as fp:
                reader = list(csv.reader(fp))
        except UnicodeDecodeError:
            with open(full_path, "r", encoding="gbk", newline="") as fp:
                reader = list(csv.reader(fp))

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
        """主键校验，返回错误列表 [{rowIndex, field, message}]。"""
        errors = []
        if safe_name == "series.csv":
            key_field = "series_xml_id"
            if key_field not in headers:
                return [{"rowIndex": -1, "field": key_field, "message": "缺少列 series_xml_id"}]
            seen = {}
            for i, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                val = (row.get(key_field) or "").strip()
                if not val:
                    errors.append({"rowIndex": i, "field": key_field, "message": "不能为空"})
                    continue
                if val in seen:
                    errors.append({
                        "rowIndex": i,
                        "field": key_field,
                        "message": f"与第 {seen[val] + 1} 行重复",
                    })
                else:
                    seen[val] = i
        elif safe_name == "variants.csv":
            f1, f2 = "series_xml_id", "default_code"
            for f in (f1, f2):
                if f not in headers:
                    errors.append({"rowIndex": -1, "field": f, "message": f"缺少列 {f}"})
            if any(e["rowIndex"] == -1 for e in errors):
                return errors
            seen = {}
            for i, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                v1 = (row.get(f1) or "").strip()
                v2 = (row.get(f2) or "").strip()
                if not v1:
                    errors.append({"rowIndex": i, "field": f1, "message": "不能为空"})
                if not v2:
                    errors.append({"rowIndex": i, "field": f2, "message": "不能为空"})
                key = (v1, v2)
                if v1 and v2:
                    if key in seen:
                        errors.append({
                            "rowIndex": i,
                            "field": f2,
                            "message": f"与第 {seen[key] + 1} 行重复（系列+型号）",
                        })
                    else:
                        seen[key] = i
        return errors

    @http.route("/diecut/catalog/csv-grid/save", type="http", auth="user", methods=["POST"], csrf=False)
    def csv_grid_save(self, **kwargs):
        try:
            payload = json.loads(request.httprequest.get_data(as_text=True) or "{}")
        except Exception:
            payload = {}

        full_path, safe_name = self._resolve_csv(payload.get("file"))
        if not safe_name:
            return request.make_response(json.dumps({"ok": False, "error": "非法文件名"}), headers=[("Content-Type", "application/json")])

        headers = payload.get("headers") or []
        rows = payload.get("rows") or []
        if not isinstance(headers, list) or not all(isinstance(h, str) and h for h in headers):
            return request.make_response(json.dumps({"ok": False, "error": "表头不合法"}), headers=[("Content-Type", "application/json")])

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
            if not isinstance(row, dict):
                continue
            writer.writerow([row.get(h, "") for h in headers])

        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8-sig", newline="") as fp:
            fp.write(output.getvalue())

        return request.make_response(
            json.dumps({"ok": True, "row_count": len(rows)}, ensure_ascii=False),
            headers=[("Content-Type", "application/json; charset=utf-8")],
        )
