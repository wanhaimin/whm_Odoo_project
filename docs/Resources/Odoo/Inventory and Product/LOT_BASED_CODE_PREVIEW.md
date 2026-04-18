---
type: resource
status: active
area: "Odoo"
topic: "Inventory and Product"
reviewed: 2026-04-18
---

# 模切行业：批次维度管理功能代码预览

这份文档包含了实现“卷材批次管理”核心逻辑所需的 Python 和 XML 代码。
> **注意**: 这仅为代码预览，尚未应用到您的系统中。

---

## 1. Python 模型代码 (`models/stock_lot.py`)

这里通过继承 Odoo 原生的 `stock.lot` (批次/序列号) 模型，添加了长、宽、面积三个关键字段。

```python
from odoo import models, fields, api

class StockLot(models.Model):
    _inherit = 'stock.lot'

    # 定义模切行业的特殊属性
    x_diecut_width = fields.Float(string='宽度 (mm)', default=0.0, help="卷材的实际宽度")
    x_diecut_length = fields.Float(string='长度 (m)', default=0.0, help="卷材的剩余长度")
    
    # 计算字段：面积 (平方米)
    # 面积 = 宽度(mm)/1000 * 长度(m)
    x_diecut_area = fields.Float(
        string='折算面积 (m²)', 
        compute='_compute_area', 
        store=True, 
        help="根据长宽自动计算的面积"
    )

    @api.depends('x_diecut_width', 'x_diecut_length')
    def _compute_area(self):
        for record in self:
            # 简单的防错：只有长宽都大于0才计算
            if record.x_diecut_width > 0 and record.x_diecut_length > 0:
                record.x_diecut_area = (record.x_diecut_width / 1000.0) * record.x_diecut_length
            else:
                record.x_diecut_area = 0.0

    # 可选：显示名称优化
    # 让批次号直接显示规格，例如: "LOT001 (5mm x 50m)"
    def name_get(self):
        result = []
        for record in self:
            name = record.name
            if record.x_diecut_width > 0:
                name = f"{name} ({record.x_diecut_width}mm x {record.x_diecut_length}m)"
            result.append((record.id, name))
        return result
```

---

## 2. XML 视图代码 (`views/stock_lot_view.xml`)

这段代码的作用是修改库存批次的表单页面，把我们刚才定义的字段显示出来，方便仓库员录入。

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- 继承并修改原生批次表单 -->
    <record id="view_production_lot_form_inherit_diecut" model="ir.ui.view">
        <field name="name">stock.lot.form.inherit.diecut</field>
        <field name="model">stock.lot</field>
        <field name="inherit_id" ref="stock.view_production_lot_form"/>
        <field name="arch" type="xml">
            
            <!-- 在"产品"字段后面，插入我们的规格信息 -->
            <xpath expr="//field[@name='product_id']" position="after">
                <label for="x_diecut_width" string="卷材规格"/>
                <div class="o_row">
                    <field name="x_diecut_width" class="oe_inline"/>
                    <span> mm  x  </span>
                    <field name="x_diecut_length" class="oe_inline"/>
                    <span> m </span>
                </div>
                
                <!-- 显示自动计算的面积 -->
                <field name="x_diecut_area" decoration-bf="1"/>
            </xpath>

            <!-- 在搜索栏增加"按宽度搜索"的功能 -->
            <!-- 比如：想找所有宽度为 5mm 的库存 -->
            <xpath expr="//search" position="inside">
                <field name="x_diecut_width" string="宽度"/>
                <filter string="宽度 > 100mm (母卷)" name="big_roll" domain="[('x_diecut_width', '>=', 100)]"/>
            </xpath>

        </field>
    </record>
</odoo>
```

---

## 3. 代码解析

### 核心亮点
1.  **自动计算面积 (`_compute_area`)**:
    *   仓库员只需要拿尺子量一下宽度、看一下米数，系统自动算出 `3.5 平方米`。这解决了财务账（按平方算）和实物账（按卷算）对不上的千古难题。

2.  **名称重写 (`name_get`)**:
    *   这一步非常贴心。以后在**领料单**、**出库单**上，选中这个批次时，它会自动带上规格尾巴。
    *   **以前显示**: `LOT2023001` (根本不知道多大)
    *   **代码生效后显示**: `LOT2023001 (10mm x 500m)` (一目了然)

3.  **视图布局 (`div class="o_row"`)**:
    *   我们在 XML 里用了 `o_row` 样式，让宽度和长度显示在同一行，中间用 `x` 连接，看起来就像 `10 mm x 50 m`，符合工人的阅读习惯。

---

如果您觉得这个逻辑符合您的预期，我们可以随时把这几段代码“注入”到您的 `diecut_custom` 模块中，重启生效。
