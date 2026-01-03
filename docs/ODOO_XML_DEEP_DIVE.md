# Odoo XML 深度透析：原理与实战 (Deep Dive into XML Architecture)

很多初学者觉得 XML 简单又难。简单是因为标签就那么几个，难是因为**“不知道为什么要这么写”**以及**“不知道还有那些隐藏写法”**。如果之前的版本太浅，这次我们将深入 Odoo 的**底层 Render 机制**，拆解每一个 TAG 背后的含义。

---

## 第一章：视图的骨架 (View Architecture)

在 Odoo 中，XML 不是用来“写代码”的，它是用来**“描述结构”**的。Odoo 的前端（JavaScript 框架 "Owl"）读取这些 XML，然后动态渲染成 HTML 页面。

### 1. `<record>` 到底是什么？
XML 文件里那一堆 `<record id="..." model="...">` 其实是在**执行数据库 INSERT 操作**。

```xml
<record id="view_mold_form" model="ir.ui.view">
    <field name="name">diecut.mold.form</field>
    <field name="model">diecut.mold</field>
    <field name="arch" type="xml"> ... </field>
</record>
```
*   **解释**：这句话等同于 SQL `INSERT INTO ir_ui_view (name, model, arch) VALUES ('diecut.mold.form', 'diecut.mold', '...');`
*   **`arch` 字段**：这是核心。`arch` (Architecture) 字段里存了一大段字符串，这段字符串就是具体的布局代码。

---

## 第二章：表单视图的布局逻辑 (Form View Layout)

表单视图遵循 **“从上到下，从左到右”** 的流式布局。

### 1. 顶级容器
*   `<header>`: **状态栏**。固定在最顶部，不随滚动条滚动。通常放 `button` (工作流按钮) 和 `statusbar` (进度条)。
*   `<sheet>`: **白纸**。中间那个白色的卡片区域。所有业务数据都写在这里。
*   `<chatter>`: **聊天区**。底部的历史记录和发送邮件区域。

### 2. 核心排版神器：`<group>`
这是最令人困惑但也最常用的标签。它不仅是容器，更是**排版控制器**。

*   **如果不用 `<group>`**: 所有字段会把 label (字段名) 和 input (输入框) 混在一起，从左往右排，乱成一锅粥。
*   **用一层 `<group>`**: 强制换行。
*   **用两层 `<group>` (标准写法)**:
    ```xml
    <group>         <!-- 外层：容器 -->
        <group>     <!-- 左列 -->
            <field name="name"/>  <!-- label在左，input在右，整齐排列 -->
            <field name="code"/>
        </group>
        <group>     <!-- 右列 -->
            <field name="date"/>
            <field name="user_id"/>
        </group>
    </group>
    ```
    *   **原理**：Odoo 会自动把内层的每个 `<group>` 渲染成一列（Column）。如果您写了 3 个内层 group，页面就会变成 3 列布局。

### 3. 选项卡机制：`<notebook>` & `<page>`
当字段太多时，不仅要分列，还要分页。
```xml
<notebook>
    <page string="基本信息"> ... </page>
    <page string="财务信息" autofocus="autofocus"> ... </page> <!-- 默认选中这页 -->
</notebook>
```

---

## 第三章：字段的七十二变 (Field Attributes & Widgets)

同一个字段，加上不同的属性，就能呈现完全不同的样子。

### 1. 视觉装饰 (Widget)
*   **Selection 字段**:
    *   `widget="radio"`: 不显示下拉框，而是显示单选按钮 (● ○ ○)。
    *   `widget="priority"`: 显示星星 (⭐)，比如重要程度。
    *   `widget="statusbar"`: 显示进度条 (草稿 -> 进行中 -> 完成)。
*   **Boolean 字段**:
    *   `widget="boolean_toggle"`: 显示像手机设置里的那个绿色开关，而不是丑陋的复选框。
*   **Char/Text 字段**:
    *   `widget="email"`: 变成蓝色链接，点击自动发邮件。
    *   `widget="phone"`: 手机端点击自动拨号。
    *   `widget="url"`: 点击打开网页。
    *   `widget="copy_clipboard"`: 旁边多一个复制按钮。
