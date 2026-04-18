---
type: resource
status: active
area: "Odoo"
topic: "Learning"
reviewed: 2026-04-18
---

# Odoo 从零开始学习教程

> **写给学习者的话:**  
> 学习编程就像学开车,一开始可能觉得复杂,但只要多练习,很快就能上手。  
> 这份教程会用最简单的语言,配合大量实例,帮助您一步步掌握 Odoo。  
> 不要着急,慢慢来,每天进步一点点就好! 💪

---

## 📚 教程使用说明

### 如何使用这份教程?

1. **按顺序学习** - 不要跳过章节,每个知识点都是基础
2. **动手实践** - 看完一节就立即动手做一遍
3. **做笔记** - 把重要的内容记下来
4. **多复习** - 学完一章后,过几天再复习一遍
5. **不懂就问** - 遇到问题不要憋着,及时寻求帮助

### 学习时间安排

- **每天学习:** 1-2 小时
- **每周复习:** 周末复习本周内容
- **总时长:** 约 3-6 个月

---

## 🎯 学习路线图

```
第一阶段 (初级) - 2 个月
    ↓
第二阶段 (中级) - 2 个月
    ↓
第三阶段 (高级) - 2 个月
```

---

# 第一阶段:初级入门 (2 个月)

> **目标:** 能够看懂和修改 Odoo 的界面,理解基本概念

---

## 第 1 周:认识 Odoo

### 第 1 天:什么是 Odoo?

#### 📖 理解 Odoo

**用生活中的例子来理解:**

想象 Odoo 就像一个**万能的办公软件**:
- 就像 Excel 可以做表格
- 就像 Word 可以写文档
- 就像微信可以聊天

**Odoo 可以:**
- 管理客户信息(就像通讯录)
- 管理销售订单(就像订货单)
- 管理库存(就像仓库账本)
- 管理财务(就像记账本)

**Odoo 的特点:**
- ✅ 模块化 - 就像乐高积木,可以自由组合
- ✅ 可定制 - 就像装修房子,可以按自己喜好改
- ✅ 开源免费 - 就像免费的软件,可以随便用

---

### 第 2 天:Odoo 的基本结构

#### 📖 理解 Odoo 的组成

**用房子来比喻:**

```
Odoo 就像一栋房子:

┌─────────────────────────────────┐
│  屋顶 (界面 - 你看到的部分)      │  ← XML 定义
├─────────────────────────────────┤
│  墙壁 (逻辑 - 处理数据的部分)    │  ← Python 代码
├─────────────────────────────────┤
│  地基 (数据库 - 存储数据的地方)  │  ← PostgreSQL
└─────────────────────────────────┘
```

**三个核心部分:**

1. **界面 (XML)** - 你看到的按钮、表格、输入框
   - 就像房子的装修
   - 决定了长什么样

2. **逻辑 (Python)** - 处理数据的规则
   - 就像房子的电路、水管
   - 决定了怎么工作

3. **数据库 (PostgreSQL)** - 存储所有数据
   - 就像房子的储物间
   - 决定了数据存在哪

---

### 第 3 天:认识 Odoo 的界面

#### 📖 Odoo 界面的组成

**打开 Odoo 后,你会看到:**

```
┌────────────────────────────────────────┐
│  [≡] Odoo    销售  采购  库存  会计    │  ← 顶部菜单栏
├────────────────────────────────────────┤
│                                        │
│  [+ 新建]  [导入]  [导出]             │  ← 操作按钮
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ 客户列表                          │ │  ← 列表视图
│  ├──────────────────────────────────┤ │
│  │ 名称      电话      城市          │ │
│  │ 张三      138...    北京          │ │
│  │ 李四      139...    上海          │ │
│  └──────────────────────────────────┘ │
│                                        │
└────────────────────────────────────────┘
```

**主要组成:**
1. **菜单栏** - 切换不同的功能模块
2. **操作按钮** - 新建、编辑、删除等
3. **视图** - 显示数据的方式(列表、表单、看板等)

---

### 第 4 天:理解"模块"的概念

#### 📖 什么是模块?

**用手机 App 来理解:**

