# Odoo 关系字段实战指南 (Relations in Action)

光说不练假把式。我们来看看在代码里通过这三行代码，到底发生了什么神奇的化学反应。

## 场景假设
1.  **刀模 (diecut.mold)**: 我们正在写的这个模型。
2.  **设计师 (res.partner)**: 系统自带的联系人表（把它当爸爸）。
3.  **适用机器 (diecut.machine)**: 假设有一个机器表（把它当朋友）。

---

## 1. Many2one: 认个爹 (关联设计师)

**代码写法 (`mold.py`)**:
```python
# 我(刀模) 属于 那个设计师
designer_id = fields.Many2one(
    'res.partner',        # 1. 爹是谁？(目标模型名)
    string='设计师',       # 2. 叫什么名？
    domain="[('category_id', '=', 'Designer')]" # 3. (可选) 过滤一下，只显示职位是设计师的人
)
```

**界面效果**:
*   出现一个**下拉框**。
*   您可以点开它，搜索“张三”，选中他。
*   选完后，这就是一个蓝色的链接，点击能直接跳转到张三的详细资料页。

---

## 2. One2many: 看孩子 (设计师看他的作品)

**代码写法 (去 `res.partner` 模型里写)**:
*(注意：这个通常是写在目标模型里的，或者用继承的方式写)*
```python
# 我(设计师) 拥有 这些刀模作品
mold_ids = fields.One2many(
    'diecut.mold',        # 1. 孩子是谁？(目标模型名)
    'designer_id',        # 2. 孩子怎么称呼我？(必须对应上面的 Many2one 字段名)
    string='设计作品'
)
```

**界面效果**:
*   出现一个**表格 (List)**。
*   点开“张三”的详情页，下面列出了所有他设计的刀模。
*   您可以直接在这里点“添加行”，直接给张三分配一个新的刀模任务。

---

## 3. Many2many: 朋友圈 (适用机器)

**代码写法 (`mold.py`)**:
```python
# 我(刀模) 适用于 这些机器
machine_ids = fields.Many2many(
    'diecut.machine',     # 1. 朋友是谁？(目标模型名)
    string='适用机台'
)
```

**界面效果**:
*   出现一个**标签栏** (就像发邮件选收件人那样)。
*   您可以选：`[模切机A]`, `[分切机B]`。
*   选好后，它们像气泡一样排在这一行。

---

## 数据库背后的秘密 (给懂点技术的您)

1.  **Many2one**: Odoo 在 `diecut_mold` 表里加了一列 `designer_id` (存的是整数 123)。
2.  **One2many**: **数据库里根本没有这一列！** 它只是 Odoo 为了显示方便，临时用 SQL `SELECT * FROM diecut_mold WHERE designer_id = 我` 查出来的。
3.  **Many2many**: Odoo 会偷偷建立一张**第三者中间表** `diecut_mold_machine_rel`，里面只有两列：`mold_id` 和 `machine_id`，专门用来记录谁和谁好。

---

## 总结：怎么选？
*   **如果不确定**: 90% 的情况都是 **Many2one**。先连上再说。
*   **如果是清单**: 比如订单行、报价单行，用 **One2many**。
*   **如果是标签**: 比如多选属性，用 **Many2many**。
