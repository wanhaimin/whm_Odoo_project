---
type: resource
status: active
area: "Odoo"
topic: "Core"
reviewed: 2026-04-18
---

# Odoo 全栈开发终极指南 (Ultimate Odoo Developer Cheat Sheet)

这份文档涵盖了 Odoo 开发的方方面面，从基础模型到高级视图，从权限控制到网页控制器。

---

## 1. 模块结构 (Module Structure)
一个标准的 Odoo 模块目录结构：
```text
my_module/
├── __init__.py          # 引导文件
├── __manifest__.py      # 模块配置文件 (核心)
├── models/              # Python 数据库模型
│   ├── __init__.py
│   └── my_model.py
├── views/               # XML 界面视图
│   └── my_view.xml
├── security/            # 权限控制
│   └── ir.model.access.csv
├── data/                # 预制数据 (如序列号)
│   └── data.xml
└── static/              # 静态文件 (CSS/JS/图片)
    └── description/
        └── icon.png
```

---

## 2. Python 模型开发 (Models)

### 模型定义
```python
from odoo import models, fields, api

class MyModel(models.Model):
    _name = 'my.app.task'        # 数据库表名 (my_app_task)
    _description = '任务管理'
    _inherit = ['mail.thread']   # 继承消息机制(聊天窗)
    _order = 'date_deadline desc, id' # 默认排序
    _rec_name = 'subject'        # 在其他地方引用时显示的字段(默认是name)

    # --- 基础字段 ---
    name = fields.Char('编号', required=True, copy=False, default='New')
    subject = fields.Char('主题', help="任务的简短描述")
    description = fields.Html('详细描述')
    active = fields.Boolean('有效', default=True) # 归档机制
    priority = fields.Selection([
        ('0', '低'),
        ('1', '中'),
        ('2', '高')
    ], string='优先级', default='1', tracking=True) # tracking=True 开启变更日志

    # --- 关系字段 ---
    # Many2one: 多对一 (比如: 任务属于哪个项目)
    project_id = fields.Many2one('my.app.project', string='所属项目', ondelete='cascade')
    
    # One2many: 一对多 (比如: 项目包含哪些任务)
    # 必须在对面模型('my.app.project') 里有一个 Many2one 指回这里
    task_ids = fields.One2many('my.app.task', 'project_id', string='子任务')

    # Many2many: 多对多 (比如: 标签)
    tag_ids = fields.Many2many('res.partner.category', string='标签')
```

### 高级特性
*   **计算字段 (Computed)**:
    ```python
    amount_total = fields.Float(compute='_compute_amount', store=True) # store=True 存入数据库以便搜索
    
    @api.depends('line_ids.price_subtotal')
    def _compute_amount(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('price_subtotal'))
    ```
*   **关联字段 (Related)**:
    直接读取关联记录的字段，类似 Excel 的 VLOOKUP。
    ```python
    # 自动获取 partner_id 里的 email
    email = fields.Char(related='partner_id.email', readonly=True)
    ```

---

## 3. XML 视图开发 (Views)

### 常用视图类型
1.  **Tree (列表视图)**: 显示多条记录。
2.  **Form (表单视图)**: 编辑单条记录详情。
3.  **Search (搜索视图)**: 定义右上角的搜索框和过滤器。
4.  **Kanban (看板视图)**: 卡片式拖拽布局。

### Form 视图骨架
```xml
<record id="view_task_form" model="ir.ui.view">
    <field name="name">my.task.form</field>
    <field name="model">my.app.task</field>
    <field name="arch" type="xml">
        <form>
            <!-- 头部状态栏 (包含按钮和状态流转) -->
            <header>
                <button name="action_done" string="完成" type="object" class="oe_highlight" invisible="state == 'done'"/>
                <button name="%(action_report_pdf)d" string="打印PDF" type="action"/>
                <field name="state" widget="statusbar" statusbar_visible="draft,process,done"/>
            </header>
            <sheet>
                <!-- 右上角智能按钮 (Smart Button) -->
                <div class="oe_button_box" name="button_box">
                    <button name="action_view_subtasks" type="object" class="oe_stat_button" icon="fa-tasks">
                        <field name="subtask_count" widget="statinfo" string="子任务"/>
                    </button>
                </div>

                <!-- 大标题 -->
                <div class="oe_title">
                    <h1><field name="name" readonly="1"/></h1>
                </div>

                <!-- 分组表单 -->
                <group>
                    <group>
                        <field name="subject"/>
                        <field name="project_id" options="{'no_create': True}"/> 
                    </group>
                    <group>
                        <field name="date_deadline"/>
                        <field name="user_id" widget="many2one_avatar_user"/>
                    </group>
                </group>

                <!-- 选项卡 (Notebook) -->
                <notebook>
                    <page string="描述">
                        <field name="description"/>
                    </page>
                    <page string="其它信息">
                        <group>
                            <field name="company_id" groups="base.group_multi_company"/>
                        </group>
                    </page>
                </notebook>
            </sheet>
            <!-- 底部聊天窗 (如果你inherit了mail.thread) -->
            <div class="oe_chatter">
                <field name="message_follower_ids"/>
                <field name="message_ids"/>
            </div>
        </form>
    </field>
</record>
```