```
Odoo 的模块 = 手机的 App

手机:
├── 微信 App     (聊天功能)
├── 支付宝 App   (支付功能)
├── 地图 App     (导航功能)
└── 相机 App     (拍照功能)

Odoo:
├── 销售模块     (管理销售)
├── 采购模块     (管理采购)
├── 库存模块     (管理库存)
└── 会计模块     (管理财务)
```

**模块的特点:**
- ✅ 独立 - 每个模块管理一个功能
- ✅ 可选 - 需要哪个就安装哪个
- ✅ 可扩展 - 可以自己开发新模块

---

### 第 5 天:创建你的第一个模块

#### 📖 模块的文件结构

**就像整理文件夹:**

```
my_first_module/              (模块文件夹)
├── __init__.py              (目录文件,像文件夹的索引)
├── __manifest__.py          (说明书,介绍这个模块)
├── models/                  (数据模型,定义数据结构)
│   ├── __init__.py
│   └── my_model.py
└── views/                   (视图文件,定义界面)
    └── my_view.xml
```

#### 🔨 实践:创建模块文件夹

**步骤 1: 创建文件夹**

在 `custom_addons` 文件夹下创建:
```
custom_addons/
└── my_first_module/
```

**步骤 2: 创建 `__init__.py`**

这个文件告诉 Python 这是一个模块:
```python
# -*- coding: utf-8 -*-
from . import models
```

**理解:** 就像在文件夹里放一个说明,告诉系统"这里面有东西"

---

**步骤 3: 创建 `__manifest__.py`**

这是模块的"身份证":
```python
# -*- coding: utf-8 -*-
{
    'name': '我的第一个模块',           # 模块名称
    'version': '1.0',                   # 版本号
    'summary': '这是一个学习模块',      # 简介
    'description': '用来学习 Odoo',     # 详细说明
    'author': '你的名字',               # 作者
    'depends': ['base'],                # 依赖的模块
    'data': [],                         # 数据文件
    'installable': True,                # 可以安装
    'application': True,                # 是应用程序
}
```

**理解每一行:**
- `name` - 就像给孩子起名字
- `version` - 就像软件的版本号 1.0, 2.0
- `depends` - 就像做菜需要的原料,这个模块需要 `base` 模块
- `installable` - 就像说"这个可以用"

---

### 第 6-7 天:复习和练习

#### 📝 复习要点

1. **Odoo 是什么?**
   - 一个企业管理软件
   - 由模块组成
   - 可以定制

2. **Odoo 的三个部分:**
   - 界面 (XML)
   - 逻辑 (Python)
   - 数据库 (PostgreSQL)

3. **模块的结构:**
   - `__init__.py` - 索引文件
   - `__manifest__.py` - 说明书
   - `models/` - 数据定义
   - `views/` - 界面定义

#### ✏️ 练习

1. 用自己的话解释什么是 Odoo
2. 画出 Odoo 的三层结构
3. 创建一个新模块,命名为 `my_practice`

---

## 第 2 周:认识 XML 视图

### 第 1 天:什么是 XML?

#### 📖 理解 XML

**XML 就像一个标签系统:**

```
想象你在整理衣柜:

<衣柜>
    <上衣区>
        <衬衫>白色衬衫</衬衫>
        <T恤>蓝色T恤</T恤>
    </上衣区>
    <裤子区>
        <牛仔裤>黑色牛仔裤</牛仔裤>
    </裤子区>
</衣柜>
```

**XML 的规则:**
1. 必须有开始标签 `<标签>` 和结束标签 `</标签>`
2. 标签可以嵌套(就像盒子套盒子)
3. 标签可以有属性(就像给盒子贴标签)

**Odoo 中的 XML:**
```xml
<odoo>
    <record id="我的视图" model="ir.ui.view">
        <field name="name">客户表单</field>
        <field name="model">res.partner</field>
    </record>
</odoo>
```

---

### 第 2 天:创建第一个表单视图

#### 📖 什么是表单视图?

**表单视图就像一张纸质表格:**

