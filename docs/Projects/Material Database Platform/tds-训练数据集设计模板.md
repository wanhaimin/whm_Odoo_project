---
type: project
status: active
area: "Material Database Platform"
topic: "Material Database Platform"
reviewed: 2026-04-18
---

# TDS 训练数据集设计模板

## 目标
为材料 / TDS 行业知识库的自然语言检索系统设计一套可落地的训练数据结构，覆盖：

1. Embedding 检索召回集
2. Reranker 精排标注集
3. Query Parser 查询解析集
4. QA / Evidence 问答解释集
5. Eval 评测集

原则：
- 优先服务“搜准、筛准、解释可追溯”
- 数据结构尽量统一，方便后续训练、评估、回放
- 每条样本尽量保留来源与证据，避免成为不可复查的黑盒

---

# 一、统一基础对象设计
建议先统一几个底层对象，不然后面各种数据集会互相打架。

## 1. 文档对象 document
```json
{
  "doc_id": "tds_3m_9448a_v2024",
  "brand": "3M",
  "series": "9448",
  "model": "9448A",
  "doc_type": "tds",
  "lang": "en",
  "source_type": "pdf",
  "source_uri": "files/3m/9448a.pdf",
  "version": "2024-03",
  "pages": 6
}
```

## 2. 切片对象 chunk
```json
{
  "chunk_id": "tds_3m_9448a_v2024_p2_tbl_01_r03",
  "doc_id": "tds_3m_9448a_v2024",
  "page": 2,
  "chunk_type": "table_row",
  "text": "Total thickness: 0.15 mm; Adhesive type: acrylic; Color: white; Carrier: tissue",
  "normalized_text": "total thickness 150 um adhesive acrylic color white carrier tissue",
  "fields": {
    "thickness_um": 150,
    "adhesive_family": "acrylic",
    "color": "white",
    "carrier": "tissue"
  }
}
```

## 3. 参数证据对象 evidence
```json
{
  "evidence_id": "ev_0001",
  "doc_id": "tds_3m_9448a_v2024",
  "chunk_id": "tds_3m_9448a_v2024_p2_tbl_01_r03",
  "page": 2,
  "field_name": "thickness_um",
  "raw_value": "0.15 mm",
  "normalized_value": 150,
  "unit": "um",
  "method": "table_extract",
  "confidence": 0.97
}
```

---

# 二、Embedding 检索召回集

## 目标
训练行业 embedding，让它更懂：
- 材料别名
- 应用场景
- 参数语义
- 中英混合术语
- 替代意图

## 样本结构（推荐 JSONL）
一行一个 query 样本：

```json
{
  "query_id": "q_0001",
  "query": "找适合摄像头模组固定的超薄黑色双面胶",
  "query_intent": "material_search",
  "positives": [
    {
      "doc_id": "tds_xxx",
      "chunk_id": "chunk_xxx_01",
      "label": 1.0
    },
    {
      "doc_id": "tds_xxx",
      "chunk_id": "chunk_xxx_02",
      "label": 0.9
    }
  ],
  "hard_negatives": [
    {
      "doc_id": "tds_yyy",
      "chunk_id": "chunk_yyy_01",
      "reason": "black but not double-sided"
    },
    {
      "doc_id": "tds_zzz",
      "chunk_id": "chunk_zzz_02",
      "reason": "double-sided but thickness too high"
    }
  ],
  "meta": {
    "language": "zh",
    "industry": "diecut_electronics"
  }
}
```

## 正样本来源
可以来自：
- 业务人员确认“这就是正确材料”
- 历史搜索点击 + 采用记录
- 已知替代关系
- 人工标注高相关 chunk

## 难负样本构造建议
优先做这几类：
1. **同类不同参数**
2. **同系列错误型号**
3. **应用接近但关键性能不满足**
4. **文本很像但字段不匹配**
5. **系列介绍页 vs 真正型号参数页**

## 推荐额外字段
```json
{
  "must_constraints": {
    "color": "black",
    "material_type": "double_sided_tape"
  },
  "soft_constraints": {
    "application": ["camera module"]
  }
}
```

这个字段后面也可用于错误分析：是没召回，还是召回了但没满足硬条件。

---

# 三、Reranker 精排标注集

## 目标
训练 reranker 区分：
- 完全匹配
- 大致匹配
- 语义相关但不满足条件
- 完全不相关

