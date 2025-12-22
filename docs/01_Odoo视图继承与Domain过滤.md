# Odoo 视图继承与 Domain 过滤完整指南

## 📚 目录
1. [Odoo 视图继承机制](#1-odoo-视图继承机制)
2. [XPath 定位与修改](#2-xpath-定位与修改)
3. [Domain 过滤机制](#3-domain-过滤机制)
4. [Options 参数配置](#4-options-参数配置)
5. [res.partner 模型详解](#5-respartner-模型详解)
6. [实战案例](#6-实战案例)

---

## 1. Odoo 视图继承机制

### 1.1 什么是视图继承?

Odoo 使用**视图继承**机制,允许你在不修改原始代码的情况下扩展或修改现有视图。这是 Odoo 模块化设计的核心特性。

### 1.2 基本结构

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="唯一标识符" model="ir.ui.view">
        <field name="name">视图名称</field>
        <field name="model">模型名称</field>
        <field name="inherit_id" ref="父视图引用"/>
        <field name="arch" type="xml">
            <!-- 这里是修改内容 -->
        </field>
    </record>
</odoo>
```

### 1.3 关键字段说明

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `id` | 字符串 | 视图的唯一标识符 | `view_order_form_diecut_filter` |
| `name` | 字符串 | 视图的描述性名称 | `sale.order.form.diecut.filter` |
| `model` | 字符串 | 固定值 `ir.ui.view` | `ir.ui.view` |
| `inherit_id` | 引用 | 要继承的父视图 | `ref="sale.view_order_form"` |
| `arch` | XML | 视图架构定义 | `type="xml"` |

### 1.4 实际示例

```xml
<record id="view_order_form_diecut_filter" model="ir.ui.view">
    <field name="name">sale.order.form.diecut.filter</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='partner_id']" position="attributes">
            <attribute name="domain">[('is_company', '=', True), ('customer_rank', '>', 0)]</attribute>
            <attribute name="options">{'no_create': True, 'no_open': True}</attribute>
        </xpath>
    </field>
</record>
```

### 1.5 视图继承的优势

✅ **无需修改核心代码**: 保持原始模块完整性  
✅ **易于维护**: 模块化管理,可独立启用/禁用  
✅ **可升级性**: Odoo 升级时不会丢失自定义修改  
✅ **可重用性**: 可以在多个模块中使用相同的技术  
✅ **团队协作**: 不同开发者可以独立扩展同一视图  

---

## 2. XPath 定位与修改

### 2.1 什么是 XPath?

XPath (XML Path Language) 是一种在 XML 文档中定位元素的查询语言。Odoo 使用 XPath 来精确定位视图中需要修改的元素。

### 2.2 基本语法

```xml
<xpath expr="XPath表达式" position="位置">
    <!-- 要插入或修改的内容 -->
</xpath>
```

### 2.3 XPath 表达式详解

#### 2.3.1 基本选择器

| 表达式 | 含义 | 示例 |
|--------|------|------|
| `/` | 根节点 | `/form` |
| `//` | 任意位置 | `//field` |
| `.` | 当前节点 | `./field` |
| `..` | 父节点 | `../field` |
| `@` | 属性 | `@name` |

#### 2.3.2 属性选择器

```xml
<!-- 选择 name 属性等于 'partner_id' 的 field 元素 -->
<xpath expr="//field[@name='partner_id']" position="after">
    <field name="new_field"/>
</xpath>

<!-- 选择 string 属性包含 '客户' 的 field 元素 -->
<xpath expr="//field[contains(@string, '客户')]" position="before">
    <field name="customer_type"/>
</xpath>

<!-- 选择具有 required 属性的 field 元素 -->
<xpath expr="//field[@required]" position="attributes">
    <attribute name="required">0</attribute>
</xpath>
```

#### 2.3.3 层级选择器

```xml
<!-- 选择 form 下的 sheet 下的 group -->
<xpath expr="//form/sheet/group" position="inside">
    <field name="new_field"/>
</xpath>

<!-- 选择 notebook 下的第一个 page -->
<xpath expr="//notebook/page[1]" position="after">
    <page string="新页面">
        <field name="new_field"/>
    </page>
</xpath>
```

#### 2.3.4 复杂选择器

```xml
<!-- 选择 name='partner_id' 且 invisible='1' 的 field -->
<xpath expr="//field[@name='partner_id' and @invisible='1']" position="attributes">
    <attribute name="invisible">0</attribute>
</xpath>

<!-- 选择包含特定子元素的 group -->
<xpath expr="//group[field[@name='partner_id']]" position="after">
    <group>
        <field name="new_field"/>
    </group>
</xpath>
```

### 2.4 Position 参数详解

| Position | 作用 | 示例 |
|----------|------|------|
| `before` | 在元素**前面**插入 | 在字段前添加新字段 |
| `after` | 在元素**后面**插入 | 在字段后添加新字段 |
| `inside` | 在元素**内部**插入 | 在 group 内添加字段 |
| `replace` | **替换**整个元素 | 完全替换字段定义 |
| `attributes` | 修改元素的**属性** | 修改 domain、options 等 |

#### 2.4.1 Before 示例

```xml
<xpath expr="//field[@name='partner_id']" position="before">
    <field name="customer_type"/>
</xpath>
```

**效果:**
```xml
<!-- 原始 -->
<field name="partner_id"/>

<!-- 修改后 -->
<field name="customer_type"/>
<field name="partner_id"/>
```

#### 2.4.2 After 示例

```xml
<xpath expr="//field[@name='partner_id']" position="after">
    <field name="partner_phone"/>
</xpath>
```

**效果:**
```xml
<!-- 原始 -->
<field name="partner_id"/>

<!-- 修改后 -->
<field name="partner_id"/>
<field name="partner_phone"/>
```

#### 2.4.3 Inside 示例

```xml
<xpath expr="//group[@name='sale_info']" position="inside">
    <field name="custom_field"/>
</xpath>
```

**效果:**
```xml
<!-- 原始 -->
<group name="sale_info">
    <field name="date_order"/>
</group>

<!-- 修改后 -->
<group name="sale_info">
    <field name="date_order"/>
    <field name="custom_field"/>
</group>
```

#### 2.4.4 Replace 示例

```xml
<xpath expr="//field[@name='partner_id']" position="replace">
    <field name="partner_id" domain="[('customer_rank', '>', 0)]"/>
</xpath>
```

**效果:**
```xml
<!-- 原始 -->
<field name="partner_id"/>

<!-- 修改后 -->
<field name="partner_id" domain="[('customer_rank', '>', 0)]"/>
```

#### 2.4.5 Attributes 示例

```xml
<xpath expr="//field[@name='partner_id']" position="attributes">
    <attribute name="domain">[('customer_rank', '>', 0)]</attribute>
    <attribute name="required">1</attribute>
    <attribute name="options">{'no_create': True}</attribute>
</xpath>
```

**效果:**
```xml
<!-- 原始 -->
<field name="partner_id"/>

<!-- 修改后 -->
<field name="partner_id" 
       domain="[('customer_rank', '>', 0)]" 
       required="1" 
       options="{'no_create': True}"/>
```

### 2.5 常用 XPath 模式

#### 2.5.1 定位特定字段

```xml
<!-- 通过 name 定位 -->
<xpath expr="//field[@name='partner_id']" position="after">

<!-- 通过 string 定位 -->
<xpath expr="//field[@string='客户']" position="after">

<!-- 通过 widget 定位 -->
<xpath expr="//field[@widget='many2one']" position="attributes">
```

#### 2.5.2 定位按钮

```xml
<!-- 通过 name 定位按钮 -->
<xpath expr="//button[@name='action_confirm']" position="before">

<!-- 通过 string 定位按钮 -->
<xpath expr="//button[@string='确认']" position="attributes">
```

#### 2.5.3 定位页面/标签页

```xml
<!-- 定位 notebook 中的特定页面 -->
<xpath expr="//notebook/page[@string='其他信息']" position="after">
    <page string="自定义信息">
        <group>
            <field name="custom_field"/>
        </group>
    </page>
</xpath>
```

#### 2.5.4 定位 Group

```xml
<!-- 通过 name 定位 group -->
<xpath expr="//group[@name='sale_info']" position="inside">

<!-- 定位第一个 group -->
<xpath expr="//group[1]" position="after">
```

---

## 3. Domain 过滤机制

### 3.1 什么是 Domain?

Domain 是 Odoo 中用于过滤记录的表达式,类似于 SQL 的 WHERE 子句。它以 Python 列表的形式定义过滤条件。

### 3.2 基本语法

```python
[('字段名', '操作符', '值')]
```

### 3.3 操作符完整列表

#### 3.3.1 比较操作符

| 操作符 | 含义 | 示例 | SQL 等价 |
|--------|------|------|----------|
| `=` | 等于 | `('is_company', '=', True)` | `WHERE is_company = True` |
| `!=` | 不等于 | `('active', '!=', False)` | `WHERE active != False` |
| `>` | 大于 | `('customer_rank', '>', 0)` | `WHERE customer_rank > 0` |
| `<` | 小于 | `('age', '<', 18)` | `WHERE age < 18` |
| `>=` | 大于等于 | `('price', '>=', 100)` | `WHERE price >= 100` |
| `<=` | 小于等于 | `('stock', '<=', 10)` | `WHERE stock <= 10` |

#### 3.3.2 集合操作符

| 操作符 | 含义 | 示例 | SQL 等价 |
|--------|------|------|----------|
| `in` | 在列表中 | `('state', 'in', ['draft', 'sent'])` | `WHERE state IN ('draft', 'sent')` |
| `not in` | 不在列表中 | `('type', 'not in', ['invoice', 'delivery'])` | `WHERE type NOT IN ('invoice', 'delivery')` |

#### 3.3.3 字符串操作符

| 操作符 | 含义 | 示例 | SQL 等价 |
|--------|------|------|----------|
| `like` | 模糊匹配(区分大小写) | `('name', 'like', '%公司%')` | `WHERE name LIKE '%公司%'` |
| `ilike` | 模糊匹配(不区分大小写) | `('email', 'ilike', '%@gmail.com')` | `WHERE email ILIKE '%@gmail.com'` |
| `not like` | 不匹配 | `('name', 'not like', '%test%')` | `WHERE name NOT LIKE '%test%'` |
| `not ilike` | 不匹配(不区分大小写) | `('name', 'not ilike', '%test%')` | `WHERE name NOT ILIKE '%test%'` |
| `=like` | 精确模式匹配 | `('name', '=like', '公司%')` | `WHERE name LIKE '公司%'` |
| `=ilike` | 精确模式匹配(不区分大小写) | `('name', '=ilike', '公司%')` | `WHERE name ILIKE '公司%'` |

#### 3.3.4 特殊操作符

| 操作符 | 含义 | 示例 | 说明 |
|--------|------|------|------|
| `=?` | 等于或为空 | `('partner_id', '=?', value)` | 如果 value 为 None/False,则忽略此条件 |
| `child_of` | 子记录 | `('category_id', 'child_of', [1, 2])` | 包含子分类 |
| `parent_of` | 父记录 | `('category_id', 'parent_of', [1, 2])` | 包含父分类 |

### 3.4 逻辑运算符

#### 3.4.1 AND (默认)

多个条件默认是 AND 关系:

```python
[('is_company', '=', True), ('customer_rank', '>', 0)]
# 等价于: is_company = True AND customer_rank > 0
```

#### 3.4.2 OR

使用 `'|'` 前缀表示 OR:

```python
['|', ('is_company', '=', True), ('customer_rank', '>', 0)]
# 等价于: is_company = True OR customer_rank > 0
```

#### 3.4.3 NOT

使用 `'!'` 前缀表示 NOT:

```python
['!', ('active', '=', False)]
# 等价于: NOT (active = False)
# 即: active = True
```

#### 3.4.4 复杂组合

```python
# (A AND B) OR C
['|', '&', ('A', '=', True), ('B', '=', True), ('C', '=', True)]

# A AND (B OR C)
['&', ('A', '=', True), '|', ('B', '=', True), ('C', '=', True)]

# (A OR B) AND (C OR D)
['&', '|', ('A', '=', True), ('B', '=', True), '|', ('C', '=', True), ('D', '=', True)]
```

### 3.5 关联字段过滤

#### 3.5.1 Many2one 字段

```python
# 通过关联字段的 ID 过滤
[('partner_id', '=', 1)]

# 通过关联字段的字段过滤
[('partner_id.country_id.code', '=', 'CN')]
[('partner_id.name', 'ilike', '公司')]
```

#### 3.5.2 One2many/Many2many 字段

```python
# 至少有一个关联记录满足条件
[('order_line.product_id', '=', 1)]

# 没有关联记录
[('order_line', '=', False)]
```

### 3.6 实际应用示例

#### 3.6.1 只显示活跃的客户公司

```xml
<attribute name="domain">[('is_company', '=', True), ('customer_rank', '>', 0), ('active', '=', True)]</attribute>
```

#### 3.6.2 显示客户或供应商(任一即可)

```xml
<attribute name="domain">['|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0)]</attribute>
```

#### 3.6.3 只显示中国的客户

```xml
<attribute name="domain">[('is_company', '=', True), ('customer_rank', '>', 0), ('country_id.code', '=', 'CN')]</attribute>
```

#### 3.6.4 排除测试客户

```xml
<attribute name="domain">[('is_company', '=', True), ('customer_rank', '>', 0), ('name', 'not ilike', 'test')]</attribute>
```

#### 3.6.5 显示特定状态的订单

```xml
<attribute name="domain">[('state', 'in', ['sale', 'done'])]</attribute>
```

#### 3.6.6 显示本月创建的记录

```xml
<attribute name="domain">[('create_date', '>=', context_today().strftime('%Y-%m-01'))]</attribute>
```

---

## 4. Options 参数配置

### 4.1 什么是 Options?

Options 是一个 Python 字典,用于配置字段在界面上的行为和显示方式。

### 4.2 基本语法

```xml
<attribute name="options">{'key': value, 'key2': value2}</attribute>
```

### 4.3 常用 Options

#### 4.3.1 Many2one 字段 Options

| Option | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `no_create` | Boolean | 禁用"创建"选项 | `{'no_create': True}` |
| `no_open` | Boolean | 禁用"打开"选项 | `{'no_open': True}` |
| `no_quick_create` | Boolean | 禁用快速创建 | `{'no_quick_create': True}` |
| `no_create_edit` | Boolean | 禁用创建和编辑 | `{'no_create_edit': True}` |
| `create_name_field` | String | 指定创建时使用的字段 | `{'create_name_field': 'display_name'}` |

**示例:**
```xml
<field name="partner_id" options="{'no_create': True, 'no_open': True}"/>
```

#### 4.3.2 Many2many 字段 Options

| Option | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `no_create` | Boolean | 禁用创建 | `{'no_create': True}` |
| `create_text` | String | 自定义创建按钮文本 | `{'create_text': '添加标签'}` |
| `link` | Boolean | 显示为链接 | `{'link': True}` |

#### 4.3.3 Date/Datetime 字段 Options

| Option | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `datepicker` | Dict | 日期选择器配置 | `{'datepicker': {'minDate': '2020-01-01'}}` |

#### 4.3.4 Selection 字段 Options

| Option | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `horizontal` | Boolean | 水平显示单选按钮 | `{'horizontal': True}` |

#### 4.3.5 Monetary 字段 Options

| Option | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `currency_field` | String | 指定货币字段 | `{'currency_field': 'currency_id'}` |

### 4.4 组合使用示例

```xml
<!-- 客户字段: 禁用创建和打开 -->
<field name="partner_id" 
       domain="[('customer_rank', '>', 0)]"
       options="{'no_create': True, 'no_open': True}"/>

<!-- 标签字段: 自定义创建文本 -->
<field name="tag_ids" 
       widget="many2many_tags"
       options="{'no_create': False, 'create_text': '创建新标签'}"/>

<!-- 日期字段: 限制最小日期 -->
<field name="date_order" 
       options="{'datepicker': {'minDate': '2020-01-01'}}"/>
```

---

## 5. res.partner 模型详解

### 5.1 模型结构

`res.partner` 是 Odoo 中最重要的模型之一,用于存储所有联系人信息(客户、供应商、员工等)。

### 5.2 核心字段

#### 5.2.1 基本信息字段

| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| `name` | Char | 名称 | `'东莞市伟电子有限公司'` |
| `display_name` | Char | 显示名称(计算字段) | `'东莞市伟电子有限公司'` |
| `ref` | Char | 内部参考编号 | `'CUST001'` |
| `is_company` | Boolean | 是否为公司 | `True` / `False` |
| `company_type` | Selection | 公司类型 | `'company'` / `'person'` |
| `active` | Boolean | 是否活跃 | `True` / `False` |

#### 5.2.2 联系方式字段

| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| `email` | Char | 邮箱 | `'info@company.com'` |
| `phone` | Char | 电话 | `'0769-12345678'` |
| `mobile` | Char | 手机 | `'13800138000'` |
| `website` | Char | 网站 | `'www.company.com'` |

#### 5.2.3 地址字段

| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| `street` | Char | 街道地址1 | `'长安镇XX路123号'` |
| `street2` | Char | 街道地址2 | `'XX工业园'` |
| `city` | Char | 城市 | `'东莞'` |
| `state_id` | Many2one | 省/州 | `res.country.state` |
| `zip` | Char | 邮编 | `'523000'` |
| `country_id` | Many2one | 国家 | `res.country` |

#### 5.2.4 客户/供应商字段

| 字段名 | 类型 | 说明 | 工作原理 |
|--------|------|------|----------|
| `customer_rank` | Integer | 客户排名 | 每次作为客户使用时 +1 |
| `supplier_rank` | Integer | 供应商排名 | 每次作为供应商使用时 +1 |

**重要说明:**
- `customer_rank > 0`: 曾经或正在作为客户使用
- `supplier_rank > 0`: 曾经或正在作为供应商使用
- 两者可以同时 > 0,表示既是客户又是供应商

#### 5.2.5 地址类型字段

| 字段名 | 类型 | 说明 | 可选值 |
|--------|------|------|--------|
| `type` | Selection | 地址类型 | `'contact'`, `'invoice'`, `'delivery'`, `'other'`, `'private'` |

**类型说明:**
- `contact`: 主联系人/公司
- `invoice`: 发票地址
- `delivery`: 送货地址
- `other`: 其他地址
- `private`: 私人地址

#### 5.2.6 关联字段

| 字段名 | 类型 | 说明 | 关联模型 |
|--------|------|------|----------|
| `user_ids` | One2many | 关联的用户(员工) | `res.users` |
| `user_id` | Many2one | 销售员 | `res.users` |
| `parent_id` | Many2one | 父公司 | `res.partner` |
| `child_ids` | One2many | 子联系人 | `res.partner` |
| `category_id` | Many2many | 标签/分类 | `res.partner.category` |

### 5.3 customer_rank 的工作机制

#### 5.3.1 自动增加

当联系人在以下情况下被使用时,`customer_rank` 会自动增加:

```python
# 在销售订单中选择客户
sale_order.partner_id = partner
# Odoo 自动执行: partner.customer_rank += 1

# 在发票中选择客户
invoice.partner_id = partner
# Odoo 自动执行: partner.customer_rank += 1
```

#### 5.3.2 手动设置

```python
# 将联系人标记为客户
partner.customer_rank = 1

# 取消客户标记
partner.customer_rank = 0
```

#### 5.3.3 在 Domain 中使用

```python
# 只显示客户
[('customer_rank', '>', 0)]

# 只显示非客户
[('customer_rank', '=', 0)]

# 显示活跃客户
[('customer_rank', '>', 0), ('active', '=', True)]
```

### 5.4 常用过滤组合

#### 5.4.1 只显示客户公司

```python
[('is_company', '=', True), ('customer_rank', '>', 0)]
```

#### 5.4.2 只显示供应商公司

```python
[('is_company', '=', True), ('supplier_rank', '>', 0)]
```

#### 5.4.3 排除员工

```python
[('user_ids', '=', False)]
# 或
[('user_ids', '=', [])]
```

#### 5.4.4 只显示主联系人(排除子地址)

```python
[('type', '=', 'contact')]
```

#### 5.4.5 只显示中国客户

```python
[('is_company', '=', True), ('customer_rank', '>', 0), ('country_id.code', '=', 'CN')]
```

#### 5.4.6 只显示有邮箱的客户

```python
[('customer_rank', '>', 0), ('email', '!=', False)]
```

---

## 6. 实战案例

### 6.1 案例1: 限制销售订单客户选择

**需求:** 在销售订单中,客户字段只显示真正的客户公司,排除员工、供应商和子地址。

**实现:**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_order_form_customer_filter" model="ir.ui.view">
        <field name="name">sale.order.form.customer.filter</field>
        <field name="model">sale.order</field>
        <field name="inherit_id" ref="sale.view_order_form"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='partner_id']" position="attributes">
                <attribute name="domain">[('is_company', '=', True), ('customer_rank', '>', 0), ('type', '=', 'contact')]</attribute>
                <attribute name="options">{'no_create': True, 'no_open': True}</attribute>
            </xpath>
        </field>
    </record>
</odoo>
```

**效果:**
- ✅ 只显示公司类型
- ✅ 只显示曾作为客户使用过的
- ✅ 只显示主联系人(不显示发票地址、送货地址)
- ✅ 禁用快速创建和打开

---

### 6.2 案例2: 添加自定义字段到销售订单

**需求:** 在销售订单的"其他信息"标签页后添加一个新的标签页,包含自定义字段。

**实现:**

```xml
<record id="view_order_form_custom_tab" model="ir.ui.view">
    <field name="name">sale.order.form.custom.tab</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/>
    <field name="arch" type="xml">
        <xpath expr="//notebook/page[@name='other_information']" position="after">
            <page string="生产信息" name="production_info">
                <group>
                    <group>
                        <field name="production_date"/>
                        <field name="production_manager_id"/>
                    </group>
                    <group>
                        <field name="production_notes"/>
                    </group>
                </group>
            </page>
        </xpath>
    </field>
</record>
```

---

### 6.3 案例3: 修改字段为必填

**需求:** 将销售订单的"付款条件"字段设置为必填。

**实现:**

```xml
<record id="view_order_form_payment_required" model="ir.ui.view">
    <field name="name">sale.order.form.payment.required</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='payment_term_id']" position="attributes">
            <attribute name="required">1</attribute>
        </xpath>
    </field>
</record>
```

---

### 6.4 案例4: 隐藏特定字段

**需求:** 在销售订单中隐藏"销售团队"字段。

**实现:**

```xml
<record id="view_order_form_hide_team" model="ir.ui.view">
    <field name="name">sale.order.form.hide.team</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='team_id']" position="attributes">
            <attribute name="invisible">1</attribute>
        </xpath>
    </field>
</record>
```

---

### 6.5 案例5: 添加字段到列表视图

**需求:** 在销售订单列表视图中添加"客户参考"列。

**实现:**

```xml
<record id="view_order_tree_customer_ref" model="ir.ui.view">
    <field name="name">sale.order.tree.customer.ref</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_tree"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='partner_id']" position="after">
            <field name="client_order_ref"/>
        </xpath>
    </field>
</record>
```

---

### 6.6 案例6: 动态 Domain (基于上下文)

**需求:** 根据当前用户只显示其负责的客户。

**实现:**

```xml
<record id="view_order_form_user_customers" model="ir.ui.view">
    <field name="name">sale.order.form.user.customers</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='partner_id']" position="attributes">
            <attribute name="domain">[('user_id', '=', uid)]</attribute>
        </xpath>
    </field>
</record>
```

**说明:** `uid` 是当前登录用户的 ID

---

### 6.7 案例7: 替换整个字段

**需求:** 完全替换"客户"字段,使用自定义的 widget。

**实现:**

```xml
<record id="view_order_form_replace_partner" model="ir.ui.view">
    <field name="name">sale.order.form.replace.partner</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='partner_id']" position="replace">
            <field name="partner_id" 
                   widget="res_partner_many2one"
                   domain="[('customer_rank', '>', 0)]"
                   context="{'show_address': 1, 'show_email': 1}"
                   options="{'no_create': True, 'no_open': True}"/>
        </xpath>
    </field>
