---
type: resource
status: active
area: "XML"
topic: "XML从入门到精通 (The UI Masterclass).md"
reviewed: 2026-04-18
---

# Odoo XML 编程指南：从入门到精通 (The UI Masterclass)

如果说 Python 是 Odoo 的**大脑**（处理逻辑），那么 XML 就是它的**脸**（负责颜值和交互）。
很多新手觉得 XML 难，是因为把它当成了“代码”。其实，**Odoo 的 XML 本质上是在填表**。

---

## 一、 核心概念：一切皆记录 (Everything is a Record)

在 Python 里，您用 `create()` 往数据库存数据。
在 XML 里，您用 `<record>` 标签往数据库存数据。
**是的，视图、菜单、动作，在 Odoo 眼里，统统都是数据库里的一行数据！**

### 1. 万能公式
```xml
<record id="身份证号_不能重名" model="模型名">
    <field name="字段名">值</field>
    <field name="字段名">值</field>
</record>
```
*   `id`:  给这行数据起个这一生唯一的代号（External ID）。
*   `model`: 告诉 Odoo，这行数据存到哪张表里去（比如 `ir.ui.view`, `ir.actions.act_window`）。

---

## 二、 界面三剑客 (Action -> Menu -> View)

要显示一个功能，必须凑齐这三样东西。

### 1. 动作 (Action): “我要去哪里？”
告诉系统：点击后，打开哪个模型？用什么视图？
```xml
<record id="action_mold_list" model="ir.actions.act_window">
    <field name="name">打开刀模列表</field>
    <field name="res_model">diecut.mold</field> <!-- 只有这个必填 -->
    <field name="view_mode">list,form</field>
</record>
```

### 2. 菜单 (Menu): “入口在哪里？”
告诉系统：在左侧/顶部在这个位置放个按钮。
```xml
<!-- 顶级菜单 -->
<menuitem id="menu_root" name="工厂管理"/>

<!-- 子菜单 (parent 指向上面那个 id) -->
<menuitem id="menu_mold" name="刀模" parent="menu_root" action="action_mold_list"/>
```

### 3. 视图 (View): “长什么样？”
这是最复杂的部分。通常有 `list` (列表) 和 `form` (表单)。

#### A. 列表视图 (List/Tree) —— 简单
```xml
<record id="view_mold_list" model="ir.ui.view">
    <field name="name">diecut.mold.list</field>
    <field name="model">diecut.mold</field>
    <field name="arch" type="xml">
        <!-- decoration: 条件变色 -->
        <list decoration-danger="active==False">
            <field name="code" optional="show"/> <!-- optional: 允许用户隐藏此列 -->
            <field name="name"/>
            <field name="mold_type" widget="badge"/> <!-- widget: 像胶囊一样显示 -->
        </list>
    </field>
</record>
```

#### B. 表单视图 (Form) —— 布局的艺术
```xml
<form>
    <!-- 顶部状态栏 -->
    <header>
        <button name="action_print" string="打印标签" type="object" class="oe_highlight"/>
        <field name="status" widget="statusbar"/>
    </header>
    
    <sheet>
        <!-- 右上角智能按钮区 -->
        <div class="oe_button_box" name="button_box">
        </div>

        <!-- 标题大字 -->
        <div class="oe_title">
            <label for="name" class="oe_edit_only"/>
            <h1><field name="name"/></h1>
        </div>

        <!-- 分组排版 (左右两列) -->
        <group>
            <group>
                <field name="code"/>
                <field name="mold_type"/>
            </group>
            <group>
                <field name="design_by"/>
                <field name="active" widget="boolean_toggle"/>
            </group>
        </group>

        <!-- 选项卡 (Notebook) -->
        <notebook>
            <page string="详细描述">
                <field name="description"/>
            </page>
            <page string="历史记录">
                <field name="history_ids"/>
            </page>
        </notebook>
    </sheet>
</form>
```

#### C. 搜索视图 (Search) —— 决定右上角能搜什么
```xml
<search>
    <field name="name"/>
    <field name="code"/>
    
    <!-- 预设过滤器 -->
    <filter string="木板模" name="wood" domain="[('mold_type','=','wood')]"/>
    
    <!-- 分组 -->
    <group expand="0" string="Group By">
        <filter string="按类型" name="group_type" context="{'group_by': 'mold_type'}"/>
    </group>
</search>
```

---

## 三、 进阶：动态交互 (Ui Logic)

不用写 Python，直接在 XML 里也能搞很多逻辑！

### 1. 这个字段什么时候出现？ (invisible)
```xml
<!-- 只有当类型是 'other' 时，才显示 '备注' 字段 -->
<field name="note" invisible="mold_type != 'other'"/>
```

### 2. 这个字段什么时候必填？ (required)
```xml
<!-- 只有在新模具时，存放位置必填 -->
<field name="location" required="status == 'new'"/>
```

### 3. 这个字段什么时候只读？ (readonly)
```xml
<!-- 一旦保存了，编号就不能改了 (id 是保存后才有的) -->
<field name="code" readonly="id != False"/>
```

---

## 四、 终极奥义：继承与修改 (Inheritance/XPath)

这是 Odoo 最强的地方：**不改源码，就能修改别人的界面**。
比如您想在“销售订单”里加个“刀模”字段。

```xml
<record id="view_order_form_inherit" model="ir.ui.view">
    <field name="name">sale.order.form.inherit</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/> <!-- 爹是谁？ -->
    <field name="arch" type="xml">
        
        <!-- 找到 partner_id 字段，在它后面加一个字段 -->
        <xpath expr="//field[@name='partner_id']" position="after">
            <field name="mold_id"/>
        </xpath>

    </field>
</record>
```
*   `xpath`: 就像 GPS 定位一样，找到要改的位置。
*   `position`: `after` (后面), `before` (前面), `replace` (替换), `inside` (里面)。

---

## 总结
1.  XML 是用来**摆盘**的。
2.  `Action` 是遥控器，`Menu` 是按钮，`View` 是电视画面。
3.  善用 `<group>` 做布局。
4.  善用 `invisible` 做动态显隐。
5.  想改别人的界面，用 `XPath`。
