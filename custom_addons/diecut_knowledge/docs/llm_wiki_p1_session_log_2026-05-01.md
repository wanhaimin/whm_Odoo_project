# LLM Wiki P1 Session Log - 2026-05-01

## 背景

本轮会话围绕 `diecut_knowledge` 的知识管理架构展开，核心目标是把系统从普通 RAG / Dify 检索，逐步调整为更接近 Karpathy `LLM Wiki` 思路的知识管理模式。

关键诉求：

- 知识管理是行业知识沉淀中心，保存加工经验、材料推荐、应用场景、客户问答、PDF/TDS/选型指南等原始资料。
- 材料选型库保存结构化事实数据，例如品牌、型号、厚度、胶系、基材、TDS 参数和选型标签。
- `chatter_ai_assistant` 是和 Odoo 对话、调用 OpenClaw、查询数据和触发任务的智能入口。
- Dify 主要负责已发布知识的检索和问答消费，不作为知识生产源。
- OpenClaw / LLM 负责重任务：PDF/TDS 解析、长文编译、Wiki 更新、交叉引用和知识图谱维护。

## 重要认知

### Karpathy LLM Wiki 的核心不是上传文档

Karpathy 原文强调三层：

```text
raw sources -> wiki -> schema
```

其中：

- `raw sources` 是不可修改的原始资料。
- `wiki` 是 LLM 维护的持久知识层。
- `schema` 是约束 LLM 如何 ingest、query、lint、更新索引和日志的总规则。

关键差异不是“能否读取 PDF”，而是：

- LLM 不是每次问答时重新从 raw 文档里临时拼答案。
- LLM 会把资料编译成稳定 Wiki，并持续维护关联、冲突、引用和索引。
- 新资料进入时，要读取旧 Wiki，决定新建、更新、合并或建立交叉引用。
- 好的问答结果也可以沉淀回 Wiki，但必须经过审核，避免错误知识污染正式库。

### Prompt 和 Schema 的关系

本轮明确了：

- `schema` 是长期稳定的知识库宪法。
- `prompt` 是具体任务模板，例如生成 ingest plan、生成 wiki patch、做 QA、做 lint。
- skill 是执行能力或工具能力，例如 PDF 解析、TDS 抽取、Odoo 写库、浏览器验证。

因此 P1 不应只是“外置 prompt”，而应升级为 `Schema-first`：

```text
schema/llm_wiki_schema.md
-> prompts/*.md
-> LLM structured JSON
-> Odoo validation/write
-> Wiki / Graph / Log / Dify
```

## 架构决策

### 统一入口

所有原始资料进入知识管理：

```text
PDF / TDS / 选型指南 / 网页 / 经验 / 客户问答
-> 编译源资料
-> Ingest Plan
-> 人工确认
-> 解析
-> LLM 编译 Wiki / FAQ / 图谱关系
-> 审核 / 发布
-> Dify 同步
```

TDS 资料额外分支：

```text
TDS source
-> 参数抽取
-> 结构化草稿
-> 人工审核
-> 材料选型库
```

### AI 顾问定位

AI 顾问不是知识生产主流程，而是实时问答和发现知识缺口的入口：

- 优先查已编译 Wiki。
- Wiki 不足时查 raw source 和材料目录，给出临时答案并标注来源层级。
- 使用 raw/catalog 作答时，生成待编译任务。
- 用户点赞或手动保存的回答进入待审核知识草稿，不自动发布。

### 图谱是核心能力

每次新增 Wiki 不应孤立生成。编译前必须参考旧 Wiki 索引和候选页面，输出：

- 新建页面。
- 更新页面。
- 关联页面。
- 冲突关系。
- 需要人工审核的风险。

Odoo 中的 `diecut.kb.wiki.link` 是 Obsidian `[[links]]` 的数据库映射。

## 本轮实施内容

### 1. Canonical Schema

新增：

```text
custom_addons/diecut_knowledge/schema/llm_wiki_schema.md
```

该文件作为最高规则源，定义：

- raw source 不可修改。
- Wiki 页面格式。
- 来源引用规则。
- 图谱链接规则。
- Ingest / Query / Lint 工作流。
- 人工审核规则。
- LLM 输出必须是结构化 JSON。
- 不允许输出 `<think>` 或把自由文本直接写库。

### 2. 外置任务 Prompt

新增：

```text
custom_addons/diecut_knowledge/prompts/ingest_plan.md
custom_addons/diecut_knowledge/prompts/wiki_patch.md
custom_addons/diecut_knowledge/prompts/wiki_graph_patch.md
custom_addons/diecut_knowledge/prompts/catalog_item_wiki.md
custom_addons/diecut_knowledge/prompts/comparison_wiki.md
custom_addons/diecut_knowledge/prompts/brand_overview.md
custom_addons/diecut_knowledge/prompts/ai_advisor_qa.md
custom_addons/diecut_knowledge/prompts/wiki_retrieval.md
custom_addons/diecut_knowledge/prompts/wiki_agent_decision.md
custom_addons/diecut_knowledge/prompts/wiki_lint.md
```

每个 prompt 只描述当前任务，并声明遵守 `llm_wiki_schema.md`。

### 3. Prompt Loader

新增：

```text
custom_addons/diecut_knowledge/services/prompt_loader.py
```

提供：

```python
load_schema()
load_prompt(name, default="")
build_system_prompt(task_name, default="")
invalidate_cache()
```

`build_system_prompt()` 会拼接：

```text
llm_wiki_schema.md + prompts/{task_name}.md
```

文件不存在时记录 warning 并使用 fallback。

### 4. 编译器和检索器接入 Schema-first

修改：

