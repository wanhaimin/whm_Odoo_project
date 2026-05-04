# 代码 Review：基于 LLM Wiki 方法论的 Knowlege 系统评估

> **日期**: 2026-04-29
> **范围**: `diecut_knowledge` + `chatter_ai_assistant` + `diecut(AI/TDS)`
> **参考**: [LLM Wiki — A pattern for building personal knowledge bases using LLMs](https://github.com/karpathy/LLM-Wiki) (Karpathy)

---

## 目录

1. [总体架构总览](#1-总体架构总览)
2. [方法论映射检查表](#2-方法論映射检查表)
3. [已实现良好项](#3-已实现良好项)
4. [中等问题](#4-中等问题)
5. [核心差距](#5-核心差距)
6. [改进建议（按优先级）](#6-改进建议按优先级)
7. [模块间数据流分析](#7-模块间数据流分析)
8. [架构决策记录](#8-架构决策记录)

---

## 1. 总体架构总览

当前代码库用三个 Odoo 模块构建了一个完整的企业知识管线：

```
                        ┌─────────────────────────────────┐
                        │         Dify (外部 LLM)           │
                        │  编译引擎 / 同步目标 / 查询后端    │
                        └──────┬──────────────┬────────────┘
                               │              │
                    ┌──────────┘              └──────────┐
                    v                                     v
┌──────────────────────────┐           ┌──────────────────────────┐
│  diecut_knowledge         │           │  chatter_ai_assistant    │
│  (Wiki 知识库核心)         │           │  (AI Worker + OpenClaw)  │
│                          │           │                          │
│  ┌─────────────────────┐  │           │  ┌─────────────────────┐  │
│  │  KbCompiler          │  │           │  │  ChatterAiCliBackend│  │
│  │  (LLM 编译引擎)       │  │           │  │  (OpenClaw 运维)     │  │
│  ├─────────────────────┤  │           │  ├─────────────────────┤  │
│  │  KbEnricher          │  │           │  │  Worker Service     │  │
│  │  (交叉引用富化)       │  │           │  │  (外部 Worker 轮询)  │  │
│  ├─────────────────────┤  │           │  ├─────────────────────┤  │
│  │  KbLinter            │  │           │  │  Source Document     │  │
│  │  (质量治理)           │  │           │  │  AI 集成(提取/解析)   │  │
│  ├─────────────────────┤  │           │  ├─────────────────────┤  │
│  │  DifyKnowledgeSync   │  │           │  │  Handbook Review     │  │
│  │  (Dify 同步)         │  │           │  │  (多产品手册解析)     │  │
│  ├─────────────────────┤  │           │  ├─────────────────────┤  │
│  │  Wiki Graph          │  │           │  │  Material Import API │  │
│  │  (图谱可视化+关联)    │  │           │  │  (外部 Agent 写回)   │  │
│  └─────────────────────┘  │           │  └─────────────────────┘  │
└──────────────────────────┘           └──────────────────────────┘
         │                                      │
         │              ┌───────────────────────┘
         │              │
         v              v
┌─────────────────────────────────────────────────────┐
│                  diecut (核心模块)                     │
│                                                     │
│  ┌────────────────────┐  ┌────────────────────────┐  │
│  │ catalog.item        │  │ catalog.source.document │  │
│  │ (结构化产品数据)     │  │ (TDS/PDF 原始资料)     │  │
│  ├────────────────────┤  ├────────────────────────┤  │
│  │ catalog.spec.line   │  │ TDS Skill 体系          │  │
│  │ (技术参数)           │  │ (brand_3m_v1, etc)     │  │
│  ├────────────────────┤  ├────────────────────────┤  │
│  │ catalog.param.AI    │  │ Draft 编辑 + Apply     │  │
│  │ (AI 参数字典)        │  │ (结构化写入数据库)      │  │
│  └────────────────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 核心数据流

```
原始资料层                   编译层                     知识层                   查询层
───────────                 ──────                     ─────                    ──────

PDF/TDS/选型指南  ──→  PdfExtractor ──→  KbCompiler ──→  kb.article ──→  DifyKnowledgeSync ──→  Dify Chat API
  (source.document)    (文本提取+OCR)     (LLM 编译)      (Wiki 页面)       (同步为 Dify 文档)      (AI Advisor)

结构化产品数据     ──→  KbCompiler   ──→  kb.article ──→  图谱关联 ──→  查询合成
  (catalog.item)       (LLM 编译)        (产品 Wiki)      (wiki.link)     (Wiki Graph / AI 问答)

                                                    KbEnricher
                                                  (交叉引用富化)
                                                        │
                                                        v
                                                  KbLinter
                                                (质量治理检查)
```

---

## 2. 方法论映射检查表

LLM Wiki 方法论有三个核心操作：**Ingest**、**Query**、**Lint**，以及两层基础设施：**Index** 和 **Log**。

### 2.1 三层架构

| LLM Wiki 层 | 当前实现 | 状态 |
|-------------|---------|------|
| Raw sources（不可变原始资料） | `diecut.catalog.source.document` + `diecut.catalog.item` | ✅ |
| Wiki（LLM 维护的 markdown 页面） | `diecut.kb.article` 含 10 种 page type | ✅ |
| Schema（约定/规则文档） | System prompts 硬编码在 Python + TDS skill JSON | ⚠️ 部分 |

### 2.2 核心操作

| 操作 | LLM Wiki 描述 | 当前实现 | 状态 |
|------|-------------|---------|------|
| **Ingest** | 读 source → 讨论 → 写/更新 wiki 页面 | KbCompiler 读 item/source → Dify LLM 生成 → 创建/更新 kb.article → 富化 → 图谱链接 | ✅ |
| **Query** | LLM 搜索 wiki 页 → 合成回答 → 带引用 | 全部走 Dify Chat API，不直接查 wiki | 🔴 |
| **Lint** | 矛盾检查 / 过时主张 / 孤儿页面 / 缺失引用 / 知识空白 | KbLinter 检查 9 种问题 | ⚠️ 缺少矛盾检测 |

### 2.3 基础设施

| 组件 | LLM Wiki 描述 | 当前实现 | 状态 |
|------|-------------|---------|------|
| **index.md** | 全部页面的统一目录，带链接和摘要 | 无，每次重新搜索 | 🔴 缺失 |
| **log.md** | 按时间顺序的日志，可 grep | `diecut.kb.wiki.log` 结构化日志存在，但无 markdown 视图 | ⚠️ 部分 |
| **CLAUDE.md** | Wiki 架构描述、page type 约定、维护规范 | 空文件 | 🔴 缺失 |
| **引用追踪** | 知识来源记录 | `diecut.kb.citation` 含 claim_text, excerpt, page_ref, confidence | ✅ 超出预期 |
| **知识图谱** | 交叉引用 | `diecut.kb.wiki.link` 含 10 种 link type + 双向链接 | ✅ 超出预期 |
| **网页搜索** | 填补知识空白 | 未实现 | 🔴 缺失 |
| **答案沉淀** | 好问答自动归档为 wiki 页 | AI Advisor 有"保存为知识"按钮，手动触发 | ⚠️ 手动 |

---

## 3. 已实现良好项

### 3.1 完整的三层资料 → 知识管线

从原始资料（PDF/TDS 等）到最终维护的 Wiki 页面，覆盖了完整的生命周期：

1. **原始资料入库**（`action_one_click_ingest`）
2. **文本提取**（PdfExtractor: pdfplumber → PaddleOCR → Tesseract 三级 fallback）
3. **路由计划**（`generate_source_route_plan`: LLM 或规则判断资料价值）
4. **AI 编译**（KbCompiler: 5 类 system prompt 覆盖不同场景）
5. **交叉引用富化**（KbEnricher: 自动提取实体 + 匹配品牌/型号/类别）
6. **图谱连接**（`_connect_article_to_wiki_graph`: 双向 link + link type 推断）
7. **引用标注**（`_create_source_citation`: claim + excerpt + page ref）
8. **质量检查**（KbLinter: 9 种 lint 规则）
9. **外部同步**（DifyKnowledgeSync: 文章/产品/QA 三路同步）

### 3.2 幂等编译

- SHA1 content hash 检测源数据是否变化（`kb_compiler.py:103-107`）
- `SELECT ... FOR UPDATE` 行级锁防止并发重复编译（`kb_compiler.py:110-113`）
- 编译 hash 匹配时直接返回现有文章，零开销

### 3.3 有类型双向图谱

`diecut.kb.wiki.link` 的 link_type 体系涵盖了知识间的多种关系：

```
mentions / same_brand / same_material / same_application
same_process / compares_with / depends_on / contradicts / updates
```

- 编译时自动创建 **forward + reverse** 双向链接
- 带 `confidence` 评分（0.5-0.85）
- 带 `reason` 说明来源
- 图谱可视化（SVG force graph）支持交互式浏览

### 3.4 品牌综述自动增量更新

`compile_brand_overview()`（`kb_compiler.py:405`）在每个产品编译后异步执行：

- 汇总品牌下所有活跃产品
- 检索已有相关 Wiki 文章
- 重新生成品牌综述 + 图谱连接 + lint
- 失败不影响主流程（`_logger.warning` 捕获）

这是 LLM Wiki "compounding knowledge" 模式的优秀实践。

### 3.5 引用追踪（超出 LLM Wiki 基础设计）

`diecut.kb.citation` 模型比纯 markdown wiki 的引用更加结构化：

| 字段 | 用途 |
|------|------|
| `claim_text` | 被引用的知识断言 |
| `page_ref` | 来源页码 |
| `excerpt` | 原文摘录 |
| `confidence` | 可信度评分 |
| `state` | valid / review / conflict |

### 3.6 路由计划 + 人机协作

`generate_source_route_plan` 让 LLM 先输出 JSON 处理方案，**人确认后再执行**：

- 判断资料的 `source_kind`（tds/selection_guide/etc）
- 推荐操作（parse_source, compile_wiki, extract_material_draft...）
- 风险等级评估（low/medium/high）
- 规则 fallback：LLM 失败时自动走规则判断

### 3.7 多模式 Wiki 知识点

10 种 `wiki_page_type` 覆盖了企业知识的常见形态：

```
source_summary / brand / material / material_category
application / process / faq / comparison / concept / query_answer
```

### 3.8 开放 Worker 架构

`chatter_ai_assistant` 的 Worker 模式允许外部 AI Agent（OpenClaw CLI）通过 HTTP 协议与 Odoo 交互：

- `/worker/claim` 拉取任务
- `/worker/complete` / `/worker/fail` 回报结果
- `/worker/material_update` 直接写回数据
- `/frontend/status` 前端轮询状态

---

## 4. 中等问题

### 4.1 System prompts 硬编码在 Python 中

**位置**: `kb_compiler.py:16-83`

5 个 system prompt 字符串直接写在 Python 代码中，包含：

- 文章结构要求（概述/参数/场景/建议/风险）
- 输出格式约定（纯 HTML，不要 markdown block）
- 知识质量规则（不编造参数、明确提醒缺失）

**问题**：
- 修改需要 PR + 升级 Odoo 模块
- 非开发者无法参与 Wiki 规范的迭代
- 不同 prompt 间可能存在不一致
- LLM Agent 无法直接读取和遵循这些规则

### 4.2 Markdown 是二等公民

**位置**: `kb_compiler.py:971-985`

`_html_to_markdownish()` 使用正则替换进行 HTML → markdown 转换：

```python
text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", text, ...)
text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", text, ...)
# ...
```

**问题**：
- HTML table 无法有损转换
- 嵌套结构（列表中的段落、表格中的列表）丢失
- LLM 如果通过 markdown 阅读文章，看到的是降质版本
- 主要的所见即所得编辑是 HTML，LLM 难以直接编辑

### 4.3 答案沉淀需要用户手动操作

**位置**: `controllers/ai_advisor.py` → `save_answer()`

"保存为知识"是一个按钮，用户必须主动点击。好答案如果用户忘记保存，就消失在对话历史中。

### 4.4 Dify 同步是单行道

知识库内容 → Dify 的同步是 **push only**（`dify_sync.py`）：

- 发布时推送到 Dify
- 没有从 Dify 拉回知识增量
- 如果用户在 Dify 内直接修改/删除文档，Odoo 侧无感知

### 4.5 多个知识存储可能存在漂移

- `diecut.catalog.item.tds_content` — HTML 字段
- `diecut.kb.article` — Wiki 正文
- Dify datasets — 同步后的文档
- `source.document.draft_payload` — TDS 结构化草稿

同一个产品的技术信息可能存在于 4 个不同位置，同步链路依赖 `sync_status` 标志位。

### 4.6 `_log_wiki_event` 创建在没有事务保障的 try/catch 中

**位置**: `kb_compiler.py:1209-1224`

```python
def _log_wiki_event(self, ...):
    try:
        self.env["diecut.kb.wiki.log"].sudo().create({...})
    except Exception as exc:
        _logger.warning("Failed to write wiki log: %s", exc)
```

日志创建失败被静默吞噬。虽然这保证了主流程不中断，但运维人员可能不知道日志写入失败。

---

## 5. 核心差距

### 5.1 [P0] Lint 不做主动矛盾检测

**现状**:
- `wiki.link` 有 `contradicts` link type
- `KbLinter` 只是统计**已存在的**矛盾链接数量（`kb_linter.py:25-31`）
- 不会在编译新资料时主动检测与现有文章的冲突

**LLM Wiki 的要求**:

> "The LLM incrementally builds and maintains a persistent wiki — noting where new data contradicts old claims, strengthening or challenging the evolving synthesis."

**缺失的能力**:
- 新编译文章时，对比现有相关文章的 summary / content，找出参数不一致
- 同一个品牌/型号在不同资料中的参数矛盾
- 新工艺知识推翻旧经验的场景
- 矛盾自动标记为 `contradicts` link + 生成 lint issue

**影响**: 知识矛盾被静默积累。销售同事可能看到两篇 Wiki 给出不同的耐温参数，但没有任何系统标记。

### 5.2 [P0] 查询时 LLM 不直接读 Wiki 结构

**现状**:
- AI Advisor、Chatter AI 全部通过 Dify Chat API 回答
- Dify 只有平坦的文档 chunk 检索，**不知道**：
  - 文章间的 wiki.link 关系（哪些文章互相引用、什么关系）
  - 文章的 compile_source、wiki_page_type 等元数据
  - 文章的 citation 链条（知识来自哪个源文档、第几页）

**LLM Wiki 的要求**:

> "The LLM searches for relevant pages, reads them, and synthesizes an answer with citations."

**缺失的能力**:
- 在 Odoo 侧构建 `KbSearcher` 服务，利用图谱做检索增强
- 回答时引用带 wiki.link 的上下文关系（"根据 A 品牌综述（关联品牌页 B）..."）
- 回答结果标记引用来源的 citation 记录
- 好的回答自动归档为新的 kb.article

**影响**: Wiki 投入了大量成本维护结构化知识（图谱、引用、分类），但在查询时这些结构对 LLM 完全不可见。Dify 的质量取决于文档 chunk 策略，与 Wiki 的内部结构无关。

### 5.3 [P1] 没有 index.md

**现状**: 编译时 `_find_wiki_candidates`（`kb_compiler.py:1046-1084`）每次通过 Odoo search 搜索相关文章，搜索策略涉及：

- 关联型号 / 品牌 / 类别的精确匹配
- 关键词模糊匹配（name, summary, keywords, content_text）
- 返回结果排序靠 ORM limit

**LLM Wiki 的要求**:

> "index.md is content-oriented. It's a catalog of everything in the wiki — each page listed with a link and a one-line summary."

**缺失的能力**:
- 没有统一的、LLM 可读的 Wiki 目录
- 每次编译都要消耗 token 搜索候选页面
- 搜索策略随着 Wiki 增长精度下降

### 5.4 [P1] 没有 CLAUDE.md / Schema 文档

**文件状态**:
- `CLAUDE.md` — 空文件（1 行）
- `AGENTS.md` — 仅有开发环境 / 构建命令，无 Wiki 架构描述

**缺失的内容**:
- Wiki page type 的定义和使用规范
- 文章内容质量标准（什么是一篇"好"的 Wiki）
- 图谱链接策略
- 何时创建 vs 更新 vs 归并文章
- 矛盾处理流程

### 5.5 [P2] 没有网页搜索集成

**现状**: 所有知识来源于已入库的文档/产品数据。

**LLM Wiki 的要求**:

> "Lint: data gaps that could be filled with a web search."

**缺失的能力**:
- 文章参数缺失时搜索公开资料
- 编译品牌综述时搜索品牌官网信息
- 评估知识时效性（是否有更新的公开资料）

### 5.6 [P2] Lint 不能建议创建新页面

**现状**: Lint 只检查**已有**文章的问题，不会建议创建缺失的页面。

**LLM Wiki 的要求**:

> "important concepts mentioned but lacking their own page"

**缺失的能力**:
- 扫描文章内容中提到的实体（品牌/材料/工艺/应用）
- 检查这些实体是否已有对应的 Wiki 页面
- 如果没有，生成"建议创建"的 lint issue

---

## 6. 改进建议（按优先级）

### P0 — 对知识质量和体系影响最大

#### 6.1 添加矛盾检测到 Lint

```python
# 在 KbLinter.lint_article() 中新增
def _detect_contradictions(self, article):
    """检查新编译文章与现有相关文章的矛盾"""
    candidates = self._find_relevant_candidates(article)
    for candidate in candidates:
        contradictions = self._compare_for_conflicts(article, candidate)
        for conflict in contradictions:
            # 创建 wiki.link (contradicts)
            # 创建 lint issue
            # 记录到 wiki.log
```

检测策略建议：
- 品牌/型号相同但关键参数（厚度/耐温/RoHS）不一致 → 高置信度矛盾
- 同一应用场景的选型建议不同 → 中等置信度矛盾
- 先以 `confidence` 字段分级，low 矛盾不打断流程，high 矛盾要求人工复核

#### 6.2 构建 Wiki 直查引擎

创建 `KbSearcher` 服务：

```
KbSearcher.search(query)
    ├── 1. 从 index.md（或 Odoo search）找到相关文章
    ├── 2. 读取文章完整内容（markdown）
    ├── 3. 沿 wiki.link 图谱扩展相关文章
    ├── 4. 收集 citation 信息
    ├── 5. 组装上下文 → 调用 LLM 合成回答
    └── 6. 可选：好的回答自动归档
```

架构选项：

| 方案 | 复杂度 | 收益 |
|------|--------|------|
| A. 直接用 LLM 读 kb.article（markdown）合成回答 | 低 | 启用图谱感知，但 LLM 调用成本高 |
| B. 用嵌入检索（embedding + vector search）筛选候选 | 中 | 效率高，但需要嵌入基础设施 |
| C. 将 kb.article + wiki.link 结构定期导出到 Dify 作为增强上下文 | 中 | 不改架构，让 Dify 感知图谱 |
| D. 混合：Odoo 侧做候选筛选 + LLM 做最终合成 | 中高 | 最灵活，但需要构建新服务 |

### P1 — 系统性改进

#### 6.3 生成 index.md

```python
# 新增 KbIndexer 服务
class KbIndexer:
    def generate_index(self):
        """生成标准 markdown 格式的 Wiki 目录"""
        articles = self.env["diecut.kb.article"].search([...])
        output = "# 知识库索引\n\n"
        for category in categories:
            output += f"## {category.name}\n\n"
            for article in category_articles:
                output += f"- [{article.name}](#) — {article.summary[:100]}\n"
        output += "\n---\n\n"
        output += f"> 最后更新: {datetime.now()} \n"
        output += f"> 总文章数: {count} \n"
        # 可存储到 ir.attachment 或生成一个 kb.article
```

触发时机：每次 ingest/compile 后自动更新。

#### 6.4 System prompts 外置化

将 `SYSTEM_PROMPT_SINGLE / COMPARISON / BRAND_OVERVIEW / SOURCE_DOCUMENT / SOURCE_ROUTE_PLAN` 从 Python 迁移到 markdown 文件：

```
custom_addons/diecut_knowledge/data/wiki_prompts/
├── README.md                          # 提示词目录说明
├── catalog_item_compile.md            # 原 SYSTEM_PROMPT_SINGLE
├── comparison_compile.md              # 原 SYSTEM_PROMPT_COMPARISON
├── brand_overview_compile.md          # 原 SYSTEM_PROMPT_BRAND_OVERVIEW
├── source_document_compile.md         # 原 SYSTEM_PROMPT_SOURCE_DOCUMENT
└── source_route_plan.md              # 原 SYSTEM_PROMPT_SOURCE_ROUTE_PLAN
```

KbCompiler 改为从文件读取：

```python
def _load_system_prompt(self, name):
    path = f"data/wiki_prompts/{name}.md"
    # 从模块文件读取
    return self.env["ir.attachment"].search([...]).raw  # 或直接读文件系统
```

#### 6.5 自动沉淀优质问答

在 AI Advisor 中增加自动沉淀逻辑：

```python
def _should_auto_save(self, answer, context):
    """判断是否自动保存问答为知识"""
    if len(answer) < 200:
        return False
    if "我不确定" in answer or "无法回答" in answer:
        return False
    if context.get("record_model") in ["catalog.item"]:
        return True  # 产品相关问答自动保存
    # 其他启发式：回答长度、引用数量、用户反馈...
```

### P2 — 基础设施增强

#### 6.6 Lint 建议创建新页面

```python
def _suggest_new_pages(self, article):
    # 从文章正文提取品牌名、材料名、工艺名
    entity_names = self._extract_entity_mentions(article.content_text)
    for name in entity_names:
        exists = self.env["diecut.kb.article"].search_count([
            ("name", "ilike", name),
            ("active", "=", True)
        ])
        if not exists:
            self._create_suggestion_issue(
                f"文中提到「{name}」但没有对应的知识页面，建议创建"
            )
```

#### 6.7 网页搜索集成

```python
# 在 KbCompiler.compile_from_item 中可选增加
def _web_search_gaps(self, item, article):
    gaps = self._identify_missing_params(item, article)
    if not gaps:
        return
    search_term = f"{item.name} {' '.join(gaps)}"
    results = web_search(search_term)
    # 将搜索结果作为 reference 写入 article
```

#### 6.8 填充 CLAUDE.md

建议在 `CLAUDE.md` 中加入以下内容：

```markdown
## Wiki 知识库架构

### 文章类型 (wiki_page_type)
- **material**: 单个材料/产品的知识页
- **brand**: 品牌综述（由 compile_brand_overview 自动维护）
- **application**: 应用场景/选型指南
- **process**: 工艺经验/问题排查
- **faq**: 常见问题
- **comparison**: 对比分析
- **concept**: 行业概念/术语
- **query_answer**: AI 问答沉淀
- **source_summary**: 源文档摘要

### 质量规范
- 每篇文章至少包含：概述、参数、场景、建议、风险
- 引用必须关联 source_document
- 图谱入链/出链 ≥ 1 才发布
- AI 编译置信度 ≥ 0.75 才自动发布
```

---

## 7. 模块间数据流分析

```
chatter_ai_assistant                  diecut_knowledge                       diecut
═══════════════════                  ═════════════════                       ══════

                     KbCompiler
   ┌───────────┐    compile_from_item() ──────→  catalog.item
   │ AI Advisor │    compile_from_source() ────→  source.document
   │ (OWL UI)  │    compile_comparison() ──────→  [catalog.item...]
   └─────┬─────┘    compile_brand_overview() ──→  diecut.brand
         │                    │
         │             ┌──────┴──────┐
         │             v             v
         │        kb.article    kb.category
         │        (Wiki 主体)   (知识分类)
         │             │
         │             ├──→ KbEnricher (交叉引用)
         │             ├──→ wiki.link (图谱)
         │             ├──→ kb.citation (引用)
         │             ├──→ KbLinter (治理)
         │             └──→ DifyKnowledgeSync (外部)
         │
         │  ┌─────────────────────────────────────────┐
         │  │  chatter_ai_assistant 的 Worker          │
         │  │  ─────────────────────────────────────  │
         │  │  OpenClaw CLI ←→ Odoo HTTP API          │
         │  │  - extract_source: PDF 文本提取          │
         │  │  - parse: TDS 结构化参数抽取              │
         │  │  - identify_handbook: 多产品手册结构     │
         │  │  - reparse: 重新解析                    │
         │  └─────────────────────────────────────────┘
         │                      │
         │               ┌──────┴──────┐
         │               v             v
         │         source.document  catalog.item
         │         (draft_payload)  (spec_lines, tds_content)
         │
         └────────── Dify Chat API ──────→ 用户问答
```

### 数据流的关键观察

1. **并行管线**: `diecut_knowledge` 和 `chatter_ai_assistant` 都做 AI 编译，但场景不同：
   - diecut_knowledge 的 KbCompiler → 长期的 Wiki 知识沉淀
   - chatter_ai_assistant 的 OpenClaw Worker → 实时的 TDS 结构化抽取 + 对话

2. **交集在 source.document**: 两个模块的操作对象都是 `diecut.catalog.source.document`，但 diecut_knowledge 侧重于 Wiki 编译（长文本知识），chatter_ai_assistant 侧重于结构化参数抽取（TDS draft）。

3. **两套 LLM 后端**: Dify（diecut_knowledge 的 KbCompiler）+ OpenClaw CLI（chatter_ai_assistant 的 Worker），互不通信。

4. **知识汇合点**: `kb.article` 是两种管道最终汇聚的地方——无论是通过 KbCompiler 编译还是通过 AI Advisor 保存。

---

## 8. 架构决策记录

### ADR-001: 为什么选择 Dify 作为编译引擎？

**决策**: KbCompiler 调用 Dify Chat API 进行 LLM 编译，而非直接调用 LLM API。

**考量**:
- Dify 提供 Prompt 管理和日志追踪（内部已有 Dify 基础设施）
- 方便非技术用户调整 Prompt 模板（Dify 的 Web UI）
- 统一的知识检索入口（Dify 同时作为 Chat 后端和知识库存储）

**代价**:
- 编译链路增加外部依赖，Dify 不可用时系统关键功能停摆
- Prompt 调整在 Dify Web UI 中，版本控制困难（不在 git 中）
- Dify 响应时间增加了编译延迟

### ADR-002: 为什么选择 OpenClaw Worker 而非直接调用 LLM？

**决策**: chatter_ai_assistant 通过外部 Worker 进程调用 OpenClaw CLI，而非 Odoo 内直接调用 LLM API。

**考量**:
- 长时间运行的 LLM 调用不阻塞 Odoo worker 进程
- Worker 可以在独立的机器上运行，资源隔离
- OpenClaw 封装了 agent 管理、session、memory 等复杂逻辑
- 异步架构支持任务队列和重试

**代价**:
- 增加了系统的部署复杂度（需要运行 Worker 进程）
- Worker 和 Odoo 之间通过 HTTP + shared secret 通信，增加了故障点
- 状态同步延迟（前端需要轮询 `/frontend/status`）

### ADR-003: Wiki 存在 Odoo 数据库中，而非 markdown 文件

**决策**: Wiki 内容存储在 PostgreSQL（Odoo ORM），而非文件系统 markdown。

**考量**:
- 与 Odoo 的权限体系集成（用户/组级别的读写控制）
- 交易保障（ACID）— 编译、富化、图谱链接在一个事务中
- 与 mail 模块集成（chatter 评论、activity 提醒）
- 搜索视图、filter、group 等开箱即用的 UI 能力

**代价**:
- LLM 不能直接用 `cat` / `grep` 操作 Wiki 文件
- Wiki 不能直接用 Obsidian 浏览（没有 markdown 文件）
- git 版本历史的可读性不如纯文本（只有一个 PostgreSQL dump 级别的 diff）
- 依赖 Odoo 环境才能访问知识库（不能方便地用 Claude Code 直接读）

---

## 附录 A: 关键文件索引

| 文件 | 行数 | 职责 |
|------|------|------|
| `diecut_knowledge/models/kb_article.py` | ~250 | Wiki 文章模型（60+ 字段） |
| `diecut_knowledge/models/kb_citation.py` | ~50 | 引用追踪模型 |
| `diecut_knowledge/models/wiki_graph.py` | ~50 | 图谱控制器 |
| `diecut_knowledge/models/source_document_compile.py` | ~200 | 源文档扩展（知识编译相关） |
| `diecut_knowledge/models/catalog_item_sync.py` | ~200 | 产品同步 + 编译触发 |
| `diecut_knowledge/services/kb_compiler.py` | ~1225 | AI 编译引擎 + 路由计划 |
| `diecut_knowledge/services/kb_enricher.py` | ~150 | 交叉引用富化 |
| `diecut_knowledge/services/kb_linter.py` | ~100 | 质量治理 |
| `diecut_knowledge/services/dify_client.py` | ~120 | Dify HTTP 客户端 |
| `diecut_knowledge/services/dify_sync.py` | ~200 | 文章 → Dify 同步 |
| `diecut_knowledge/services/pdf_extractor.py` | ~150 | PDF/图片文本提取 |
| `diecut_knowledge/controllers/ai_advisor.py` | ~150 | AI 顾问聊天端点 |
| `diecut_knowledge/controllers/wiki_graph.py` | ~60 | 图谱数据端点 |
| `chatter_ai_assistant/models/ai_run.py` | ~907 | AI 运行编排 |
| `chatter_ai_assistant/models/diecut_source_document.py` | ~447 | 源文档 AI 集成 |
| `chatter_ai_assistant/models/handbook_review.py` | ~722 | 手册结构审查 |
| `chatter_ai_assistant/tools/openclaw_backends.py` | ~266 | OpenClaw CLI 后端 |
| `chatter_ai_assistant/tools/worker_service.py` | ~96 | Worker 轮询服务 |
| `chatter_ai_assistant/controllers/worker_api.py` | ~83 | Worker REST API |
| `diecut/models/catalog_ai.py` | ~1594 | 源文档主模型 + Copilot 上下文 |
| `diecut/tools/tds_skill_context.py` | ~300 | TDS Skill 上下文加载 |
| `diecut/data/tds_skills/generic_tds_v1.json` | — | 通用 TDS Skill |
| `diecut/data/tds_skills/diecut_domain_v1.json` | — | 模切领域 Skill |
| `diecut/data/tds_skills/brand_3m_v1.json` | — | 3M 品牌 Skill |

---

## 附录 B: 术语对照

| LLM Wiki 术语 | 本项目中对应 |
|---------------|-------------|
| Raw source | `diecut.catalog.source.document` / `diecut.catalog.item` |
| Wiki page | `diecut.kb.article` |
| Wiki page type | `wiki_page_type` 字段 |
| Cross-reference | `diecut.kb.wiki.link`（有类型边） |
| Citation | `diecut.kb.citation` |
| Ingest | KbCompiler.compile_*() + KbEnricher + graph linking |
| Lint | KbLinter.lint_article() |
| Index | 缺失（建议新建 KbIndexer）|
| Log | `diecut.kb.wiki.log` |
| Schema | 散落在 system prompt + skill JSON + 缺失的 CLAUDE.md |
| Query | Dify Chat API（外部）/ AI Advisor（UI）|
| Compounding | compile_brand_overview 自动更新 |
| Human in the loop | route_plan + review state + lint issues |
| Search engine | 缺失（建议新建 KbSearcher）|

---

*本文档由 Claude Code 基于 LLM Wiki 方法论（Karpathy）对 `diecut_knowledge`、`chatter_ai_assistant`、`diecut(AI/TDS)` 模块的全面代码审查生成。*
