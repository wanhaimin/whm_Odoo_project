---
type: resource
status: active
area: "Odoo"
topic: "Views and ORM"
reviewed: 2026-04-18
---

# @api 装饰器完全指南

## 📚 目录
1. [@api 装饰器概述](#1-api-装饰器概述)
2. [@api.model 详解](#2-apimodel-详解)
3. [@api.model_create_multi 详解](#3-apimodel_create_multi-详解)
4. [@api.depends 详解](#4-apidepends-详解)
5. [@api.onchange 详解](#5-apionchange-详解)
6. [@api.constrains 详解](#6-apiconstrains-详解)
7. [其他常用装饰器](#7-其他常用装饰器)
8. [实战案例](#8-实战案例)

---

## 1. @api 装饰器概述

### 1.1 什么是 @api 装饰器?

`@api` 装饰器是 Odoo 框架提供的一组 Python 装饰器,用于:
- 定义方法的调用方式
- 自动处理记录集
- 触发计算字段更新
- 实现字段验证
- 优化性能

### 1.2 常用装饰器列表

| 装饰器 | 用途 | 常见场景 |
|--------|------|----------|
| `@api.model` | 类方法,不依赖记录 | 创建记录、搜索、工具方法 |
| `@api.model_create_multi` | 批量创建记录 | 优化 create 方法 |
| `@api.depends` | 计算字段依赖 | 自动计算字段值 |
| `@api.onchange` | 字段变化触发 | 动态更新其他字段 |
| `@api.constrains` | 字段约束验证 | 数据验证 |
| `@api.returns` | 定义返回值类型 | 指定返回记录集类型 |
| `@api.autovacuum` | 定时任务 | 自动清理数据 |

---

## 2. @api.model 详解

### 2.1 基本概念

`@api.model` 装饰器用于定义**类方法**,这些方法:
- 不依赖于特定的记录
- 可以在没有记录的情况下调用
- 通常用于创建、搜索等操作

### 2.2 基本语法

```python
@api.model
def method_name(self, param1, param2):
    # 方法体
    return result
```

### 2.3 使用场景

#### 2.3.1 创建记录

```python
@api.model
def create(self, vals):
    # 在创建前修改值
    if vals.get('name', 'New') == 'New':
        vals['name'] = self.env['ir.sequence'].next_by_code('sale.order')
    return super(SaleOrder, self).create(vals)
```

#### 2.3.2 搜索方法

```python
@api.model
def search_active_customers(self):
    return self.search([
        ('active', '=', True),
        ('customer_rank', '>', 0)
    ])
```

#### 2.3.3 工具方法

```python
@api.model
def get_default_country(self):
    return self.env['res.country'].search([('code', '=', 'CN')], limit=1)
```

#### 2.3.4 默认值方法

```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    
    date_order = fields.Datetime(
        string='Order Date',
        default=lambda self: self._get_default_date_order()
    )
    
    @api.model
    def _get_default_date_order(self):
        return fields.Datetime.now()
```

### 2.4 调用方式

```python
# 通过模型调用
self.env['sale.order'].search_active_customers()

# 通过记录集调用(也可以,但不常见)
order = self.env['sale.order'].browse(1)
order.search_active_customers()  # 也可以,但不推荐
```

---

## 3. @api.model_create_multi 详解

### 3.1 基本概念

`@api.model_create_multi` 是 `@api.model` 的增强版,专门用于优化 `create` 方法:
- 支持批量创建记录
- 提高性能
- 减少数据库操作

### 3.2 基本语法

```python
@api.model_create_multi
def create(self, vals_list):
    # vals_list 是一个列表,包含多个字典
    for vals in vals_list:
        # 处理每个字典
        pass
    return super(ModelName, self).create(vals_list)
```

### 3.3 旧版 vs 新版

#### 3.3.1 旧版 (@api.model)

```python
@api.model
def create(self, vals):
    # vals 是一个字典
    if vals.get('name', 'New') == 'New':
        vals['name'] = self.env['ir.sequence'].next_by_code('sale.order')
    return super(SaleOrder, self).create(vals)
```

**调用:**
```python
# 创建单条记录
order = self.env['sale.order'].create({'partner_id': 1})

# 创建多条记录(效率低)
for i in range(100):
    self.env['sale.order'].create({'partner_id': i})  # 100 次数据库操作
```

#### 3.3.2 新版 (@api.model_create_multi)

```python
@api.model_create_multi
def create(self, vals_list):
    # vals_list 是一个列表
    for vals in vals_list:
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('sale.order')
    return super(SaleOrder, self).create(vals_list)
```

**调用:**
```python
# 创建单条记录(自动转换为列表)
order = self.env['sale.order'].create({'partner_id': 1})

# 创建多条记录(效率高)
vals_list = [{'partner_id': i} for i in range(100)]
orders = self.env['sale.order'].create(vals_list)  # 1 次数据库操作
```

### 3.4 兼容性处理

为了同时支持旧版和新版调用:

```python
@api.model_create_multi
def create(self, vals_list):
    # 兼容性处理: 如果传入的是字典,转换为列表
    if isinstance(vals_list, dict):
        vals_list = [vals_list]
    
    for vals in vals_list:
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('sale.order')
    
    return super(SaleOrder, self).create(vals_list)
```

### 3.5 性能对比

**旧版 (100 条记录):**
```python
for i in range(100):
    self.env['sale.order'].create({'partner_id': i})
```
- 数据库操作: 100 次
- 触发器执行: 100 次
- 约束检查: 100 次
- **总时间: ~10 秒**

**新版 (100 条记录):**
```python
vals_list = [{'partner_id': i} for i in range(100)]
self.env['sale.order'].create(vals_list)
```
- 数据库操作: 1 次(批量插入)
- 触发器执行: 1 次
- 约束检查: 1 次
- **总时间: ~0.5 秒**

**性能提升: 20 倍!**

---

## 4. @api.depends 详解

### 4.1 基本概念

`@api.depends` 用于定义**计算字段**的依赖关系:
- 当依赖字段变化时,自动重新计算
- 提高性能,避免不必要的计算
- 支持关联字段依赖

### 4.2 基本语法

```python
@api.depends('field1', 'field2', 'field3')
def _compute_computed_field(self):
    for record in self:
        record.computed_field = record.field1 + record.field2
```

### 4.3 使用场景

#### 4.3.1 简单计算

```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    
    amount_untaxed = fields.Monetary(string='Untaxed Amount')
    amount_tax = fields.Monetary(string='Tax')
    amount_total = fields.Monetary(
        string='Total',
        compute='_compute_amount_total',
        store=True
    )
    
    @api.depends('amount_untaxed', 'amount_tax')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = record.amount_untaxed + record.amount_tax
```

#### 4.3.2 One2many 依赖

```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    
    order_line = fields.One2many('sale.order.line', 'order_id')
    total_quantity = fields.Float(
        string='Total Quantity',
        compute='_compute_total_quantity',
        store=True
    )
    
    @api.depends('order_line.product_uom_qty')
    def _compute_total_quantity(self):
        for record in self:
            record.total_quantity = sum(record.order_line.mapped('product_uom_qty'))
```

#### 4.3.3 Many2one 关联字段依赖

```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    
    partner_id = fields.Many2one('res.partner')
    partner_country = fields.Char(
        string='Partner Country',
        compute='_compute_partner_country',
        store=True
    )
    
    @api.depends('partner_id.country_id.name')
    def _compute_partner_country(self):
        for record in self:
            record.partner_country = record.partner_id.country_id.name or ''
```

#### 4.3.4 多层依赖

```python
@api.depends('order_line.price_subtotal', 'order_line.product_id.taxes_id')
def _compute_amount_total(self):
    for record in self:
        total = 0
        for line in record.order_line:
            total += line.price_subtotal
            # 计算税额
            for tax in line.product_id.taxes_id:
                total += line.price_subtotal * tax.amount / 100
        record.amount_total = total
```

### 4.4 store 参数

```python
# store=True: 存储到数据库,可以在 domain 中使用
amount_total = fields.Monetary(
    compute='_compute_amount_total',
    store=True  # 存储
)

# store=False (默认): 不存储,每次访问时计算
display_name = fields.Char(
    compute='_compute_display_name',
    store=False  # 不存储
)
```

### 4.5 性能优化

✅ **推荐: 使用 store=True**
```python
@api.depends('amount_untaxed', 'amount_tax')
def _compute_amount_total(self):
    for record in self:
        record.amount_total = record.amount_untaxed + record.amount_tax
```

❌ **避免: 复杂计算不存储**
```python
# 每次访问都要计算,很慢
@api.depends('order_line.price_subtotal')
def _compute_amount_total(self):
    for record in self:
        # 复杂计算
        total = 0
        for line in record.order_line:
            total += line.price_subtotal * (1 + line.tax_rate / 100)
        record.amount_total = total
```

---

## 5. @api.onchange 详解

### 5.1 基本概念

`@api.onchange` 用于在界面上字段值变化时触发:
- 动态更新其他字段
- 显示警告信息
- 修改 domain
- **只在界面上生效,不影响后台创建**

### 5.2 基本语法

```python
@api.onchange('field1', 'field2')
def _onchange_field1(self):
    # 修改其他字段
    self.field3 = self.field1 + self.field2
    
    # 返回警告
    if self.field1 < 0:
        return {
            'warning': {
                'title': '警告',
                'message': 'field1 不能为负数'
            }
        }
    
    # 修改 domain
    return {
        'domain': {
            'field4': [('category', '=', self.field1)]
        }
    }
```

### 5.3 使用场景

#### 5.3.1 自动填充字段

```python
@api.onchange('partner_id')
def _onchange_partner_id(self):
    if self.partner_id:
        self.partner_shipping_id = self.partner_id
        self.partner_invoice_id = self.partner_id
        self.payment_term_id = self.partner_id.property_payment_term_id
```

#### 5.3.2 计算金额

```python
@api.onchange('product_uom_qty', 'price_unit', 'discount')
def _onchange_amount(self):
    self.price_subtotal = self.product_uom_qty * self.price_unit * (1 - self.discount / 100)
```

#### 5.3.3 显示警告

```python
@api.onchange('date_order')
def _onchange_date_order(self):
    if self.date_order and self.date_order < fields.Date.today():
        return {
            'warning': {
                'title': '日期警告',
                'message': '订单日期不能早于今天'
            }
        }
```

#### 5.3.4 修改 Domain

```python
@api.onchange('partner_id')
def _onchange_partner_id(self):
    if self.partner_id:
        return {
            'domain': {
                'partner_shipping_id': [('parent_id', '=', self.partner_id.id)],
                'partner_invoice_id': [('parent_id', '=', self.partner_id.id)],
            }
        }
```

#### 5.3.5 清空字段

```python
@api.onchange('product_id')
def _onchange_product_id(self):
    if not self.product_id:
        self.price_unit = 0
        self.product_uom_qty = 0
        self.product_uom = False
```

### 5.4 返回值

```python
@api.onchange('field1')
def _onchange_field1(self):
    return {
        # 警告信息
        'warning': {
            'title': '警告标题',
            'message': '警告内容',
        },
        
        # 修改 domain
        'domain': {
            'field2': [('category', '=', self.field1)],
            'field3': [('active', '=', True)],
        },
    }
```

### 5.5 注意事项

⚠️ **重要:** `@api.onchange` 只在界面上生效

```python
# 界面上创建记录
# ✅ onchange 会触发
order = self.env['sale.order'].create({
    'partner_id': 1,  # 会触发 _onchange_partner_id
})

# 后台创建记录
# ❌ onchange 不会触发
order = self.env['sale.order'].create({
    'partner_id': 1,  # 不会触发 _onchange_partner_id
})
```

**解决方案:** 如果需要在后台也生效,使用 `create` 或 `write` 方法:

```python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        if vals.get('partner_id'):
            partner = self.env['res.partner'].browse(vals['partner_id'])
            vals['payment_term_id'] = partner.property_payment_term_id.id
    return super().create(vals_list)
```

---

## 6. @api.constrains 详解

### 6.1 基本概念

`@api.constrains` 用于定义字段约束:
- 在创建或修改记录时验证
- 验证失败抛出异常
- 阻止保存

### 6.2 基本语法

```python
from odoo.exceptions import ValidationError

@api.constrains('field1', 'field2')
def _check_fields(self):
    for record in self:
        if record.field1 < 0:
            raise ValidationError('field1 不能为负数')
```

### 6.3 使用场景

#### 6.3.1 数值范围验证

```python
@api.constrains('discount')
def _check_discount(self):
    for record in self:
        if record.discount < 0 or record.discount > 100:
            raise ValidationError('折扣必须在 0-100 之间')
```

#### 6.3.2 日期验证

```python
@api.constrains('date_start', 'date_end')
def _check_dates(self):
    for record in self:
        if record.date_end and record.date_start and record.date_end < record.date_start:
            raise ValidationError('结束日期不能早于开始日期')
```

#### 6.3.3 唯一性验证

```python
@api.constrains('code')
def _check_code_unique(self):
    for record in self:
        if self.search_count([('code', '=', record.code), ('id', '!=', record.id)]) > 0:
            raise ValidationError(f'代码 {record.code} 已存在')
```

#### 6.3.4 关联字段验证

```python
@api.constrains('partner_id', 'partner_shipping_id')
def _check_shipping_address(self):
    for record in self:
        if record.partner_shipping_id and record.partner_shipping_id.parent_id != record.partner_id:
            raise ValidationError('送货地址必须属于客户')
```

#### 6.3.5 复杂业务逻辑验证

```python
@api.constrains('state', 'order_line')
def _check_order_lines(self):
    for record in self:
        if record.state == 'sale' and not record.order_line:
            raise ValidationError('确认的订单必须至少有一行明细')
```

### 6.4 SQL 约束 vs Python 约束

#### 6.4.1 SQL 约束

```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', '代码必须唯一'),
        ('amount_positive', 'CHECK(amount_total >= 0)', '金额不能为负'),
    ]
```

**优点:**
- 性能高(数据库层面)
- 始终有效

**缺点:**
- 错误信息不友好
- 无法实现复杂逻辑

#### 6.4.2 Python 约束

```python
@api.constrains('code')
def _check_code_unique(self):
    for record in self:
        if self.search_count([('code', '=', record.code), ('id', '!=', record.id)]) > 0:
            raise ValidationError(f'代码 {record.code} 已存在,请使用其他代码')
```

**优点:**
- 错误信息友好
- 可以实现复杂逻辑

**缺点:**
- 性能较低(Python 层面)

### 6.5 性能优化

✅ **推荐: 简单验证使用 SQL 约束**
```python
_sql_constraints = [
    ('amount_positive', 'CHECK(amount_total >= 0)', '金额不能为负'),
]
```

✅ **推荐: 复杂验证使用 Python 约束**
```python
@api.constrains('state', 'order_line')
def _check_order_lines(self):
    # 复杂逻辑
    pass
```

---

## 7. 其他常用装饰器

### 7.1 @api.returns

指定方法的返回值类型:

```python
@api.returns('res.partner')
def get_partner(self):
    return self.env['res.partner'].browse(1)
```

### 7.2 @api.autovacuum

定时任务,每天自动执行:

```python
@api.autovacuum
def _gc_lost_attachments(self):
    # 清理孤立的附件
    pass
```

### 7.3 @api.model_cr

已废弃,不推荐使用。

---

## 8. 实战案例

### 8.1 案例1: 自动生成序列号

```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    
    name = fields.Char(string='Order Reference', required=True, copy=False, default='New')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.order') or 'New'
        return super().create(vals_list)
```

### 8.2 案例2: 计算订单总额

```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    
    order_line = fields.One2many('sale.order.line', 'order_id')
    amount_total = fields.Monetary(
        string='Total',
        compute='_compute_amount_total',
        store=True
    )
    
    @api.depends('order_line.price_subtotal')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = sum(record.order_line.mapped('price_subtotal'))
```

### 8.3 案例3: 客户变化时自动填充地址

```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    
    partner_id = fields.Many2one('res.partner')
    partner_shipping_id = fields.Many2one('res.partner')
    partner_invoice_id = fields.Many2one('res.partner')
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.partner_shipping_id = self.partner_id
            self.partner_invoice_id = self.partner_id
            return {
                'domain': {
                    'partner_shipping_id': [('parent_id', '=', self.partner_id.id)],
                    'partner_invoice_id': [('parent_id', '=', self.partner_id.id)],
                }
            }
```

### 8.4 案例4: 折扣验证

```python
class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    
    discount = fields.Float(string='Discount (%)', default=0.0)
    
    @api.constrains('discount')
    def _check_discount(self):
        for record in self:
            if record.discount < 0 or record.discount > 100:
                raise ValidationError('折扣必须在 0-100 之间')
```

### 8.5 案例5: 综合示例

```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    
    name = fields.Char(default='New')
    partner_id = fields.Many2one('res.partner', required=True)
    date_order = fields.Datetime(default=fields.Datetime.now)
    order_line = fields.One2many('sale.order.line', 'order_id')
    amount_total = fields.Monetary(compute='_compute_amount_total', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('sale', 'Sale'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], default='draft')
    
    # 自动生成序列号
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.order')
        return super().create(vals_list)
    
    # 计算总额
    @api.depends('order_line.price_subtotal')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = sum(record.order_line.mapped('price_subtotal'))
    
    # 客户变化时自动填充
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.partner_shipping_id = self.partner_id
            self.partner_invoice_id = self.partner_id
    
    # 验证订单明细
    @api.constrains('state', 'order_line')
    def _check_order_lines(self):
        for record in self:
            if record.state == 'sale' and not record.order_line:
                raise ValidationError('确认的订单必须至少有一行明细')
```

---

## 9. 总结

### 9.1 装饰器对比

| 装饰器 | 触发时机 | 用途 | 性能 |
|--------|----------|------|------|
| `@api.model` | 手动调用 | 类方法 | 高 |
| `@api.model_create_multi` | 创建记录 | 批量创建 | 很高 |
| `@api.depends` | 依赖字段变化 | 计算字段 | 中 |
| `@api.onchange` | 界面字段变化 | 动态更新 | 低(仅界面) |
| `@api.constrains` | 保存记录 | 数据验证 | 中 |

### 9.2 最佳实践

1. ✅ 使用 `@api.model_create_multi` 优化创建
2. ✅ 计算字段使用 `store=True` 提高性能
3. ✅ 简单验证使用 SQL 约束
4. ✅ 复杂验证使用 Python 约束
5. ⚠️ `@api.onchange` 只在界面生效

---

**文档版本:** 1.0  
**最后更新:** 2025-12-21  
**作者:** Antigravity AI Assistant