</record>
```

---

## 7. 最佳实践

### 7.1 命名规范

#### 7.1.1 视图 ID 命名

```
view_<模型名>_<视图类型>_<功能描述>
```

示例:
- `view_order_form_customer_filter`
- `view_partner_tree_customer_only`
- `view_product_form_hide_cost`

#### 7.1.2 视图 Name 命名

```
<模型名>.<视图类型>.<功能描述>
```

示例:
- `sale.order.form.customer.filter`
- `res.partner.tree.customer.only`
- `product.product.form.hide.cost`

### 7.2 XPath 最佳实践

✅ **使用 name 属性定位** (最稳定)
```xml
<xpath expr="//field[@name='partner_id']" position="after">
```

⚠️ **避免使用索引定位** (容易出错)
```xml
<!-- 不推荐 -->
<xpath expr="//field[3]" position="after">
```

✅ **使用具体的路径** (更精确)
```xml
<xpath expr="//form/sheet/group/field[@name='partner_id']" position="after">
```

### 7.3 Domain 最佳实践

✅ **使用字段而不是硬编码值**
```xml
<!-- 推荐 -->
<attribute name="domain">[('user_id', '=', uid)]</attribute>

<!-- 不推荐 -->
<attribute name="domain">[('user_id', '=', 1)]</attribute>
```

✅ **组合多个条件时保持可读性**
```python
# 推荐: 每个条件一行
[
    ('is_company', '=', True),
    ('customer_rank', '>', 0),
    ('active', '=', True)
]

