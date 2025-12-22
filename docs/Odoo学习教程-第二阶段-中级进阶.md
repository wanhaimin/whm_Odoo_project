# Odoo 学习教程 - 第二阶段:中级进阶 (2个月)

> **写给学习者的话:**  
> 恭喜你完成了第一阶段!现在你已经掌握了 Odoo 的基础知识。  
> 第二阶段会深入学习 Python 编程和业务逻辑,这是 Odoo 的核心能力。  
> 不要担心,我们会继续用简单的例子,一步一步来! 💪

---

## 📚 第二阶段学习目标

完成本阶段后,你将能够:
- ✅ 用 Python 定义数据模型
- ✅ 理解和使用 @api 装饰器
- ✅ 实现复杂的业务逻辑
- ✅ 管理用户权限
- ✅ 创建工作流

---

## 第 9 周:Python 模型基础

### 第 1 天:什么是模型?

#### 📖 理解模型

**用表格来理解:**

```
想象一个 Excel 表格:

客户表:
┌──────┬──────┬──────┬──────┐
│ ID   │ 姓名 │ 电话 │ 城市 │
├──────┼──────┼──────┼──────┤
│ 1    │ 张三 │ 138..│ 北京 │
│ 2    │ 李四 │ 139..│ 上海 │
└──────┴──────┴──────┴──────┘

在 Odoo 中,这个表格就是一个"模型"
```

**模型的作用:**
- 定义数据的结构(有哪些列)
- 定义数据的类型(文本、数字、日期等)
- 定义数据之间的关系(客户和订单的关系)

---

### 第 2 天:创建第一个模型

#### 🔨 实践:创建产品模型

**步骤 1: 创建模型文件**

在 `models/` 文件夹下创建 `product.py`:

```python
# -*- coding: utf-8 -*-
from odoo import models, fields

class Product(models.Model):
    # 模型的内部名称(数据库表名)
    _name = 'my.product'
    
    # 模型的描述
    _description = '产品'
    
    # 定义字段(就像表格的列)
    name = fields.Char('产品名称', required=True)
    price = fields.Float('价格')
    description = fields.Text('描述')
```

**理解每一行:**

1. `from odoo import models, fields`
   - 导入 Odoo 的工具
   - 就像从工具箱里拿出工具

2. `class Product(models.Model):`
   - 定义一个产品类
   - 继承自 `models.Model`(使用 Odoo 的基础功能)

3. `_name = 'my.product'`
   - 模型的内部名称
   - 数据库表名会是 `my_product`

4. `name = fields.Char('产品名称', required=True)`
   - 定义一个文本字段
   - `required=True` 表示必填

---

### 第 3 天:常用字段类型

#### 📖 字段类型就像数据类型

**想象你在填表:**

```
姓名: [文本框]        ← Char (文本)
年龄: [数字框]        ← Integer (整数)
价格: [小数框]        ← Float (小数)
生日: [日期选择器]    ← Date (日期)
是否会员: [复选框]    ← Boolean (是/否)
备注: [大文本框]      ← Text (长文本)
```

#### 🔨 实践:使用不同字段类型

```python
class Product(models.Model):
    _name = 'my.product'
    _description = '产品'
    
    # 文本字段(短文本,如名称)
    name = fields.Char('产品名称', required=True)
    
    # 整数字段(如库存数量)
    stock_qty = fields.Integer('库存数量', default=0)
    
    # 小数字段(如价格)
    price = fields.Float('价格', digits=(10, 2))
    
    # 日期字段
    manufacture_date = fields.Date('生产日期')
    
    # 日期时间字段
    create_datetime = fields.Datetime('创建时间', default=fields.Datetime.now)
    
    # 布尔字段(是/否)
    is_available = fields.Boolean('是否可用', default=True)
    
    # 长文本字段(如描述)
    description = fields.Text('产品描述')
    
    # 选择字段(下拉选项)
    product_type = fields.Selection([
        ('physical', '实物产品'),
        ('service', '服务'),
        ('digital', '数字产品')
    ], string='产品类型', default='physical')
```

**字段参数说明:**

- `required=True` - 必填
- `default=0` - 默认值
- `digits=(10, 2)` - 总共10位,小数2位
- `help='帮助文本'` - 鼠标悬停时显示的提示

