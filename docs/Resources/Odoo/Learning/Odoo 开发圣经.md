---
type: resource
status: active
area: "Odoo"
topic: "Learning"
reviewed: 2026-04-18
---

# Odoo 开发圣经 (The Odoo Development Encyclopedia)

> 版本：适应 Odoo 16/17+
> 目标：提供从入门到精通的“百科全书式”参考指南。

---

# 目录 (Table of Contents)

1.  **第一章：架构与核心概念 (Architecture & Core)**
2.  **第二章：模型与字段 (Models & Fields)**
3.  **第三章：ORM 方法论 (ORM Methods)**
4.  **第四章：视图与界面 (Views & UI)**
5.  **第五章：动作与菜单 (Actions & Menus)**
6.  **第六章：权限与安全 (Security)**
7.  **第七章：QWeb 报表 (Reporting)**
8.  **第八章：Web 开发与控制器 (Controllers)**
9.  **第九章：常用调试与技巧 (Tips & Debugging)**

---

# 第一章：架构与核心概念

## 1.1 模块结构详解
任何 Odoo 功能都必须封装在模块（Addons）中。
*   `__manifest__.py`: 模块的身份证。
    *   `depends`: 决定了模块加载顺序（非常重要，继承谁就要依赖谁）。
    *   `data`: 需要加载到数据库的 XML/CSV 文件列表（按顺序加载）。
    *   `demo`: 仅在演示模式下加载的数据。
    *   `assets`: 定义 JS/CSS 静态资源包。

## 1.2 Odoo MVC 架构
*   **Model**: Python 类 (`models/`)，映射数据库表。
*   **View**: XML 文件 (`views/`)，定义前端页面布局。
*   **Controller**: Python 类 (`controllers/`)，处理 HTTP 请求（用于网站或 API）。

---

# 第二章：模型与字段 (Models & Fields)

## 2.1 模型类型
```python
# 1. 常规模型 (存在数据库中)
class RegularModel(models.Model):
    _name = 'my.model'

# 2. 瞬态模型 (临时数据，定期自动清理，常用于向导 Wizard)
class WizardModel(models.TransientModel):
    _name = 'my.wizard'

# 3. 抽象模型 (不存表，仅供继承使用，如 mail.thread)
class AbstractModel(models.AbstractModel):
    _name = 'my.mixin'
```

## 2.2 字段属性大全 (Field Attributes)
所有字段通用的参数：
*   `string="名称"`: 界面显示的标签。
*   `required=True`: 数据库级必填（不能为空）。
*   `readonly=True`: 界面完全只读（代码中可写）。
*   `index=True`: **性能优化**，在数据库创建索引。
*   `default=...`: 默认值（可以是值，也可以是函数引用）。
*   `help="..."`: 鼠标悬停时的提示文本。
*   `copy=False`: 复制记录时，该字段不被复制（如“单号”）。
*   `translate=True`: 开启多语言翻译支持（仅 Text/Char）。
*   `tracking=True`: 开启修改日志记录（需要继承 `mail.thread`）。

## 2.3 特殊字段类型
*   `fields.Binary()`: 存储文件/图片（Base64编码）。
*   `fields.Monetary()`: 货币字段（必须配合 `currency_id` 字段使用）。
*   `fields.Html()`: 富文本编辑器字段。
*   `fields.Reference()`: 动态关联（可以关联到任意模型，类似“多态”）。

## 2.4 SQL 约束 (SQL Constraints)
**最强的数据完整性保障**，直接作用于数据库层面。
```python
_sql_constraints = [
    # (约束名, SQL规则, 报错信息)
    ('name_unique', 'UNIQUE(name)', '名称必须唯一！'),
    ('age_check', 'CHECK(age > 0)', '年龄必须大于0！'),
]
```

---

# 第三章：ORM 方法论 (ORM Methods)

## 3.1 核心 CRUD
*   `model.create(vals_list)`: 批量创建，返回记录集。
    *   `vals_list`: `[{'name': 'A'}, {'name': 'B'}]`
*   `record.write(vals)`: 修改记录。
    *   注意：会触发 `@api.onchange` 和 `@api.constrains`。
*   `record.unlink()`: 删除记录。
    *   注意：如果有关联数据的 `ondelete='restrict'` 可能会报错。

## 3.2 搜索 (Search)
*   `search(domain, offset=0, limit=None, order=None)`: 返回记录集。
*   `search_count(domain)`: 只返回数量（性能更快）。
*   `read_group(domain, fields, groupby)`: **聚合查询**，用于统计报表（类似 SQL GROUP BY）。

## 3.3 环境 (Environment) - `self.env`
Odoo 的上下文核心。
*   `self.env.cr`: 数据库游标，可执行 `self.env.cr.execute("SELECT * FROM ...")`。
*   `self.env.user`: 当前用户对象。
*   `self.env.company`: 当前公司。
*   `self.env.context`: 上下文字典（只读，如需修改请用 `with_context`）。

```python
# 切换用户上下文 (Sudo)
records = self.env['my.model'].sudo().search(...)

# 切换上下文参数
records = self.env['my.model'].with_context(active_test=False).search(...)
```

