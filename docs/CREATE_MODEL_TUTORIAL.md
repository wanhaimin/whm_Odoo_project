# Odoo 手把手教程：如何创建一个新模型 (刀模管理)

您完全可以自己动手！这是掌握 Odoo 开发最直接的方式。
为了配合您的模切业务，我们将一起创建一个简单的 **“刀模 (Mold)”** 模型，用来管理工厂里的刀模工具。

---

## 准备工作
请确保您的 VS Code 已经打开了 `diecut_custom` 目录。
我们将在这个现有的模块里添加新功能。

---

## 第一步：定义数据结构 (Python)
**目标**：告诉数据库我们需要一张新表，表里有哪些列。

1.  在 `diecut_custom/models/` 文件夹下，新建一个文件 `mold.py`。
2.  **动手写代码** (请复制或手敲以下内容):

```python
from odoo import models, fields

class DiecutMold(models.Model):
    _name = 'diecut.mold'        # 1. 数据库表名 (会自动变成 diecut_mold)
    _description = '刀模数据库'    # 2. 描述
    _rec_name = 'code'           # 3. 搜索或关联时，默认显示模具编号

    # --- 字段定义 ---
    name = fields.Char(string='刀模名称', required=True)
    code = fields.Char(string='模具编号', required=True, help="例如: M-2023-001")
    mold_type = fields.Selection([
        ('wood', '木板模'),
        ('etch', '蚀刻模'),
        ('engrave', '雕刻模')
    ], string='模具类型', default='wood')
    
    location = fields.Char(string='存放位置', help="例如: A-01-03")
    active = fields.Boolean(string='有效', default=True) # 自带归档功能
```

3.  **注册文件**:
    打开 `diecut_custom/models/__init__.py`，在里面加一行：
    ```python
    from . import mold
    ```
    *解释: 如果不加这行，Odoo 根本不知道你写了 `mold.py` 这个文件。*

---

## 第二步：设置访问权限 (Security)
**目标**：告诉 Odoo 谁有权读写这张表。如果不写这个，菜单出来了也点不进去（会报权限错误）。

1.  打开 `diecut_custom/security/ir.model.access.csv` 文件。
2.  在文件最末尾，**追加**一行：

```csv
access_diecut_mold,Diecut Mold Access,model_diecut_mold,base.group_user,1,1,1,1
```

*   `model_diecut_mold`: 对应我们刚才定义的 `_name = 'diecut.mold'` (把点换成下划线，前面加 model_)。
*   `1,1,1,1`: 代表 读、写、创建、删除 权限全部开放。

---

## 第三步：设计界面 (XML)
**目标**：定义菜单、列表长什么样、表单长什么样。

1.  在 `diecut_custom/views/` 文件夹下，新建一个文件 `mold_views.xml`。
2.  **动手写代码**:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- 1. 定义动作 (Action): 点击菜单后发生什么 -->
    <record id="action_diecut_mold" model="ir.actions.act_window">
        <field name="name">刀模管理</field>
        <field name="res_model">diecut.mold</field>
        <field name="view_mode">tree,form</field>
    </record>

    <!-- 2. 定义列表视图 (Tree) -->
    <record id="view_diecut_mold_tree" model="ir.ui.view">
        <field name="name">diecut.mold.tree</field>
        <field name="model">diecut.mold</field>
        <field name="arch" type="xml">
            <tree>
                <field name="code"/>
                <field name="name"/>
                <field name="mold_type"/>
                <field name="location"/>
            </tree>
        </field>
    </record>

    <!-- 3. 定义表单视图 (Form) -->
    <record id="view_diecut_mold_form" model="ir.ui.view">
        <field name="name">diecut.mold.form</field>
        <field name="model">diecut.mold</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <div class="oe_title">
                        <h1><field name="code" placeholder="模具编号..."/></h1>
                    </div>
                    <group>
                        <group>
                            <field name="name"/>
                            <field name="mold_type"/>
                        </group>
                        <group>
                            <field name="location"/>
                            <field name="active" widget="boolean_toggle"/>
                        </group>
                    </group>
                </sheet>
            </form>
        </field>
    </record>

    <!-- 4. 定义菜单 (Menu) -->
    <!-- 一级菜单 -->
    <menuitem id="menu_diecut_root" name="模切管理" web_icon="diecut_custom,static/description/icon.png"/>
    
    <!-- 二级菜单 (配置) -->
    <menuitem id="menu_diecut_config" name="配置" parent="menu_diecut_root" sequence="100"/>

    <!-- 三级菜单 (刀模) -->
    <menuitem id="menu_diecut_mold_act" 
              name="刀模库" 
              parent="menu_diecut_config" 
              action="action_diecut_mold"
              sequence="10"/>
</odoo>
```

---

## 第四步：注册视图文件 (Manifest)
**目标**：告诉 Odoo 加载这个 XML 文件。

1.  打开 `diecut_custom/__manifest__.py`。
2.  找到 `'data': [...]` 列表。
3.  把新文件加进去（**注意逗号**）：

```python
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/mold_views.xml',  # <--- 把这一行加进去！
    ],
```

---

## 第五步：重启与升级
这是最激动人心的一步！

1.  **重启服务**: 在终端里按 `Ctrl+C` 停止，然后再次运行 `./Start_Odoo.bat`。
2.  **升级模块**:
    *   打开浏览器 -> 应用 (Apps)。
    *   搜索 `diecut`。
    *   点击 **升级 (Upgrade)** 按钮。
3.  **验证**:
    *   刷新页面。
    *   您应该能看到一个新的主菜单 **“模切管理”**。
    *   点进去，打开 **“配置 -> 刀模库”**。
    *   试着新建一个刀模看看！

---

## 总结
这就是 Odoo 开发的 **"五步法"**:
1.  **Model**: 造数据表 (`.py`)
2.  **Init**: 注册 Python 文件 (`__init__.py`)
3.  **Security**: 给权限 (`.csv`)
4.  **View**: 画界面 (`.xml`)
5.  **Manifest**: 注册 XML 文件 (`__manifest__.py`)

恭喜您，迈出了成为 Odoo 独立开发者的第一步！