### 继承与修改 (XPath)
**核心思想**：不修改源码，而是通过“打补丁”的方式修改现有视图。
```xml
<record id="view_partner_form_inherit" model="ir.ui.view">
    <field name="inherit_id" ref="base.view_partner_form"/> <!-- 这是你要改的父视图ID -->
    <field name="model">res.partner</field>
    <field name="arch" type="xml">
        <!-- 在 'wat' 字段后面添加一个新字段 -->
        <xpath expr="//field[@name='vat']" position="after">
            <field name="x_my_custom_field"/>
        </xpath>
        
        <!-- 替换掉原来的某个 Group -->
        <xpath expr="//group[@name='sale']" position="attributes">
            <attribute name="invisible">1</attribute> <!-- 隐藏它 -->
        </xpath>
    </field>
</record>
```

---

## 4. 权限控制 (Security)

### ACL (访问控制列表)
文件：`security/ir.model.access.csv`
控制 **"谁"** 可以对 **"哪个模型"** 进行 **"读/写/创建/删除"**。
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_my_task_user,My Task User,model_my_app_task,base.group_user,1,1,1,0
access_my_task_mgr,My Task Manager,model_my_app_task,base.group_system,1,1,1,1
```
*   `1`: 允许, `0`: 禁止
*   如果不写这一行，默认谁都看不了新模型。

### Record Rules (记录规则)
控制 **"只能看到自已的数据"**。
```xml
<record id="rule_see_own_tasks" model="ir.rule">
    <field name="name">Only see own tasks</field>
    <field name="model_id" ref="model_my_app_task"/>
    <field name="domain_force">[('user_id', '=', user.id)]</field>
    <field name="groups" eval="[(4, ref('base.group_user'))]"/>
</record>
```

---

## 5. 常用 ORM 环境 (Environment)
在代码中 `self.env` 是万能钥匙。

*   `self.env.user`: 当前登录用户 (Record对象)
*   `self.env.company`: 当前公司
*   `self.env.context`: 当前上下文 (字典)
*   `self.env.cr`: 数据库游标 (用于执行原生 SQL)
*   `self.env.ref('xml_id')`: 获取 XML ID 对应的记录
    *   `self.env.ref('base.main_company')`

---

## 6. HTTP 控制器 (Controllers)
如果你要开发 API 给外部调用，或者开发网站页面。
```python
from odoo import http
from odoo.http import request

class MyController(http.Controller):
    
    # 网页路由 (返回 HTML)
    @http.route('/my/tasks', type='http', auth='user', website=True)
    def list_tasks(self, **kw):
        tasks = request.env['my.app.task'].search([])
        return request.render('my_module.task_list_template', {'tasks': tasks})

    # JSON API (返回 JSON数据)
    @http.route('/api/create_task', type='json', auth='public', methods=['POST'])
    def create_task_api(self, subject):
        new_task = request.env['my.app.task'].sudo().create({'subject': subject})
        return {'id': new_task.id, 'status': 'success'}
```

---

## 7. 常用快捷小技巧
*   **调试模式**: 在 URL 后加 `?debug=1` (开启调试模式) 或 `?debug=assets` (调试 JS/CSS)。
*   **超级管理员**: `sudo()`，例如 `self.env['res.partner'].sudo().create(...)`，绕过权限规则。
*   **获取当前时间**: `fields.Datetime.now()`。
*   **抛出错误**:
    ```python
    from odoo.exceptions import UserError, ValidationError
    raise UserError("操作不允许！")
    ```