```
┌─────────────────────────┐
│  客户信息表              │
├─────────────────────────┤
│  姓名: [_____________]  │
│  电话: [_____________]  │
│  地址: [_____________]  │
│                         │
│  [保存]  [取消]         │
└─────────────────────────┘
```

#### 🔨 实践:创建表单视图

**步骤 1: 创建视图文件**

在 `views/` 文件夹下创建 `customer_view.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- 这是注释,不会被执行 -->
    
    <!-- 定义一个表单视图 -->
    <record id="view_customer_form" model="ir.ui.view">
        <!-- 视图的名称 -->
        <field name="name">customer.form</field>
        
        <!-- 这个视图是给哪个模型用的 -->
        <field name="model">res.partner</field>
        
        <!-- 视图的结构 -->
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <!-- 显示姓名字段 -->
                        <field name="name"/>
                        
                        <!-- 显示电话字段 -->
                        <field name="phone"/>
                        
                        <!-- 显示邮箱字段 -->
                        <field name="email"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
</odoo>
```

**理解每一部分:**

1. `<?xml version="1.0"?>` - 告诉系统这是 XML 文件
2. `<odoo>` - Odoo 的根标签,所有内容都在里面
3. `<record>` - 定义一条记录(就像数据库的一行)
4. `<field name="arch">` - 定义视图的结构
5. `<form>` - 表单视图
6. `<sheet>` - 表单的主体部分
7. `<group>` - 分组,让字段排列整齐
8. `<field name="name"/>` - 显示一个字段

---

### 第 3 天:理解视图的层次结构

#### 📖 视图的嵌套关系

**就像俄罗斯套娃:**

```xml
<odoo>                          ← 最外层(大娃娃)
    <record>                    ← 第二层(中娃娃)
        <field name="arch">     ← 第三层(小娃娃)
            <form>              ← 第四层(更小的娃娃)
                <sheet>         ← 第五层
                    <group>     ← 第六层
                        <field name="name"/>  ← 最里层
                    </group>
                </sheet>
            </form>
        </field>
    </record>
</odoo>
```

**每一层的作用:**
- `<odoo>` - 告诉系统这是 Odoo 的 XML
- `<record>` - 定义一个视图记录
- `<field name="arch">` - 视图的具体内容
- `<form>` - 表单类型
- `<sheet>` - 表单的主体
- `<group>` - 字段分组
- `<field>` - 具体的字段

---

### 第 4 天:添加更多字段

#### 🔨 实践:丰富表单内容

```xml
<form>
    <sheet>
        <!-- 第一组:基本信息 -->
        <group string="基本信息">
            <field name="name"/>
            <field name="phone"/>
            <field name="email"/>
        </group>
        
        <!-- 第二组:地址信息 -->
        <group string="地址信息">
            <field name="street"/>
            <field name="city"/>
            <field name="zip"/>
        </group>
    </sheet>
</form>
```

**新增的内容:**
- `string="基本信息"` - 给分组加标题
- 多个 `<group>` - 创建多个分组

**效果:**
```
┌─────────────────────────┐
│  基本信息                │
│  姓名: [_____________]  │
│  电话: [_____________]  │
│  邮箱: [_____________]  │
├─────────────────────────┤
│  地址信息                │
│  街道: [_____________]  │
│  城市: [_____________]  │
│  邮编: [_____________]  │
└─────────────────────────┘
```

---

### 第 5 天:创建列表视图

#### 📖 什么是列表视图?

**列表视图就像 Excel 表格:**

```
┌──────────┬──────────┬──────────┐
│ 姓名     │ 电话     │ 城市     │
├──────────┼──────────┼──────────┤
│ 张三     │ 138...   │ 北京     │
│ 李四     │ 139...   │ 上海     │
│ 王五     │ 137...   │ 广州     │
└──────────┴──────────┴──────────┘
```

#### 🔨 实践:创建列表视图

```xml
<record id="view_customer_tree" model="ir.ui.view">
    <field name="name">customer.tree</field>
    <field name="model">res.partner</field>
    <field name="arch" type="xml">
        <!-- tree 表示列表视图 -->
        <tree>
            <!-- 每个 field 就是一列 -->
            <field name="name"/>
            <field name="phone"/>
            <field name="city"/>
            <field name="email"/>
        </tree>
    </field>
</record>
```

