---
description: 升级 Odoo 模块 (diecut_custom)
---

# 升级 Odoo 模块

执行以下命令升级 diecut 模块：

// turbo
```bash
docker exec my_odoo_project_devcontainer-web-1 odoo -d odoo -u diecut --stop-after-init --db_host=db --db_user=odoo --db_password=odoo
```

- 如果 exit code = 0：升级成功
- 如果 exit code != 0：查看日志排查错误
