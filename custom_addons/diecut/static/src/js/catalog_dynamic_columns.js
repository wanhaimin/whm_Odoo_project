/** @odoo-module **/

/**
 * 材料型号清单 - SearchPanel 联动列显隐
 *
 * Odoo 17 SearchPanel 层级分类 DOM 结构：
 *   <li class="o_search_panel_category_value">
 *     <header class="active">          ← active 在 header 上
 *       <div class="o_search_panel_label">
 *         <span class="o_search_panel_label_title">泡棉类</span>
 *       </div>
 *     </header>
 *     <ul>  ← 子分类列表
 *       <li class="o_search_panel_category_value">
 *         <header class="active">  ← 如果选的是子分类
 *           ...
 *
 * Odoo 17 列表视图 DOM：
 *   <th data-name="field_name">  （表头）
 *   <td name="field_name">       （数据单元格）
 */

const SHOW_KEYWORDS = {
    catalog_density: ["泡棉", "屏蔽材料", "金属箔", "石墨"],
};

const STYLE_ID = "diecut-dynamic-col-style";
let _lastFingerprint = "";

function getActiveCategoryPath() {
    const names = [];

    const activeHeader = document.querySelector(
        ".o_search_panel_category_value > header.active"
    );
    if (!activeHeader) return names;

    const selfLabel = activeHeader.querySelector(".o_search_panel_label_title");
    if (selfLabel) names.push(selfLabel.textContent.trim());

    let li = activeHeader.closest("li.o_search_panel_category_value");
    if (!li) return names;

    let parentLi = li.parentElement && li.parentElement.closest("li.o_search_panel_category_value");
    while (parentLi) {
        const parentLabel = parentLi.querySelector(
            ":scope > header .o_search_panel_label_title"
        );
        if (parentLabel) names.push(parentLabel.textContent.trim());
        parentLi = parentLi.parentElement && parentLi.parentElement.closest("li.o_search_panel_category_value");
    }

    return names;
}

function computeVisibility() {
    const pathNames = getActiveCategoryPath();
    const result = {};

    for (const [field, keywords] of Object.entries(SHOW_KEYWORDS)) {
        result[field] = pathNames.some((name) =>
            keywords.some((kw) => name.includes(kw))
        );
    }
    return result;
}

function applyVisibility(visMap) {
    const fingerprint = JSON.stringify(visMap);
    if (fingerprint === _lastFingerprint) return;
    _lastFingerprint = fingerprint;

    let styleEl = document.getElementById(STYLE_ID);
    if (!styleEl) {
        styleEl = document.createElement("style");
        styleEl.id = STYLE_ID;
        document.head.appendChild(styleEl);
    }

    const rules = [];
    for (const [field, show] of Object.entries(visMap)) {
        const display = show ? "table-cell" : "none";
        rules.push(
            `.o_list_view th[data-name="${field}"] { display: ${display} !important; }`,
            `.o_list_view td[name="${field}"] { display: ${display} !important; }`,
        );
    }
    styleEl.textContent = rules.join("\n");
}

function refresh() {
    applyVisibility(computeVisibility());
}

document.addEventListener("click", (ev) => {
    if (ev.target.closest(".o_search_panel")) {
        setTimeout(refresh, 200);
        setTimeout(refresh, 600);
    }
}, true);

setInterval(() => {
    if (document.querySelector(".o_search_panel")) {
        refresh();
    }
}, 2000);
