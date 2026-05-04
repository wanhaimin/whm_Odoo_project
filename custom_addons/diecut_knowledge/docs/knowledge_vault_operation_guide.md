# Knowledge Vault 文件夹镜像操作指引

## 1. 这个功能解决什么问题

Knowledge Vault 是给知识管理模块增加的本地文件夹镜像层。

它的作用是：

- 用 `raw/inbox` 接收 PDF、TXT、Markdown 等原始资料。
- 用 `wiki/` 导出 Odoo Wiki 文章，方便 Obsidian / OpenClaw / LLM Agent 浏览和维护。
- Odoo 仍然负责审核、发布、权限、图谱、引用、材料目录关联和 Dify 同步。

核心原则：

```text
raw 文件夹 = 原始资料入口，不修改原文
wiki 文件夹 = Wiki Markdown 镜像，可用 Obsidian 浏览和编辑
Odoo = 正式知识库、审核发布中心
```

## 2. 推荐目录

建议把 Vault 放在项目外部目录，或者放在已被 `.gitignore` 忽略的位置。

如果 Odoo 运行在 Docker 容器里，设置页填写的是“容器内路径”，不是 Windows 路径。当前项目推荐使用：

```text
/mnt/extra-addons/.diecut_knowledge_vault
```

这个路径在 Windows 主机上通常对应：

```text
E:\workspace\my_odoo_project\custom_addons\.diecut_knowledge_vault
```

如果你是在非 Docker 的本机 Odoo 中运行，才可以直接使用 Windows 路径，例如：

```text
E:\workspace\knowledge_vault
```

如果希望 Vault 放在 `diecut_knowledge` 模块目录下，也可以填写：

```text
/mnt/extra-addons/diecut_knowledge/knowledge_vault
```

初始化后目录结构如下：

```text
knowledge_vault/
  AGENTS.md
  raw/
    inbox/
    processed/
    failed/
  wiki/
    index.md
    log.md
    brands/
    materials/
    applications/
    processes/
    faq/
    sources/
    concepts/
    comparisons/
    query-answers/
  assets/
```

## 3. 第一次配置

进入 Odoo：

```text
设置 -> 行业知识库 -> Knowledge Vault 文件夹镜像
```

填写：

```text
Vault 根目录 = /mnt/extra-addons/.diecut_knowledge_vault
Raw Inbox 扫描上限 = 20
```

然后点击：

```text
初始化目录
```

成功后，本地会生成 `raw/`、`wiki/`、`assets/` 和 `AGENTS.md`。

## 4. 导入原始资料

把资料放入：

```text
knowledge_vault/raw/inbox/
```

支持第一版文件类型：

- `.pdf`
- `.txt`
- `.md`
- `.markdown`

然后在 Odoo 设置页点击：

```text
扫描 Raw Inbox
```

系统会做这些事：

- 读取 `raw/inbox` 文件。
- 按文件 hash 去重。
- 创建 `编译源资料` 记录。
- PDF/TXT/MD 进入知识管理原始资料库。
- 成功处理的文件移动到 `raw/processed`。
- 失败文件移动到 `raw/failed`。

注意：

- 扫描后不会直接生成正式 Wiki。
- 扫描后也不会直接发布到 Dify。
- 资料会先进入 Ingest Plan / 人工确认 / 编译流程。

## 5. 编译 Wiki

资料进入 Odoo 后，进入：

```text
行业知识库 -> 编译源资料
```

打开对应资料，可以执行：

- 生成处理方案
- 解析原始资料
- 编译为 Wiki
- 确认方案并执行

建议流程：

```text
生成处理方案
-> 人工检查方案
-> 确认方案并执行
-> 检查生成的 Wiki
-> 发布或保持评审
```

如果是 TDS：

```text
编译 Wiki
+ 抽取材料参数草稿
+ 人工审核后写入材料选型库
```

## 6. 导出 Wiki 到 Obsidian

在设置页点击：

```text
导出 Wiki
```

系统会把 Odoo 中 `review` / `published` 状态的 Wiki 文章导出到：

```text
knowledge_vault/wiki/
```

每篇文章会生成一个 Markdown 文件，并包含 frontmatter，例如：

