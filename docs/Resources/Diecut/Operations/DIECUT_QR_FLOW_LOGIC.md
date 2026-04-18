---
type: resource
status: active
area: "Diecut"
topic: "Operations"
reviewed: 2026-04-18
---

# 模切行业：二维码“裂变与重生”逻辑流程图 & 实现指南

这些理念其实源于 **精益制造 (Lean Manufacturing)** 和 **WMS (仓储管理)** 的高级实践，广泛应用于造纸、薄膜和胶带行业。我的工作是**将这些先进的工业管理思想，翻译成 Odoo 能听懂的代码语言**，帮您落地。

以下是为您定制的完整逻辑流程图与技术实现蓝图。

---

## 1. 核心业务流程图 (Mermaid Flowchart)

```mermaid
graph TD
    %% 定义样式
    classDef mother fill:#f9f,stroke:#333,stroke-width:2px;
    classDef child fill:#bbf,stroke:#333,stroke-width:2px;
    classDef scrap fill:#cfc,stroke:#333,stroke-width:2px;

    subgraph 采购入库 [Phase 1: 母卷诞生]
        S[供应商发货] -->|收货| A(生成母卷批次 A001)
        A -->|打印| P1[贴大标签: 1000mm 原装]
        A :::mother
    end

    subgraph 分切裂变 [Phase 2: 母码生子码]
        A -->|投料| M[分切机任务]
        M -->|产出| B{分切逻辑}
        B -->|切成5卷| C1(子卷 A001-1)
        B -->|切成5卷| C2(子卷 A001-2)
        B -->|...| C3(子卷 A001-N)
        C1 -->|自动触发| P2[打印机狂吐: 10张小标签]
        C1 :::child
        C2 :::child
    end

    subgraph 生产领用 [Phase 3: 消耗]
        C1 -->|扫码领料| W[模切机生产]
        W -->|用完| D[空管废弃]
        W -->|没用完| E{剩余多少?}
    end

    subgraph 余料重生 [Phase 4: 循环利用]
        E -->|剩 20米| F(生成/更新余料批次 A001-1-R)
        F -->|打印| P3[贴余料标签: 醒目颜色]
        F -->|回库| Stock[仓库余料区]
        Stock -->|下次优先推荐| W
        F :::scrap
    end
```

---

## 2. Odoo 技术实现逻辑 (Technical Logic)

要在 Odoo 中实现上述“自动裂变”的酷炫效果，我们需要通过 **Python 开发 (Server Actions / Wizards)** 来串联标准模块。

### 2.1 "母码生子码" 的实现 (The Splitting Wizard)

Odoo 原生 MRP 虽然能拆解，但手动输入几十个序列号太累。我们需要开发一个**“分切向导 (Splitting Wizard)”**。

*   **界面设计**: 
    *   工人扫母卷码：`LOT_A001` (显示: 宽1000mm / 长100m)
    *   输入分切方案：`20mm * 50卷`
    *   点击按钮：`开始分切`

*   **后台逻辑 (Python)**:
    ```python
    def action_split_rolls(self):
        # 1. 扣减母卷库存
        consume_material(lot='LOT_A001', qty=1000mm)
        
        # 2. 循环生成子卷批次
        new_lots = []
        for i in range(1, 51):
            # 自动命名规则: 母卷号 + 流水号
            new_name = f"{self.mother_lot.name}-{i:03d}" 
            
            # 创建新批次记录 (写入 width, length)
            lot = self.env['stock.lot'].create({
                'name': new_name,
                'product_id': self.product_id.id,
                'x_width': 20, 
                'x_length': 100
            })
            new_lots.append(lot)
            
        # 3. 增加子卷库存
        add_inventory(lots=new_lots)
        
        # 4. 指挥打印机 (这是最帅的一步)
        # 调用打印机接口，直接把 new_lots 数据发过去，打印机开始工作
        return self.print_labels(new_lots)
    ```

### 2.2 "余料重生" 的实现 (Return Wizard)

当工人把没用完的材料退回来时：

*   **操作**: 工人拿手机扫一下旧标签 `A001-1`。
*   **弹窗**: 
    *   系统问：`原长度 100m，请问还剩多少？`
    *   工人输：`23` (米)。
*   **逻辑**:
    *   **简单模式**: 直接修改系统里 `A001-1` 的 `x_length` 字段为 23。
    *   **严格模式**: 自动生成新批号 `A001-1-REST`，属性设为 23m，并**强制打印**一张黄色标签（可以设置余料标签为醒目的黄色），覆盖在旧标签上。
    *   **智能推荐**: 下次系统派单时，MRP 逻辑会优先搜索 `x_length < 50` 的批次，强行派给工人，不让工人领新料。

---

## 3. 为什么这可以实现？
Odoo 的开放性（Open Source）允许我们：
1.  **重写数据模型**: 让我们能把长、宽加进去。
2.  **调用硬件接口**: 让我们能控制打印机自动打印，而不是人工去点“打印”。
3.  **修改算法**: 让我们能改变 MRP 的“派料逻辑”，实现“余料优先”。

这就是 Odoo 区别于僵化的传统标准 ERP 的最大魅力：**它适应您的流程，而不是让您适应软件。**