---

### 第 4 天:关联字段 - Many2one

#### 📖 理解 Many2one

**用生活例子理解:**

```
订单表:
┌──────┬──────────┬──────┐
│ ID   │ 订单号   │ 客户 │
├──────┼──────────┼──────┤
│ 1    │ SO001    │ 张三 │  ← 多个订单
│ 2    │ SO002    │ 张三 │  ← 可以属于
│ 3    │ SO003    │ 李四 │  ← 一个客户
└──────┴──────────┴──────┘

这就是 Many2one (多对一)
多个订单 → 一个客户
```

#### 🔨 实践:添加客户关联

```python
class SaleOrder(models.Model):
    _name = 'my.sale.order'
    _description = '销售订单'
    
    name = fields.Char('订单号', required=True)
    
    # Many2one 字段
    # 多个订单可以属于一个客户
    partner_id = fields.Many2one(
        'res.partner',      # 关联的模型
        string='客户',      # 显示名称
        required=True       # 必填
    )
    
    order_date = fields.Date('订单日期')
    amount_total = fields.Float('总金额')
```

**理解:**
- `'res.partner'` - 关联到客户模型
- 在界面上会显示为下拉框
- 可以选择一个客户

---

### 第 5 天:关联字段 - One2many

#### 📖 理解 One2many

**用生活例子理解:**

```
订单表:
┌──────┬──────────┐
│ ID   │ 订单号   │
├──────┼──────────┤
│ 1    │ SO001    │ ← 一个订单
└──────┴──────────┘
         ↓
订单明细表:
┌──────┬──────────┬────────┬──────┐
│ ID   │ 订单ID   │ 产品   │ 数量 │
├──────┼──────────┼────────┼──────┤
│ 1    │ 1        │ 苹果   │ 10   │  ← 可以有
│ 2    │ 1        │ 香蕉   │ 5    │  ← 多个
│ 3    │ 1        │ 橙子   │ 8    │  ← 明细
└──────┴──────────┴────────┴──────┘

这就是 One2many (一对多)
一个订单 → 多个明细
```

#### 🔨 实践:添加订单明细

```python
class SaleOrder(models.Model):
    _name = 'my.sale.order'
    _description = '销售订单'
    
    name = fields.Char('订单号')
    partner_id = fields.Many2one('res.partner', '客户')
    
    # One2many 字段
    # 一个订单可以有多个明细
    order_line_ids = fields.One2many(
        'my.sale.order.line',  # 明细模型
        'order_id',            # 明细模型中的关联字段
        string='订单明细'
    )

class SaleOrderLine(models.Model):
    _name = 'my.sale.order.line'
    _description = '销售订单明细'
    
    # Many2one 关联回订单
    order_id = fields.Many2one('my.sale.order', '订单')
    
    product_id = fields.Many2one('product.product', '产品')
    quantity = fields.Float('数量')
    price_unit = fields.Float('单价')
```

**理解:**
- 订单有 `order_line_ids` (一对多)
- 明细有 `order_id` (多对一)
- 它们互相关联

---

### 第 6-7 天:复习和练习

#### 📝 复习要点

1. **模型是什么?**
   - 数据的结构定义
   - 就像 Excel 表格

2. **常用字段类型:**
   - `Char` - 短文本
   - `Integer` - 整数
   - `Float` - 小数
   - `Date` - 日期
   - `Boolean` - 是/否
   - `Text` - 长文本
   - `Selection` - 下拉选项

3. **关联字段:**
   - `Many2one` - 多对一
   - `One2many` - 一对多

#### ✏️ 练习

1. 创建一个图书模型,包含:
   - 书名
   - 作者
   - 价格
   - 出版日期
   - 是否在售

2. 创建借阅记录模型,关联图书和读者

---

## 第 10 周:@api 装饰器

### 第 1 天:什么是装饰器?

#### 📖 理解装饰器

**用生活例子理解:**

```
想象你是一个厨师:

普通做菜:
1. 洗菜
2. 切菜
3. 炒菜

加了"装饰"的做菜:
@穿围裙        ← 装饰器1
@洗手          ← 装饰器2
def 做菜():
    1. 洗菜
    2. 切菜
    3. 炒菜

装饰器会在做菜前自动执行
```

