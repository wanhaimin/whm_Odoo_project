---
description: Odoo 闭环开发模式：编码 → 部署 → 浏览器验证 → 修复 → 再验证
---

# Odoo 闭环开发工作流

## 环境信息
- **Odoo 地址**: http://localhost:8070
- **登录账号**: admin
- **登录密码**: admin
- **数据库名称**: odoo
- **Docker 容器名**: my_odoo_project_devcontainer-web-1
- **自定义模块路径**: custom_addons/diecut
- **模块升级命令**: `docker exec my_odoo_project_devcontainer-web-1 odoo -d odoo -u diecut --stop-after-init --db_host=db --db_user=odoo --db_password=odoo`
- **重启容器命令**: `docker restart my_odoo_project_devcontainer-web-1` (或者 `docker restart 2f4989397555`)

## 开发流程（严格按顺序执行）

### 第一步：理解需求
- 仔细阅读用户的需求描述和截图
- 如果需求不清晰，先提问确认，不要猜测

### 第二步：编写代码
- 修改 Python 模型（models/）、XML 视图（views/）、JS 前端等
- 遵循 Odoo 19 开发规范（参见全局规则）
- 如有新模型必须添加 security/ir.model.access.csv 权限

### 第三步：部署更新
// turbo
- 首先执行重启容器命令：`docker restart my_odoo_project_devcontainer-web-1`
- 接着执行模块升级命令，等待完成
- 检查退出码，如果 exit code != 0：
  - 查看完整错误日志
  - 修复代码问题
  - 重新执行升级，直到 exit code = 0

### 第四步：浏览器验证
- 使用 browser_subagent 打开浏览器
- 访问 http://localhost:8070
- 如果未登录：输入账号密码登录
- 导航到相关页面，验证功能是否正确
- 截图记录当前状态
- 自动Allow

### 第五步：问题修复循环
- 如果浏览器中发现问题：
  1. 分析问题原因
  2. 回到第二步修改代码
  3. 重新执行第三步部署
  4. 重新执行第四步浏览器验证
- 重复直到功能完全正确

### 第六步：向用户汇报
- 说明做了什么修改
- 展示浏览器验证结果
- 如有录屏，提供给用户