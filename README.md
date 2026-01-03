# whm_Odoo_project
用于开发Odoo项目的github仓库

---

# Odoo 19 (Docker版) 项目常用命令指南

本项目目前运行在 **Docker** 环境中。所有的服务（Odoo 应用、PostgreSQL 数据库）都运行在容器内。

## 1. 快速开始 (Windows 推荐)

为了简化操作，根目录下提供了两个批处理脚本：

*   **`Start_Odoo.bat`** (双击运行)
    *   启动 Odoo 服务和数据库。
    *   自动打开日志窗口，方便查看报错。
    *   访问地址: [http://localhost:8070](http://localhost:8070)
*   **`Stop_Odoo.bat`** (双击运行)
    *   停止并移除容器，释放系统资源。

---

## 2. Docker 常用命令 (命令行)

如果你更喜欢在终端 (VS Code / PowerShell) 中手动操作，主要使用 `docker-compose` 命令。
**前提：请先进入 `.devcontainer` 目录：**
```powershell
cd .devcontainer
```

### 启动与停止
```powershell
# 启动服务 (后台运行)
docker-compose up -d

# 停止服务 (并移除容器)
docker-compose down

# 停止服务 (仅暂停，不移除)
docker-compose stop
```

### 查看日志
```powershell
# 查看实时日志 (按 Ctrl+C 退出)
docker-compose logs -f web

# 查看最近 50 行日志 (简略)
docker-compose logs -f --tail=50 web
```

### 重启服务
由于开启了开发模式，大部分代码修改会自动生效。如果遇到无法生效的情况（如修改了 `__manifest__.py` 或安全性文件）：
```powershell
docker-compose restart web
```

---

## 3. 进阶开发命令 (进入容器)

要在 Docker 内部执行 Odoo 命令（比如创建模块脚手架、运行 shell），需要使用 `docker exec` 进入容器。

### 进入 Odoo 容器终端
```powershell
docker exec -it devcontainer-web-1 /bin/bash
```

### 常用命令案例 (在容器内执行)

如果你已经在容器内，或者使用单行命令：

**1. 创建新模块 (Scaffold)**
```powershell
# 在主机上直接运行 (推荐)
# 在 custom_addons 目录下创建名为 my_new_module 的模块
docker exec devcontainer-web-1 odoo scaffold my_new_module /mnt/extra-addons
```

**2. 强制升级模块 (Update)**
如果网页端升级失败，可以尝试在命令行强制升级：
```powershell
# 这里的 -d odoo 记得改成你实际的数据库名
docker exec devcontainer-web-1 odoo -c /etc/odoo/odoo.conf -d odoo -u my_module_name
```

---

## 4. 目录结构说明

*   `.devcontainer/`: Docker 环境配置文件 (`docker-compose.yml`)。
*   `custom_addons/`: **开发工作区**。你编写的所有模块都在这里，实时同步到容器中。
*   `odoo/`: 官方源码 (仅供 PyCharm 索引和阅读，不要修改)。
*   `venv/`: 本地虚拟环境 (仅供 PyCharm 代码提示)。

## 5. 常见问题

*   **端口被占用**：检查是否有其他 Odoo 实例在运行，确保 8070 和 5434 端口空闲。
*   **代码不生效**：尝试重启页面，或者运行 `docker-compose restart web`。
*   **数据库连接失败**：使用 PyCharm 连接数据库时，请使用端口 `5434`，用户 `odoo`，密码 `odoo`。
