# whm_Odoo_project
用于开发Odoo项目的github仓库

---

# Odoo 项目常用命令指南

## 1. 环境准备
在运行任何命令之前，请确保已激活 Python 虚拟环境。

**PowerShell:**
```powershell
.\venv\Scripts\Activate.ps1
```

**CMD:**
```cmd
.\venv\Scripts\activate.bat
```

---

## 2. 启动 Odoo
最常用的启动命令，使用配置文件运行：

```powershell
python odoo/odoo-bin -c odoo.conf
```

---

## 3. 常用开发参数

### 更新模块 (-u)
当你修改了模块代码（尤其是 Python 文件或 XML 视图）后，需要更新模块才能生效。
`-u` 后面跟模块名称，多个模块用逗号分隔。

```powershell
# 更新所有模块（一般不建议，太慢）
python odoo/odoo-bin -c odoo.conf -u all

# 更新指定模块（例如 my_module_a）
python odoo/odoo-bin -c odoo.conf -u my_module_a
```

### 初始化/安装模块 (-i)
如果是一个全新的模块，从未安装过，使用 `-i` 进行安装。

```powershell
python odoo/odoo-bin -c odoo.conf -i my_module_a
```

### 指定数据库 (-d)
如果你的本地有多个数据库，可以使用 `-d` 指定要操作的那个。

```powershell
python odoo/odoo-bin -c odoo.conf -d my_odoo_db
```

### 开发模式 (--dev)
我们在配置文件中已经设置了 `dev_mode = reload`，这会在 Python 代码修改时自动重启服务，并在 XML 修改时直接读取文件。
命令行手动开启方式：

```powershell
python odoo/odoo-bin -c odoo.conf --dev=all
```

---
## 4. 目录结构说明
- `odoo/`: 官方源代码
- `custom_addons/`: 你自己开发的模块放在这里
- `odoo.conf`: 配置文件（数据库连接、端口等）
- `venv/`: Python 虚拟环境

