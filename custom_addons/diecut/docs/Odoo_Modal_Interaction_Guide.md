# Odoo 弹窗交互优化指南

本文档总结了我们在 `diecut_quote` 模块中实现的高级弹窗交互功能，包括防止弹窗自动关闭、启用多层弹窗叠加、自定义窗口大小以及权限控制方案。

---

## 1. 防止自定义按钮操作后自动关闭弹窗

### 问题描述
在 Odoo 的 `target="new"` 弹窗模式下，点击任何服务器端动作（Python 方法）按钮后，默认行为是关闭弹窗并刷新底层视图。我们希望执行逻辑（如“同步数据”）后，弹窗保持打开。

### 解决方案
在 Python 方法末尾，返回一个重新加载当前视图的动作。

**代码示例 (`models/diecut_quote.py`)**:

```python
def action_sync_something(self):
    # ... 执行业务逻辑 ...
    
    # 关键：返回 reload 动作以保持窗口打开
    return self._get_action_reload()

def _get_action_reload(self):
    """辅助方法：返回重新加载当前 Form 视图的动作"""
    self.ensure_one()
    return {
        'type': 'ir.actions.act_window',
        'res_model': 'diecut.quote', # 当前模型
        'res_id': self.id,
        'view_mode': 'form',
        'target': 'new', # 保持弹窗模式
        'context': {'form_view_initial_mode': 'edit', 'dialog_size': 'extra-large'}, # 保持编辑状态和大小
    }
```

---

## 2. 自定义“保存并保持”按钮

### 问题描述
Odoo 默认的“保存”按钮在弹窗中通常意味着“保存并关闭”。我们需要一个按钮既能保存数据，又不会关闭窗口。

### 解决方案
1. 在 Python 中定义一个仅调用 `_get_action_reload` 的方法。
2. 在 XML 视图的 `<footer>`区域添加自定义按钮。

**Python 代码**:
```python
def action_save_and_stay(self):
    """保存并保持窗口打开"""
    # Odoo 按钮点击会自动触发 write/save，所以只需返回 reload 动作即可
    return self._get_action_reload()
```

**XML 视图 (`views/diecut_quote_views.xml`)**:
```xml
<form>
    <!-- ... 表单内容 ... -->
    
    <!-- 自定义底部按钮 -->
    <footer>
        <button string="保存" type="object" name="action_save_and_stay" class="btn-primary" data-hotkey="s"/>
        <button string="关闭" special="cancel" class="btn-secondary" data-hotkey="z"/>
    </footer>
</form>
```

---

## 3. 设置弹窗大小 (Dialog Size)

### 问题描述
默认的弹窗大小可能太小，无法展示宽表格（如报价明细）。

### 解决方案
在打开动作的 `context` 中传递 `dialog_size` 参数。

**可选值**: `small`, `medium` (默认), `large`, `extra-large`, `fullscreen` (全屏)

**Python 代码**:
```python
def action_open_form(self):
    return {
        'type': 'ir.actions.act_window',
        # ...
        'target': 'new',
        # 设置为超大号窗口
        'context': {'dialog_size': 'extra-large'},
    }
```

---

## 4. Many2one 字段与多层弹窗 (Modal Stacking)

### Many2one 点击行为详解

**默认行为**：
Odoo 的 `Many2one` 字段**默认都是可以被点击的**。
- **在列表视图（只读状态）**：字段表现为**蓝色超链接**。点击后会打开关联记录的 Form 视图。如果当前已经在弹窗中，它会以**叠加弹窗（Stacked Modal）**的形式打开。
- **在表单视图（编辑状态）**：字段表现为下拉框，但在输入框右侧（或通过“外部链接”图标）可以点击打开关联记录。

### 如何控制点击行为 (XML Options)

可以通过 `options` 属性来精细控制 `Many2one` 字段的行为：

1.  **启用点击（默认）**:
    ```xml
    <field name="customer_id" />
    <!-- 或显式启用 -->
    <field name="customer_id" options="{'no_open': False}" />
    ```

2.  **禁用点击（禁止打开弹窗）**:
    如果你不希望用户查看关联记录详情，可以设置 `no_open` 为 `True`。
    ```xml
    <field name="currency_id" options="{'no_open': True}" />
    ```

3.  **禁止创建（只允许选择）**:
    防止用户在下拉框中“创建新记录”或“创建并编辑”。
    ```xml
    <field name="product_id" options="{'no_create': True, 'no_create_edit': True}" />
    ```

---

## 5. 权限控制 (Permission Control)

实现“只能查看不能编辑”或“部分字段不可见”，Odoo 提供了**模型级**和**字段级**两层控制。

### 5.1 控制“只读” vs “编辑” (Model Access)

如果你希望某类用户（如“报价员”）在查看材料详情弹窗时**不能修改**数据，最安全、最彻底的方法是配置模型访问权限（ACL）。

**文件**: `security/ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
# 示例：报价员对产品（即材料）只有读权限，没有写/创/删权限
access_diecut_user_product,product.template user access,product.model_product_template,diecut.group_diecut_user,1,0,0,0
```

*   **效果**：当该组用户点击材料链接打开弹窗时，Odoo 检测到他没有 `write` 权限，弹窗会自动移除“编辑”和“保存”按钮，强制显示为只读模式。

### 5.2 控制“字段部分可见” (Field Groups)

如果你希望用户通过权限能看材料，但**不能看敏感字段**（如“采购底价”），可以使用字段组权限。

**方式 A：在 Python 模型中定义（推荐，全局生效）**

```python
# models/product_diecut.py

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    raw_material_unit_price = fields.Float(
        string="采购成本",
        # 仅“采购经理”或“成本主管”组可见
        groups="purchase.group_purchase_manager,diecut.group_cost_manager" 
    )
```

**方式 B：在 XML 视图中定义（仅界面隐藏）**

```xml
<field name="standard_price" groups="base.group_system"/>
```

*   **效果**：不属于指定组的用户打开弹窗时，这些敏感字段对他们完全不可见（直接消失）。