**在 Odoo 中:**
```python
@api.depends('price', 'quantity')  # 装饰器
def _compute_total(self):          # 方法
    # 当 price 或 quantity 变化时
    # 自动执行这个方法
    self.total = self.price * self.quantity
```

---

### 第 2 天:@api.depends - 自动计算

#### 📖 理解 @api.depends

**用购物车理解:**

```
购物车:
单价: 10元
数量: 5个
总价: ?

当单价或数量变化时,总价自动更新
这就是 @api.depends 的作用
```

#### 🔨 实践:计算订单总额

```python
class SaleOrder(models.Model):
    _name = 'my.sale.order'
    
    order_line_ids = fields.One2many('my.sale.order.line', 'order_id', '明细')
    
    # 计算字段
    amount_total = fields.Float(
        '总金额',
        compute='_compute_amount_total',  # 计算方法
        store=True                         # 存储到数据库
    )
    
    # @api.depends 告诉 Odoo:
    # 当订单明细的小计变化时,重新计算总额
    @api.depends('order_line_ids.price_subtotal')
    def _compute_amount_total(self):
        for record in self:
            # 计算所有明细的小计之和
            record.amount_total = sum(record.order_line_ids.mapped('price_subtotal'))

class SaleOrderLine(models.Model):
    _name = 'my.sale.order.line'
    
    order_id = fields.Many2one('my.sale.order', '订单')
    quantity = fields.Float('数量')
    price_unit = fields.Float('单价')
    
    # 计算小计
    price_subtotal = fields.Float(
        '小计',
        compute='_compute_price_subtotal',
        store=True
    )
    
    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for record in self:
            record.price_subtotal = record.quantity * record.price_unit
```

**理解:**
- 当数量或单价变化时,小计自动更新
- 当小计变化时,订单总额自动更新
- 就像 Excel 的公式

---

### 第 3 天:@api.onchange - 界面联动

#### 📖 理解 @api.onchange

**用表单填写理解:**

```
填写地址表单:

选择省份: [广东 ▼]
         ↓ (自动更新)
选择城市: [深圳 ▼]  ← 只显示广东的城市
         ↓ (自动更新)
选择区县: [南山区 ▼]  ← 只显示深圳的区县

这就是 @api.onchange 的作用
```

#### 🔨 实践:选择产品后自动填充价格

```python
class SaleOrderLine(models.Model):
    _name = 'my.sale.order.line'
    
    product_id = fields.Many2one('product.product', '产品')
    price_unit = fields.Float('单价')
    quantity = fields.Float('数量', default=1)
    
    # 当产品变化时触发
    @api.onchange('product_id')
    def _onchange_product_id(self):
        # 如果选择了产品
        if self.product_id:
            # 自动填充产品的价格
            self.price_unit = self.product_id.list_price
```

**效果:**
```
1. 用户选择产品: "苹果"
2. 单价自动填充: 5.00
3. 用户可以修改单价
```

---

### 第 4 天:@api.constrains - 数据验证

#### 📖 理解 @api.constrains

**用考试规则理解:**

```
考试规则:
- 分数必须在 0-100 之间
- 如果不符合,不允许保存

这就是 @api.constrains 的作用
```

#### 🔨 实践:验证折扣范围

```python
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SaleOrderLine(models.Model):
    _name = 'my.sale.order.line'
    
    product_id = fields.Many2one('product.product', '产品')
    price_unit = fields.Float('单价')
    discount = fields.Float('折扣(%)', default=0)
    
    # 验证折扣
    @api.constrains('discount')
    def _check_discount(self):
        for record in self:
            # 如果折扣不在 0-100 之间
            if record.discount < 0 or record.discount > 100:
                # 抛出错误,阻止保存
                raise ValidationError('折扣必须在 0-100 之间!')
```

**效果:**
```
用户输入折扣: 150
点击保存
系统提示: "折扣必须在 0-100 之间!"
无法保存
```

---

### 第 5 天:@api.model - 类方法

#### 📖 理解 @api.model

**用工具箱理解:**

```
普通方法:
需要先拿出一个工具(记录),才能使用

@api.model 方法:
不需要工具,直接可以使用
就像计算器,不需要先有数字
```

#### 🔨 实践:创建默认订单