---

# 第四章：视图与界面 (Views & UI)

## 4.1 Form 视图高级元素
*   `notebook` / `page`: 选项卡布局。
*   `group`: 表单列布局（默认两列）。
*   `separator`: 分割线。
*   `div class="oe_button_box"`: 智能按钮区域。
*   `widget`:
    *   `statusbar`: 状态条。
    *   `many2one_avatar`: 显示用户头像。
    *   `radio`: 单选按钮。
    *   `priority`: 星级评分。

## 4.2 Tree (List) 视图特性
*   `editable="top/bottom"`: 允许直接在列表里编辑，不打开弹窗。
*   `decoration-danger="state=='cancel'"`: 条件标红。
*   `decoration-info="state=='draft'"`: 条件标蓝。
*   `default_order="create_date desc"`: 默认排序。

## 4.3 Search 视图 (过滤器)
```xml
<search>
    <field name="name"/> <!-- 只有定义了 field 才能搜 -->
    <filter string="我的任务" name="my_tasks" domain="[('user_id','=',uid)]"/>
    <group string="分组">
        <filter string="按客户" name="group_by_partner" context="{'group_by':'partner_id'}"/>
    </group>
</search>
```

---

# 第五章：动作与菜单 (Actions & Menus)

## 5.1 窗口动作 (ir.actions.act_window)
决定打开哪个模型，显示什么视图。
*   `res_model`: 目标模型。
*   `view_mode`: 视图类型顺 (tree,form,kanban)。
*   `context`: 传递默认值。
*   `domain`: 默认筛选。
*   `limit`: 每页条数。

## 5.2 服务器动作 (ir.actions.server)
点击菜单直接运行一段 Python 代码。
```xml
<record id="action_sync_stock" model="ir.actions.server">
    <field name="model_id" ref="model_product_product"/>
    <field name="state">code</field>
    <field name="code">
        # 可直接写 Python 代码
        records.action_update_quantity()
    </field>
</record>
```

## 5.3 计划任务 (Scheduled Actions / Cron)
定时执行的任务。
*   `interval_number` / `interval_type`: 执行频率 (如 1 Days)。
*   `numbercall`: 执行多少次后停止 (-1 为无限)。
*   `doall`: 如果服务器宕机错过了时间，重启后是否补做。

---

# 第六章：权限与安全 (Security)

## 6.1 用户组 (Groups)
XML 定义：
```xml
<record id="group_manager" model="res.groups">
    <field name="name">Manager</field>
    <field name="category_id" ref="base.module_category_my_app"/>
    <field name="implied_ids" eval="[(4, ref('group_user'))]"/> <!-- 继承普通用户权限 -->
</record>
```

## 6.2 三层权限体系
1.  **菜单级**: 菜单没权限，用户根本看不到入口。
2.  **模型级 (CSV)**: 看到了入口，但没权限读写数据（报错 Access Error）。
3.  **记录级 (Record Rules)**: 有权限读写，但只能操作**自己的**数据。

---

# 第七章：QWeb 报表 (Reporting)

## 7.1 原理
Odoo 报表 = HTML 模板 + WKHTMLTOPDF (转换器)。

## 7.2 模板语法 (QWeb)
类似 Vue/React 的模板语言。
*   `t-foreach="docs" t-as="o"`: 循环。
*   `t-if="o.amount > 100"`: 判断。
*   `t-field="o.date" t-options='{"widget": "date"}'`: 格式化输出。
*   `t-esc`: 输出原始文本（会转义 HTML）。
*   `t-out`: 输出 HTML（不转义）。

---

# 第八章：高级开发技巧 (Pro Tips)

## 8.1 覆盖 (Inheritance) 的三种模式
1.  **类继承 (`_inherit = 'model'`)**:
    *   直接修改原模型（添加字段、修改方法）。
    *   **最常用**。
2.  **原型继承 (`_inherit = 'model'`, `_name = 'new.model'`)**:
    *   复制原模型的所有字段和逻辑，创建一个新表。
3.  **委托继承 (`_inherits = {'res.partner': 'partner_id'}`)**:
    *   多表关联，看似在操作主表，实际字段存在父表中（很少用，慎用）。

## 8.2 性能优化建议
*   **避免在循环中 search/create/write**:
    ❌ 错误：`for x in ids: model.create(...)`
    ✅ 正确：`vals_list = [...]; model.create(vals_list)`
*   **计算字段性能**:
    一定要给 `depends` 加全，否则不触发更新。
    如果计算字段不需要搜索，尽量不要加 `store=True`，否则拖慢写库速度。
*   **SQL 优化**: 使用 `read_group` 代替 Python 循环统计。

## 8.3 调试工具
*   **Odoo Shell**: 命令行交互工具 `python odoo-bin shell -d mydb`。
*   **Web Debug 模式**:
    *   **Open View**: 查看当前视图的源码 ID。
    *   **Edit Action**: 查看当前动作的参数。

---

(本文档持续更新，涵盖了 Odoo 开发 95% 的核心知识点)