**理解:**
- `<tree>` - 列表视图的标签
- 每个 `<field>` - 表格的一列
- 顺序 - 从左到右排列

---

### 第 6-7 天:复习和练习

#### 📝 复习要点

1. **XML 是什么?**
   - 一种标记语言
   - 用标签组织内容
   - 必须有开始和结束标签

2. **表单视图:**
   - 用 `<form>` 标签
   - 用 `<group>` 分组
   - 用 `<field>` 显示字段

3. **列表视图:**
   - 用 `<tree>` 标签
   - 每个 `<field>` 是一列

#### ✏️ 练习

1. 创建一个产品表单视图,包含:
   - 产品名称
   - 价格
   - 描述

2. 创建一个产品列表视图,显示:
   - 产品名称
   - 价格

---

## 第 3 周:理解 Domain 过滤

### 第 1 天:什么是 Domain?

#### 📖 理解 Domain

**Domain 就像筛选器:**

```
想象你在超市买水果:

所有水果:
├── 苹果 (红色, 5元)
├── 苹果 (青色, 4元)
├── 香蕉 (黄色, 3元)
└── 橙子 (橙色, 6元)

筛选条件:
- 只要苹果 → [('类型', '=', '苹果')]
- 价格小于5元 → [('价格', '<', 5)]
- 红色的苹果 → [('类型', '=', '苹果'), ('颜色', '=', '红色')]
```

**在 Odoo 中:**
```python
# 只显示公司类型的客户
[('is_company', '=', True)]

# 只显示北京的客户
[('city', '=', '北京')]

# 只显示公司且在北京的客户
[('is_company', '=', True), ('city', '=', '北京')]
```

---

### 第 2 天:Domain 的基本语法

#### 📖 Domain 的结构

**Domain 是一个列表,里面是元组:**

```python
[('字段名', '操作符', '值')]
```

**例子:**
```python
# 姓名等于张三
[('name', '=', '张三')]

# 价格大于100
[('price', '>', 100)]

# 城市是北京
[('city', '=', '北京')]
```

**常用操作符:**

| 操作符 | 含义 | 例子 |
|--------|------|------|
| `=` | 等于 | `('name', '=', '张三')` |
| `!=` | 不等于 | `('name', '!=', '李四')` |
| `>` | 大于 | `('price', '>', 100)` |
| `<` | 小于 | `('price', '<', 50)` |
| `>=` | 大于等于 | `('age', '>=', 18)` |
| `<=` | 小于等于 | `('age', '<=', 60)` |

---

### 第 3 天:多个条件的组合

#### 📖 AND 条件(并且)

**默认情况下,多个条件是 AND 关系:**

```python
# 公司 并且 在北京
[('is_company', '=', True), ('city', '=', '北京')]
```

**理解:**
```
所有客户:
├── 张三 (个人, 北京) ❌ 不是公司
├── ABC公司 (公司, 北京) ✅ 符合
├── XYZ公司 (公司, 上海) ❌ 不在北京
└── 李四 (个人, 上海) ❌ 都不符合
```

---

#### 📖 OR 条件(或者)

**使用 `'|'` 表示 OR:**

```python
# 在北京 或者 在上海
['|', ('city', '=', '北京'), ('city', '=', '上海')]
```

**理解:**
```
所有客户:
├── 张三 (北京) ✅ 在北京
├── 李四 (上海) ✅ 在上海
├── 王五 (广州) ❌ 都不符合
└── 赵六 (深圳) ❌ 都不符合
```

**注意:** `'|'` 要放在两个条件的**前面**

---

### 第 4 天:在视图中使用 Domain

#### 🔨 实践:过滤客户

**场景:** 在销售订单中,只显示公司类型的客户

```xml
<field name="partner_id" 
       domain="[('is_company', '=', True)]"/>
```

**效果:**
- 点击客户下拉框
- 只显示公司,不显示个人

---

**场景:** 只显示北京的客户

```xml
<field name="partner_id" 
       domain="[('city', '=', '北京')]"/>
```

---

**场景:** 只显示公司且在北京的客户