```python
class SaleOrder(models.Model):
    _name = 'my.sale.order'
    
    name = fields.Char('订单号', default='New')
    partner_id = fields.Many2one('res.partner', '客户')
    order_date = fields.Date('订单日期')
    
    # @api.model 表示这是一个类方法
    # 不需要特定的记录就可以调用
    @api.model
    def create(self, vals):
        # 如果订单号是 'New'
        if vals.get('name', 'New') == 'New':
            # 自动生成序列号
            vals['name'] = self.env['ir.sequence'].next_by_code('my.sale.order')
        
        # 调用父类的 create 方法
        return super(SaleOrder, self).create(vals)
```

**效果:**
```
创建新订单:
订单号自动生成: SO001, SO002, SO003...
```

---

### 第 6-7 天:复习和练习

#### 📝 复习要点

1. **@api.depends**
   - 自动计算
   - 当依赖字段变化时触发
   - 用于计算字段

2. **@api.onchange**
   - 界面联动
   - 当字段值变化时触发
   - 只在界面上生效

3. **@api.constrains**
   - 数据验证
   - 保存时检查
   - 不符合条件则阻止保存

4. **@api.model**
   - 类方法
   - 不需要记录就能调用

#### ✏️ 练习

1. 创建一个订单模型,实现:
   - 自动计算总金额
   - 选择客户后自动填充地址
   - 验证订单日期不能是过去的日期

---

## 第 11-12 周:权限管理

### 第 1 天:为什么需要权限?

#### 📖 理解权限

**用公司管理理解:**

```
公司里不同的人有不同的权限:

老板:
✅ 查看所有数据
✅ 修改所有数据
✅ 删除数据

经理:
✅ 查看部门数据
✅ 修改部门数据
❌ 删除数据

员工:
✅ 查看自己的数据
❌ 修改他人数据
❌ 删除数据

这就是权限管理
```

---

### 第 2 天:访问权限 (ir.model.access)

#### 📖 理解访问权限

**访问权限控制四个操作:**

```
CRUD 权限:
C - Create  (创建)
R - Read    (读取)
U - Update  (更新)
D - Delete  (删除)
```

#### 🔨 实践:设置产品权限

**步骤 1: 创建权限文件**

在 `security/` 文件夹下创建 `ir.model.access.csv`:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_my_product_user,my.product.user,model_my_product,base.group_user,1,1,1,0
access_my_product_manager,my.product.manager,model_my_product,base.group_system,1,1,1,1
```

**理解每一列:**

| 列名 | 含义 | 示例值 |
|------|------|--------|
| `id` | 权限ID | `access_my_product_user` |
| `name` | 权限名称 | `my.product.user` |
| `model_id:id` | 模型ID | `model_my_product` |
| `group_id:id` | 用户组ID | `base.group_user` |
| `perm_read` | 读取权限 | `1` (允许) |
| `perm_write` | 写入权限 | `1` (允许) |
| `perm_create` | 创建权限 | `1` (允许) |
| `perm_unlink` | 删除权限 | `0` (禁止) |

**效果:**
```
普通用户 (base.group_user):
✅ 可以查看产品
✅ 可以修改产品
✅ 可以创建产品
❌ 不能删除产品

管理员 (base.group_system):
✅ 可以查看产品
✅ 可以修改产品
✅ 可以创建产品
✅ 可以删除产品
```

---

### 第 3 天:记录规则 (ir.rule)

#### 📖 理解记录规则

**用部门管理理解:**

```
销售部门:
只能看到自己部门的订单

财务部门:
可以看到所有订单

这就是记录规则
```

#### 🔨 实践:只能看自己的订单

```xml
<record id="sale_order_personal_rule" model="ir.rule">
    <field name="name">Personal Sale Orders</field>
    <field name="model_id" ref="model_my_sale_order"/>
    <field name="domain_force">[('user_id', '=', user.id)]</field>
    <field name="groups" eval="[(4, ref('base.group_user'))]"/>
</record>
```

**理解:**
- `domain_force` - 过滤条件
- `[('user_id', '=', user.id)]` - 只显示当前用户的记录
- `groups` - 应用到哪些用户组

**效果:**
```
用户 A 登录:
只能看到自己创建的订单

用户 B 登录:
只能看到自己创建的订单