```text
custom_addons/diecut_knowledge/services/kb_compiler.py
custom_addons/diecut_knowledge/services/kb_searcher.py
```

变化：

- 原有大段硬编码 prompt 改为 `_DEFAULT_*` 兜底。
- 编译任务改用 `build_system_prompt(...)`。
- Wiki 问答、Agent decision、Wiki retrieval 也接入 schema + prompt。
- 保持现有 Dify/OpenClaw 调用方式不变。

### 5. Wiki Index 总目录文章

新增：

```text
custom_addons/diecut_knowledge/services/kb_index_builder.py
```

新增 `compile_source`：

```text
wiki_index = 知识库目录
```

新增方法：

```python
env["diecut.kb.article"].cron_refresh_wiki_index()
```

行为：

- 创建或更新 `知识库总目录`。
- 按分类列出 `review` / `published` 文章。
- 排除目录自身。
- 每条包括文章名、页面类型、来源类型、摘要、入链/出链数量。
- 使用 `skip_auto_enrich=True` 避免递归 enrichment。
- 更新后设置 `sync_status="pending"`。

新增 cron：

```text
每 6 小时刷新一次 Wiki Index
```

### 6. AI Advisor 点赞沉淀

后端新增：

```text
/diecut_knowledge/ai/like_answer
```

行为：

- 复用 `_save_answer_as_article()`。
- 创建 `compile_source="ai_answer"`、`state="review"` 的知识草稿。
- 不自动发布。
- 成功后返回文章 ID。

补充：

- `_save_answer_as_article()` 在 enrichment 后调用 `KbLinter(env).lint_article(article)`。
- lint 失败只记录日志，不影响保存。

前端修改：

```text
static/src/js/ai_advisor_drawer.js
static/src/xml/ai_advisor_drawer.xml
static/src/scss/ai_advisor_drawer.scss
```

新增：

- `likedIds`
- `likingIds`
- 点赞按钮
- 点赞后按钮变金色并禁用
- 静默保存，不弹通知

会话消息增加：

```text
liked_article_id
```

历史加载时可恢复点赞状态。

## 验证结果

### 代码检查

已验证：

- Python touched files 可编译。
- JS `node --check` 通过。
- XML 使用 Python UTF-8 解析通过。

### 模块升级

执行：

```powershell
docker exec my_odoo_project_devcontainer-web-1 odoo -d odoo -u diecut_knowledge --stop-after-init --db_host=db --db_user=odoo --db_password=odoo -c /etc/odoo/odoo.conf
```

结果：成功。

### Wiki Index

Odoo shell 验证：

- `build_system_prompt()` 已包含 schema 和 task prompt。
- `知识库总目录` 已生成。
- `compile_source="wiki_index"`。
- `state="published"`。
- `sync_status="pending"`。
- cron 已存在并启用，间隔 6 小时。

### AI 点赞沉淀路由

容器重启后验证：

- `/diecut_knowledge/ai/like_answer` 可访问。
- JSON-RPC 返回 `ok: true`。
- 生成 `AI沉淀：...` 草稿。
- 中文 UTF-8 请求可正常保存。
- 测试文章已删除。

## 过程中遇到的问题

### 1. 运行中 Odoo worker 不认识新路由

单独执行 `-u diecut_knowledge --stop-after-init` 后，当前 Web worker 未必加载新增 controller route。

处理：

```powershell
docker restart my_odoo_project_devcontainer-web-1
```

重启后路由正常。

### 2. PowerShell 中文编码风险

PowerShell 直接读取或发送中文时，可能出现 mojibake 或问号。

处理原则：

- 后续文件检查优先使用 Python `read_text(encoding="utf-8")`。
- JSON 请求使用 UTF-8 bytes。
- 不用 PowerShell 显示结果判断文件真实编码。

### 3. 测试文章清理

点赞路由测试会真实创建文章。测试后按文章 ID 删除，避免污染知识库。

## 当前状态

P1 基础设施已完成：

- schema-first 规则体系已落地。
- prompts 已外置。
- prompt loader 已接入编译器和检索器。
- Wiki Index 总目录已能自动生成。
- AI 顾问点赞沉淀已能创建待审核知识。

但这不是最终智能效果的终点。它只是把系统改成后续可持续优化的结构。

## 后续建议

### P2：真正的 Wiki Agent 编译闭环

下一步应重点做：

- 编译前读取 Wiki Index 和候选旧页面。
- LLM 输出 `pages_to_create`、`pages_to_update`、`links_to_create`、`conflicts`、`citations`。
- Odoo 校验 JSON 后应用 patch。
- 如果发现旧链接污染，生成移除建议或进入人工审核。

### P2：LLM Agent 检索继续增强

AI 顾问应继续改进：

- 问题意图识别。
- Wiki / raw source / catalog item 三层候选检索。
- LLM 判断证据是否足够。
- 不因当前打开 Wiki 弱命中而阻止 raw/catalog fallback。
- 对材料推荐明确标注“建议实测验证”。

### P2：治理和复盘

建议保留：

- Ingest Plan 人工确认。
- 冲突、低置信、来源不足、疑似重复时不自动发布。
- 点赞和保存问答默认进入 `review`。
- 专人维护正式知识库，对客户和员工开放发布态内容。

## 总结

本轮的核心成果不是“多写几个 prompt”，而是把知识管理模块调整为：

```text
Schema-first
-> Task Prompt
-> Structured JSON
-> Odoo 校验与入库
-> Wiki / Graph / Log / Lint / Dify
```

这更接近 Karpathy LLM Wiki 的精髓：知识不是一次性上传后等待检索，而是被持续编译、维护、关联和复盘。