# 不推荐: 全部在一行
[('is_company', '=', True), ('customer_rank', '>', 0), ('active', '=', True)]
```

### 7.4 模块化组织

将不同功能的视图继承放在不同的文件中:

```
views/
├── sale_order_customer_filter.xml
├── sale_order_custom_fields.xml
├── sale_order_hide_fields.xml
└── sale_order_tree_columns.xml
```

在 `__manifest__.py` 中按顺序加载:

```python
'data': [
    'views/sale_order_customer_filter.xml',
    'views/sale_order_custom_fields.xml',
    'views/sale_order_hide_fields.xml',
    'views/sale_order_tree_columns.xml',
],
```

---

## 8. 调试技巧

### 8.1 启用开发者模式

**方法1:** 通过 URL
```
http://localhost:8069/web?debug=1
```

**方法2:** 通过设置
```
设置 → 激活开发者模式
```

### 8.2 查看视图结构

在开发者模式下:
1. 打开任意表单
2. 点击右上角的 **🐞 调试** 图标
3. 选择 **编辑视图: 表单**
4. 可以看到完整的视图 XML 结构

### 8.3 测试 Domain

在 Python Shell 中测试:

```python
# 进入 Odoo Shell
python odoo/odoo-bin shell -c odoo.conf -d my_odoo_db

