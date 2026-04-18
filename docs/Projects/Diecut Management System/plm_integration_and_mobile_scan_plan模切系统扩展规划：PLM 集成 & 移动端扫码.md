---
type: project
status: active
area: "Diecut Management System"
topic: "Diecut Management System"
reviewed: 2026-04-18
---

# 模切系统扩展规划：PLM 集成 & 移动端扫码

> 📅 创建日期：2026-02-26  
> 📌 状态：规划备用  
> 🏷️ 模块：diecut

---

## 目录

- [一、与 PLM 系统集成（JSON-RPC）](#一与-plm-系统集成json-rpc)
- [二、移动端扫码查看分类](#二移动端扫码查看分类)
- [三、实施优先级与时间规划](#三实施优先级与时间规划)

---

## 一、与 PLM 系统集成（JSON-RPC）

### 1.1 需求背景

通过 Odoo 的 **External API**（JSON-RPC / XML-RPC）接收外部 PLM 系统推送的物料数据，实现：

- 新物料自动同步到 Odoo 的 `product.template`
- 物料属性变更（厚度、宽度、分类等）自动更新
- 功能标签（`product.tag`）和材质分类（`product.category`）自动关联

### 1.2 技术方案对比

| 方案 | 适用场景 | 复杂度 | 安全性 |
|---|---|---|---|
| **A. Odoo 原生 JSON-RPC** | PLM 支持 HTTP 调用，快速对接 | ⭐ 低 | 中（用户名密码认证） |
| **B. 自定义 REST Controller** | 需要定制化接口格式 | ⭐⭐ 中 | 高（API Key 认证） |
| **C. 消息队列（RabbitMQ）** | 高并发、异步场景 | ⭐⭐⭐ 高 | 高 |

### 1.3 方案 A：使用 Odoo 原生 JSON-RPC（推荐首选）

**优点**：零 Odoo 侧开发，仅需 PLM 侧编写调用脚本。

#### PLM 侧调用代码（Python 示例）

```python
# plm_sync/odoo_client.py
import requests
import json

class OdooClient:
    """PLM 系统调用 Odoo 的客户端封装"""

    def __init__(self, url: str, db: str, username: str, password: str):
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.uid = self._authenticate()

    def _authenticate(self) -> int:
        """认证并获取用户 ID"""
        response = requests.post(f"{self.url}/jsonrpc", json={
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "common",
                "method": "authenticate",
                "args": [self.db, self.username, self.password, {}]
            }
        })
        uid = response.json().get("result")
        if not uid:
            raise ConnectionError("Odoo 认证失败，请检查账号密码")
        return uid

    def execute(self, model: str, method: str, args: list, kwargs: dict | None = None) -> any:
        """调用 Odoo ORM 方法"""
        response = requests.post(f"{self.url}/jsonrpc", json={
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": "object",
                "method": "execute_kw",
                "args": [self.db, self.uid, self.password, model, method, args, kwargs or {}]
            }
        })
        result = response.json()
        if "error" in result:
            raise Exception(f"Odoo RPC 错误: {result['error']}")
        return result.get("result")

    def sync_material(self, material_data: dict) -> dict:
        """同步单条物料数据到 Odoo"""
        code = material_data.get("code")
        if not code:
            raise ValueError("物料编码 (code) 不能为空")

        # 1. 查找是否已存在
        existing_ids = self.execute("product.template", "search", [
            [("default_code", "=", code), ("is_raw_material", "=", True)]
        ])

        # 2. 构建 vals
        vals = {
            "name": material_data.get("name"),
            "default_code": code,
            "is_raw_material": True,
            "thickness": material_data.get("thickness", 0),
            "width": material_data.get("width", 0),
            "length": material_data.get("length", 0),
        }

        # 3. 处理分类（按名称匹配）
        if material_data.get("category_name"):
            categ_ids = self.execute("product.category", "search", [
                [("name", "=", material_data["category_name"]),
                 ("category_type", "=", "raw")]
            ])
            if categ_ids:
                vals["categ_id"] = categ_ids[0]

        # 4. 处理功能标签（按名称匹配）
        if material_data.get("tags"):
            tag_ids = self.execute("product.tag", "search", [
                [("name", "in", material_data["tags"])]
            ])
            if tag_ids:
                vals["product_tag_ids"] = [(6, 0, tag_ids)]  # 替换所有标签

        # 5. 创建或更新
        if existing_ids:
            self.execute("product.template", "write", [existing_ids, vals])
            return {"status": "updated", "id": existing_ids[0], "code": code}
        else:
            new_id = self.execute("product.template", "create", [vals])
            return {"status": "created", "id": new_id, "code": code}
```

#### PLM 侧调用示例

```python
# plm_sync/run_sync.py
from odoo_client import OdooClient

client = OdooClient(
    url="http://your-odoo-server:8069",
    db="odoo_dev",
    username="admin",
    password="admin"
)

# 同步单条物料
result = client.sync_material({
    "code": "PET-025-500",
    "name": "PET薄膜 25μm × 500mm",
    "category_name": "保护膜",
    "tags": ["绝缘隔离", "防护保洁"],
    "thickness": 0.025,
    "width": 500,
    "length": 200,
})
print(result)
# 输出: {'status': 'created', 'id': 42, 'code': 'PET-025-500'}

# 批量同步
materials = [
    {"code": "CU-035", "name": "铜箔 35μm", "category_name": "金属箔", "tags": ["导电/屏蔽"], "thickness": 0.035},
    {"code": "EVA-2.0", "name": "EVA泡棉 2.0mm", "category_name": "泡棉类", "tags": ["缓冲减震"], "thickness": 2.0},
]
for mat in materials:
    print(client.sync_material(mat))
```

### 1.4 方案 B：自定义 REST Controller（进阶方案）

当 PLM 系统需要更简洁的 RESTful 接口时，在 Odoo 侧创建自定义 Controller。

#### Odoo 侧代码

```python
# controllers/api_material.py
from odoo import http
from odoo.http import request
from odoo.fields import Command

class MaterialAPI(http.Controller):

    @http.route('/api/v1/material/sync', type='json', auth='api_key',
                methods=['POST'], csrf=False)
    def sync_material(self, **kwargs):
        """
        接收 PLM 推送的物料数据
        
        请求体示例:
        {
            "code": "PET-025-500",
            "name": "PET薄膜 25μm × 500mm",
            "category_name": "保护膜",
            "tags": ["绝缘隔离", "防护保洁"],
            "thickness": 0.025,
            "width": 500,
            "length": 200
        }
        """
        data = request.jsonrequest

        # 参数校验
        if not data.get('code'):
            return {'error': '物料编码 (code) 不能为空', 'status': 'failed'}

        product = request.env['product.template'].sudo().search([
            ('default_code', '=', data['code']),
            ('is_raw_material', '=', True)
        ], limit=1)

        vals = {
            'name': data.get('name'),
            'default_code': data['code'],
            'is_raw_material': True,
            'thickness': data.get('thickness', 0),
            'width': data.get('width', 0),
            'length': data.get('length', 0),
        }

        # 分类匹配
        if data.get('category_name'):
            categ = request.env['product.category'].sudo().search([
                ('name', '=', data['category_name']),
                ('category_type', '=', 'raw')
            ], limit=1)
            if categ:
                vals['categ_id'] = categ.id

        # 功能标签匹配
        if data.get('tags'):
            tags = request.env['product.tag'].sudo().search([
                ('name', 'in', data['tags'])
            ])
            if tags:
                vals['product_tag_ids'] = [Command.set(tags.ids)]

        # 创建或更新
        if product:
            product.sudo().write(vals)
            return {'status': 'updated', 'id': product.id}
        else:
            product = request.env['product.template'].sudo().create(vals)
            return {'status': 'created', 'id': product.id}

    @http.route('/api/v1/material/<string:code>', type='json', auth='api_key',
                methods=['GET'], csrf=False)
    def get_material(self, code, **kwargs):
        """根据编码查询物料信息"""
        product = request.env['product.template'].sudo().search([
            ('default_code', '=', code),
            ('is_raw_material', '=', True)
        ], limit=1)

        if not product:
            return {'error': f'未找到编码为 {code} 的物料', 'status': 'not_found'}

        return {
            'status': 'ok',
            'data': {
                'id': product.id,
                'name': product.name,
                'code': product.default_code,
                'category': product.categ_id.name,
                'tags': product.product_tag_ids.mapped('name'),
                'thickness': product.thickness,
                'width': product.width,
                'length': product.length,
            }
        }
```

#### PLM 侧调用

```python
import requests

# 使用 Odoo API Key 认证
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer your-odoo-api-key-here"
}

# 推送物料
response = requests.post(
    "http://odoo-server:8069/api/v1/material/sync",
    json={"jsonrpc": "2.0", "params": {
        "code": "PET-025",
        "name": "PET薄膜 25μm",
        "category_name": "保护膜",
        "tags": ["绝缘隔离"],
        "thickness": 0.025
    }},
    headers=headers
)
print(response.json())
```

#### 需要的文件改动

| 文件 | 操作 |
|---|---|
| `controllers/__init__.py` | 添加 `from . import api_material` |
| `controllers/api_material.py` | 新建（上述代码） |
| `__manifest__.py` | 确保 `controllers` 已导入 |

### 1.5 安全考虑

| 安全措施 | 方案 A (JSON-RPC) | 方案 B (REST) |
|---|---|---|
| 认证方式 | 用户名 + 密码 | API Key (推荐) |
| 权限控制 | 受 Odoo 用户权限约束 | `sudo()` 跳过权限（需谨慎） |
| IP 白名单 | 通过反向代理（Nginx）配置 | 同左 |
| HTTPS | 生产环境必须启用 | 同左 |
| 速率限制 | 无原生支持，需 Nginx 配置 | 可在 Controller 中添加 |

---

## 二、移动端扫码查看分类

### 2.1 需求背景

在仓库/车间场景中，工作人员通过手机扫描原材料上的 **QR 码**，直接查看该材料的：

- 材质分类（胶带类、泡棉类…）
- 功能标签（绝缘隔离、导电屏蔽…）
- 规格参数、供应商、价格等详细信息

### 2.2 技术方案对比

| 方案 | 说明 | 复杂度 | 推荐场景 |
|---|---|---|---|
| **A. Odoo Mobile App** | 原生支持扫码，直接跳转产品表单 | ⭐ | 内部员工使用 |
| **B. Web QR 码 + 移动浏览器** | 生成 QR 码链接到 Web 端 | ⭐⭐ | 通用场景 |
| **C. 微信小程序 / 企业微信** | 对接微信生态 | ⭐⭐⭐ | 国内企业用户 |

### 2.3 方案 A：Odoo Mobile App（最简单）

Odoo 官方 Mobile App 内置条码扫描功能，扫描后自动跳转到对应产品的表单视图。

**无需额外开发**，只需确保：
- 产品有 `barcode` 字段值（可用 `default_code` 作为条码）
- 手机已安装 Odoo Mobile App 并登录

### 2.4 方案 B：QR 码生成 + Web 端访问（推荐）

#### Step 1：模型层 —— 生成 QR 码

```python
# models/product_diecut.py 中添加
import qrcode
import io
import base64

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    qr_code_image = fields.Binary(
        string='产品二维码',
        compute='_compute_qr_code',
        store=True,
        help='扫码后跳转到产品详情页'
    )

    @api.depends('id')
    def _compute_qr_code(self):
        """为每个产品生成 QR 码"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for product in self:
            if not product.id or isinstance(product.id, models.NewId):
                product.qr_code_image = False
                continue

            # QR 码内容：产品详情页 URL
            url = f"{base_url}/odoo/product-template/{product.id}"

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=8,
                border=2,
            )
            qr.add_data(url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            product.qr_code_image = base64.b64encode(buffer.getvalue())
```

#### Step 2：视图层 —— 在表单中显示 QR 码

```xml
<!-- views/my_material_base_views.xml -->
<!-- 在产品表单的 sheet 区域添加 QR 码头像 -->
<xpath expr="//div[@class='oe_title']" position="before">
    <div class="oe_avatar">
        <field name="qr_code_image" widget="image"
               invisible="not qr_code_image" />
    </div>
</xpath>
```

#### Step 3：打印标签（可选）

```xml
<!-- report/product_qr_label.xml -->
<template id="report_product_qr_label">
    <t t-call="web.html_container">
        <t t-foreach="docs" t-as="product">
            <div class="page" style="text-align: center; padding: 10mm;">
                <!-- QR 码 -->
                <img t-att-src="image_data_uri(product.qr_code_image)"
                     style="width: 30mm; height: 30mm;" />
                <!-- 产品信息 -->
                <div style="font-size: 10pt; margin-top: 3mm;">
                    <strong t-esc="product.name" />
                </div>
                <div style="font-size: 8pt; color: #666;">
                    <span t-esc="product.default_code" />
                    | <span t-esc="product.categ_id.name" />
                </div>
            </div>
        </t>
    </t>
</template>
```

#### Step 4（可选）：自定义移动端友好页面

如果需要比 Odoo 标准表单更好的移动端体验：

```python
# controllers/mobile_material.py
from odoo import http
from odoo.http import request

class MobileMaterial(http.Controller):

    @http.route('/m/material/<int:product_id>', type='http', auth='public',
                website=True)
    def material_detail(self, product_id, **kwargs):
        """移动端友好的产品详情页"""
        product = request.env['product.template'].sudo().browse(product_id)
        if not product.exists():
            return request.not_found()

        return request.render('diecut.mobile_material_detail', {
            'product': product,
        })
```

```xml
<!-- views/mobile_material_template.xml -->
<template id="mobile_material_detail" name="移动端物料详情">
    <t t-call="website.layout">
        <div class="container-fluid py-3" style="max-width: 480px;">
            <!-- 顶部：名称 + 编码 -->
            <h4 class="mb-1" t-esc="product.name" />
            <small class="text-muted" t-esc="product.default_code" />
            <hr class="my-2" />

            <!-- 分类标签 -->
            <div class="mb-3">
                <span class="badge bg-primary me-1"
                      t-esc="product.categ_id.name" />
                <t t-foreach="product.product_tag_ids" t-as="tag">
                    <span class="badge me-1"
                          t-attf-style="background-color: #{tag.color}; color: white;"
                          t-esc="tag.name" />
                </t>
            </div>

            <!-- 规格参数 -->
            <div class="card mb-3">
                <div class="card-header fw-bold">📐 规格参数</div>
                <ul class="list-group list-group-flush">
                    <li class="list-group-item d-flex justify-content-between">
                        <span>厚度</span>
                        <span><t t-esc="product.thickness" /> mm</span>
                    </li>
                    <li class="list-group-item d-flex justify-content-between">
                        <span>宽度</span>
                        <span><t t-esc="product.width" /> mm</span>
                    </li>
                    <li class="list-group-item d-flex justify-content-between">
                        <span>长度</span>
                        <span t-esc="product.length_smart" />
                    </li>
                    <li class="list-group-item d-flex justify-content-between">
                        <span>形态</span>
                        <span t-if="product.rs_type == 'R'">卷料</span>
                        <span t-elif="product.rs_type == 'S'">片料</span>
                    </li>
                </ul>
            </div>

            <!-- 供应商 -->
            <div class="card mb-3" t-if="product.main_vendor_id">
                <div class="card-header fw-bold">🏭 供应商</div>
                <ul class="list-group list-group-flush">
                    <li class="list-group-item d-flex justify-content-between">
                        <span>主要供应商</span>
                        <span t-esc="product.main_vendor_id.name" />
                    </li>
                    <li class="list-group-item d-flex justify-content-between">
                        <span>单价/m²</span>
                        <span t-esc="product.raw_material_price_m2" />
                    </li>
                </ul>
            </div>
        </div>
    </t>
</template>
```

### 2.5 QR 码方案中的 URL 设计

| URL 模式 | 跳转目标 | 适用场景 |
|---|---|---|
| `/odoo/product-template/{id}` | Odoo 后台产品表单 | 内部员工（需登录） |
| `/m/material/{id}` | 自定义移动端页面 | 仓库工人（无需登录） |
| `/shop/product/{slug}` | Website 产品页 | 外部客户 |

---

## 三、实施优先级与时间规划

### 优先级矩阵

```
紧急 ↑
     │
     │  ┌─────────────┐
     │  │ QR 码生成    │  ← 基础功能，半天可完成
     │  │ (方案 B)     │
     │  └─────────────┘
     │
     │          ┌─────────────────┐
     │          │ PLM JSON-RPC    │  ← 等有对接需求时再做
     │          │ (方案 A)        │
     │          └─────────────────┘
     │
     │                  ┌─────────────────┐
     │                  │ REST Controller │  ← 进阶需求
     │                  │ (方案 B)        │
     │                  └─────────────────┘
     │
     │                          ┌──────────────┐
     │                          │ 移动端定制页  │  ← 锦上添花
     │                          │ 微信小程序    │
     │                          └──────────────┘
     └──────────────────────────────────────────→ 重要

```

### 工时估算

| 功能 | 预计工时 | 前置条件 |
|---|---|---|
| QR 码生成 + 表单显示 | 0.5 天 | 无 |
| QR 码打印标签 | 0.5 天 | QR 码生成 |
| PLM JSON-RPC 对接 | 1-2 天 | PLM 侧提供数据格式 |
| 自定义 REST API | 1 天 | 明确接口规范 |
| 移动端定制页面 | 1 天 | QR 码生成 |

### 需要的模块依赖

```python
# __manifest__.py 中需确认的依赖
'depends': ['base', 'product', 'website'],  # website 用于移动端页面
'external_dependencies': {
    'python': ['qrcode'],  # 已有
},
```

---

> 💡 **建议**：优先实现 **QR 码生成**（半天即可完成），其他功能等有实际对接需求时再启动。
