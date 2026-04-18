---
type: resource
status: active
area: "Odoo"
topic: "Inventory and Product"
reviewed: 2026-04-18
---

# Odoo 产品模型参考文档

## 概述

Odoo 使用两个核心模型来管理产品：

- **`product.template`** - 产品模板，存储产品的共享信息
- **`product.product`** - 产品变体，代表具体可销售/可采购的产品

两者的关系：一个产品模板可以有多个产品变体。

---

## product.template（产品模板）

### 数据表名
`product_template`

### 字段列表

#### 基础信息

| 字段名                 | 类型      | 说明                | 必填 |
| ---------------------- | --------- | ------------------- | ---- |
| `name`                 | Char      | 产品名称（可翻译）  | ✅    |
| `sequence`             | Integer   | 排序序号，默认 1    |      |
| `description`          | Html      | 产品描述            |      |
| `description_purchase` | Text      | 采购描述            |      |
| `description_sale`     | Text      | 销售描述            |      |
| `type`                 | Selection | 产品类型            |      |
| `active`               | Boolean   | 是否活跃，默认 True |      |
| `color`                | Integer   | 颜色索引            |      |

#### type 字段可选值
- `consu` - 消耗品（默认）
- `service` - 服务
- `combo` - 组合产品

#### 分类与标签

| 字段名            | 类型                        | 说明     |
| ----------------- | --------------------------- | -------- |
| `categ_id`        | Many2one → product.category | 产品分类 |
| `product_tag_ids` | Many2many → product.tag     | 产品标签 |
| `is_favorite`     | Boolean                     | 是否收藏 |

#### 价格相关

| 字段名               | 类型                              | 说明                   |
| -------------------- | --------------------------------- | ---------------------- |
| `list_price`         | Float                             | 销售价格               |
| `standard_price`     | Float                             | 成本价（存储在变体上） |
| `currency_id`        | Many2one → res.currency           | 货币                   |
| `cost_currency_id`   | Many2one → res.currency           | 成本货币               |
| `pricelist_rule_ids` | One2many → product.pricelist.item | 价格表规则             |

#### 单位与规格

| 字段名            | 类型                | 说明                       |
| ----------------- | ------------------- | -------------------------- |
| `uom_id`          | Many2one → uom.uom  | 计量单位                   |
| `uom_ids`         | Many2many → uom.uom | 可用包装单位               |
| `uom_name`        | Char                | 单位名称（只读，关联字段） |
| `volume`          | Float               | 体积                       |
| `volume_uom_name` | Char                | 体积单位名称（计算字段）   |
| `weight`          | Float               | 重量                       |
| `weight_uom_name` | Char                | 重量单位名称（计算字段）   |

#### 销售与采购

| 字段名               | 类型                            | 说明              |
| -------------------- | ------------------------------- | ----------------- |
| `sale_ok`            | Boolean                         | 可销售，默认 True |
| `purchase_ok`        | Boolean                         | 可采购，默认 True |
| `service_tracking`   | Selection                       | 服务跟踪类型      |
| `seller_ids`         | One2many → product.supplierinfo | 供应商信息        |
| `variant_seller_ids` | One2many → product.supplierinfo | 变体供应商信息    |

#### 编码与条形码

| 字段名         | 类型 | 说明                           |
| -------------- | ---- | ------------------------------ |
| `default_code` | Char | 内部参考（计算字段，来自变体） |
| `barcode`      | Char | 条形码（计算字段，来自变体）   |

#### 变体相关

| 字段名                                      | 类型                                       | 说明                               |
| ------------------------------------------- | ------------------------------------------ | ---------------------------------- |
| `product_variant_ids`                       | One2many → product.product                 | 产品变体列表                       |
| `product_variant_id`                        | Many2one → product.product                 | 第一个变体（计算字段）             |
| `product_variant_count`                     | Integer                                    | 变体数量（计算字段）               |
| `attribute_line_ids`                        | One2many → product.template.attribute.line | 属性行                             |
| `valid_product_template_attribute_line_ids` | Many2many                                  | 有效的属性行                       |
| `has_configurable_attributes`               | Boolean                                    | 是否可配置产品（计算字段）         |
| `is_product_variant`                        | Boolean                                    | 是否为变体（计算字段，始终 False） |
| `is_dynamically_created`                    | Boolean                                    | 是否动态创建（计算字段）           |

#### 其他

| 字段名                   | 类型                        | 说明                 |
| ------------------------ | --------------------------- | -------------------- |
| `company_id`             | Many2one → res.company      | 公司                 |
| `combo_ids`              | Many2many → product.combo   | 组合产品             |
| `product_document_ids`   | One2many → product.document | 产品文档             |
| `product_document_count` | Integer                     | 文档数量（计算字段） |
| `product_properties`     | Properties                  | 自定义属性           |
| `product_tooltip`        | Char                        | 产品提示（计算字段） |