## 推荐格式
```json
{
  "query_id": "q_0001",
  "query": "PET 基材，50u 左右，耐温 150 度以上的双面胶",
  "candidates": [
    {
      "chunk_id": "chunk_a",
      "doc_id": "doc_a",
      "score_label": 3,
      "reason": "PET、厚度接近、耐温满足，属于双面胶"
    },
    {
      "chunk_id": "chunk_b",
      "doc_id": "doc_b",
      "score_label": 2,
      "reason": "PET 双面胶且厚度接近，但耐温信息缺失"
    },
    {
      "chunk_id": "chunk_c",
      "doc_id": "doc_c",
      "score_label": 1,
      "reason": "是 PET 双面胶，但厚度偏差较大"
    },
    {
      "chunk_id": "chunk_d",
      "doc_id": "doc_d",
      "score_label": 0,
      "reason": "不是双面胶"
    }
  ]
}
```

## 标注分级建议
- **3** = 完全符合，可优先推荐
- **2** = 基本符合，但缺少部分确认信息
- **1** = 相关但不够精确
- **0** = 不相关或关键条件冲突

## 标注注意点
不要只按“像不像”打分，要按：
- 硬条件是否满足
- 应用是否匹配
- 参数是否完整
- 证据是否可靠

## 适合加入的辅助字段
```json
{
  "constraint_match": {
    "material_type": true,
    "backing": true,
    "thickness_um": true,
    "heat_resistance_c": false
  }
}
```

这有助于后续解释为什么排在前面/后面。

---

# 四、Query Parser 查询解析集

## 目标
把自然语言转成结构化 DSL / filter object。

## 推荐输出结构
```json
{
  "query": "找总厚度 30u 以内、黑色、可模切的双面胶",
  "parsed": {
    "intent": "material_search",
    "material_type": "double_sided_tape",
    "constraints": {
      "thickness_um": { "lte": 30 },
      "color": "black",
      "die_cuttable": true
    },
    "soft_preferences": [],
    "application": [],
    "sort_preference": ["constraint_match", "completeness"]
  }
}
```

## Query Parser 数据集建议字段
```json
{
  "query_id": "qp_0001",
  "query": "有没有可以替代 3M 9448A 的国产双面胶",
  "parsed": {
    "intent": "substitute_search",
    "reference_model": "3M 9448A",
    "constraints": {
      "material_type": "double_sided_tape",
      "origin_preference": "domestic"
    },
    "soft_preferences": ["similar_function", "similar_application"]
  },
  "notes": "替代查询不能直接等同参数全等，要保留 substitute_search 意图"
}
```

## Query Parser 要覆盖的语言现象
### 1. 范围表达
- 50u 左右
- 小于 30u
- 不低于 150℃
- 越薄越好

### 2. 模糊偏好
- 性价比高一点
- 更适合模切
- 稳妥一点
- 便宜一些

### 3. 替代表达
- 替代 3M 9448A
- 类似 Nitto 某型号
- 有没有平替

### 4. 应用导向表达
- 摄像头模组固定
- 电池包固定
- FPC 贴合
- 遮光防尘

### 5. 中英混合表达
- PET 双面 tape
- acrylic 胶系
- black tape
- release liner

## Query Parser 的难点样本一定要单独补
比如：
- “50u 左右” 到底映射成 45~55 还是 40~60
- “耐高温” 到底映射成多少度
- “超薄” 按行业内部约定是多少

这些最好通过**行业规则字典**单独维护，不要全靠模型猜。

---

# 五、QA / Evidence 问答解释集

## 目标
训练或约束最终回答层，保证答案：
- 有依据
- 不乱编
- 能标明哪些条件满足/不满足/未知

## 推荐样本格式
```json
{
  "qa_id": "qa_0001",
  "query": "有没有耐温 200 度以上的黑色双面胶？",
  "evidence": [
    {
      "doc_id": "doc_a",
      "chunk_id": "chunk_a1",
      "page": 3,
      "text": "Short term temperature resistance: 220C",
      "field_name": "short_term_temp_c",
      "normalized_value": 220
    },
    {
      "doc_id": "doc_a",
      "chunk_id": "chunk_a2",
      "page": 2,
      "text": "Color: black",
      "field_name": "color",
      "normalized_value": "black"
    }
  ],
  "answer": {
    "summary": "有候选材料满足黑色且短时耐温超过 200℃，但需确认你要的是短时耐温还是长期耐温。",
    "matched_constraints": ["color", "short_term_temp_c"],
    "unknown_constraints": ["long_term_temp_c"],
    "recommended_next_step": "确认耐温口径（短时/长期）后再筛"
  }
}
```

