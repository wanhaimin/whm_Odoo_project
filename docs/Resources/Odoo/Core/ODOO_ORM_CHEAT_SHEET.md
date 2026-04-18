---
type: resource
status: active
area: "Odoo"
topic: "Core"
reviewed: 2026-04-18
---

# Odoo ORM 独孤九剑 (常用语法速查表)

ORM 是 Odoo 的灵魂。掌握了这些，您就不需要写一句 SQL，就能操控整个数据库。

## 一、 查 (Search / Read) —— 最常用的招式

### 1. `search()` - 找出一堆记录
返回的是一个**记录集 (Recordset)**，就像一个列表一样。
```python
# 找出所有的木板模
molds = self.env['diecut.mold'].search([('mold_type', '=', 'wood')])

# 找出所有“新”的、且名字里包含“A01”的模具
molds = self.env['diecut.mold'].search([
    ('status', '=', 'new'),
    ('name', 'like', 'A01')
])
```

### 2. `search_count()` - 只想知道有多少个
比 search 更快，因为不读数据，只数数。
```python
count = self.env['diecut.mold'].search_count([('mold_type', '=', 'wood')])
# 返回: 52
```

### 3. `browse()` - 知道 ID，直接拿记录
就像拿着身份证号去查人，最快。
```python
mold = self.env['diecut.mold'].browse(1)  # 拿 ID=1 的那个模具
# 如果要拿好几个：
molds = self.env['diecut.mold'].browse([1, 2, 3])
```

### 4. `filtered()` - 在内存里再次筛选
已经查出来一堆了，想用 Python 逻辑再筛一遍（比数据库筛更灵活）。
```python
# 筛选出所有名字以 'X' 开头的模具
x_molds = all_molds.filtered(lambda m: m.name.startswith('X'))
```

---

## 二、 增 (Create)

我们要造一个新模具。
```python
new_mold = self.env['diecut.mold'].create({
    'name': '苹果手机刀模',
    'code': 'M-2023-888',
    'mold_type': 'etch',
    'location': 'Wait for assignment'
})
# create 方法会返回新创建的那条记录对象，您可以立刻用它
print(new_mold.id) 
```

---

## 三、 改 (Write) —— 也是“保存”背后的动作

我们要批量修改，或者单条修改。
```python
# 1. 找到要改的记录 (比如 ID=5 的那个)
mold = self.env['diecut.mold'].browse(5)

# 2. 改它！
mold.write({
    'location': 'B-01-01',
    'active': False   # 把它归档（软删除）
})

# 3. 批量改！(威力巨大，慎用)
# 把所有木板模都改成 'active': False
wood_molds = self.env['diecut.mold'].search([('mold_type', '=', 'wood')])
wood_molds.write({'active': False})
```

---

## 四、 删 (Unlink) —— 真正的删除

```python
# 1. 找到记录
bad_molds = self.env['diecut.mold'].search([('code', '=', 'ERROR')])

# 2. 删！(数据库里彻底没了，找不回来的)
bad_molds.unlink()
```

---

## 五、 这里的 `self.env` 是个啥？
它是 Odoo 的**环境上下文 (Environment)**，是通往数据库的钥匙。
*   `self.env.user`: 当前登录的用户是谁？
*   `self.env.company`: 当前在哪个公司？
*   `self.env['模型名']`: 拿到那个模型的“总代理”。

---

## 六、 常用小技巧

### 1. 遍历记录 (Loop)
```python
molds = self.env['diecut.mold'].search([])
for mold in molds:
    print(mold.name)  # 就像遍历普通 Python 列表一样
    # ORM 会自动帮您去数据库取数据 (Lazy Loading)
```

### 2. 获取关联字段的值 (Dot Notation)
最爽的特性！不用写 JOIN 语句，直接用点号 `.`
```python
# 假设 mold 有个 designer_id (Many2one)
print(mold.designer_id.name)       # 设计师的名字
print(mold.designer_id.email)      # 设计师的邮箱
print(mold.designer_id.company_id.name) # 设计师所属公司的名字 (无限套娃)
```