# 测试 domain
partners = env['res.partner'].search([('customer_rank', '>', 0)])
print(partners)
```

### 8.4 查看字段信息

在开发者模式下:
1. 打开表单
2. 点击字段
3. 右键 → **查看字段信息**
4. 可以看到字段的技术名称、类型、domain 等

---

## 9. 常见问题

### 9.1 XPath 找不到元素

**问题:** 视图继承不生效,没有报错

**原因:** XPath 表达式错误,找不到目标元素

**解决:**
1. 启用开发者模式
2. 查看原始视图结构
3. 确认字段名称、路径是否正确

### 9.2 Domain 不生效

**问题:** 设置了 domain 但过滤不生效

**原因:** 
- Domain 语法错误
- 字段名称错误
- 逻辑运算符使用错误

**解决:**
1. 在 Python Shell 中测试 domain
2. 检查字段是否存在
3. 检查逻辑运算符的位置

### 9.3 视图继承冲突

**问题:** 多个模块修改同一视图导致冲突

**原因:** 多个模块使用相同的 XPath 定位同一元素

**解决:**
1. 使用更具体的 XPath 表达式
2. 调整模块加载顺序
3. 使用 `priority` 字段控制视图优先级

```xml
<field name="priority">20</field>
```

### 9.4 升级后视图不更新

**问题:** 修改了视图但界面没有变化

**原因:** 
- 模块没有升级
- 浏览器缓存
- Odoo 缓存

**解决:**
```bash
# 升级模块
python odoo/odoo-bin -c odoo.conf -u module_name -d database_name --stop-after-init

