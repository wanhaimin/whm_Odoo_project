# Odoo 悬浮窗（弹窗）实现方案文档

在 Odoo 中，实现“点击跳转但不离开当前页面”的最佳实践是使用 **Target New (Modal/Wizard)** 模式。本案以“报价单明细快速查看原材料详情”为例。

## 1. 核心原理
Odoo 的 `ir.actions.act_window` 支持 `target` 参数：
- `current`: 在当前窗口打开（默认，会覆盖当前页面）。
- `new`: 在当前页面上方弹出悬浮对话框（Modal）。
- `inline`: 在表单内部平铺打开（较少用）。

## 2. 具体实现步骤

### 第一步：后端 Python 逻辑设计
在明细行模型中定义跳转 Action。这里有两种方案：

#### 方案 A：通用方案（指向产品变体）
直接打开关联的 `product.product` 记录。
```python
def action_open_material(self):
    self.ensure_one()
    return {
        'type': 'ir.actions.act_window',
        'res_model': 'product.product',
        'res_id': self.material_id.id,
        'view_mode': 'form',
        'target': 'new',
    }
```

#### 方案 B：进阶方案（指向模板 + 指定专用视图）—— **本项目采用**
为了显示更完整的模切规格和参数，指向 `product.template` 并强制使用特定的定制视图。
```python
def action_open_material(self):
    self.ensure_one()
    if not self.material_id: return True
    
    # 获取模切定制的产品模板视图 ID
    view_id = self.env.ref('diecut.product_template_form_view_diecut').id
    
    return {
        'type': 'ir.actions.act_window',
        'name': '原材料详细数据',
        'res_model': 'product.template',
        'res_id': self.material_id.product_tmpl_id.id, # 获取变体背后的模板 ID
        'view_mode': 'form',
        'view_id': view_id,   # 强制指定视图
        'target': 'new',      # 悬浮窗显示
        'context': {'create': False},
    }
```

### 2.1 代码深度解析（为什么这样写？）

- **`res_model` 与 `res_id` 的配对**: 
  - 如果指向变体，`res_id` 是 `self.material_id.id`。
  - 如果指向模板，`res_id` 是 `self.material_id.product_tmpl_id.id`。
  - **报错排查**：如果不传 `res_id`，Odoo 会默认打开列表页。

- **`view_id` 的深层作用 (方案 B)**:
  在大型系统中，一个模型（如产品）可能有几十个不同的 Form 视图。通过 `view_id`，我们可以精确控制弹出的窗口展示哪一个界面（例如只展示业务相关的“模切属性”页面）。

- **`self.ensure_one()`**: 
  安全检查。确保当前操作上下文仅针对单条记录。

### 第二步：前端 XML 视图配置
在列表（List/Tree）视图中，我们需要做两件事：
1. **禁用字段默认链接**：防止点击名称时触发默认的 `current` 跳转。
2. **添加自定义操作按钮**：调用上一步定义的 Python 方法。

```xml
<field name="material_line_ids" mode="list">
    <list editable="bottom">
        <!-- options="{'no_open': True}" 禁用默认跳转链接 -->
        <field name="material_id" options="{'no_open': True}"/>
        
        <!-- 添加按钮调用 Python Action -->
        <button name="action_open_material" 
                type="object" 
                icon="fa-arrow-right" 
                title="快速查看" 
                class="oe_link"/>
                
        <!-- 其他字段 --!>
        <field name="raw_width"/>
    </list>
</field>
```

## 3. 方案优点
1. **保持上下文**：用户在录入报价单时，可以随时查看材料参数，关闭弹窗后依然停留在原来的录入状态，无需重新加载页面。
2. **防误触**：通过禁用 Many2one 字段自带的 `no_open`，避免了用户习惯性点击导致的“页面跳走”问题。
3. **交互规范**：符合 Odoo 官方对 Wizard（向导）和查看关联信息的交互规范。

## 4. 扩展应用场景
该方案同样适用于：
- 在订单页面快速查看/修改客户资料。
- 在库存移动页面直接打开批次详情。
- 在生产订单页面查看工艺指导文件。

---
**提示**：修改完成后，请务必执行模块升级（`-u module_name`）以使 XML 配置和 Python 函数生效。
