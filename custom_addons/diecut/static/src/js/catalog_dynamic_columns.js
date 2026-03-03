/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

const SHOW_KEYWORDS = {
    catalog_density: ["泡棉", "屏蔽材料", "金属箔", "石墨"],
};

patch(ListRenderer.prototype, {
    getActiveColumns() {
        // 先获取 Odoo 原本计算出的激活列
        let columns = super.getActiveColumns();

        // 验证 1: 确保只在 product.product 下生效
        const resModel = this.props.list.resModel;
        if (resModel !== "product.product") {
            return columns;
        }

        // 验证 2: 确保是在「材料型号清单」视图中生效
        // 依据: 只有这个特定视图才会同时放出 `product_tmpl_id` 和 `catalog_categ_id` 这两列
        const hasSeries = columns.some((col) => col.name === "product_tmpl_id");
        const hasCatalogCateg = columns.some((col) => col.name === "catalog_categ_id");

        if (!hasSeries || !hasCatalogCateg) {
            return columns;
        }

        const records = this.props.list.records;
        // 如果当前没有任何记录，无需处理隐藏
        if (!records || records.length === 0) {
            return columns;
        }

        // 过滤列：如果某列在当前记录中全为空，则剃除它（不让 Owl 渲染）
        return columns.filter((col) => {
            if (col.type === "field" && col.name) {
                // 1. 判断是否该列所有记录都为空
                const isAllEmpty = records.every((record) => {
                    const val = record.data[col.name];
                    if (val === false || val === null || val === undefined || val === "") return true;
                    if (typeof val === "string") {
                        const trimmed = val.trim();
                        // 如果只是破折号、省略号、或者默认带的「原材料/xxx」前缀，也视作空
                        if (trimmed === "" || trimmed === "—" || trimmed === "-" || /^原材料\/.*$/.test(trimmed) || trimmed === "..." || /^\.\.\.$/.test(trimmed)) {
                            return true;
                        }
                    }
                    if (typeof val === "number" && val === 0) return true;
                    // 对于 Many2one / Many2many 等关联字段
                    if (Array.isArray(val) && val.length === 0) return true;

                    return false;
                });

                if (isAllEmpty) {
                    return false; // 在渲染前直接剔除这列，彻底隐藏
                }

                // 2. 特殊业务逻辑: 密度列仅当当前列表内的某些记录属于特定分类时显示
                if (col.name === "catalog_density") {
                    const categoryMatches = records.some((record) => {
                        const categ = record.data.catalog_categ_id;
                        if (categ && categ[1]) {
                            const categName = categ[1];
                            return SHOW_KEYWORDS.catalog_density.some((kw) => categName.includes(kw));
                        }
                        return false;
                    });
                    if (!categoryMatches) {
                        return false;
                    }
                }
            }
            return true;
        });
    }
});
