---
description: Odoo 浏览器优先开发模式：先复现定位，再编码部署，再回归验证
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

## 浏览器工具选择

### Playwright 适用场景
- 适合复现用户操作路径：登录、点菜单、切换列表/表单、点击按钮、填写字段、保存、截图
- 适合回归验证：修复后重复同一路径，确认功能恢复正常
- 适合轻量定位：确认问题页面、入口菜单、模型、action、基础报错表现

### Chrome DevTools 适用场景
- 适合深入排查前端问题：console 报错、RPC/network 异常、DOM 结构、CSS 样式、事件绑定、性能问题
- 适合回答“为什么页面现在坏了”，而不是只回答“能不能复现”
- 适合在 Playwright 已经定位到具体页面后，对单个问题做精确观察

### 默认使用规则
- 默认先用 Playwright 做轻量复现和流程验证
- 如果问题涉及 JS 报错、RPC 失败、元素不显示、样式错位、事件不触发，再进入 Chrome DevTools
- 修复完成后，优先回到 Playwright 做同路径回归，而不是只看 DevTools 里错误消失

### 第一步：理解需求
- 仔细阅读用户的需求描述和截图
- 如果需求不清晰，先提问确认，不要猜测

### 第二步：浏览器轻量复现与定位
- 使用浏览器打开 http://localhost:8070
- 如果未登录：输入账号密码登录
- 优先进入当前需求对应的模型页面、菜单入口或 action，而不是先猜代码位置
- 默认优先用 Playwright 复现；只有需要深入看 console / network / DOM 时再切到 Chrome DevTools
- 只记录轻量信息：
  - 当前模型 / 菜单 / action
  - URL hash
  - 关键报错或异常表现
  - 1 张截图结论
- 除非问题必须深入排查，否则不要抓取整页 DOM、全量 console、全量 network 日志，避免无效 token 消耗

### 第三步：从页面回查代码
- 根据浏览器定位结果，反查相关 Python 模型、XML 视图、JS patch、菜单、action、domain
- 先确认问题属于哪一层：
  - 视图结构 / XML
  - Owl / JS 前端交互
  - action / menu / domain / context
  - 权限 / 数据状态
  - Python ORM / 计算逻辑

### 第四步：编写代码
- 修改 Python 模型（models/）、XML 视图（views/）、JS 前端等
- 遵循 Odoo 19 开发规范（参见全局规则）
- 如有新模型必须添加 security/ir.model.access.csv 权限

### 第五步：部署更新
// turbo
- 首先执行重启容器命令：`docker restart my_odoo_project_devcontainer-web-1`
- 接着执行模块升级命令，等待完成
- 检查退出码，如果 exit code != 0：
  - 查看完整错误日志
  - 修复代码问题
  - 重新执行升级，直到 exit code = 0

### 第六步：浏览器回归验证
- 访问 http://localhost:8070
- 回到同一页面、同一记录、同一操作路径，验证功能是否正确
- 如有必要，再看最小范围的 console / RPC 错误
- 截图记录修复后的状态

### 第七步：问题修复循环
- 如果浏览器中发现问题：
  1. 先判断是否已能从当前页面继续定位
  2. 回到第三步继续回查代码
  3. 再执行第四步到第六步
- 重复直到功能完全正确

### 第八步：向用户汇报
- 说明做了什么修改
- 展示浏览器复现点与浏览器验证结果
- 如有录屏，提供给用户