### 主要方法

| 方法名                                | 说明                 |
| ------------------------------------- | -------------------- |
| `create(vals)`                        | 创建产品模板         |
| `write(vals)`                         | 更新产品模板         |
| `unlink()`                            | 删除产品模板         |
| `copy(default)`                       | 复制产品模板         |
| `_compute_product_variant_id()`       | 计算第一个变体       |
| `_compute_product_variant_count()`    | 计算变体数量         |
| `_create_variant_ids()`               | 创建变体             |
| `_get_possible_combinations()`        | 获取可能的属性组合   |
| `_is_combination_possible()`          | 检查组合是否可能     |
| `_get_closest_possible_combination()` | 获取最接近的可能组合 |
| `get_single_product_variant()`        | 获取单一变体信息     |
| `get_contextual_price()`              | 获取上下文价格       |
| `_get_contextual_pricelist()`         | 获取上下文价格表     |
| `get_import_templates()`              | 获取导入模板         |

---

## product.product（产品变体）

### 数据表名
`product_product`

### 继承关系

```python
class ProductProduct(models.Model):
    _name = "product.product"
    _inherits = {'product.template': 'product_tmpl_id'}
```

**重要**：通过 `_inherits` 委托继承 `product.template`，可以直接访问模板的所有字段。

### 字段列表

#### 核心关联

| 字段名            | 类型                        | 说明     | 必填 |
| ----------------- | --------------------------- | -------- | ---- |
| `product_tmpl_id` | Many2one → product.template | 产品模板 | ✅    |

#### 编码与标识

| 字段名         | 类型 | 说明                 |
| -------------- | ---- | -------------------- |
| `default_code` | Char | 内部参考（SKU）      |
| `barcode`      | Char | 条形码               |
| `code`         | Char | 参考编码（计算字段） |
| `partner_ref`  | Char | 客户参考（计算字段） |

#### 价格相关

| 字段名           | 类型  | 说明                        |
| ---------------- | ----- | --------------------------- |
| `price_extra`    | Float | 变体额外价格（来自属性值）  |
| `lst_price`      | Float | 销售价格（基础价 + 额外价） |
| `standard_price` | Float | 成本价                      |

#### 规格相关

| 字段名   | 类型  | 说明 |
| -------- | ----- | ---- |
| `volume` | Float | 体积 |
| `weight` | Float | 重量 |

#### 变体属性

| 字段名                                 | 类型                                         | 说明                               |
| -------------------------------------- | -------------------------------------------- | ---------------------------------- |
| `product_template_attribute_value_ids` | Many2many → product.template.attribute.value | 属性值                             |
| `product_template_variant_value_ids`   | Many2many                                    | 变体属性值                         |
| `combination_indices`                  | Char                                         | 组合索引（计算字段，用于快速查找） |

#### 状态

| 字段名               | 类型    | 说明                              |
| -------------------- | ------- | --------------------------------- |
| `active`             | Boolean | 是否活跃                          |
| `is_product_variant` | Boolean | 是否为变体（计算字段，始终 True） |
| `is_favorite`        | Boolean | 收藏（关联到模板）                |

#### 图片

| 字段名                             | 类型    | 说明                                   |
| ---------------------------------- | ------- | -------------------------------------- |
| `image_variant_1920`               | Image   | 变体图片（1920px）                     |
| `image_variant_1024`               | Image   | 变体图片（1024px）                     |
| `image_variant_512`                | Image   | 变体图片（512px）                      |
| `image_variant_256`                | Image   | 变体图片（256px）                      |
| `image_variant_128`                | Image   | 变体图片（128px）                      |
| `image_1920`                       | Image   | 最终图片（优先变体图片，否则模板图片） |
| `image_1024`                       | Image   | 最终图片（1024px）                     |
| `image_512`                        | Image   | 最终图片（512px）                      |
| `image_256`                        | Image   | 最终图片（256px）                      |
| `image_128`                        | Image   | 最终图片（128px）                      |
| `can_image_variant_1024_be_zoomed` | Boolean | 变体图片是否可放大                     |
| `can_image_1024_be_zoomed`         | Boolean | 图片是否可放大                         |

#### 其他

| 字段名                       | 类型                              | 说明                    |
| ---------------------------- | --------------------------------- | ----------------------- |
| `product_uom_ids`            | One2many → product.uom            | 单位条形码              |
| `pricelist_rule_ids`         | One2many → product.pricelist.item | 价格表规则              |
| `product_document_ids`       | One2many → product.document       | 产品文档                |
| `product_document_count`     | Integer                           | 文档数量                |
| `additional_product_tag_ids` | Many2many → product.tag           | 附加标签                |
| `all_product_tag_ids`        | Many2many                         | 所有标签（模板 + 变体） |
| `write_date`                 | Datetime                          | 最后更新时间            |

