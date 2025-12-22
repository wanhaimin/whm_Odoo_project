# XPath 高级用法详解

## 📚 目录
1. [XPath 基础回顾](#1-xpath-基础回顾)
2. [高级选择器](#2-高级选择器)
3. [XPath 轴](#3-xpath-轴)
4. [XPath 函数](#4-xpath-函数)
5. [复杂定位策略](#5-复杂定位策略)
6. [实战案例](#6-实战案例)
7. [性能优化](#7-性能优化)
8. [调试技巧](#8-调试技巧)

---

## 1. XPath 基础回顾

### 1.1 什么是 XPath?

XPath (XML Path Language) 是一种在 XML 文档中查找信息的语言。在 Odoo 中,XPath 用于定位视图中的元素以进行修改。

### 1.2 基本语法

```xml
<xpath expr="XPath表达式" position="位置">
    <!-- 要插入或修改的内容 -->
</xpath>
```

### 1.3 基本选择器

| 表达式 | 含义 | 示例 |
|--------|------|------|
| `nodename` | 选择所有名为 nodename 的节点 | `field` |
| `/` | 从根节点选择 | `/form` |
| `//` | 从任意位置选择 | `//field` |
| `.` | 当前节点 | `.` |
| `..` | 父节点 | `..` |
| `@` | 属性 | `@name` |

---

## 2. 高级选择器

### 2.1 属性选择器

#### 2.1.1 精确匹配

```xml
<!-- 选择 name 属性等于 'partner_id' 的 field -->
<xpath expr="//field[@name='partner_id']" position="after">
    <field name="new_field"/>
</xpath>
```

#### 2.1.2 包含匹配

```xml
<!-- 选择 string 属性包含 '客户' 的 field -->
<xpath expr="//field[contains(@string, '客户')]" position="before">
    <field name="customer_type"/>
</xpath>

<!-- 选择 name 属性以 'partner' 开头的 field -->
<xpath expr="//field[starts-with(@name, 'partner')]" position="attributes">
    <attribute name="required">1</attribute>
</xpath>
```

#### 2.1.3 多属性匹配

```xml
<!-- 选择同时满足多个属性条件的元素 -->
<xpath expr="//field[@name='partner_id' and @invisible='1']" position="attributes">
    <attribute name="invisible">0</attribute>
</xpath>

<!-- 使用 OR 条件 -->
<xpath expr="//field[@name='partner_id' or @name='customer_id']" position="after">
    <field name="new_field"/>
</xpath>
```

#### 2.1.4 属性存在性检查

```xml
<!-- 选择具有 required 属性的所有 field -->
<xpath expr="//field[@required]" position="attributes">
    <attribute name="required">0</attribute>
</xpath>

<!-- 选择没有 invisible 属性的 field -->
<xpath expr="//field[not(@invisible)]" position="attributes">
    <attribute name="invisible">1</attribute>
</xpath>
```

### 2.2 位置选择器

#### 2.2.1 索引选择

```xml
<!-- 选择第一个 field -->
<xpath expr="//field[1]" position="after">
    <field name="new_field"/>
</xpath>

<!-- 选择最后一个 field -->
<xpath expr="//field[last()]" position="after">
    <field name="new_field"/>
</xpath>

<!-- 选择倒数第二个 field -->
<xpath expr="//field[last()-1]" position="after">
    <field name="new_field"/>
</xpath>

<!-- 选择前三个 field -->
<xpath expr="//field[position() <= 3]" position="attributes">
    <attribute name="readonly">1</attribute>
</xpath>
```

#### 2.2.2 相对位置

```xml
<!-- 选择 partner_id 字段后的第一个 field -->
<xpath expr="//field[@name='partner_id']/following-sibling::field[1]" position="replace">
    <field name="replacement_field"/>
</xpath>

<!-- 选择 partner_id 字段前的所有 field -->
<xpath expr="//field[@name='partner_id']/preceding-sibling::field" position="attributes">
    <attribute name="readonly">1</attribute>
</xpath>
```

### 2.3 层级选择器

#### 2.3.1 子元素选择

```xml
<!-- 选择 form 的直接子元素 sheet -->
<xpath expr="/form/sheet" position="inside">
    <group>
        <field name="new_field"/>
    </group>
</xpath>

<!-- 选择 group 下的所有 field (任意深度) -->
<xpath expr="//group//field" position="attributes">
    <attribute name="readonly">1</attribute>
</xpath>

<!-- 选择 group 的直接子 field (不包括孙子) -->
<xpath expr="//group/field" position="attributes">
    <attribute name="readonly">1</attribute>
</xpath>
```

#### 2.3.2 父元素选择

```xml
<!-- 选择包含 partner_id 字段的 group -->
<xpath expr="//field[@name='partner_id']/.." position="after">
    <group>
        <field name="new_field"/>
    </group>
</xpath>

<!-- 选择包含 partner_id 字段的 group,并在其内部添加字段 -->
<xpath expr="//field[@name='partner_id']/../.." position="inside">
    <field name="new_field"/>
</xpath>
```

### 2.4 条件选择器

#### 2.4.1 子元素条件

```xml
<!-- 选择包含 partner_id 字段的 group -->
<xpath expr="//group[field[@name='partner_id']]" position="after">
    <group>
        <field name="new_field"/>
    </group>
</xpath>

<!-- 选择至少包含 2 个 field 的 group -->
<xpath expr="//group[count(field) >= 2]" position="inside">
    <field name="new_field"/>
</xpath>

<!-- 选择不包含任何 field 的 group -->
<xpath expr="//group[not(field)]" position="inside">
    <field name="new_field"/>
</xpath>
```

#### 2.4.2 文本内容条件

```xml
<!-- 选择 string 属性包含 '客户' 的 label -->
<xpath expr="//label[contains(@string, '客户')]" position="replace">
    <label string="客户信息"/>
</xpath>

<!-- 选择文本内容为 '保存' 的 button -->
<xpath expr="//button[text()='保存']" position="attributes">
    <attribute name="string">确认保存</attribute>
</xpath>
```

---

## 3. XPath 轴

XPath 轴定义了相对于当前节点的节点集。

### 3.1 轴的概念

轴是一种选择节点的方向,从当前节点出发,沿着某个方向选择节点。

### 3.2 常用轴

| 轴名称 | 说明 | 示例 |
|--------|------|------|
| `self` | 当前节点 | `self::field` |
| `child` | 子节点 | `child::field` |
| `parent` | 父节点 | `parent::group` |
| `ancestor` | 所有祖先节点 | `ancestor::form` |
| `descendant` | 所有后代节点 | `descendant::field` |
| `following` | 当前节点之后的所有节点 | `following::field` |
| `preceding` | 当前节点之前的所有节点 | `preceding::field` |
| `following-sibling` | 当前节点之后的兄弟节点 | `following-sibling::field` |
| `preceding-sibling` | 当前节点之前的兄弟节点 | `preceding-sibling::field` |
| `attribute` | 属性节点 | `attribute::name` |

### 3.3 轴的使用

#### 3.3.1 Self 轴

```xml
<!-- 选择当前 field 节点本身 -->
<xpath expr="//field[@name='partner_id']/self::field" position="attributes">
    <attribute name="required">1</attribute>
</xpath>
```

#### 3.3.2 Child 轴

```xml
<!-- 选择 group 的所有子 field (等价于 group/field) -->
<xpath expr="//group/child::field" position="attributes">
    <attribute name="readonly">1</attribute>
</xpath>
```

#### 3.3.3 Parent 轴

```xml
<!-- 选择 partner_id 字段的父 group -->
<xpath expr="//field[@name='partner_id']/parent::group" position="after">
    <group>
        <field name="new_field"/>
    </group>
</xpath>
```

#### 3.3.4 Ancestor 轴

```xml
<!-- 选择 partner_id 字段的所有祖先 form 节点 -->
<xpath expr="//field[@name='partner_id']/ancestor::form" position="attributes">
    <attribute name="string">修改后的表单</attribute>
</xpath>

<!-- 选择 partner_id 字段的第一个 group 祖先 -->
<xpath expr="//field[@name='partner_id']/ancestor::group[1]" position="after">
    <group>
        <field name="new_field"/>
    </group>
</xpath>
```

#### 3.3.5 Following-sibling 轴

```xml
<!-- 选择 partner_id 字段后的第一个兄弟 field -->
<xpath expr="//field[@name='partner_id']/following-sibling::field[1]" position="replace">
    <field name="replacement_field"/>
</xpath>

<!-- 选择 partner_id 字段后的所有兄弟 field -->
<xpath expr="//field[@name='partner_id']/following-sibling::field" position="attributes">
    <attribute name="readonly">1</attribute>
</xpath>
```

#### 3.3.6 Preceding-sibling 轴

```xml
<!-- 选择 partner_id 字段前的第一个兄弟 field -->
<xpath expr="//field[@name='partner_id']/preceding-sibling::field[1]" position="attributes">
    <attribute name="readonly">1</attribute>
</xpath>

<!-- 选择 partner_id 字段前的所有兄弟 field -->
<xpath expr="//field[@name='partner_id']/preceding-sibling::field" position="attributes">
    <attribute name="readonly">1</attribute>
</xpath>
```

---

## 4. XPath 函数

### 4.1 字符串函数

#### 4.1.1 contains()

```xml
<!-- 选择 string 属性包含 '客户' 的 field -->
<xpath expr="//field[contains(@string, '客户')]" position="after">
    <field name="new_field"/>
</xpath>

<!-- 选择 name 属性包含 'partner' 或 'customer' 的 field -->
<xpath expr="//field[contains(@name, 'partner') or contains(@name, 'customer')]" position="attributes">
    <attribute name="required">1</attribute>
</xpath>
```

#### 4.1.2 starts-with()

```xml
<!-- 选择 name 属性以 'partner' 开头的 field -->
<xpath expr="//field[starts-with(@name, 'partner')]" position="attributes">
    <attribute name="readonly">1</attribute>
</xpath>

<!-- 选择 string 属性以 '客户' 开头的 field -->
<xpath expr="//field[starts-with(@string, '客户')]" position="after">
    <field name="new_field"/>
</xpath>
```

#### 4.1.3 string-length()

```xml
<!-- 选择 name 属性长度大于 10 的 field -->
<xpath expr="//field[string-length(@name) > 10]" position="attributes">
    <attribute name="invisible">1</attribute>
</xpath>
```

#### 4.1.4 concat()

```xml
<!-- 动态生成属性值 -->
<xpath expr="//field[@name='partner_id']" position="attributes">
    <attribute name="string" eval="concat('客户', ' - ', '必填')"/>
</xpath>
```

### 4.2 数值函数

#### 4.2.1 count()

```xml
<!-- 选择包含超过 3 个 field 的 group -->
<xpath expr="//group[count(field) > 3]" position="inside">
    <separator string="更多字段"/>
</xpath>

<!-- 选择没有 field 的 group -->
<xpath expr="//group[count(field) = 0]" position="inside">
    <field name="new_field"/>
</xpath>
```

#### 4.2.2 position()

```xml
<!-- 选择前 3 个 field -->
<xpath expr="//field[position() <= 3]" position="attributes">
    <attribute name="readonly">1</attribute>
</xpath>

<!-- 选择偶数位置的 field -->
<xpath expr="//field[position() mod 2 = 0]" position="attributes">
    <attribute name="invisible">1</attribute>
</xpath>
```

#### 4.2.3 last()

```xml
<!-- 选择最后一个 field -->
<xpath expr="//field[last()]" position="after">
    <field name="new_field"/>
</xpath>

<!-- 选择倒数第二个 field -->
<xpath expr="//field[last()-1]" position="after">
    <field name="new_field"/>
</xpath>
```

### 4.3 布尔函数

#### 4.3.1 not()

```xml
<!-- 选择没有 invisible 属性的 field -->
<xpath expr="//field[not(@invisible)]" position="attributes">
    <attribute name="invisible">1</attribute>
</xpath>

<!-- 选择不包含 field 的 group -->
<xpath expr="//group[not(field)]" position="inside">
    <field name="new_field"/>
</xpath>
```

#### 4.3.2 true() 和 false()

```xml
<!-- 选择 required 属性为 true 的 field -->
<xpath expr="//field[@required='1' or @required='true']" position="attributes">
    <attribute name="required">0</attribute>
</xpath>
```

### 4.4 节点集函数

#### 4.4.1 name()

```xml
<!-- 选择所有名为 'field' 的元素 -->
<xpath expr="//*[name()='field']" position="attributes">
    <attribute name="readonly">1</attribute>
</xpath>
```

#### 4.4.2 local-name()

```xml
<!-- 选择本地名称为 'field' 的元素(忽略命名空间) -->
<xpath expr="//*[local-name()='field']" position="attributes">
    <attribute name="readonly">1</attribute>
</xpath>
```

---

## 5. 复杂定位策略

### 5.1 多条件组合

#### 5.1.1 AND 条件

```xml
<!-- 选择 name='partner_id' 且 invisible='1' 的 field -->
<xpath expr="//field[@name='partner_id' and @invisible='1']" position="attributes">
    <attribute name="invisible">0</attribute>
</xpath>

<!-- 选择 name 以 'partner' 开头且 required='1' 的 field -->
<xpath expr="//field[starts-with(@name, 'partner') and @required='1']" position="attributes">
    <attribute name="required">0</attribute>
</xpath>
```

#### 5.1.2 OR 条件

```xml
<!-- 选择 name='partner_id' 或 name='customer_id' 的 field -->
<xpath expr="//field[@name='partner_id' or @name='customer_id']" position="after">
    <field name="new_field"/>
</xpath>

<!-- 选择 widget='many2one' 或 widget='many2many' 的 field -->
<xpath expr="//field[@widget='many2one' or @widget='many2many']" position="attributes">
    <attribute name="options">{'no_create': True}</attribute>
</xpath>
```

#### 5.1.3 复杂组合

```xml
<!-- (name='partner_id' 且 required='1') 或 (name='customer_id') -->
<xpath expr="//field[(@name='partner_id' and @required='1') or @name='customer_id']" position="attributes">
    <attribute name="readonly">1</attribute>
</xpath>
```

### 5.2 嵌套定位

#### 5.2.1 定位特定结构

```xml
<!-- 选择 notebook 下的 page 下的 group 下的 field -->
<xpath expr="//notebook/page/group/field[@name='partner_id']" position="after">
    <field name="new_field"/>
</xpath>

<!-- 选择 form 下的 sheet 下的第一个 group -->
<xpath expr="//form/sheet/group[1]" position="inside">
    <field name="new_field"/>
</xpath>
```

#### 5.2.2 跨层级定位

```xml
<!-- 选择任意位置的 notebook 下的 page -->
<xpath expr="//notebook/page[@string='其他信息']" position="after">
    <page string="自定义信息">
        <group>
            <field name="custom_field"/>
        </group>
    </page>
</xpath>
```

### 5.3 动态定位

#### 5.3.1 基于属性值定位

```xml
<!-- 选择 string 属性值包含当前模型名称的 field -->
<xpath expr="//field[contains(@string, 'Partner')]" position="attributes">
    <attribute name="string">客户</attribute>
</xpath>
```

#### 5.3.2 基于子元素定位

```xml
<!-- 选择包含 partner_id 字段的 group -->
<xpath expr="//group[field[@name='partner_id']]" position="after">
    <group>
        <field name="new_field"/>
    </group>
</xpath>

<!-- 选择包含至少一个 required 字段的 group -->
<xpath expr="//group[field[@required='1']]" position="attributes">
    <attribute name="string">必填信息</attribute>
</xpath>
```

---

## 6. 实战案例

### 6.1 案例1: 在特定字段后添加新字段

**需求:** 在销售订单的 `partner_id` 字段后添加 `partner_phone` 字段。

**实现:**

```xml
<xpath expr="//field[@name='partner_id']" position="after">
    <field name="partner_phone"/>
</xpath>
```

---

### 6.2 案例2: 修改 Notebook 中的页面

**需求:** 在销售订单的"其他信息"标签页后添加"生产信息"标签页。

**实现:**

```xml
<xpath expr="//notebook/page[@name='other_information']" position="after">
    <page string="生产信息" name="production_info">
        <group>
            <field name="production_date"/>
            <field name="production_manager_id"/>
        </group>
    </page>
</xpath>
```

---

### 6.3 案例3: 隐藏特定 Group 中的所有字段

**需求:** 隐藏销售订单中 `sale_info` group 下的所有字段。

**实现:**

```xml
<xpath expr="//group[@name='sale_info']/field" position="attributes">
    <attribute name="invisible">1</attribute>
</xpath>
```

---

### 6.4 案例4: 替换按钮

**需求:** 替换销售订单的"确认"按钮,添加自定义逻辑。

**实现:**

```xml
<xpath expr="//button[@name='action_confirm']" position="replace">
    <button name="custom_action_confirm" 
            string="确认订单" 
            type="object" 
            class="oe_highlight"
            states="draft,sent"/>
</xpath>
```

---

### 6.5 案例5: 在表单顶部添加警告横幅

**需求:** 在销售订单表单顶部添加一个警告横幅。

**实现:**

```xml
<xpath expr="//form/sheet" position="before">
    <div class="alert alert-warning" role="alert">
        <strong>注意:</strong> 请确认所有信息无误后再提交订单。
    </div>
</xpath>
```

---

### 6.6 案例6: 修改列表视图的列

**需求:** 在销售订单列表视图的 `partner_id` 列后添加 `client_order_ref` 列。

**实现:**

```xml
<xpath expr="//tree/field[@name='partner_id']" position="after">
    <field name="client_order_ref"/>
</xpath>
```

---

### 6.7 案例7: 条件性显示字段

**需求:** 只在 `state` 为 `sale` 时显示 `invoice_status` 字段。

**实现:**

```xml
<xpath expr="//field[@name='invoice_status']" position="attributes">
    <attribute name="invisible">[('state', '!=', 'sale')]</attribute>
</xpath>
```

---

### 6.8 案例8: 在特定位置插入分隔符

**需求:** 在 `partner_id` 和 `date_order` 字段之间插入分隔符。

**实现:**

```xml
<xpath expr="//field[@name='partner_id']" position="after">
    <separator string="订单信息"/>
</xpath>
```

---

### 6.9 案例9: 修改字段的 widget

**需求:** 将 `partner_id` 字段的 widget 改为 `res_partner_many2one`。

**实现:**

```xml
<xpath expr="//field[@name='partner_id']" position="attributes">
    <attribute name="widget">res_partner_many2one</attribute>
    <attribute name="context">{'show_address': 1, 'show_email': 1}</attribute>
</xpath>
```

---

### 6.10 案例10: 在 Group 内部的特定位置添加字段

**需求:** 在 `sale_info` group 的第一个字段前添加新字段。

**实现:**

```xml
<xpath expr="//group[@name='sale_info']/field[1]" position="before">
    <field name="custom_field"/>
</xpath>
```

---

## 7. 性能优化

### 7.1 使用具体路径

❌ **不推荐:**
```xml
<xpath expr="//field[@name='partner_id']" position="after">
```

✅ **推荐:**
```xml
<xpath expr="//form/sheet/group/field[@name='partner_id']" position="after">
```

**原因:** 具体路径减少了搜索范围,提高了匹配速度。

### 7.2 避免使用复杂的函数

❌ **不推荐:**
```xml
<xpath expr="//field[substring(@name, 1, 7)='partner']" position="after">
```

✅ **推荐:**
```xml
<xpath expr="//field[starts-with(@name, 'partner')]" position="after">
```

**原因:** `starts-with()` 比 `substring()` 更高效。

### 7.3 使用属性选择器而不是函数

❌ **不推荐:**
```xml
<xpath expr="//field[name()='field']" position="after">
```

✅ **推荐:**
```xml
<xpath expr="//field" position="after">
```

**原因:** 直接使用元素名称比使用 `name()` 函数更快。

### 7.4 缓存常用的 XPath 表达式

如果需要多次使用相同的 XPath,考虑使用变量或继承链。

---

## 8. 调试技巧

### 8.1 启用开发者模式

**方法1:** URL
```
http://localhost:8069/web?debug=1
```

**方法2:** 设置
```
设置 → 激活开发者模式
```

### 8.2 查看视图结构

1. 打开表单
2. 点击右上角 **🐞 调试** 图标
3. 选择 **编辑视图: 表单**
4. 查看完整的 XML 结构

### 8.3 使用浏览器开发者工具

1. 按 `F12` 打开开发者工具
2. 选择 **Elements** 标签
3. 查找对应的 HTML 元素
4. 推断对应的 Odoo 字段名称

### 8.4 测试 XPath 表达式

**在线工具:**
- [XPath Tester](https://www.freeformatter.com/xpath-tester.html)
- [XPath Playground](https://scrapinghub.github.io/xpath-playground/)

**步骤:**
1. 复制视图的 XML 结构
2. 粘贴到在线工具
3. 测试 XPath 表达式
4. 验证是否选择了正确的元素

### 8.5 使用日志

在 Python 代码中添加日志:

```python
import logging
_logger = logging.getLogger(__name__)

_logger.info("XPath 定位成功")
```

### 8.6 分步调试

如果 XPath 不工作:

1. **简化表达式**: 从最简单的开始
   ```xml
   //field
   ```

2. **逐步添加条件**:
   ```xml
   //field[@name='partner_id']
   ```

3. **添加路径**:
   ```xml
   //form/sheet/group/field[@name='partner_id']
   ```

4. **添加更多条件**:
   ```xml
   //form/sheet/group/field[@name='partner_id' and @required='1']
   ```

---

## 9. 常见错误

### 9.1 XPath 找不到元素

**错误:** 视图继承不生效

**原因:**
- 字段名称错误
- 路径不正确
- 父视图还未加载

**解决:**
1. 检查字段名称是否正确
2. 使用开发者模式查看视图结构
3. 确认模块依赖关系

### 9.2 Position 参数错误

**错误:** 元素位置不对

**原因:**
- `position` 参数使用不当

**解决:**
- `before`: 在元素前
- `after`: 在元素后
- `inside`: 在元素内
- `replace`: 替换元素
- `attributes`: 修改属性

### 9.3 多个元素匹配

**错误:** XPath 匹配了多个元素

**原因:**
- XPath 表达式不够具体

**解决:**
使用更具体的路径或添加更多条件:
```xml
<!-- 不够具体 -->
<xpath expr="//field[@name='name']" position="after">

<!-- 更具体 -->
<xpath expr="//form/sheet/group/field[@name='name']" position="after">
```

### 9.4 属性值类型错误

**错误:** 属性值不匹配

**原因:**
- 属性值类型不对(字符串 vs 数字 vs 布尔值)

**解决:**
```xml
<!-- 错误: 布尔值应该用 '1' 或 'True' -->
<xpath expr="//field[@required=true]" position="attributes">

<!-- 正确 -->
<xpath expr="//field[@required='1']" position="attributes">
```

---

## 10. 最佳实践

### 10.1 命名规范

✅ **使用有意义的 ID**
```xml
<record id="view_sale_order_form_add_production_info" model="ir.ui.view">
```

❌ **避免使用通用 ID**
```xml
<record id="view_1" model="ir.ui.view">
```

### 10.2 注释

✅ **添加注释说明**
```xml
<!-- 在客户字段后添加客户电话字段 -->
<xpath expr="//field[@name='partner_id']" position="after">
    <field name="partner_phone"/>
</xpath>
```

### 10.3 模块化

✅ **将不同功能的视图继承分开**
```
views/
├── sale_order_add_fields.xml
├── sale_order_hide_fields.xml
└── sale_order_modify_domain.xml
```

❌ **避免将所有修改放在一个文件中**

### 10.4 优先级

如果多个模块修改同一视图,使用 `priority` 控制顺序:

```xml
<record id="view_sale_order_form_custom" model="ir.ui.view">
    <field name="name">sale.order.form.custom</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/>
    <field name="priority">20</field>
    <field name="arch" type="xml">
        <!-- ... -->
    </field>
</record>
```

**说明:** 数字越小,优先级越高(默认为 16)

---

## 11. 总结

### 11.1 核心要点

1. **XPath** 是定位 XML 元素的强大工具
2. **轴** 提供了灵活的节点选择方式
3. **函数** 增强了 XPath 的表达能力
4. **性能优化** 很重要,使用具体路径
5. **调试技巧** 帮助快速定位问题

### 11.2 学习路径

1. ✅ 掌握基本选择器
2. ✅ 理解 Position 参数
3. ✅ 学习属性选择器
4. ✅ 掌握常用函数
5. ✅ 理解轴的概念
6. 🔜 学习复杂的组合表达式
7. 🔜 实践性能优化
8. 🔜 掌握调试技巧

### 11.3 参考资源

- [W3Schools XPath Tutorial](https://www.w3schools.com/xml/xpath_intro.asp)
- [MDN XPath Documentation](https://developer.mozilla.org/en-US/docs/Web/XPath)
- [Odoo Documentation](https://www.odoo.com/documentation/)

---

**文档版本:** 1.0  
**最后更新:** 2025-12-21  
**作者:** Antigravity AI Assistant