```yaml
---
odoo_article_id: 123
title: 多孔陶瓷吸盘
state: published
compile_source: source_document
wiki_page_type: source_summary
wiki_slug: 多孔陶瓷吸盘
compiled_at: 2026-05-01T12:00:00
source_document_id: 45
source_item_id:
---
```

文章中的相关页面会写成 Obsidian 双链：

```markdown
[[多孔陶瓷吸盘|多孔陶瓷吸盘]]
[[3m-9448|3M 9448]]
```

## 7. 用 Obsidian 打开

打开 Obsidian，选择：

```text
Open folder as vault
```

选择：

```text
E:\workspace\knowledge_vault
```

你可以：

- 浏览 `wiki/index.md`
- 查看 Graph View
- 搜索 Wiki
- 阅读每个 Markdown 页面
- 查看 `AGENTS.md` 了解 LLM 规则

## 8. 在 Obsidian 修改 Wiki

可以修改 `wiki/*.md`，但要注意：

- 不要修改 `raw/` 原始文件。
- 不要删除 frontmatter 中的 `odoo_article_id`。
- 尽量保留 `wiki_slug`。
- 新增关联时使用 Obsidian 双链：

```markdown
[[wiki-slug|页面标题]]
```

修改完成后，回到 Odoo 设置页点击：

```text
导入 Wiki 修改
```

系统会：

- 检测 Markdown hash 变化。
- 回写到 Odoo `content_md`。
- 如果原文章是 `published`，会自动退回 `review`。
- 解析 Markdown 双链并同步到 Odoo 图谱链接。
- 设置 Dify 同步状态为待处理。

重点：Obsidian 修改不会直接覆盖正式发布内容，必须重新审核。

## 9. 什么情况下不要直接改文件

不要在文件夹里直接做这些事：

- 修改 `raw/processed` 里的 PDF 原件。
- 删除 `wiki/*.md` 试图删除 Odoo 文章。
- 手动改 frontmatter 的 `odoo_article_id`。
- 大批量重命名 Markdown 文件。
- 把未经审核的 AI 回答直接复制成 published Wiki。

如果要删除或归档知识，建议在 Odoo 里操作。

## 10. Cron 是否要打开

第一版默认不自动开启 cron。

建议先手动使用：

- 初始化目录
- 扫描 Raw Inbox
- 导出 Wiki
- 导入 Wiki 修改

确认流程稳定后，再考虑启用：

- `知识库 Vault：扫描 Raw Inbox`
- `知识库 Vault：导出 Wiki Markdown`
- `知识库 Vault：导入 Wiki 修改`

建议不要一开始就打开自动导入，避免 Obsidian 临时编辑内容被误导入。

## 11. 推荐日常流程

### 新资料入库

```text
把 PDF/TXT/MD 放入 raw/inbox
-> Odoo 点击“扫描 Raw Inbox”
-> 打开编译源资料
-> 生成处理方案
-> 人工确认
-> 编译 Wiki
-> 审核发布
-> 导出 Wiki
-> Obsidian 查看图谱
```

### 维护 Wiki

```text
Odoo 导出 Wiki
-> Obsidian 阅读和补充双链
-> Odoo 导入 Wiki 修改
-> 审核变更
-> 发布
-> Dify 同步
```

### AI 顾问沉淀

```text
AI 顾问问答
-> 点赞或保存为知识
-> 生成 review 草稿
-> 人工审核
-> 接入 Wiki 图谱
-> 发布后同步 Dify
```

## 12. 目前限制

第一版不是完整 Git/Obsidian 双向协作系统，还有这些限制：

- 不做复杂多人冲突合并。
- 文件删除不会自动删除 Odoo 文章。
- Markdown 导入只做基础 frontmatter 和双链解析。
- raw 文件只支持 PDF/TXT/MD/Markdown。
- published 文章被 Obsidian 修改后会回到 review，需要人工确认。

## 13. 最佳实践

- raw 文件名尽量清楚，例如 `3M-9448A-TDS.pdf`。
- 一个资料一个文件，不要把很多无关资料合并成一个 PDF。
- 重要事实必须保留来源页码或原文片段。
- Wiki 文章不要太长，长资料应拆成品牌页、型号页、应用页、FAQ 页。
- 每次导入后看一下 Odoo 图谱链接，避免错误标题污染图谱。
- 客户和员工只开放 `published` 内容。
