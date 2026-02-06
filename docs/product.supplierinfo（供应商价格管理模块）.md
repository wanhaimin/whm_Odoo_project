product.supplierinfo是odoo的原生模型吗



product.supplierinfo 是 Odoo 的核心原生模型（属于 product 模块）。

在 Odoo 中，它的官方名称通常被称为 "供应商价格表" (Vendor Pricelist)。
它的主要作用：

1. 连接产品与供应商：它建立了产品模板 (product.template) 或产品变体 (product.product) 与合作伙伴 (res.partner) 之间的关联。
2. 管理采购价格：存储不同供应商对同一产品的报价。
3. 支持分级定价：可以根据起订量 (min_qty) 设置不同的价格。
4. 管理交期：定义了从该供应商处采购的预计交货提前期 (delay)。
5. 有效期管理：可以设置价格的开始日期和结束日期。
在我们的项目中：
您当前的 diecut 模块通过以下代码对它进行了继承和扩展：

class ProductSupplierinfo(models.Model):    
_inherit = 'product.supplierinfo'
您在原生字段（价格、交期、供应商）的基础上，额外增加了针对模切行业的字段，例如：
• price_per_m2 (单价/m²)
• price_per_kg (单价/kg)
总结： 这是一个非常基础且重要的 Odoo 原生模型，我们只是在原生的框架内添加了更多符合您业务需求的“计算规则”和“显示字段”。

product.supplierinfo 模型的原生核心字段如下（基于 Odoo 19.0 标准定义）：

1. 核心关联字段
partner_id (Vendor): 供应商。关联到 res.partner。
product_tmpl_id
     (Product Template): 产品模板。关联到 product.template。
product_id
 (Product Variant): 产品变体。如果设置了，则该价格仅适用于特定变体。
currency_id (Currency): 报价币种。默认为公司本位币。
2. 价格与数量
price
   (Unit Price): 单位价格。这是最核心的价格字段，对应您在界面上看到的“单价(卷/张)”。
   min_qty (Quantity): 起订量。享受该报价所需达到的最小采购数量。
discount
   (Discount %): 折扣百分比。
3. 时间与效率
    delay (Lead Time): 交期。从下订单到收到货的天数。
    date_start (Start Date): 报价有效期开始日期。
    date_end (End Date): 报价有效期结束日期。
4. 供应商特定信息
    product_name (Vendor Product Name): 供应商方的产品名称。
    product_code (Vendor Product Code): 供应商方的产品编码。
5. 系统辅助字段
    sequence (Sequence): 序号。用于确定多个供应商报价的优先级（序号越小，优先级越高）。
    company_id (Company): 所属公司（多公司环境下使用）。
    product_uom_id
        (Unit of Measure): 采购单位。

# Q:product有categore模型，supplierinfo模型外，还有哪些模型？

A:
Odoo 的产品系统是一个高度关联的体系。除了您提到的类别 (product.category) 和供应商信息 (product.supplierinfo)，产品体系中还有以下几个核心模型：

1. 核心定义模型 (核心中的核心)
product.template (产品模板)：
存储产品的通用信息（名称、类型、基础规格、销售价格等）。我们在 
product_diecut.py
 中继承的就是这个。
product.product (产品产品/变体)：
代表具体的“单品”。如果一个模板有不同的颜色或尺寸，每一个组合就是一个 product.product 记录。如果你不启用变体，通常一个 Template 对应一个 Product。
2. 变体与属性模型 (用于管理规格多样性)
product.attribute (产品属性)：例如“颜色”、“材质”。
product.attribute.value (属性值)：例如“红色”、“蓝色”、“3M 胶带”。
product.template.attribute.line (模板属性行)：定义某个产品模板拥有哪些属性。
3. 计量单位模型 (基础支撑)
uom.uom (计量单位)：例如“卷”、“平方米”、“kg”、“mm”。
uom.category (单位类别)：将单位分组，例如“长度”类（包含 m, mm, cm），只有同类单位之间才能自动换算。
4. 销售/价格策略模型 (销售预测)
product.pricelist (价格表)：针对客户的售价策略。可以设置“VIP 客户打 9 折”或“夏季促销”等复杂逻辑。
product.pricelist.item (价格表明细)：具体的规则，例如“买满 100 件单价减 5 元”。
5. 物流与包装模型
product.packaging (产品包装)：定义产品的装箱规格，例如“1 箱 = 10 卷”。
stock.production.lot (批次/序列号)：用于追踪具体的某一批材料（在开启批次管理时使用）。
6. 关联的业务模型 (跨模块)
mrp.bom (物料清单/BOM)：在制造模块中，定义生产一个产品需要哪些原材料。
product.image (产品多图)：管理产品的多张图片。