```xml
<field name="partner_id" 
       domain="[('is_company', '=', True), ('city', '=', '北京')]"/>
```

---

### 第 5 天:动态 Domain

#### 📖 引用其他字段

**场景:** 送货地址必须属于客户

```xml
<!-- partner_id 是客户字段 -->
<field name="partner_id"/>

<!-- partner_shipping_id 是送货地址 -->
<!-- 只显示属于当前客户的地址 -->
<field name="partner_shipping_id" 
       domain="[('parent_id', '=', partner_id)]"/>
```

**理解:**
```
客户: ABC公司 (ID=1)

所有地址:
├── 北京办公室 (parent_id=1) ✅ 属于ABC公司
├── 上海分公司 (parent_id=1) ✅ 属于ABC公司
├── 深圳办公室 (parent_id=2) ❌ 属于XYZ公司
└── 广州分公司 (parent_id=2) ❌ 属于XYZ公司

只显示: 北京办公室, 上海分公司
```

---

### 第 6-7 天:复习和练习

#### 📝 复习要点

1. **Domain 是什么?**
   - 过滤条件
   - 用列表和元组表示
   - 格式: `[('字段', '操作符', '值')]`

2. **常用操作符:**
   - `=` 等于
   - `!=` 不等于
   - `>` 大于
   - `<` 小于

3. **组合条件:**
   - 默认是 AND
   - 使用 `'|'` 表示 OR

#### ✏️ 练习

1. 写出以下过滤条件:
   - 价格大于100的产品
   - 北京或上海的客户
   - 公司且价格大于1000的订单

2. 在视图中添加 Domain 过滤

---

## 第 4 周:视图继承

### 第 1 天:什么是视图继承?

#### 📖 理解视图继承

**用装修房子来理解:**

```
原始房子(Odoo 自带的视图):
┌─────────────┐
│  客厅        │
│  卧室        │
│  厨房        │
└─────────────┘

你的改造(继承):
┌─────────────┐
│  客厅        │  ← 保持不变
│  卧室        │  ← 保持不变
│  厨房        │  ← 保持不变
│  书房        │  ← 新增
└─────────────┘
```

**优势:**
- ✅ 不修改原始代码
- ✅ 可以随时撤销
- ✅ 升级不受影响

---

### 第 2 天:XPath 定位

#### 📖 什么是 XPath?

**XPath 就像地址:**

```
想象你要在一本书中找到某一页:

方法1: 翻到第50页
方法2: 找到"第三章"的"第二节"

XPath 就是方法2,用路径来定位
```

**基本语法:**

```xml
<!-- 找到名为 partner_id 的字段 -->
//field[@name='partner_id']

<!-- 找到所有字段 -->
//field

<!-- 找到 form 下的 sheet -->
//form/sheet
```

---

### 第 3 天:在字段后添加内容

#### 🔨 实践:添加新字段

**场景:** 在客户的电话字段后,添加一个传真字段

```xml
<record id="view_partner_form_inherit" model="ir.ui.view">
    <!-- 继承哪个视图 -->
    <field name="inherit_id" ref="base.view_partner_form"/>
    
    <field name="arch" type="xml">
        <!-- 找到 phone 字段 -->
        <xpath expr="//field[@name='phone']" position="after">
            <!-- 在它后面添加 fax 字段 -->
            <field name="fax"/>
        </xpath>
    </field>
</record>
```

**效果:**
```
原来:
姓名: [_______]
电话: [_______]
邮箱: [_______]

修改后:
姓名: [_______]
电话: [_______]
传真: [_______]  ← 新增
邮箱: [_______]
```

---

### 第 4 天:修改字段属性

#### 🔨 实践:添加过滤条件

**场景:** 在销售订单中,客户字段只显示公司

```xml
<record id="view_order_form_inherit" model="ir.ui.view">
    <field name="inherit_id" ref="sale.view_order_form"/>
    
    <field name="arch" type="xml">
        <!-- 找到 partner_id 字段 -->
        <xpath expr="//field[@name='partner_id']" position="attributes">
            <!-- 修改它的 domain 属性 -->
            <attribute name="domain">[('is_company', '=', True)]</attribute>
        </xpath>
    </field>
</record>
```

