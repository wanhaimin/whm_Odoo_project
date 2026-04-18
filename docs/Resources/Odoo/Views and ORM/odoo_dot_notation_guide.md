---
type: resource
status: active
area: "Odoo"
topic: "Views and ORM"
reviewed: 2026-04-18
---

# Odoo 开发核心：深入理解点语法 (Dot Notation)

Odoo 的 ORM（对象关系映射）框架最强大的特性之一就是其“点语法”。它允许开发者像操作普通 Python 对象一样操作数据库记录，无需编写复杂的 SQL 语句。

本文档结合你的 `diecut` 模块代码，详细解析点语法的核心机制、常用场景及最佳实践。

---

## 1. 核心概念：RecordSet (记录集)

在 Odoo 代码中，`self` 或查询返回的对象通常不是单一的一行数据，而是一个 **RecordSet（记录集）**。
*   It behaves like a list: 可以遍历，可以切片。
*   It behaves like an object: 如果记录集里只有**一条**记录，可以直接用点号访问字段。

---

## 2. 基础场景：像访问属性一样读取数据

这是最直接的用法。Odoo 会自动将数据库列映射为 Python 属性。

```python
# 假设 record 是一个 diecut.quote 的实例
print(record.name)           # 输出: "Q20260211001"
print(record.product_name)   # 输出: "绝缘片"
print(record.quote_date)     # 输出: datetime.date(2026, 2, 11)
```

**底层原理**：当你访问 `record.name` 时，Odoo 的 ORM 才会去数据库查询该字段的值（惰性加载），并缓存到内存中。后续再次访问不仅快，而且不会产生额外的 SQL 查询。

---

## 3. 进阶场景：关系字段“穿透” (Traversing Relations)

这是点语法最迷人的地方。通过 `Many2one` 字段，你可以直接获取关联表的字段，甚至可以无限级联。

### 示例 1：获取客户信息
在你的 `diecut.quote` 中，`customer_id` 是关联到 `res.partner` 表的字段。

```python
# 无需查 res.partner 表，直接点过去
customer_name = record.customer_id.name   # 获取客户名称
customer_phone = record.customer_id.phone # 获取客户电话

# 如果客户有关联的销售员 (user_id)，还可以继续点
salesperson_email = record.customer_id.user_id.email 
```

### 示例 2：在 Wizard 中填充默认值
在你的 `diecut_quote.py` 的 `DiecutQuoteWizard` 中：

```python
# 这里直接通过 quote 对象穿透获取了关联客户的 ID
res['customer_id'] = quote.customer_id.id 
```

**注意**：
*   如果是读取值用于显示或逻辑判断，直接用 `record.field`。
*   如果是赋值给 `Many2one` 字段，通常需要赋值 ID (整数)。但 Odoo 的 `write/create` 方法往往也智能支持直接赋值记录集对象。

---

## 4. 高级场景：集合操作 (One2many & Many2many)

当字段是 `One2many` (如 `material_line_ids`) 时，点号访问拿到的是一个包含多条记录的 RecordSet。Odoo 提供了强大的工具方法来处理它们。

### 4.1. 批量提取 (.mapped)
这是处理子表数据最高效的方法。

**你的代码案例 (第 82 行)**：
```python
# 计算所有材料行的单位成本之和
record.total_material_cost = sum(record.material_line_ids.mapped('unit_consumable_cost'))
```

*   **传统写法 (不推荐)**：
    ```python
    total = 0
    for line in record.material_line_ids:
        total += line.unit_consumable_cost
    ```
*   **Mapped 写法 (推荐)**：
    `mapped` 会自动遍历所有行，取值，并返回一个列表。代码更简洁，底层通常有优化。

### 4.2. 跨表批量提取
`.mapped` 也支持穿透！
```python
# 获取报价单中所有材料对应的产品名称列表
# material_line_ids -> material_id (Product) -> name
product_names = record.material_line_ids.mapped('material_id.name')
# 结果: ['3M 467', 'PET 0.1mm', '铜箔']
```

### 4.3. 过滤 (.filtered)
如果你指向处理特定条件的子记录：

```python
# 只要 "良率 > 95%" 的行
high_yield_lines = record.material_line_ids.filtered(lambda l: l.yield_rate > 0.95)

# 或者用字符串表达式 (更简洁)
high_yield_lines = record.material_line_ids.filtered('yield_rate > 0.95')
```

---

## 5. 动态赋值：Compute 与 Onchange

在 Odoo 的 `compute` (计算字段) 和 `onchange` (由 UI 触发的变化) 方法中，点语法用于**修改内存中的数据**。

### 你的代码案例 (第 154 行)
```python
# 在 onchange 方法中
if line.slitting_width == 0.0:
    # 将当前行的分切宽，设置为第一行的分切宽
    line.slitting_width = first_line.slitting_width
```

**重要区别**：
*   **在 `compute` / `onchange` 中**：直接用 `record.field = value`。Odoo 会自动感知变化并在稍后处理保存（如果是 store=True）或仅更新 UI。
*   **在普通业务方法 (如 Button Action) 中**：
    *   虽然 `record.field = value` 也能工作（通过 `__setattr__` 调用 `write`），但性能略低，且可能触发多次重算。
    *   推荐用 `record.write({'field': value})` 来显式写入数据库。

---

## 6. 常见陷阱：Singleton Error (单例错误)

这是新手最常遇到的报错：`ValueError: Expected singleton: diecut.quote(1, 2)`。

### 原因
当你试图对一个包含**多条记录**的 RecordSet 使用点语法访问字段时，Odoo 无法确定你到底想要哪一条记录的值。

```python
# 假设 self 包含 id 为 1 和 2 的两条报价单
print(self.name) # 报错！因为 self 不是单例
```

### 解决方法
1.  **遍历 (最常用)**：
    ```python
    for record in self:
        print(record.name) # 安全，record 肯定是单例
    ```
2.  **强制单例 (确保逻辑正确时使用)**：
    ```python
    self.ensure_one() # 如果 self 不止一条，直接抛错；如果是 1 条，返回自身
    print(self.name)
    ```

---

## 7. 总结：Diecut 模块中的点语法全景

回到你的 `diecut_quote.py`，看看这一行代码包含了多少知识点：

```python
line.raw_length = (line.material_id.length or 0.0) * 1000.0
```

1.  **`line`**: 这是一个 `diecut.quote.material.line` 的单例对象。
2.  **`.material_id`**: 这是一个 `Many2one` 穿透，跳到了 `product.product` 模型。
3.  **`.length`**: 读取产品表上的 `length` 字段。
4.  **`line.raw_length = ...`**: 通过赋值操作，触发 Odoo 的缓存更新，最终将写入数据库。

掌握点语法，就掌握了 Odoo 开发 80% 的逻辑编写能力。它让代码读起来像伪代码一样自然，极大地提高了开发效率。
