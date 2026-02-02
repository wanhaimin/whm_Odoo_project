---
description: 升级 Odoo 模块 (diecut_custom)
---

# 升级 Odoo 模块

在修改完代码后，执行以下命令升级模块使更改生效。

## 升级命令

// turbo
```powershell
docker-compose exec web odoo -d odoo -u diecut_custom --stop-after-init --db_host=db --db_user=odoo --db_password=odoo
```

工作目录: `e:\whm_Odoo_project\.devcontainer`

## 参数说明

| 参数                | 说明                           |
| ------------------- | ------------------------------ |
| `-d odoo`           | 数据库名称                     |
| `-u diecut_custom`  | 要升级的模块名称               |
| `--stop-after-init` | 升级完成后停止，不进入交互模式 |

## 升级多个模块

如需同时升级多个模块，用逗号分隔：

```powershell
docker-compose exec web odoo -d odoo -u diecut_custom,my_material_list --stop-after-init
```

## 注意事项

1. 确保 Odoo Docker 容器正在运行
2. 升级完成后刷新浏览器页面
3. 如果添加了新字段，升级会自动创建数据库列
4. 序列配置 (noupdate="1") 的更改需要在 Odoo 后台手动修改