**position 的值:**
- `after` - 在后面添加
- `before` - 在前面添加
- `inside` - 在里面添加
- `replace` - 替换
- `attributes` - 修改属性

---

### 第 5 天:隐藏字段

#### 🔨 实践:隐藏不需要的字段

**场景:** 隐藏客户表单中的网站字段

```xml
<xpath expr="//field[@name='website']" position="attributes">
    <attribute name="invisible">1</attribute>
</xpath>
```

**常用属性:**
- `invisible="1"` - 隐藏
- `readonly="1"` - 只读
- `required="1"` - 必填

---

### 第 6-7 天:复习和练习

#### 📝 复习要点

1. **视图继承:**
   - 不修改原始代码
   - 使用 `inherit_id` 指定父视图
   - 使用 XPath 定位元素

2. **XPath 语法:**
   - `//field[@name='xxx']` - 找到字段
   - `position` - 指定位置

3. **常用 position:**
   - `after` - 后面
   - `before` - 前面
   - `attributes` - 修改属性

#### ✏️ 练习

1. 在产品表单的价格字段后,添加成本字段
2. 修改客户字段,只显示北京的客户
3. 隐藏产品表单中的条形码字段

---

## 第 5-8 周:综合练习

### 项目:客户管理系统

#### 需求

创建一个简单的客户管理系统,包含:

1. **客户信息:**
   - 姓名
   - 电话
   - 邮箱
   - 地址
   - 客户类型(个人/公司)

2. **视图:**
   - 表单视图
   - 列表视图

3. **过滤:**
   - 只显示公司客户
   - 只显示北京客户

#### 实现步骤

**第 1 步:创建模块结构**

```
my_customer/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── customer.py
└── views/
    └── customer_view.xml
```

**第 2 步:定义模型**

```python
# models/customer.py
from odoo import models, fields

class Customer(models.Model):
    _name = 'my.customer'
    _description = '客户'
    
    name = fields.Char('姓名', required=True)
    phone = fields.Char('电话')
    email = fields.Char('邮箱')
    street = fields.Char('街道')
    city = fields.Char('城市')
    customer_type = fields.Selection([
        ('person', '个人'),
        ('company', '公司')
    ], string='客户类型')
```

**第 3 步:创建视图**

```xml
<!-- views/customer_view.xml -->
<odoo>
    <!-- 表单视图 -->
    <record id="view_customer_form" model="ir.ui.view">
        <field name="name">customer.form</field>
        <field name="model">my.customer</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="name"/>
                        <field name="phone"/>
                        <field name="email"/>
                        <field name="customer_type"/>
                    </group>
                    <group>
                        <field name="street"/>
                        <field name="city"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    
    <!-- 列表视图 -->
    <record id="view_customer_tree" model="ir.ui.view">
        <field name="name">customer.tree</field>
        <field name="model">my.customer</field>
        <field name="arch" type="xml">
            <tree>
                <field name="name"/>
                <field name="phone"/>
                <field name="city"/>
                <field name="customer_type"/>
            </tree>
        </field>
    </record>
</odoo>
```

---

## 📚 第一阶段总结

### 你已经学会了

✅ **Odoo 基础概念**
- 什么是 Odoo
- 模块的概念
- 文件结构

✅ **XML 视图**
- 表单视图
- 列表视图
- 视图继承

✅ **Domain 过滤**
- 基本语法
- 组合条件
- 动态过滤

✅ **实践项目**
- 创建完整模块
- 定义数据模型
- 创建视图

### 下一步

准备好进入**第二阶段(中级)**了吗?

在第二阶段,你将学习:
- Python 模型定义
- @api 装饰器
- 权限管理
- 工作流

---

**恭喜你完成第一阶段!** 🎉

记住:
- 不要着急,慢慢来
- 多练习,多动手
- 遇到问题不要放弃
- 学习是一个过程,享受它!

**继续加油!** 💪

---

**文档版本:** 1.0  
**创建日期:** 2025-12-21  
**作者:** Antigravity AI Assistant  
**适用人群:** Odoo 初学者
