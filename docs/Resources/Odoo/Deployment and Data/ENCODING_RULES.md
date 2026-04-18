---
type: resource
status: active
area: "Odoo"
topic: "Deployment and Data"
reviewed: 2026-04-18
---

# 中文编码规则

## 目标

本项目所有中文内容都以 UTF-8 作为唯一标准写入格式，避免在 Windows、PowerShell、Docker、Odoo shell、XML 视图、AI/TDS 草稿之间传递时出现乱码。

## 核心规则

1. 仓库文件统一保存为 UTF-8。
2. 不要通过 PowerShell 直接把中文注入到源码、`odoo shell`、数据库脚本或 `docker exec ... python -c`。
3. 修改中文 XML、字段标题、菜单标题、说明文案时，只直接修改 UTF-8 文件，再通过模块升级刷新数据库。
4. 如果必须通过脚本写中文到数据库或 ORM：
   - 脚本本体保持 ASCII
   - 中文使用 `\\uXXXX` 或从 UTF-8 文件读取
5. 页面中文是否正常，最终以数据库真值和浏览器强刷后的结果为准，不以 PowerShell 终端输出判断。

## 高风险路径

修改以下目录时，默认按高风险中文写入处理：

- `custom_addons/diecut/views/`
- `custom_addons/diecut/models/catalog_*.py`
- `custom_addons/diecut/wizard/`
- `custom_addons/diecut/scripts/tds_import_drafts/`
- `custom_addons/diecut/data/`

## 安全修改流程

### 1. 修改 UTF-8 文件

- 直接修改源码文件
- 不要在 PowerShell heredoc、`python -c`、`odoo shell` 内联脚本里直接写中文

### 2. 跑编码扫描

```powershell
py -3 C:\Users\Lenovo\.codex\skills\encoding-guard\scripts\scan_encoding_issues.py E:\workspace\my_odoo_project
```

如果是大范围改动，至少覆盖：

- `custom_addons/diecut/views/`
- `custom_addons/diecut/models/`
- `custom_addons/diecut/static/`

### 3. 升级模块

```powershell
docker exec my_odoo_project_devcontainer-web-1 odoo -d odoo -u diecut --stop-after-init --db_host=db --db_user=odoo --db_password=odoo
```

### 4. 查数据库真值

重点检查：

- `ir_ui_view.arch_db`
- `ir_model_fields.field_description`

检查时重点关注：

- `????`
- 明显 mojibake
- 本应为中文但出现半角符号噪音的标题

示例：

```powershell
@'
import psycopg2
conn = psycopg2.connect(host='db', dbname='odoo', user='odoo', password='odoo')
cur = conn.cursor()
cur.execute("select id, name from ir_ui_view where name ilike '%catalog.item%' order by id desc limit 10")
for row in cur.fetchall():
    print(row)
conn.close()
'@ | docker exec -i my_odoo_project_devcontainer-web-1 python3 -
```

### 5. 浏览器强刷验收

- 打开对应页面
- 使用 `Ctrl+F5` 强刷
- 再确认中文标题、字段名、标签、HTML 说明文本是否正常

## 禁止做法

- PowerShell heredoc 中直接写中文再 pipe 给 Python 或 Odoo
- 用 shell 重定向临时拼中文 XML / JSON
- 直接在 `docker exec ... python -c` 中硬塞中文字符串
- 终端里看到中文正常，就认为数据库和页面一定正常

## 推荐做法

- 改 XML：直接改 UTF-8 文件
- 改字段标题：直接改 Python 源码中的 `string`
- 改数据库中文：从 UTF-8 文件读取，或用 `\\uXXXX`
- 批量修复中文：写 ASCII Python 脚本，由脚本生成中文内容

## 项目约定

- 中文写入安全路径优先级：
  1. UTF-8 源码文件
  2. ASCII 脚本 + `\\uXXXX`
  3. UTF-8 草稿文件导入
- 不再把 PowerShell 直注中文作为正式可接受方案