# 清除浏览器缓存
Ctrl + Shift + R (强制刷新)

# 清除 Odoo 缓存
删除 __pycache__ 文件夹
```

---

## 10. 总结

### 10.1 核心要点

1. **视图继承** 是 Odoo 扩展的核心机制
2. **XPath** 用于精确定位要修改的元素
3. **Domain** 用于过滤记录,类似 SQL WHERE
4. **Options** 用于配置字段行为
5. **res.partner** 是最重要的基础模型之一

### 10.2 学习路径

1. ✅ 理解视图继承的基本概念
2. ✅ 掌握 XPath 的常用表达式
3. ✅ 熟练使用 Domain 过滤
4. ✅ 了解常用 Options 配置
5. ✅ 深入学习 res.partner 模型
6. 🔜 学习动态 Domain
7. 🔜 学习视图继承的优先级
8. 🔜 学习复杂的 XPath 表达式

### 10.3 参考资源

- [Odoo 官方文档](https://www.odoo.com/documentation/)
- [Odoo 开发者文档](https://www.odoo.com/documentation/master/developer.html)
- [XPath 教程](https://www.w3schools.com/xml/xpath_intro.asp)

---

**文档版本:** 1.0  
**最后更新:** 2025-12-21  
**作者:** Antigravity AI Assistant
