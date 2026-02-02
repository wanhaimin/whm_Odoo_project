模具编号 M-2026-001 的生成由两部分代码配合完成：

1. 序列定义 (
ir_sequence_data.xml
)
xml
<record id="seq_diecut_mold" model="ir.sequence">
    <field name="name">刀模编号序列</field>
    <field name="code">diecut.mold</field>
    <field name="prefix">M-%(year)s-</field>
    <field name="padding">3</field>
    <field name="company_id" eval="False"/>
</record>
配置项	值	说明
code
diecut.mold	序列的唯一标识符，用于在代码中调用
prefix	M-%(year)s-	前缀格式，%(year)s 是动态变量，会替换为当前年份
padding	3	序号位数，不足 3 位会用 0 补齐
2. 编号生成逻辑 (
mold.py
 第 107-112 行)
python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('diecut.mold') or 'New'
    return super(DiecutMold, self).create(vals_list)
当创建新的刀模记录时，如果 
code
 字段的值是 'New'（默认值），系统会自动调用 ir.sequence 的 next_by_code() 方法获取下一个序列号。

编号格式解读
以 M-2026-001 为例：

部分	含义
M	固定前缀，代表 Mold（模具）
2026	当前年份
001	该年度的第 1 个模具（3 位数字，不足补 0）
下一个创建的模具编号将自动变为 M-2026-002，以此类推。

可用的动态变量
Odoo 序列支持以下动态变量（可用于 prefix 或 suffix）：

变量	说明	示例
%(year)s	4 位年份	2026
%(y)s	2 位年份	26
%(month)s	月份	02
%(day)s	日期	02
%(doy)s	一年中的第几天	033
%(woy)s	一年中的第几周	05
%(h24)s	24 小时制小时	13
如果需要修改编码规则，只需调整 
ir_sequence_data.xml
 中的配置即可。


# 手动更改序列号流程
 打开开发者模式
点击右上角 设置 → 激活开发者模式（或在URL后加 ?debug=1）
进入序列设置
点击 设置 → 技术 → 序列
或直接访问：/web#action=&model=ir.sequence&view_type=list
找到并修改序列
搜索 刀模编号序列 或 diecut.mold
点击进入编辑
修改配置
字段	修改为
前缀 (Prefix)	M-%(year)s%(month)s%(day)s-
序号大小 (Padding)	4
保存
下图所示
![[Pasted image 20260202135409.png]]