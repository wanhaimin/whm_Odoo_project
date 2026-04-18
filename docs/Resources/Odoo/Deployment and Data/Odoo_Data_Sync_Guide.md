---
type: resource
status: active
area: "Odoo"
topic: "Deployment and Data"
reviewed: 2026-04-18
---

# Odoo 数据一致性与双向同步机制指南 (Data Synchronization Guide)

本文档基于模切项目中的真实案例（原材料单价与供应商价格表的双向联动），总结了在 Odoo 中实现**数据强一致性**、**高性能**且**用户体验友好**的核心开发模式。

---

## 1. 核心设计哲学

在 ERP 系统中，**数据一致性 (Data Consistency)** 高于一切。
当一个业务数据（如“价格”）存在多种表现形式（按卷计价 vs 按平方计价）或存在于多个层级（产品主表 vs 供应商子表）时，必须构建一套机制，确保它们**永远指向同一个真理**，杜绝数据打架。

### 架构模型：“铁三角”同步
1.  **UI 前端 (Frontend)**：负责给用户“爽”的体验（即时跳变、自动计算）。
2.  **Model 后端 (Backend)**：负责数据的逻辑闭环（保存时强制约束）。
3.  **DB 数据库 (Storage)**：负责存储唯一的真理源头 (Single Source of Truth)。

---

## 2. 关键技术实现模式

### 模式 A：计算字段的反向更新 (`Inverse` 机制)
这是实现“既能自动计算，又能手动修改”的神器。

*   **场景**：主产品表上有一个“原材料单价”，但它其实是读取自背后某个“主供应商”的价格。我们希望用户改主表字段时，背后的供应商价格也变。
*   **代码结构**：
    ```python
    # 1. 定义字段
    raw_material_unit_price = fields.Monetary(
        compute='_compute_price',  # 读：怎么算出来
        inverse='_inverse_price',  # 写：改了以后怎么回写去源头
        store=True                 # 存：为了性能，存在数据库里
    )
    
    # 2. 读逻辑 (Compute)
    @api.depends('seller_ids.price')
    def _compute_price(self):
        for r in self:
            # 从子表取值显示
            r.raw_material_unit_price = r.main_seller_id.price
            
    # 3. 写逻辑 (Inverse) - 核心！
    def _inverse_price(self):
        for r in self:
            # 把值写回子表，实现双向绑定
            if r.main_seller_id:
                r.main_seller_id.price = r.raw_material_unit_price
    ```
*   **价值**：无论通过界面、Excel 导入还是代码 API 修改该字段，`inverse` 函数都会强制执行。这是**保障后端数据一致性**的最后一道防线。

### 模式 B：列表视图的即时联动 (`UI Onchange` 机制)
这是解决“列表编辑时，改了A列，B列不动”痛点的方案。

*   **痛点**：Odoo 的 `editablle="bottom"` 列表视图为了性能，默认不会因为你改了一个格就去重算整行，这会导致用户改了“平方价”，旁边的“卷价”还是旧的，必须点保存才变。
*   **解决方案**：显式添加 `@api.onchange` 装饰器。
    ```python
    @api.onchange('raw_material_price_m2')
    def _onchange_ui_feedback(self):
        # 纯 UI 逻辑，只在内存中跑，不存库
        # 作用：告诉前端 JS，还要把另外这一列也变一下
        if self.area > 0:
            self.raw_material_unit_price = self.raw_material_price_m2 * self.area
    ```
*   **价值**：提供类似 Excel 的丝滑体验，**保障前端视觉一致性**。

### 模式 C：影子缓存 (`Shadow Caching` 机制)
这是解决“未保存的数据怎么跨表传递”的高级技巧（此前解决 `AttributeError` 时用到）。

*   **场景**：用户改了主表的“长宽”，还没保存（数据库里是旧的），此时子表要去算价格，如果去查数据库就会算错。
*   **实现**：父表算好结果，直接塞给子表的一个临时字段（影子字段）。
*   **原则**：父表主动 Push（推送）永远比子表被动 Pull（拉取）更即时、更准确。

---

## 3. Odoo 开发知识点总结

### 1. `store=True` vs `store=False`
*   **store=False (默认)**：
    *   **计算型**：每次打开网页，CPU 都要现场算一遍。
    *   **缺点**：无法在这个字段上进行搜索、分组、排序。
*   **store=True (推荐)**：
    *   **存储型**：算好一次存进数据库。以后读它就和读普通字段一样快。
    *   **触发**：只有当 `@api.depends` 里的源字段变化时，才会触发重算。
    *   **优点**：**性能极高**，支持搜索分组，是企业级开发的首选。

### 2. `api.depends` vs `api.onchange`
| 特性         | api.depends                  | api.onchange                      |
| :----------- | :--------------------------- | :-------------------------------- |
| **触发时机** | 后端逻辑（计算字段）         | 前端动作（用户修改）              |
| **主要用途** | 只要相关数据变了，我就要重算 | 用户正在填表，我给他个反馈/默认值 |
| **持久化**   | 结果会存入数据库             | 结果仅在界面显示，需用户点保存    |
| **执行环境** | 系统自动执行                 | 仅用户交互时执行                  |

### 3. List View (Tree View) 的特殊性
*   在 Form 视图中，所有字段都在内存里，联动很容易。
*   在 List 视图中，Odoo 为了快，只加载当前显示的列。
*   **坑**：如果你在列表中想用 `onchange` 更新一个**隐藏列**的值，通常会失败。**原则：** 在列表中联动的字段，最好都使其 `optional="show"` 或显式存在于视图架构中。

### 4. 性能误区
*   **误解**：“逻辑写多了系统就慢。”
*   **真相**：
    *   Odoo 的性能瓶颈通常在 **IO（读写数据库）**，而不是 CPU 计算。
    *   像加减乘除这种逻辑，哪怕写一万行，CPU 也是眨眼跑完。
    *   真正慢的是 `for` 循环里查数据库（N+1查询）。
    *   **我们的优化**：通过 `store=True` 减少计算频率，通过 `inverse` 确保单点更新，这恰恰是**高性能**的写法。

---

此文档可作为后续开发复杂业务逻辑的参考蓝本。
