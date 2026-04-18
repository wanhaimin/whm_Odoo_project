---
type: resource
status: active
area: "Odoo"
topic: "Views and ORM"
reviewed: 2026-04-18
---

# Domain 高级过滤技术

## 📚 目录
1. [Domain 基础回顾](#1-domain-基础回顾)
2. [高级操作符](#2-高级操作符)
3. [逻辑运算详解](#3-逻辑运算详解)
4. [关联字段过滤](#4-关联字段过滤)
5. [动态 Domain](#5-动态-domain)
6. [计算字段过滤](#6-计算字段过滤)
7. [性能优化](#7-性能优化)
8. [实战案例](#8-实战案例)

---

## 1. Domain 基础回顾

### 1.1 什么是 Domain?

Domain 是 Odoo 中用于过滤记录的表达式,类似于 SQL 的 WHERE 子句。它以 Python 列表的形式定义。

### 1.2 基本语法

```python
[('字段名', '操作符', '值')]
```

### 1.3 基本示例

```python
# 单个条件
[('is_company', '=', True)]

# 多个条件 (AND)
[('is_company', '=', True), ('customer_rank', '>', 0)]

# OR 条件
['|', ('is_company', '=', True), ('customer_rank', '>', 0)]
```

---

## 2. 高级操作符

### 2.1 比较操作符

| 操作符 | 含义 | 示例 | SQL 等价 |
|--------|------|------|----------|
| `=` | 等于 | `('state', '=', 'draft')` | `state = 'draft'` |
| `!=` | 不等于 | `('state', '!=', 'cancel')` | `state != 'cancel'` |
| `>` | 大于 | `('amount_total', '>', 1000)` | `amount_total > 1000` |
| `<` | 小于 | `('amount_total', '<', 500)` | `amount_total < 500` |
| `>=` | 大于等于 | `('customer_rank', '>=', 1)` | `customer_rank >= 1` |
| `<=` | 小于等于 | `('supplier_rank', '<=', 5)` | `supplier_rank <= 5` |

### 2.2 集合操作符

#### 2.2.1 in

```python
# 状态在指定列表中
[('state', 'in', ['draft', 'sent', 'sale'])]

# SQL: WHERE state IN ('draft', 'sent', 'sale')
```

```python
# 客户 ID 在指定列表中
[('partner_id', 'in', [1, 2, 3, 4, 5])]

# SQL: WHERE partner_id IN (1, 2, 3, 4, 5)
```

#### 2.2.2 not in

```python
# 状态不在指定列表中
[('state', 'not in', ['cancel', 'done'])]

# SQL: WHERE state NOT IN ('cancel', 'done')
```

```python
# 排除特定客户
[('partner_id', 'not in', [1, 2, 3])]

# SQL: WHERE partner_id NOT IN (1, 2, 3)
```

### 2.3 字符串操作符

#### 2.3.1 like (区分大小写)

```python
# 名称包含 '公司'
[('name', 'like', '%公司%')]

# SQL: WHERE name LIKE '%公司%'
```

**通配符:**
- `%`: 匹配任意字符(0个或多个)
- `_`: 匹配单个字符

```python
# 名称以 '东莞' 开头
[('name', 'like', '东莞%')]

# 名称以 '有限公司' 结尾
[('name', 'like', '%有限公司')]

# 名称第二个字符是 '莞'
[('name', 'like', '_莞%')]
```

#### 2.3.2 ilike (不区分大小写)

```python
# 邮箱包含 'gmail' (不区分大小写)
[('email', 'ilike', '%gmail%')]

# SQL: WHERE email ILIKE '%gmail%'
```

```python
# 名称包含 'company' (不区分大小写)
[('name', 'ilike', '%company%')]
# 可以匹配: 'Company', 'COMPANY', 'company'
```

#### 2.3.3 not like / not ilike

```python
# 名称不包含 'test'
[('name', 'not like', '%test%')]

# 名称不包含 'demo' (不区分大小写)
[('name', 'not ilike', '%demo%')]
```

#### 2.3.4 =like / =ilike

```python
# 精确模式匹配
[('name', '=like', '东莞%')]
# 等价于 starts-with

[('email', '=ilike', '%@gmail.com')]
# 等价于 ends-with (不区分大小写)
```

### 2.4 特殊操作符

#### 2.4.1 =? (等于或为空)

```python
# 如果 partner_id 为 None/False,则忽略此条件
[('partner_id', '=?', partner_id)]

# 等价于:
if partner_id:
    domain = [('partner_id', '=', partner_id)]
else:
    domain = []
```

**使用场景:**
```python
def get_orders(self, partner_id=None, state=None):
    domain = [
        ('partner_id', '=?', partner_id),
        ('state', '=?', state),
    ]
    return self.env['sale.order'].search(domain)
```

#### 2.4.2 child_of (包含子记录)

```python
# 包含分类及其所有子分类
[('category_id', 'child_of', [1, 2])]

# 示例: 如果分类 1 有子分类 3, 4, 5
# 则会匹配 category_id 为 1, 3, 4, 5 的记录
```

**实际应用:**
```python
# 查找某个公司及其所有子公司的联系人
[('parent_id', 'child_of', company_id)]
```

#### 2.4.3 parent_of (包含父记录)

```python
# 包含分类及其所有父分类
[('category_id', 'parent_of', [5])]

# 示例: 如果分类 5 的父分类是 3, 3 的父分类是 1
# 则会匹配 category_id 为 1, 3, 5 的记录
```

---

## 3. 逻辑运算详解

### 3.1 AND (默认)

多个条件默认是 AND 关系:

```python
[('is_company', '=', True), ('customer_rank', '>', 0)]
# 等价于: is_company = True AND customer_rank > 0
```

### 3.2 OR

使用 `'|'` 前缀表示 OR:

```python
['|', ('is_company', '=', True), ('customer_rank', '>', 0)]
# 等价于: is_company = True OR customer_rank > 0
```

### 3.3 NOT

使用 `'!'` 前缀表示 NOT:

```python
['!', ('active', '=', False)]
# 等价于: NOT (active = False)
# 即: active = True
```

```python
['!', ('state', 'in', ['cancel', 'done'])]
# 等价于: NOT (state IN ('cancel', 'done'))
# 即: state NOT IN ('cancel', 'done')
```

### 3.4 复杂逻辑组合

#### 3.4.1 (A AND B) OR C

```python
['|', '&', ('A', '=', True), ('B', '=', True), ('C', '=', True)]
```

**理解方式:**
- `'|'` 表示后面两个条件是 OR
- `'&'` 表示后面两个条件是 AND
- 结构: `|` → (`&` → A, B), C

**实际示例:**
```python
# (is_company = True AND customer_rank > 0) OR supplier_rank > 0
['|', '&', ('is_company', '=', True), ('customer_rank', '>', 0), ('supplier_rank', '>', 0)]
```

#### 3.4.2 A AND (B OR C)

```python
['&', ('A', '=', True), '|', ('B', '=', True), ('C', '=', True)]
```

**实际示例:**
```python
# active = True AND (customer_rank > 0 OR supplier_rank > 0)
['&', ('active', '=', True), '|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0)]
```

#### 3.4.3 (A OR B) AND (C OR D)

```python
['&', '|', ('A', '=', True), ('B', '=', True), '|', ('C', '=', True), ('D', '=', True)]
```

**实际示例:**
```python
# (is_company = True OR type = 'contact') AND (customer_rank > 0 OR supplier_rank > 0)
['&', '|', ('is_company', '=', True), ('type', '=', 'contact'), '|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0)]
```

#### 3.4.4 NOT (A AND B)

```python
['!', '&', ('A', '=', True), ('B', '=', True)]
# 等价于: NOT (A = True AND B = True)
# 根据德摩根定律: A != True OR B != True
```

**实际示例:**
```python
# NOT (is_company = True AND active = False)
['!', '&', ('is_company', '=', True), ('active', '=', False)]
```

#### 3.4.5 复杂示例

```python
# ((A OR B) AND C) OR (D AND E)
['|', '&', '|', ('A', '=', True), ('B', '=', True), ('C', '=', True), '&', ('D', '=', True), ('E', '=', True)]
```

**解析:**
```
|                           # 最外层 OR
├─ &                        # 左侧 AND
│  ├─ |                     # A OR B
│  │  ├─ A = True
│  │  └─ B = True
│  └─ C = True
└─ &                        # 右侧 AND
   ├─ D = True
   └─ E = True
```

### 3.5 逻辑运算符规则

#### 3.5.1 前缀表示法

Odoo 使用**前缀表示法**(波兰表示法):

```
操作符 操作数1 操作数2
```

**示例:**
```python
# 中缀: A OR B
# 前缀: | A B
['|', A, B]

# 中缀: A AND B
# 前缀: & A B
['&', A, B]

# 中缀: NOT A
# 前缀: ! A
['!', A]
```

#### 3.5.2 操作符作用范围

- `'|'` (OR): 作用于后面的 **2 个** 条件
- `'&'` (AND): 作用于后面的 **2 个** 条件
- `'!'` (NOT): 作用于后面的 **1 个** 条件

**示例:**
```python
# | A B C
# 错误理解: A OR B OR C
# 正确理解: (A OR B) AND C

# 正确的 A OR B OR C:
['|', '|', A, B, C]
# 解析: | (| A B) C
```

#### 3.5.3 多个 OR 条件

```python
# A OR B OR C
['|', '|', A, B, C]

# A OR B OR C OR D
['|', '|', '|', A, B, C, D]

# A OR B OR C OR D OR E
['|', '|', '|', '|', A, B, C, D, E]
```

**规律:** n 个条件需要 n-1 个 `'|'`

#### 3.5.4 多个 AND 条件

```python
# A AND B AND C (默认)
[A, B, C]

# 显式写法
['&', '&', A, B, C]
```

---

## 4. 关联字段过滤

### 4.1 Many2one 字段

#### 4.1.1 通过 ID 过滤

```python
# 客户 ID 等于 1
[('partner_id', '=', 1)]

# 客户 ID 在列表中
[('partner_id', 'in', [1, 2, 3])]

# 客户 ID 不为空
[('partner_id', '!=', False)]

# 客户 ID 为空
[('partner_id', '=', False)]
```

#### 4.1.2 通过关联字段的字段过滤

```python
# 客户的国家代码是 'CN'
[('partner_id.country_id.code', '=', 'CN')]

# 客户名称包含 '公司'
[('partner_id.name', 'ilike', '%公司%')]

# 客户的城市是 '东莞'
[('partner_id.city', '=', '东莞')]

# 客户的销售员是当前用户
[('partner_id.user_id', '=', uid)]
```

#### 4.1.3 多层关联

```python
# 客户的国家的货币是 'CNY'
[('partner_id.country_id.currency_id.name', '=', 'CNY')]

# 订单的客户的父公司名称包含 '集团'
[('order_id.partner_id.parent_id.name', 'ilike', '%集团%')]
```

### 4.2 One2many 字段

#### 4.2.1 存在性检查

```python
# 有订单明细
[('order_line', '!=', False)]

# 没有订单明细
[('order_line', '=', False)]
```

#### 4.2.2 子记录条件

```python
# 至少有一个订单明细的产品 ID 是 1
[('order_line.product_id', '=', 1)]

# 至少有一个订单明细的数量大于 10
[('order_line.product_uom_qty', '>', 10)]

# 至少有一个订单明细的产品名称包含 '电脑'
[('order_line.product_id.name', 'ilike', '%电脑%')]
```

### 4.3 Many2many 字段

#### 4.3.1 包含特定记录

```python
# 标签包含 ID 为 1 的标签
[('tag_ids', 'in', [1])]

# 标签包含 ID 为 1 或 2 的标签
[('tag_ids', 'in', [1, 2])]
```

#### 4.3.2 不包含特定记录

```python
# 标签不包含 ID 为 1 的标签
[('tag_ids', 'not in', [1])]
```

#### 4.3.3 存在性检查

```python
# 有标签
[('tag_ids', '!=', False)]

# 没有标签
[('tag_ids', '=', False)]
```

### 4.4 关联字段的复杂过滤

#### 4.4.1 组合条件

```python
# 客户是公司且国家是中国
[('partner_id.is_company', '=', True), ('partner_id.country_id.code', '=', 'CN')]
```

#### 4.4.2 OR 条件

```python
# 客户的城市是 '东莞' 或 '深圳'
['|', ('partner_id.city', '=', '东莞'), ('partner_id.city', '=', '深圳')]

# 更简洁的写法
[('partner_id.city', 'in', ['东莞', '深圳'])]
```

---

## 5. 动态 Domain

### 5.1 使用上下文变量

#### 5.1.1 uid (当前用户 ID)

```python
# 只显示当前用户负责的客户
[('user_id', '=', uid)]
```

```xml
<field name="partner_id" domain="[('user_id', '=', uid)]"/>
```

#### 5.1.2 context (上下文)

```python
# 从上下文获取值
[('partner_id', '=', context.get('default_partner_id'))]
```

```xml
<field name="order_id" 
       domain="[('partner_id', '=', context.get('partner_id'))]"
       context="{'partner_id': partner_id}"/>
```

#### 5.1.3 parent (父记录)

在 One2many 字段中使用:

```xml
<field name="order_line">
    <tree>
        <field name="product_id" 
               domain="[('categ_id', '=', parent.product_category_id)]"/>
    </tree>
</field>
```

### 5.2 使用字段值

#### 5.2.1 引用同一记录的其他字段

```xml
<!-- 送货地址必须属于客户 -->
<field name="partner_shipping_id" 
       domain="[('parent_id', '=', partner_id)]"/>

<!-- 发票地址必须属于客户 -->
<field name="partner_invoice_id" 
       domain="[('parent_id', '=', partner_id)]"/>
```

#### 5.2.2 引用关联字段

```xml
<!-- 产品必须属于客户的首选分类 -->
<field name="product_id" 
       domain="[('categ_id', '=', partner_id.product_category_id)]"/>
```

### 5.3 Python 代码中的动态 Domain

#### 5.3.1 基本用法

```python
def get_domain(self):
    domain = []
    
    if self.partner_id:
        domain.append(('partner_id', '=', self.partner_id.id))
    
    if self.state:
        domain.append(('state', '=', self.state))
    
    return domain

# 使用
orders = self.env['sale.order'].search(self.get_domain())
```

#### 5.3.2 条件性添加

```python
def get_orders(self, partner_id=None, state=None, date_from=None):
    domain = []
    
    if partner_id:
        domain.append(('partner_id', '=', partner_id))
    
    if state:
        domain.append(('state', '=', state))
    
    if date_from:
        domain.append(('date_order', '>=', date_from))
    
    return self.env['sale.order'].search(domain)
```

#### 5.3.3 使用 expression 模块

```python
from odoo.osv import expression

def get_complex_domain(self):
    domain1 = [('is_company', '=', True)]
    domain2 = [('customer_rank', '>', 0)]
    
    # AND
    domain = expression.AND([domain1, domain2])
    # 结果: [('is_company', '=', True), ('customer_rank', '>', 0)]
    
    # OR
    domain = expression.OR([domain1, domain2])
    # 结果: ['|', ('is_company', '=', True), ('customer_rank', '>', 0)]
    
    return domain
```

### 5.4 @api.onchange 中的动态 Domain

```python
@api.onchange('partner_id')
def _onchange_partner_id(self):
    if self.partner_id:
        return {
            'domain': {
                'partner_shipping_id': [('parent_id', '=', self.partner_id.id)],
                'partner_invoice_id': [('parent_id', '=', self.partner_id.id)],
            }
        }
```

---

## 6. 计算字段过滤

### 6.1 存储的计算字段

如果计算字段设置了 `store=True`,可以直接在 domain 中使用:

```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    
    amount_total = fields.Monetary(
        string='Total',
        compute='_compute_amount_total',
        store=True  # 存储到数据库
    )
```

```python
# 可以直接过滤
[('amount_total', '>', 1000)]
```

### 6.2 未存储的计算字段

如果计算字段没有 `store=True`,**不能**直接在 domain 中使用:

```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    
    display_name = fields.Char(
        compute='_compute_display_name',
        store=False  # 不存储
    )
```

```python
# 错误: 不能直接过滤未存储的计算字段
[('display_name', 'ilike', '%test%')]  # ❌ 会报错
```

**解决方案:** 使用 `search` 方法:

```python
def search_by_display_name(self, name):
    # 先获取所有记录
    all_records = self.env['sale.order'].search([])
    
    # 在 Python 中过滤
    filtered_records = all_records.filtered(
        lambda r: name.lower() in r.display_name.lower()
    )
    
    return filtered_records
```

---

## 7. 性能优化

### 7.1 使用索引字段

✅ **推荐:** 使用有索引的字段

```python
# 好: name 通常有索引
[('name', '=', 'Test')]

# 好: Many2one 字段有索引
[('partner_id', '=', 1)]
```

❌ **避免:** 过滤未索引的字段

```python
# 慢: 如果 description 没有索引
[('description', 'ilike', '%test%')]
```

### 7.2 避免复杂的字符串匹配

✅ **推荐:** 使用精确匹配

```python
[('state', '=', 'draft')]
```

❌ **避免:** 使用 like/ilike

```python
[('state', 'ilike', '%draft%')]  # 慢
```

### 7.3 使用 in 而不是多个 OR

✅ **推荐:**
```python
[('state', 'in', ['draft', 'sent', 'sale'])]
```

❌ **避免:**
```python
['|', '|', ('state', '=', 'draft'), ('state', '=', 'sent'), ('state', '=', 'sale')]
```

### 7.4 限制关联字段的层级

✅ **推荐:** 1-2 层

```python
[('partner_id.country_id', '=', 1)]
```

❌ **避免:** 过多层级

```python
[('order_id.partner_id.parent_id.country_id.region_id', '=', 1)]  # 太慢
```

### 7.5 使用 limit 限制结果数量

```python
# 只获取前 100 条
orders = self.env['sale.order'].search(domain, limit=100)

# 只获取第一条
order = self.env['sale.order'].search(domain, limit=1)
```

### 7.6 使用 count 而不是 len

✅ **推荐:**
```python
count = self.env['sale.order'].search_count(domain)
```

❌ **避免:**
```python
count = len(self.env['sale.order'].search(domain))  # 会加载所有记录
```

---

## 8. 实战案例

### 8.1 案例1: 只显示活跃的客户公司

```python
[
    ('is_company', '=', True),
    ('customer_rank', '>', 0),
    ('active', '=', True)
]
```

### 8.2 案例2: 显示本月创建的订单

```python
from datetime import datetime, date

# 本月第一天
first_day = date.today().replace(day=1)

[('create_date', '>=', first_day)]
```

### 8.3 案例3: 显示金额在 1000-5000 之间的订单

```python
[
    ('amount_total', '>=', 1000),
    ('amount_total', '<=', 5000)
]
```

### 8.4 案例4: 显示客户或供应商(任一即可)

```python
['|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0)]
```

### 8.5 案例5: 显示中国或美国的客户

```python
[('country_id.code', 'in', ['CN', 'US'])]
```

### 8.6 案例6: 排除测试和演示客户

```python
[
    ('name', 'not ilike', '%test%'),
    ('name', 'not ilike', '%demo%')
]
```

### 8.7 案例7: 显示有邮箱且已验证的客户

```python
[
    ('email', '!=', False),
    ('email_verified', '=', True)
]
```

### 8.8 案例8: 显示当前用户负责的客户

```python
[('user_id', '=', uid)]
```

### 8.9 案例9: 显示有订单的客户

```python
[('sale_order_ids', '!=', False)]
```

### 8.10 案例10: 复杂组合

**需求:** 显示满足以下条件的订单:
- (状态是 draft 或 sent) 且 (金额 > 1000)
- 或 状态是 sale

```python
[
    '|',
    '&', 
    ('state', 'in', ['draft', 'sent']), 
    ('amount_total', '>', 1000),
    ('state', '=', 'sale')
]
```

**解析:**
```
|                                   # OR
├─ &                                # AND
│  ├─ state in ['draft', 'sent']
│  └─ amount_total > 1000
└─ state = 'sale'
```

---

## 9. 常见错误

### 9.1 逻辑运算符数量错误

❌ **错误:**
```python
['|', ('A', '=', True), ('B', '=', True), ('C', '=', True)]
# 错误理解: A OR B OR C
# 实际结果: (A OR B) AND C
```

✅ **正确:**
```python
['|', '|', ('A', '=', True), ('B', '=', True), ('C', '=', True)]
# 正确: A OR B OR C
```

### 9.2 字段名称错误

❌ **错误:**
```python
[('partner', '=', 1)]  # 字段名是 partner_id,不是 partner
```

✅ **正确:**
```python
[('partner_id', '=', 1)]
```

### 9.3 类型不匹配

❌ **错误:**
```python
[('amount_total', '=', '1000')]  # 字符串
```

✅ **正确:**
```python
[('amount_total', '=', 1000)]  # 数字
```

### 9.4 使用未存储的计算字段

❌ **错误:**
```python
[('display_name', 'ilike', '%test%')]  # display_name 通常不存储
```

✅ **正确:**
```python
[('name', 'ilike', '%test%')]  # 使用存储的字段
```

---

## 10. 最佳实践

### 10.1 使用常量

✅ **推荐:**
```python
DRAFT_STATES = ['draft', 'sent']
DONE_STATES = ['sale', 'done']

domain = [('state', 'in', DRAFT_STATES)]
```

❌ **避免:**
```python
domain = [('state', 'in', ['draft', 'sent'])]  # 硬编码
```

### 10.2 使用辅助函数

```python
def _get_active_partners_domain(self):
    return [
        ('active', '=', True),
        ('is_company', '=', True),
        ('customer_rank', '>', 0)
    ]

# 使用
partners = self.env['res.partner'].search(self._get_active_partners_domain())
```

### 10.3 注释复杂的 Domain

```python
domain = [
    # 只显示活跃的客户公司
    ('active', '=', True),
    ('is_company', '=', True),
    ('customer_rank', '>', 0),
    
    # 排除测试客户
    ('name', 'not ilike', '%test%'),
    
    # 只显示中国客户
    ('country_id.code', '=', 'CN'),
]
```

### 10.4 使用 expression 模块

```python
from odoo.osv import expression

base_domain = [('active', '=', True)]
customer_domain = [('customer_rank', '>', 0)]
supplier_domain = [('supplier_rank', '>', 0)]

# 客户或供应商
domain = expression.AND([
    base_domain,
    expression.OR([customer_domain, supplier_domain])
])
```

---

## 11. 总结

### 11.1 核心要点

1. **Domain** 是 Odoo 的核心过滤机制
2. **逻辑运算符** 使用前缀表示法
3. **关联字段** 可以使用点号访问
4. **动态 Domain** 提供灵活性
5. **性能优化** 很重要

### 11.2 学习路径

1. ✅ 掌握基本操作符
2. ✅ 理解逻辑运算符
3. ✅ 学习关联字段过滤
4. ✅ 掌握动态 Domain
5. 🔜 学习性能优化技巧
6. 🔜 实践复杂场景

---

**文档版本:** 1.0  
**最后更新:** 2025-12-21  
**作者:** Antigravity AI Assistant
