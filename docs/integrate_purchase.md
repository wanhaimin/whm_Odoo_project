# Odoo 原生模块（如采购）整合与一键安装指南

在 Odoo 中，将原生的功能模块（核心模型、视图、菜单等）无缝整合到您自行开发的系统（如模切管理系统 `diecut`）中是完全可行的。

**结论：能！只需通过声明模块依赖即可实现一键安装与深度整合。**

---

## 一、 实现机制：模块依赖 (Depends)

Odoo 的底层架构允许模块之间通过继承和依赖来融合。要整合原生模块，核心在于修改您的自定义模块的 `__manifest__.py` 配置文件。

### 1. 修改 `__manifest__.py` 文件

打开您现有的模切模块（例如 `diecut`）的 `__manifest__.py` 文件，在 `depends` 列表中加入原生的采购模块名 `'purchase'`：

```python
{
    'name': '模切管理系统',
    'version': '1.0',
    'category': 'Manufacturing',
    'summary': 'Die-cut Management System',
    # 在 depends 列表中添加 'purchase'
    'depends': [
        'base', 
        'sale_management', 
        'stock', 
        'purchase'  # <--- 声明依赖原生采购模块
    ], 
    'data': [
        # ... 您的各种 xml 视图文件及安全权限设置文件 ...
    ],
    'installable': True,
    'application': True,
}
```

### 2. “一键安装”效果说明

完成上述配置后，当您在一台全新的 Odoo 实例或新的数据库上，点击 **“安装您的模切管理系统”** 时：

1. Odoo 底层的依赖解析机制会自动分析 `depends` 列表。
2. 系统会发现您的模块依赖了 `purchase` 模块。
3. 系统会 **自动、一键式地先安装采购模块**（以及采购模块所依赖的所有其他底层关联模块）。
4. 最后再安装您的模切管理模块。

无需人工分别去安装对应的原生模块。

---

## 二、 深度业务整合与二次开发 (进阶)

一旦通过 `depends` 引入了原生模块，您就可以进行深度的业务整合与代码继承（遵循 Odoo 19 的开发规范）。

### 1. 数据模型融合 (Python 层面)
在您的 Python 模型中，可以通过 `_inherit` 直接向原生采购单增加自定义的中文字段（例如额外的模具参数、原材料属性等）：

```python
# models/purchase_order_inherit.py
from odoo import models, fields

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # 为原生采购单增加自定义的模切相关字段
    diecut_project_id = fields.Many2one('diecut.project', string="关联模切项目")
```

### 2. 视图融合 (XML 层面)
在您的 XML 视图中，可以通过 `xpath` 定位原生采购单的视图结构，将模切特定功能的按钮或者信息切入到系统的原生采购页面中。使用 `invisible` 等现代属性控制显示：

```xml
<!-- views/purchase_order_views_inherit.xml -->
<odoo>
    <record id="view_purchase_order_form_inherit_diecut" model="ir.ui.view">
        <field name="name">purchase.order.form.inherit.diecut</field>
        <field name="model">purchase.order</field>
        <field name="inherit_id" ref="purchase.purchase_order_form"/>
        <field name="arch" type="xml">
            <!-- 在原生采购单的 partner_id 字段之后插入自定义字段 -->
            <xpath expr="//field[@name='partner_id']" position="after">
                <field name="diecut_project_id"/>
            </xpath>
        </field>
    </record>
</odoo>
```

### 3. 菜单与动作融合

您可以在自己模切模块的顶部菜单（Top Menu）中，挂载一个指向原生 `purchase.order` 的菜单动作（Action）。这样，用户在具有完全中文环境配置的模切系统中操作时，也能无缝点击切入标准的采购流程。

在 Odoo 中，菜单（Menu）实际上只是指向“动作”（Action）的快捷方式。您完全可以通过在自己的 `diecut` 模块中写几行 XML 代码，将原生的“采购”功能无缝挂载到您的“模切管理系统”的菜单下。

这里最推荐的方法是：**在您的模切菜单体系下，新建一个菜单项，但是直接去调用原生采购模块的 Action（动作）。** 这样既不破坏原生采购模块自身的菜单结构，又能在您的系统中实现“统一入口”。

#### 具体实现方法 (XML 示例代码)

假设您的模切系统有一个主根菜单叫 `diecut_menu_root`。您的 XML 文件写法如下：

```xml
<!-- views/my_diecut_menu_views.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- 1. 定义模切管理的根菜单 (如果您之前已经定义了，忽略此行) -->
    <menuitem id="diecut_menu_root" 
              name="模切管理" 
              web_icon="diecut,static/description/icon.png"
              sequence="10"/>

    <!-- 2. 在模切根菜单下，创建一个“采购”分类节点 -->
    <menuitem id="diecut_menu_purchase_category" 
              name="采购管理" 
              parent="diecut_menu_root" 
              sequence="40"/>

    <!-- 3. 【核心步骤】将原生采购单挂载到您的菜单下 -->
    <!-- 注意这里的 action 属性，它直接调用了原生模块 purchase 里面的 action：purchase.purchase_form_action -->
    <menuitem id="diecut_menu_purchase_orders" 
              name="原生采购单" 
              parent="diecut_menu_purchase_category" 
              action="purchase.purchase_form_action" 
              sequence="10"/>
              
    <!-- 同样地，如果你想把原生供应商池也引入进来 -->
    <menuitem id="diecut_menu_suppliers" 
              name="供应商" 
              parent="diecut_menu_purchase_category" 
              action="account.res_partner_action_supplier" 
              sequence="20"/>
</odoo>
```

#### 这种方式的好处：
1. **用户体验极佳：** 用户不需要退出“模切系统”跑去“采购 App”里下单。点击您的菜单，直接呈现标准的 Odoo 采购列表和表单。
2. **完全解耦：** 我们只是引用了 `action="purchase.purchase_form_action"`，并没有修改原生的菜单结构。未来 Odoo 升级采购模块时，您的这部分代码也非常安全。
3. **权限一致：** 因为调用的是原生 Action，所以原生的所有采购读写权限、审批流都会自动沿用，不需要您额外再写一遍权限代码。

*需要注意的是：使用这种做法时，依然要在您模块的 `__manifest__.py` 文件的 `depends` 里包含 `'purchase'` 才能确保在安装时不会提示找不到该 Action。*