## 这个数据集的核心规则
答案不是只说“有/没有”，而是要区分：
- 明确满足
- 明确不满足
- 信息不足
- 需补充确认

这对业务信任非常关键。

---

# 六、Eval 评测集设计

## 原则
评测集不要和训练集混在一起。
最好按时间或来源隔离。

## 建议至少分 3 组
### 1. 常规查询集
覆盖高频：
- 材料筛选
- 参数问答
- 应用检索

### 2. 困难查询集
覆盖：
- 模糊表达
- 缺参数文档
- 中英混输
- 同系列多型号混淆
- 单位转换

### 3. 替代料查询集
单独拿出来测，因为这是独立难题。

## 评测集样本结构
```json
{
  "query_id": "eval_001",
  "query": "找 50u 左右黑色 PET 双面胶",
  "gold_docs": ["doc_a", "doc_b"],
  "gold_chunks": ["chunk_a1", "chunk_b3"],
  "gold_parse": {
    "material_type": "double_sided_tape",
    "color": "black",
    "backing": "PET",
    "thickness_um": { "min": 45, "max": 55 }
  }
}
```

## 推荐指标
### 检索
- Recall@10
- Recall@20
- MRR
- nDCG

### 解析
- intent accuracy
- slot F1
- range extraction accuracy
- unit normalization accuracy

### 业务结果
- Top3 可用率
- 参数误判率
- 人工复核通过率

---

# 七、推荐的目录结构
如果你准备开始积累数据，我建议这样放：

```text
datasets/
  raw/
    docs/
    ocr/
  structured/
    documents.jsonl
    chunks.jsonl
    evidences.jsonl
  train/
    embedding_train.jsonl
    reranker_train.jsonl
    query_parser_train.jsonl
    qa_train.jsonl
  eval/
    retrieval_eval.jsonl
    parser_eval.jsonl
    qa_eval.jsonl
  dictionaries/
    synonyms.json
    units.json
    vague_terms.json
```

---

# 八、负样本构造建议
这是最容易被忽视，但最影响效果的部分。

## Embedding 的负样本
优先采这些：
- 同品牌同系列但错型号
- 同型号不同版本且参数冲突
- 同应用但材料类型不同
- 同材料类型但关键指标不满足

## Reranker 的负样本
优先采这些：
- 文本非常像，但少一个关键约束
- 参数看起来接近，但测试条件不同
- 系列页描述很诱人，但型号页不满足

## Query Parser 的对抗样本
- 错别字
- 中英文混写
- 单位混用
- “左右 / 不低于 / 尽量 / 最好 / 平替” 这些模糊表达

---

# 九、落地建议：先标什么最划算
如果现在人力有限，不要一开始什么都标。

## 第一批最值钱的标注
1. **100~300 条真实查询**
2. 每条查询对应 **3~10 个候选** 的相关性标注
3. 每条查询的 **结构化解析结果**
4. 关键材料的 **字段证据抽取**

这样就足够先训一个：
- 初版 embedding
- 初版 reranker
- 初版 query parser

## 第二批再补
- 替代料专项
- 难查询专项
- 缺失信息专项
- 多语言专项

---

# 十、非常重要的经验规则
## 1. 不要把“没写”当“满足”
TDS 不写，不代表有这个性能。

## 2. 不要把系列页当型号页
系列宣传页常常只适合粗召回，不适合最终判定。

## 3. 参数必须带条件
尤其：
- 剥离力
- 保持力
- 耐温
- 电性能

## 4. 模型负责理解，规则负责兜底
像单位换算、阈值比较、范围判断，最好规则化。

## 5. 答案一定留证据
否则业务人员不会放心用。

---

# 十一、下一步建议
如果继续往下推进，推荐顺序是：

1. 先把 **documents / chunks / evidences** 三张底表定下来
2. 再定 **query parser DSL**
3. 然后开始积累 **100 条真实查询训练集**
4. 先做一个小规模评测闭环
5. 再决定具体用什么 embedding / reranker / parser 模型

---

# 一句话总结
TDS 检索训练数据最关键的不是“量大”，而是：

> 查询、候选、参数、证据、约束这五件事要能对齐。

只要这五层对齐，后面的 embedding、reranker、query parser 和回答层都会越来越稳。