*   **Many2many 字段**:
    *   `widget="many2many_tags"`: 显示彩色胶囊标签。
    *   `widget="many2many_checkboxes"`: 显示一排复选框。

### 2. 行为控制 (Modifiers)
这些属性的值是 **Python 表达式 (Domain)**，这赋予了 XML 动态逻辑能力。

*   **`invisible="..."` (隐身术)**
    *   `invisible="mold_type == 'wood'"`: 如果是木板模，这行就消失。
    *   *注意*：如果隐身的字段是必填的，Odoo 会自动取消它的必填校验，非常智能。
*   **`readonly="..."` (定身术)**
    *   `readonly="status == 'done'"`: 如果单据已完成，这行变灰，不能改。
*   **`required="..."` (强迫术)**
    *   `required="price > 1000"`: 如果价格大于 1000，备注必须填。

---

## 第四章：列表视图的高级玩法 (List View)

列表不仅仅是把数据列出来，它有很多隐藏技能。

### 1. 颜色与样式
```xml
<!-- decoration-{颜色}: danger(红), info(蓝), warning(黄), success(绿), muted(灰), bf(加粗) -->
<list decoration-danger="price &lt; 0" decoration-bf="id != False">
```
*   如果价格小于 0，整行变红。
*   `&lt;` 是 `<` 的转义字符（XML 里不能直接写 `<`）。

### 2. 允许编辑 (Editable List)
默认点击列表行是打开详情页。如果您想**像 Excel 一样直接在列表里修改**：
```xml
<list editable="top"> <!-- 新建行出现在顶部 -->
<!-- 或 -->
<list editable="bottom"> <!-- 新建行出现在底部 -->
```

### 3. 可选显示的列 (Optional)
有些列不重要，但偶尔想看。
```xml
<field name="create_date" optional="hide"/> <!-- 默认隐藏，但用户可以在右上角三个点里勾选显示 -->
<field name="write_date" optional="show"/> <!-- 默认显示，但用户可以勾选隐藏 -->
```

---

## 第五章：上帝之手 —— XPath (继承与修改)

这是 Odoo 最难理解的部分，也是二次开发的核心。
*   **场景**：原生代码里有一个视图 A，非常复杂。你想在其中加一个字段，但不想（也不能）复制粘贴整个 A 的代码。
*   **做法**：你写一个“补丁”视图 B，告诉系统“把 B 贴在 A 上面”。

### 定位策略 (Locator)
必须精准定位到你想改的那个点。
1.  **按字段名找** `//field[@name='xxx']` (最常用)
2.  **按标签找** `//group` (如果不唯一，会只找第一个，风险大)
3.  **按属性找** `//page[@string='Note']`
4.  **组合拳** `//group[@name='main_info']/field[@name='partner_id']`

### 操作指令 (Position)
找到后，干什么？
1.  `after`: 在它屁股后面加。
2.  `before`: 在它前面加。
3.  `inside`: 塞到它肚子里（通常用于往 group 或 notebook 里插东西）。
4.  `replace`: **把它干掉，换成我的**。
    *   *高级用法*：如果内容留空 `<xpath ... position="replace"/>`，那就等于**删除**该元素。
5.  `attributes`: **只改属性，不改内容**。
    ```xml
    <xpath expr="//field[@name='phone']" position="attributes">
        <attribute name="required">1</attribute> <!-- 强行把电话变成必填 -->
        <attribute name="string">手机号</attribute> <!-- 强行改标签名 -->
    </xpath>
    ```

---

## 学习建议
不要试图背诵所有属性。
1.  **先抄**: 找一个类似的原生模块（比如 `sale`, `stock`），看它们的 `views/*.xml` 是怎么写的。
2.  **再改**: 试着改动其中一个参数（比如把 `invisible` 条件改反），看看效果。
3.  **最后悟**: 理解为什么 Odoo 要这么设计——为了**低代码**，用配置代替编程。
