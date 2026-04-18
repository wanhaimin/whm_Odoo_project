---
type: resource
status: active
area: "Odoo"
topic: "Views and ORM"
reviewed: 2026-04-18
---

# Odoo 关系字段 (Relational Fields) 彻底指南

在 Odoo（以及所有ORM框架）中，定义两个模型之间的关系是最核心但也最容易混淆的部分。记住这个核心原则：
**Always look from the standpoint of "This Object" (永远站在“当前模型”的角度看对面)。**

---

## 1. 核心关系图解

| 关系类型 | 英文名称 | 符号表示 | 口诀/心法 | 典型示例 |
| :--- | :--- | :--- | :--- | :--- |
| **多对一** | **Many2one** | `M2O` | **“我指向它（单选）”**<br>我是众多小弟之一，指向唯一的大佬。 | 销售订单 -> 客户<br>产品 -> 类别 |
| **一对多** | **One2many** | `O2M` | **“它指向我（列表）”**<br>我是大佬，下面挂着一串清单。 | 客户 -> 多个订单<br>订单 -> 多个明细行 |
| **多对多** | **Many2many** | `M2M` | **“互相勾搭（多选）”**<br>海王对海王，大家随意连。 | 产品 <-> 标签<br>用户 <-> 群组 |

---

## 2. 详细解析

### 2.1 Many2one (多对一)
*   **场景**：你要在表单上加一个 **“下拉选择框”**。
*   **逻辑**：当前记录（此模型的某一行）只能这就必须属于/指向**一个**目标记录。
*   **数据库**：在当前表（`self`）中创建一个**外键列**（如 `partner_id`），存储目标记录的 ID。
*   **代码示例**：
    ```python
    # 在 sale.order 模型中
    # 站在订单角度：一个订单只能属于一个客户。
    partner_id = fields.Many2one('res.partner', string='客户')
    ```

### 2.2 One2many (一对多)
*   **场景**：你要在表单上加一个 **“明细行列表 (Table/List)”**。
*   **逻辑**：当前记录（此模型）是“主”，目标模型里有很多条记录是属于我的。
*   **关键约束**：**One2many 必须依赖于对面存在一个 Many2one。**
    *   因为数据库里通过外键关联，必须要在对方表里有一个字段指向我，我才能把它们抓取出来展示。
*   **数据库**：当前表里**没有任何字段**。这只是一个视图层的虚字段。
*   **代码示例**：
    ```python
    # 在 res.partner 模型中
    # 站在客户角度：我可以拥有很多个订单。
    # comodel_name='sale.order': 对方模型名
    # inverse_name='partner_id': 对方模型里指向我的那个字段名 (必须存在!)
    order_ids = fields.One2many('sale.order', 'partner_id', string='销售订单')
    ```

### 2.3 Many2many (多对多)
*   **场景**：你要在表单上加一个 **“标签栏 (Tags)”** 或者 **“多选列表”**。
*   **逻辑**：两边都是平等的。
*   **数据库**：Odoo 会自动创建一张 **第三张中间表**（如 `product_tag_rel`），记录 `product_id` 和 `tag_id` 的配对关系。
*   **代码示例**：
    ```python
    # 在 product.template 模型中
    tag_ids = fields.Many2many('product.tag', string='标签')
    ```

---

## 3. 常见误区与实战判断

### Q1: 我该用 M2O 还是 O2M？
*   **看“拥有权”归谁**：
    *   如果数据是 **“存”** 在对方那里的（比如订单行存在 `sale.order.line` 表里），你在主单（`sale.order`）想看，就用 **One2many**。
    *   如果数据是 **“选”** 过来的（比如客户存在 `res.partner` 表里，你只是引用一下），你在主单想选，就用 **Many2one**。

### Q2: Inverse Name 是什么？
*   定义 `One2many` 时必填的第二个参数。它告诉 Odoo：**“去对面那个模型找，哪个字段是存我的 ID 的？”**
*   如果没有这个反向字段，Odoo 就找不到哪些记录属于你了。

### Q3: 级联删除 (ondelete)
*   定义 `Many2one` 时常用 `ondelete='cascade'`。
*   **含义**：如果那边的大佬（Target）被删了，这边的小弟（Source）怎么办？
    *   `'set null'`: 默认值。大佬没了，我就变成“无主孤魂”（字段置空）。
    *   `'cascade'`: 大佬没了，我也跟着自杀（级联删除行）。常用于 `order_line`。

---
*文档生成时间：2026-02-13*