管理员登录:
可以看到所有订单
```

---

### 第 4-7 天:综合练习

#### 项目:订单管理系统权限

**需求:**

1. **普通销售员:**
   - 可以创建订单
   - 可以查看自己的订单
   - 可以修改草稿状态的订单
   - 不能删除订单

2. **销售经理:**
   - 可以查看所有订单
   - 可以修改所有订单
   - 可以删除订单

3. **财务人员:**
   - 可以查看所有订单
   - 不能修改订单
   - 不能删除订单

---

## 第 13-16 周:工作流和状态管理

### 第 1 天:什么是工作流?

#### 📖 理解工作流

**用请假流程理解:**

```
请假流程:

草稿 → 提交 → 审批 → 批准
 ↓      ↓      ↓      ↓
可修改  等待   等待   完成
        ↓      ↓
       可取消  可拒绝
```

**在 Odoo 中:**
```python
state = fields.Selection([
    ('draft', '草稿'),
    ('submitted', '已提交'),
    ('approved', '已批准'),
    ('rejected', '已拒绝'),
], default='draft')
```

---

### 第 2 天:实现状态管理

#### 🔨 实践:订单状态流程

```python
class SaleOrder(models.Model):
    _name = 'my.sale.order'
    
    name = fields.Char('订单号')
    partner_id = fields.Many2one('res.partner', '客户')
    
    # 状态字段
    state = fields.Selection([
        ('draft', '草稿'),
        ('sent', '已发送'),
        ('sale', '销售订单'),
        ('done', '已完成'),
        ('cancel', '已取消'),
    ], string='状态', default='draft')
    
    # 确认订单
    def action_confirm(self):
        self.state = 'sale'
    
    # 完成订单
    def action_done(self):
        self.state = 'done'
    
    # 取消订单
    def action_cancel(self):
        self.state = 'cancel'
```

---

### 第 3 天:添加状态按钮

#### 🔨 实践:在视图中添加按钮

```xml
<record id="view_sale_order_form" model="ir.ui.view">
    <field name="model">my.sale.order</field>
    <field name="arch" type="xml">
        <form>
            <!-- 状态栏 -->
            <header>
                <!-- 确认按钮 -->
                <button name="action_confirm" 
                        string="确认订单" 
                        type="object"
                        states="draft"
                        class="oe_highlight"/>
                
                <!-- 完成按钮 -->
                <button name="action_done" 
                        string="完成" 
                        type="object"
                        states="sale"/>
                
                <!-- 取消按钮 -->
                <button name="action_cancel" 
                        string="取消" 
                        type="object"
                        states="draft,sent,sale"/>
                
                <!-- 状态显示 -->
                <field name="state" widget="statusbar"/>
            </header>
            
            <sheet>
                <group>
                    <field name="name"/>
                    <field name="partner_id"/>
                </group>
            </sheet>
        </form>
    </field>
</record>
```

**效果:**
```
草稿状态:
[确认订单] [取消]

销售订单状态:
[完成] [取消]

已完成状态:
(没有按钮)
```

---

### 第 4-7 天:综合项目

#### 项目:完整的订单管理系统

**功能:**
1. 订单创建和编辑
2. 状态流程管理
3. 权限控制
4. 自动计算金额
5. 数据验证

---

## 📚 第二阶段总结

### 你已经学会了

✅ **Python 模型**
- 定义数据结构
- 使用各种字段类型
- 建立数据关联

✅ **@api 装饰器**
- @api.depends - 自动计算
- @api.onchange - 界面联动
- @api.constrains - 数据验证
- @api.model - 类方法

✅ **权限管理**
- 访问权限
- 记录规则
- 用户组管理

✅ **工作流**
- 状态管理
- 按钮和动作
- 业务流程

### 下一步

准备好进入**第三阶段(高级)**了吗?

在第三阶段,你将学习:
- JavaScript 自定义组件
- QWeb 报表开发
- 性能优化
- API 集成

---

**恭喜你完成第二阶段!** 🎉

你已经掌握了 Odoo 的核心能力!

**继续加油!** 💪

---

**文档版本:** 1.0  
**创建日期:** 2025-12-21  
**作者:** Antigravity AI Assistant  
**适用人群:** Odoo 中级学习者
