---
type: resource
status: active
area: "Odoo"
topic: "Core"
reviewed: 2026-04-18
---

# Odoo 字段类型全景图 (Odoo Fields Cheat Sheet)

Odoo 的字段 (Fields) 主要分为三大类：**基础类型**、**关系类型**、**特殊类型**。

## 1. 基础数据类型 (Basic Types)
最常用的，对应数据库里的普通列。

| 字段类型 | 写法 | 用途 | 例子 |
| :--- | :--- | :--- | :--- |
| **Char** | `fields.Char()` | **短文本**，单行文字。 | 姓名、编号、电话 |
| **Text** | `fields.Text()` | **长文本**，多行文字。 | 备注、描述、日记 |
| **Integer** | `fields.Integer()` | **整数**，不能有小数。 | 数量、年龄、排序 |
| **Float** | `fields.Float()` | **小数**，带小数点。往往配合 `digits` 参数控制精度。 | 价格(9.99)、长度(1.5m) |
| **Boolean** | `fields.Boolean()` | **布尔值**，只有是/否。 | 是否有效、是否VIP |
| **Date** | `fields.Date()` | **日期** (YYYY-MM-DD)。 | 生日、入职日期 |
| **Datetime**| `fields.Datetime()`| **时间** (YYYY-MM-DD HH:MM:SS)。 | 下单时间、打卡时间 |
| **Monetary**| `fields.Monetary()`| **金额**，会自动带上货币符号 (￥/$)。 | 订单总价、成本 |

## 2. 关系类型 (Relational Types) ✨核心
Odoo 的灵魂，用来把不同的表连起来。

| 字段类型 | 写法 | 用途 | 例子 |
| :--- | :--- | :--- | :--- |
| **Many2one** | `fields.Many2one('model.name')` | **多对一** (我属于谁)。 | Order 属于 Customer <br> 刀模 属于 设计人 |
| **One2many** | `fields.One2many('model', 'inverse_field')` | **一对多** (我有那些)。 | Order 包含 OrderLines <br> 客户 有 多个地址 |
| **Many2many** | `fields.Many2many('model.name')` | **多对多** (互相关联)。 | 标签 (一个产品有多个标签，一个标签贴在多个产品) |

## 3. 特殊/高级类型 (Advanced Types)

| 字段类型          | 写法                                         | 用途                         | 例子                |
| :------------ | :----------------------------------------- | :------------------------- | :---------------- |
| **Selection** | `fields.Selection([('a','A'), ('b','B')])` | **下拉单选**，值是固定的。            | 性别(男/女)、状态(草稿/确认) |
| **Binary**    | `fields.Binary()`                          | **文件/图片**，存二进制数据。          | 产品图片、上传的PDF附件     |
| **Html**      | `fields.Html()`                            | **富文本**，带格式的编辑器。           | 网页内容、邮件正文         |
| **Image**     | `fields.Image()`                           | **图片专用**，比 Binary 多了缩略图优化。 | 头像、缩略图            |

---

## 常用参数 (Common Attributes)
所有字段都可以加这些参数：

*   `string="名称"`: 界面上显示的标签。
*   `required=True`: **必填**，不填不能保存。
*   `readonly=True`: **只读**，用户不能改。
*   `help="..."`: 鼠标悬停时的提示文字。
*   `default=...`: 默认值 (可以是固定值，也可以是函数)。
*   `index=True`: 建立数据库索引 (加速搜索)。

---

### 实战示例 (刀模模型改良版)

```python
class DiecutMold(models.Model):
    _name = 'diecut.mold'

    # 基础
    name = fields.Char(string='刀模名称', required=True)
    price = fields.Float(string='制作成本', digits=(10, 2))
    note = fields.Text(string='备注信息')
    
    # 关系 (假设您已经有了 res.partner 表管理联系人)
    # design_by 就不需要用 Selection 了，改用 Many2one 关联真实用户表更灵活
    designer_id = fields.Many2one('res.partner', string='设计人')
    
    # 特殊
    drawing_file = fields.Binary(string='设计图纸 (PDF)')
    status = fields.Selection([
        ('new', '新开模'),
        ('used', '使用中'),
        ('scrapped', '已报废')
    ], string='状态', default='new')
```