uom.uom 模型负责的是 计量单位（Unit of Measure），而价格单位在 Odoo 中通常是基于计量单位派生出来的。

1. uom.uom 的核心职责：数量衡量
它主要负责定义物理数量的衡量标准和换算逻辑。例如：

重量类：克 (g)、公斤 (kg)、吨 (t)。
长度类：毫米 (mm)、米 (m)。
面积类：平方米 (m²)。
离散类：个 (Units)、卷 (Rolls)、张 (Sheets)。
2. 它它是如何影响“价格”的？
在 Odoo 的标准逻辑中：

价格是基于单位的：当你定义产品价格为 100 元时，默认指的就是“每 1 [计量单位]”的价格。
自动换算价格：如果你定义产品的基本单位是“克(g)”，但你按“公斤(kg)”卖，uom.uom 里的换算系数（1kg = 1000g）会让系统自动把 1g 的价格乘以 1000 算成 1kg 的价格。
3. “计量单位”与您的“价格单位”需求
在您的模切业务中，您提到的“价格单位”通常有两种含义：

业务层面的计价单位：您可能想说“这个材料是按 平方米 计价的”还是“按 卷 计价的”。
在 Odoo 中，你会通过在产品上设置 “采购单位” (Purchase UoM) 来实现这一点。
单纯的辅助显示：比如您在代码里加的 price_unit = fields.Char(string='价格单位')。
这是一个纯文本字段，仅仅是为了给人看（比如填入“RMB/kg”），它并不参与 Odoo 的自动数量换算。
总结：
uom.uom 就像是一把尺子或一个秤，它告诉 Odoo：

这东西怎么数（是个、是米、还是公斤？）。
大单位和小单位之间怎么变（1 卷 = 50 米）。
而“价格”只是挂在这些单位上的标签。 改变了单位的换算系数，系统里的价格也会跟着变。

在我们的模切模块中，因为行业特殊，有时候供应商报价是按“卷”，但我们需要换算成“平方米”或“公斤”来对账，所以我们才会在 product.supplierinfo 里手写了 price_per_m2 这样的扩展字段来做更精细的控制。

# 理解 Odoo 的价格控制体系，关键在于理清 “进项成本 -> 基础定价 -> 销项售价” 这条链路，以及 “单位” 如何在其中起到桥梁作用。

以下是这些核心模型在价格控制中的逻辑关系图解：

1. 成本端 (Purchase / Cost)
这是价格的起点，主要由 product.supplierinfo 负责。

多供应商比价：一个产品模板可以关联多个 product.supplierinfo 记录。
成本计算的基础：
Odoo 原生的 standard_price（标准成本）通常来自最优先的一条供应商记录。
在您的项目中：我们通过 
action_set_as_main
 手动指定一个供应商，将其价格同步到产品的 raw_material_unit_price（原材料单价），从而锁定了该材料的计算基准。
2. 定义端 (The Base)
这是价格的宿主，由 product.template 负责。

list_price (销售价格)：这是产品的“公开标价”。通常作为一个基数。
standard_price (成本价格)：反映了库存的价值。它可以是手动填写的，也可以根据采购订单自动更新。
计价单位的定义：产品上定义的 
uom_id
（单位）决定了上述价格是“每平方米”还是“每卷”。
3. 销售端 (Sales / Revenue)
这是最复杂的价格变化区，由 product.pricelist (价格表) 负责。

价格表规则：它不是一个简单的金额，而是一套计算公式。例如：
固定价格：针对 A 客户，无论何时都卖 50 元。
基于公式：售价 = 成本 (standard_price) + 20% 利润。
分级定价：买 1-99 卷不打折，买 100 卷以上打 9 折。
优先级：系统会根据“客户是谁”和“购买数量”自动搜索匹配的价格表，从而决定订单上的最终价格。
4. 转换引擎 (The Bridge)
这是所有的单位换算核心，由 uom.uom 负责。

它是价格的“分母”：
如果采购单位是“卷”(Roll)，销售单位是“平方米”(m²)。
当你从 product.supplierinfo 拿到一个“卷”的价格时，uom.uom 的换算系数会自动算出“平方米”的单价。
公式：单价 (单位 B) = 单价 (单位 A) / (单位 A 换算为单位 B 的比例)。
总结：它们之间的关系链
供应商报价 (supplierinfo) 产生的价格 $\rightarrow$ 经过 单位 (uom.uom) 换算 $\rightarrow$ 存入 产品成本 (standard_price)。
产品基础价 (list_price) 定义一个基准。
价格表 (pricelist) 根据业务逻辑（打折、加价、促销）对 基础价 或 成本价 进行二次加工，得出 最终成交价。
为什么在您的模切项目中我们要扩展这些模型？
因为 Odoo 原生的单位换算比较死板。在模切行业：