### 主要方法

| 方法名                           | 说明                     |
| -------------------------------- | ------------------------ |
| `create(vals)`                   | 创建产品变体             |
| `write(vals)`                    | 更新产品变体             |
| `unlink()`                       | 删除产品变体             |
| `copy(default)`                  | 复制产品变体             |
| `name_get()`                     | 获取显示名称             |
| `_compute_product_code()`        | 计算产品编码             |
| `_compute_partner_ref()`         | 计算客户参考             |
| `_compute_combination_indices()` | 计算组合索引             |
| `_compute_image_1920()`          | 计算图片                 |
| `_price_compute()`               | 计算价格                 |
| `price_compute()`                | 获取价格                 |
| `_get_product_price()`           | 获取产品价格（带价格表） |
| `_is_variant_possible()`         | 检查变体是否可能         |

---

## 两者关系图

```
┌───────────────────────────────────────────────────────────────┐
│                     product.template                          │
│                     (产品模板)                                │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ 共享信息                                                │  │
│  │ - name (名称)                                           │  │
│  │ - list_price (销售价格)                                 │  │
│  │ - categ_id (分类)                                       │  │
│  │ - uom_id (单位)                                         │  │
│  │ - sale_ok / purchase_ok                                 │  │
│  │ - description (描述)                                    │  │
│  │ - attribute_line_ids (属性行)                           │  │
│  └─────────────────────────────────────────────────────────┘  │
│                             │                                 │
│                   product_variant_ids                         │
│                       (One2many)                              │
│                             │                                 │
│              ┌──────────────┼──────────────┐                  │
│              ▼              ▼              ▼                  │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐     │
│  │product.product│  │product.product│  │product.product│     │
│  │   (变体 1)    │  │   (变体 2)    │  │   (变体 3)    │     │
│  ├───────────────┤  ├───────────────┤  ├───────────────┤     │
│  │红色-S码       │  │红色-M码       │  │蓝色-L码       │     │
│  │SKU: TS-R-S    │  │SKU: TS-R-M    │  │SKU: TS-B-L    │     │
│  │条形码: 123    │  │条形码: 124    │  │条形码: 125    │     │
│  └───────────────┘  └───────────────┘  └───────────────┘     │
└───────────────────────────────────────────────────────────────┘
```

---

## 使用示例

### 1. 继承 product.template 添加字段

```python
from odoo import models, fields

class ProductTemplateExtend(models.Model):
    _inherit = 'product.template'
    
    # 添加自定义字段
    x_custom_field = fields.Char("自定义字段")
    x_material = fields.Char("材质")
    x_origin_country = fields.Many2one('res.country', string="原产国")
```

### 2. 继承 product.product 添加字段

```python
from odoo import models, fields

class ProductProductExtend(models.Model):
    _inherit = 'product.product'
    
    # 添加变体特有字段
    x_serial_number = fields.Char("序列号")
    x_manufacturing_date = fields.Date("生产日期")
```

### 3. 覆盖方法

```python
from odoo import models, api

class ProductTemplateExtend(models.Model):
    _inherit = 'product.template'
    
    @api.model
    def create(self, vals):
        # 自定义创建逻辑
        if not vals.get('default_code'):
            vals['default_code'] = self.env['ir.sequence'].next_by_code('product.template.code')
        return super().create(vals)
    
    def write(self, vals):
        # 自定义更新逻辑
        result = super().write(vals)
        if 'list_price' in vals:
            # 价格变化时的处理
            pass
        return result
```

### 4. 查询产品

```python
# 查找所有可销售产品
products = self.env['product.template'].search([('sale_ok', '=', True)])

# 查找特定分类的产品变体
variants = self.env['product.product'].search([
    ('categ_id.name', '=', '原材料'),
    ('active', '=', True)
])

# 通过变体获取模板
template = variant.product_tmpl_id

# 通过模板获取所有变体
variants = template.product_variant_ids
```

---

## 注意事项

1. **库存跟踪**：库存是在 `product.product`（变体）级别跟踪的，不是模板级别

2. **价格计算**：
   - 模板的 `list_price` 是基础价格
   - 变体的 `lst_price` = 模板的 `list_price` + 变体的 `price_extra`

3. **条形码和内部参考**：
   - 这些字段实际存储在 `product.product`
   - 模板上的是计算字段，来自第一个变体

4. **单变体产品**：
   - 没有属性的产品只有一个变体
   - 此时模板和变体几乎等价

5. **删除限制**：
   - 不能删除有库存移动或销售订单行的产品
   - 建议使用 `active = False` 归档而非删除
