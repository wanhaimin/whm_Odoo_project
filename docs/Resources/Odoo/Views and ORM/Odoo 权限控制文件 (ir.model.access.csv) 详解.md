---
type: resource
status: active
area: "Odoo"
topic: "Views and ORM"
reviewed: 2026-04-18
---

# Odoo 权限控制文件 (ir.model.access.csv) 详解

这张表就像是公司的“门禁卡系统”，哪怕您造了豪宅 (Model)，没配门禁卡 (Access)，谁也进不去。

| 字段 (Column) | 含义 (Meaning) | 怎么填 (How to fill) | 例子 |
| :--- | :--- | :--- | :--- |
| **id** | **这条规则的身份证号** | **随便填**，只要全系统唯一就行。推荐格式：`access_模型名_角色名`。 | `access_diecut_mold_user` |
| **name** | **规则的名字** | **随便填**，给人看的，方便以后查。 | `diecut.mold.user.access` |
| **model_id:id** | **要管哪个模型？** | **固定格式**：`模块名.model_把点换成下划线的模型名`。这是最容易填错的地方！ | `diecut_custom.model_diecut_mold` |
| **group_id:id** | **谁能用？(用户组)** | 指向一个具体的 **“用户组 ID”**。 <br> - `base.group_user`: 只要是内部员工都能用。<br> - `base.group_system`: 只有超级管理员能用。<br> - `base.group_public`: 连没登录的路人都能用。<br> - **留空**: 全世界所有人都能用（极其危险！）。 | `base.group_user` |
| **perm_read** | **能看吗？** | `1` = 能, `0` = 不能 | `1` |
| **perm_write** | **能改吗？** | `1` = 能, `0` = 不能 | `1` |
| **perm_create** | **能新建吗？** | `1` = 能, `0` = 不能 | `1` |
| **perm_unlink** | **能删吗？** | `1` = 能, `0` = 不能 | `0` (很多时候我们不想让员工删数据) |

---

### 实战示例

**场景 1：刀模数据，我想让所有员工能看、能改、能建、能删。**
```csv
access_diecut_mold_all,Diecut Mold All,diecut_custom.model_diecut_mold,base.group_user,1,1,1,1
```

**场景 2：刀模数据，只允许管理员删，普通员工只能看和改，不能删。**
这就需要写**两条**规则：

1. **普通员工 (User)**: 不能删 (0)
```csv
access_diecut_mold_user,User Access,diecut_custom.model_diecut_mold,base.group_user,1,1,1,0
```

2. **管理员 (Manager)**: 啥都能干 (1)
```csv
access_diecut_mold_manager,Manager Access,diecut_custom.model_diecut_mold,base.group_system,1,1,1,1
```
*(Odoo 会自动把权限叠加，如果您既是员工又是管理员，您就拥有了两者的并集权限)*。
