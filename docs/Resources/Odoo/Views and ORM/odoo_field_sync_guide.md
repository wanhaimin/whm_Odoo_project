---
type: resource
status: active
area: "Odoo"
topic: "Views and ORM"
reviewed: 2026-04-18
---

# Odoo 字段双向同步与数据联动指南

在 Odoo 开发中，经常需要实现“修改 A 字段自动更新 B 字段，反之亦然”的双向同步逻辑。本文总结了三种核心实现方式及其适用场景。

## 1. 核心机制对比

| 方式 | 英文术语 | 适用场景 | 典型例子 | 双向性 |
| :--- | :--- | :--- | :--- | :--- |
| **计算与反写** | `Compute` + `Inverse` | 字段之间有**逻辑换算**关系 (非直接存储) | 米 ↔ 毫米<br>单价 ↔ 总价 | ✅ 需要显式定义 `inverse` 函数 |
| **关联字段** | `Related` | 直接**引用**其他模型的字段 | 订单上的客户电话 ↔ 客户表里的电话 | ✅ 需设置 `readonly=False` |
| **变更事件** | `Onchange` | 两个**独立存储**的字段需要联动 | 选择产品 -> 自动填价格<br>改数量 -> 自动算折扣 | ⚠️ 仅 UI 层面，需小心死循环 |

---

## 2. 详细实现指南

### 2.1 方式一：Compute + Inverse (最推荐)
**场景**：字段 B 是通过字段 A 计算出来的（如单位换算、汇率折算），但希望用户能直接修改 B，并反向更新 A。

**代码示例**：
```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # 主数据（实际存储）
    length = fields.Float(string="长度 (m)")

    # 辅数据（计算得出）
    length_mm = fields.Float(
        string="长度 (mm)",
        compute='_compute_length_mm',
        inverse='_inverse_length_mm', # 关键：定义反写函数
        store=True,                   # 可选：是否持久化到数据库
        readonly=False                # 关键：允许用户在前台修改
    )

    @api.depends('length')
    def _compute_length_mm(self):
        for r in self:
            r.length_mm = (r.length or 0.0) * 1000.0

    def _inverse_length_mm(self):
        """用户修改 length_mm 时触发，反算 length"""
        for r in self:
            r.length = (r.length_mm or 0.0) / 1000.0
```

### 2.2 方式二：Related (最简单)
**场景**：直接“借用”另一个模型（Many2one）的字段。
**注意**：`related` 默认是只读的。如果设为 `readonly=False`，修改它会**直接更改源模型的数据**（危险操作，慎用）。

**代码示例**：
```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    main_vendor_id = fields.Many2one('res.partner', string="主供应商")

    # 直接引用供应商的电话
    vendor_phone = fields.Char(
        related='main_vendor_id.phone', 
        store=True,
        readonly=False  # ⚠️ 警告：在这里改电话，供应商通讯录里的电话也会变！
    )
```

### 2.3 方式三：Onchange (UI 交互)
**场景**：两个字段都是独立的存储字段，没有必然的计算公式，只是为了方便用户输入。
**特点**：逻辑只在前端触发，不保证数据库强一致性。

**代码示例**：
```python
    unit_price = fields.Float("单价")
    total_price = fields.Float("总价")

    @api.onchange('unit_price')
    def _on_price_change(self):
        if self.unit_price > 0:
            self.total_price = self.unit_price * 10  # 假设数量=10

    @api.onchange('total_price')
    def _on_total_change(self):
        if self.total_price > 0:
            self.unit_price = self.total_price / 10
```

---

## 3. 实战建议 (Best Practices)

1.  **优先使用 Compute + Inverse**：逻辑最清晰，数据一致性最好。Odoo 框架会自动处理依赖和触发顺序。
2.  **慎用 Related 的写操作**：
    *   ✅ 用于：在子单据中快速修改父单据的非关键信息（如备注）。
    *   ❌ 避免：在销售订单里修改产品的标准名称（这会导致历史订单与库存数据混乱）。
3.  **Onchange 的局限性**：Onchange 不会在 `create` 或 `write` 方法被后台调用时执行。如果通过代码导入数据，Onchange 逻辑会失效。因此，核心业务逻辑（如价格计算）应尽量写在 model 层（compute/create/write）而非仅靠 onchange。

---
*文档生成时间：2026-02-13*
