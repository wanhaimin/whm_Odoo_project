# Odoo 权限配置与组织架构设置指南

本文档总结了在 Odoo 中进行权限管理和组织架构设置的核心知识点，旨在帮助开发者和管理员理解如何构建安全、灵活的权限体系。

---

## 1. 组织架构 (Organization Structure)

在配置权限之前，首先需要理解 Odoo 如何映射现实世界的组织架构。

### 1.1 公司 (Companies)
- **多公司架构 (Multi-Company)**: Odoo 原生支持多公司环境。
- **数据隔离**: 不同公司之间的数据默认是隔离的（通过 `company_id` 字段和记录规则）。
- **父子关系**: 设置父子公司关系，不仅方便财务合并，也能定义数据共享的层级。

### 1.2 部门 (Departments)
- **HR 模块基础**: 虽然主要用于 HR，但在审批流（如请假、报销）中非常重要。
- **层级管理**: 每个部门可以设置上级部门和部门经理，这通常用于定义审批权限。

### 1.3 用户 (Users)
- **关联员工**: 用户 (res.users) 是登录账号，员工 (hr.employee) 是人事档案。两者需关联才能通过“部门经理”查找上级。
- **关联公司**: 每个用户属于一个“默认公司”，但可以访问多个“允许的公司”。

---

## 2. 权限控制的三层体系

Odoo 的权限控制可以想象成一个三层的漏斗，层层过滤。

### 第一层：功能访问 (Menu & View Access) -> "能不能看到菜单"
- **菜单隐藏**: 如果用户不属于某个菜单所要求的用户组，该菜单对用户完全不可见。
- **视图元素**: 某些按钮或页面元素可以通过 `groups="base.group_no_one"` 属性隐藏。

### 第二层：对象访问 (Access Rights / ACL) -> "能不能操作模型"
这是最基础的 CRUD（创建、读取、更新、删除）权限控制，定义在 `security/ir.model.access.csv` 文件中。

- **配置方式**: 为每个“模型”分配给特定的“用户组”相应的 CRUD 权限 (1=允许, 0=禁止)。
- **示例**:
  ```csv
  id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
  access_diecut_user,diecut.quote user,model_diecut_quote,group_diecut_user,1,1,1,0
  ```
  *(解释：diecut_user 组对 diecut.quote 模型可读、可写、可创，但不可删)*

### 第三层：记录规则 (Record Rules) -> "能不能看到这条数据"
这是最细粒度的控制，决定用户在拥有模型访问权的前提下，具体能看到**哪些行**数据。

- **应用场景**:
  - “业务员只能看自己的单据”
  - “经理可以看本部门所有人的单据”
  - “多公司数据隔离”
- **配置方式 (XML)**: 定义 Domain 过滤规则。
- **示例 (只看自己的)**:
  ```xml
  <record id="rule_diecut_quote_personal" model="ir.rule">
      <field name="name">个人报价单</field>
      <field name="model_id" ref="model_diecut_quote"/>
      <field name="groups" eval="[(4, ref('group_diecut_user'))]"/>
      <field name="domain_force">[('user_id', '=', user.id)]</field>
  </record>
  ```

---

## 3. 用户组 (Groups) 的设计策略

用户组是权限管理的核心枢纽。Odoo 将权限赋予“组”，再将“用户”添加到“组”中。

### 3.1 用户组的分类
1.  **内部组 (Internal Users)**: 系统默认的基础组，区分内部员工和门户用户（客户/供应商）。
2.  **角色组 (Role Groups)**: 根据业务角色定义，如“模切报价员”、“模切审核经理”。
3.  **功能组 (Technical Features)**: 控制特定按钮或字段的可见性，如“显示会计分录”、“允许应用折扣”。

### 3.2 继承机制 (Inheritance)
- **组的继承**: 高级组通常继承低级组的权限。如果“经理组”继承了“员工组”，那么经理自动拥有员工的所有权限，无需重复配置。
- **隐含组 (Implied IDs)**: 在定义组时，通过 `implied_ids` 字段指定继承关系。

### 3.3 最佳实践
- **金字塔结构**:
  - `User`: 普通用户，基本的 CRUD 权限，Record Rule 限制为“个人”。
  - `Manager`: 经理，完全的 CRUD 权限，Record Rule 限制为“本部门”或“全公司”。
  - `Administrator`: 管理员，配置权限，无视规则。

---

## 4. 字段级权限 (Field Level Access)

控制特定字段的可见性，即使这行数据对用户可见。

- **Python 定义**: `field_name = fields.Char(groups="base.group_system")`
- **XML 视图**: `<field name="cost_price" groups="sales_team.group_sale_manager"/>`
- **效果**: 不在组内的用户，无论是在表单还是列表中，该字段都会彻底消失，仿佛不存在。

---

## 5. 项目中的实施步骤

1.  **梳理角色**: 画出公司的组织架构图，列出所有需要登录系统的角色（如：报价员、工程主管、财务、总经理）。
2.  **定义 User/Manager 组**: 在 `security/security.xml` 中创建这些组。
3.  **配置 ACL**: 在 `ir.model.access.csv` 中分配每个模型的基础 CRUD 权限。
4.  **配置 Record Rules**: 针对需要隔离数据的模型，编写 XML 规则（如多公司规则、个人数据规则）。
5.  **分配菜单**: 将菜单项绑定到对应的组。
6.  **测试**: 创建不同角色的测试账号，登录验证“能不能看”、“能不能改”、“能不能删”。

---

> **提示**: 在开发初期，可以使用 Odoo 的“超级管理员” (Admin) 进行所有操作。但是在交付前，务必使用普通权限账号进行完整测试，以避免“管理员能用，员工报错”的常见问题。
