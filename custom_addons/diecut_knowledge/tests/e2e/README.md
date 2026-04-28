# diecut_knowledge E2E 测试

用 Playwright 驱动浏览器，对 `diecut_knowledge` 模块做端到端冒烟测试。

## 运行

前提：Odoo 已在 `http://localhost:8070` 运行（默认 docker compose 启动），账号 admin/admin。

```bash
# 默认 headless（无 UI），最快
.venv/Scripts/python.exe custom_addons/diecut_knowledge/tests/e2e/smoke.py

# 调试模式：显示浏览器、放慢操作
HEADLESS=0 SLOWMO_MS=300 .venv/Scripts/python.exe custom_addons/diecut_knowledge/tests/e2e/smoke.py
```

## 一键 Dev Loop

`scripts/dev_loop.py` 把"升级模块 + 跑 e2e"绑成一个命令：

```bash
.venv/Scripts/python.exe custom_addons/diecut_knowledge/scripts/dev_loop.py
```

## 测试覆盖

| 步骤 | 验证点 |
|---|---|
| 登录 | admin 凭据可用 |
| 行业知识库菜单 | 顶级菜单 + 文章 kanban 正常加载 |
| 5 大分类 | 种子数据完整：材料选型/模切工艺/刀模设计/行业标准/客户问答库 |
| 创建文章 | name/category/content_html 字段可写 |
| 状态机 | 草稿 → 评审 → 退回草稿 → 发布 工作流按钮 |
| 同步按钮 | 发布后「立即同步到 Dify」「加入同步队列」按钮出现 |
| 设置页 | Dify API 配置块可达 |
| 同步日志 | 菜单可达 |

截图保存到 `output/playwright/diecut_knowledge/` 下，按时间戳命名。

## 环境变量

| 变量 | 默认值 |
|---|---|
| `ODOO_URL` | `http://localhost:8070` |
| `ODOO_DB` | `odoo` |
| `ODOO_LOGIN` | `admin` |
| `ODOO_PASSWORD` | `admin` |
| `HEADLESS` | `1`（CI 模式） |
| `SLOWMO_MS` | `0` |
